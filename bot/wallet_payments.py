"""Direct TON/USDT receipts, persistent invoices and at-most-once delivery."""
import asyncio
import logging
import time
from decimal import Decimal, ROUND_UP
from uuid import uuid4
from urllib.parse import urlencode

from pytoniq_core import Address
from pytoniq_core.tlb.transaction import InternalMsgInfo
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from bot.database.engine import sessionmaker
from bot.database.models import WalletInvoice, UserStars
from bot.settings import settings

logger = logging.getLogger(__name__)
USDT_MASTER = 'EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs'
UNITS = {'TON': 10**9, 'USDT': 10**6}
_client = None


def chain_client():
    from bot.cryptopay import ton_wallet
    if ton_wallet:
        # Share the same limiter as Fragment's wallet operations (1 request/sec).
        return ton_wallet.client
    global _client
    if _client is None:
        from tonutils.client import TonapiClient
        _client = TonapiClient(settings.ton_api.api_key, rps=1, max_retries=3)
    return _client


def quoted_amount(usd, usd_per_coin, asset):
    price, rate = Decimal(str(usd)), Decimal(str(usd_per_coin))
    if asset not in UNITS or not price.is_finite() or not rate.is_finite() or price <= 0 or rate <= 0:
        raise ValueError('Invalid wallet quote')
    precision = Decimal('.0001') if asset == 'TON' else Decimal('.01')
    return int((price / rate).quantize(precision, rounding=ROUND_UP) * UNITS[asset])


def transfer_url(invoice):
    params = {'amount': str(int(invoice.atomic_amount)), 'text': invoice.order_id}
    if invoice.asset == 'USDT':
        params['jetton'] = USDT_MASTER
    return f'ton://transfer/{invoice.receiver}?{urlencode(params)}'


async def create_invoice(*, bot_id, buyer_id, chat_id, recipient, product, quantity, asset, usd, base_stars):
    if not settings.ton_api.receive_address or not settings.ton_api.api_key:
        raise ValueError('Wallet payments are not configured')
    if product not in ('stars', 'premium') or (product == 'stars' and quantity < 50) or (product == 'premium' and quantity not in (3, 6, 12)):
        raise ValueError('Invalid product')
    address = Address(settings.ton_api.receive_address)
    if address.wc != 0 or address.is_test_only:
        raise ValueError('A mainnet wallet is required')
    token = 'ton' if asset == 'TON' else USDT_MASTER
    data = await chain_client()._get('/rates', params={'tokens': token, 'currencies': 'usd'})
    key = 'TON' if asset == 'TON' else USDT_MASTER
    rate = data['rates'][key]['prices']['USD']
    now = int(time.time())
    invoice = WalletInvoice(
        order_id=uuid4().hex, bot_id=bot_id, buyer_id=buyer_id, chat_id=chat_id,
        recipient=recipient, product=product, quantity=quantity, asset=asset,
        receiver=address.to_str(is_bounceable=False),
        atomic_amount=quoted_amount(usd, rate, asset), base_stars=Decimal(str(base_stars)),
        created=now, expires=now + 900, status='pending',
    )
    async with sessionmaker() as session:
        session.add(invoice)
        await session.commit()
    # A missing referrer never prevents persisting the invoice itself.
    from bot.referrals import register_payment
    await register_payment('wallet', invoice.order_id, buyer_id, base_stars)
    return invoice


def extract_receipt(tx, asset, receiving_account):
    """Parse actual inbound messages, not TonAPI's mutable event actions."""
    try:
        account = Address(receiving_account)
        message = tx.in_msg
        if not message or not isinstance(message.info, InternalMsgInfo):
            return None
        if tx.account_addr != account.hash_part or message.info.dest != account or message.info.bounced:
            return None
        desc = tx.description
        if desc.type_ != 'ordinary':
            return None
        compute = desc.compute_ph
        # Non-bounceable TON deposits can credit an undeployed wallet without VM execution.
        undeployed_credit = (
            asset == 'TON' and not message.info.bounce and not tx.out_msgs
            and compute.type_ == 'skipped' and compute.reason.type_ == 'no_state'
            and desc.credit_ph is not None and desc.credit_ph.credit.grams > 0
        )
        executed = (
            not desc.aborted and compute.type_ == 'vm' and compute.success
            and compute.exit_code in (0, 1)
            and (desc.action is None or (desc.action.success and desc.action.result_code == 0))
        )
        if not (executed or undeployed_credit):
            return None
        body = message.body.begin_parse()
        if asset == 'TON':
            if body.load_uint(32) != 0:
                return None
            amount = message.info.value_coins
        else:
            # TEP-74 internal_transfer into the wallet derived from the official USDT master.
            if body.load_uint(32) != 0x178D4519:
                return None
            body.load_uint(64)
            amount = body.load_coins()
            body.load_address()
            body.load_address()
            body.load_coins()
            body = body.load_ref().begin_parse() if body.load_bit() else body
            if body.load_uint(32) != 0:
                return None
        memo = body.load_snake_string()
        if amount <= 0 or len(memo) != 32:
            return None
        return {'memo': memo, 'amount': amount, 'timestamp': tx.now, 'transaction': tx.cell.hash.hex()}
    except (AttributeError, ValueError, IndexError, AssertionError, OverflowError):
        return None


async def confirm(invoice_id, receipt):
    try:
        async with sessionmaker() as session, session.begin():
            invoice = await session.scalar(select(WalletInvoice).where(WalletInvoice.id == invoice_id).with_for_update())
            if not invoice or invoice.provider != 'wallet' or invoice.status not in ('pending', 'expired'):
                return False
            if receipt['memo'] != invoice.order_id or receipt['amount'] != invoice.atomic_amount or receipt['timestamp'] < invoice.created:
                return False
            invoice.transaction = receipt['transaction']
            invoice.status = 'paid' if receipt['timestamp'] <= invoice.expires else 'review'
            return True
    except IntegrityError:
        return False


async def claim(invoice_id):
    async with sessionmaker() as session, session.begin():
        return await session.scalar(update(WalletInvoice).where(
            WalletInvoice.id == invoice_id, WalletInvoice.status == 'paid',
        ).values(status='processing').returning(WalletInvoice))


async def finish(invoice_id, status, tx_hash=None, *, fallback=False):
    async with sessionmaker() as session, session.begin():
        invoice = await session.scalar(select(WalletInvoice).where(WalletInvoice.id == invoice_id).with_for_update())
        if not invoice or invoice.status != 'processing':
            return
        if fallback:
            await session.execute(insert(UserStars).values(user_id=invoice.buyer_id, stars=invoice.quantity).on_conflict_do_update(
                index_elements=['user_id'], set_={'stars': UserStars.stars + invoice.quantity},
            ))
        invoice.status = status
        invoice.delivery_transaction = tx_hash


async def deliver(invoice, bot):
    from bot.cryptopay import fragment_api, ton_wallet
    from bot.referrals import register_payment, credit_payment
    # Any failure or crash after this durable claim is held for review, never retried.
    claimed = await claim(invoice.id)
    if not claimed:
        return
    try:
        await register_payment(claimed.provider, claimed.order_id, claimed.buyer_id, claimed.base_stars)
        await credit_payment(claimed.provider, claimed.order_id)
        try:
            method = fragment_api.create_star_buy_invoice if claimed.product == 'stars' else fragment_api.create_premium_gift_invoice
            result = await asyncio.to_thread(method, claimed.quantity, claimed.recipient)
            payload = fragment_api.parse_invoice(result)
            if payload is None:
                raise ValueError('No Fragment invoice')
            if ton_wallet is None:
                raise ValueError('No delivery wallet')
        except Exception:
            fallback = claimed.product == 'stars'
            await finish(claimed.id, 'credited' if fallback else 'review', fallback=fallback)
            text = ('Звёзды зачислены на резервный баланс.' if fallback else 'Premium ожидает проверки поддержкой.')
            await bot.send_message(claimed.chat_id, f'Оплата получена. {text}\nПоддержка: @maneramur или @velunae.')
            return
        try:
            tx_hash = await ton_wallet.send_ton(payload['ton_address'], payload['ton_amount'], payload['comment'])
            if not tx_hash:
                raise ValueError('Uncertain transfer')
        except Exception:
            await finish(claimed.id, 'review')
            await bot.send_message(claimed.chat_id, 'Оплата получена, отправка требует проверки. Не оплачивайте повторно. Поддержка: @maneramur или @velunae.')
            return
        await finish(claimed.id, 'sent', str(tx_hash))
        product = f'{claimed.quantity} звёзд' if claimed.product == 'stars' else f'Premium на {claimed.quantity} мес.'
        await bot.send_message(claimed.chat_id, f'✅ Оплата получена! {product} отправлены получателю @{claimed.recipient}.')
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception('Wallet order requires review: %s', claimed.order_id)
        await finish(claimed.id, 'review')


async def scan(bot):
    async with sessionmaker() as session:
        invoices = (await session.scalars(select(WalletInvoice).where(
            WalletInvoice.provider == 'wallet',
            WalletInvoice.bot_id == bot.id, WalletInvoice.status.in_(('pending', 'expired', 'paid')),
            WalletInvoice.created >= int(time.time()) - 86400,
        ).order_by(WalletInvoice.created))).all()
    groups = {}
    for invoice in invoices:
        if invoice.status == 'paid':
            await deliver(invoice, bot)
        else:
            groups.setdefault((invoice.asset, invoice.receiver), []).append(invoice)
    for (asset, receiver), pending in groups.items():
        client = chain_client()
        account = receiver
        if asset == 'USDT':
            account = (await client.run_get_method(USDT_MASTER, 'get_wallet_address', [Address(receiver)]))[0].to_str()
        oldest = min(i.created for i in pending)
        by_memo = {i.order_id: i for i in pending}
        before = None
        for _ in range(10):
            try:
                transactions = await client.get_transactions(account, limit=100, from_lt=before)
            except Exception as exc:
                from tonutils.exceptions import HTTPClientResponseError
                if isinstance(exc, HTTPClientResponseError) and str(exc).startswith('HTTP 404 Error for '):
                    break
                raise
            if not transactions:
                break
            for tx in transactions:
                receipt = extract_receipt(tx, asset, account)
                if receipt and receipt['memo'] in by_memo:
                    invoice = by_memo[receipt['memo']]
                    if await confirm(invoice.id, receipt):
                        await deliver(invoice, bot)
            if min(tx.now for tx in transactions) < oldest or len(transactions) < 100:
                break
            before = min(tx.lt for tx in transactions) - 1
    async with sessionmaker() as session, session.begin():
        await session.execute(update(WalletInvoice).where(
            WalletInvoice.provider == 'wallet',
            WalletInvoice.bot_id == bot.id, WalletInvoice.status == 'pending',
            WalletInvoice.expires < int(time.time()),
        ).values(status='expired'))


async def recover_payments(bot):
    # A transfer may have reached TON before the previous process stopped.
    async with sessionmaker() as session, session.begin():
        await session.execute(update(WalletInvoice).where(
            WalletInvoice.provider == 'wallet',
            WalletInvoice.bot_id == bot.id, WalletInvoice.status == 'processing',
        ).values(status='review'))
    while True:
        try:
            await scan(bot)
        except Exception as exc:
            logger.warning('Wallet receipt scan deferred: %s', type(exc).__name__)
        await asyncio.sleep(10)
