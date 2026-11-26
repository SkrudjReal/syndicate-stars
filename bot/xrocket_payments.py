"""Current xRocket Pay API; no payouts or withdrawals are implemented here."""
import asyncio
import hashlib
import hmac
import logging
import time
from decimal import Decimal, InvalidOperation
from uuid import uuid4
from urllib.parse import urlsplit

import aiohttp
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from bot.database.engine import sessionmaker
from bot.database.models import WalletInvoice
from bot.inline_rates import rate_cache
from bot.settings import settings
from bot.wallet_payments import quoted_amount, deliver

logger = logging.getLogger(__name__)


class XRocketError(RuntimeError):
    def __init__(self, status, problem):
        self.status, self.problem = status, problem
        super().__init__(f'xRocket HTTP {status}: {problem}')


class XRocketClient:
    BASE = 'https://pay.api.xrocket.exchange'

    def __init__(self):
        self.lock = asyncio.Lock()
        self.last_request = 0.0

    async def request(self, method, path, *, params=None, body=None):
        if not settings.xrocket.token:
            raise ValueError('xRocket is not configured')
        for attempt in range(3):
            async with self.lock:
                await asyncio.sleep(max(0, 1 - (time.monotonic() - self.last_request)))
                self.last_request = time.monotonic()
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as session:
                    async with session.request(method, self.BASE + path, params=params, json=body,
                                               headers={'Authorization': 'Bearer ' + settings.xrocket.token}) as response:
                        data = await response.json()
                        status = response.status
                        retry = response.headers.get('Retry-After', '1')
            if 200 <= status < 300:
                return data
            if status == 429 and attempt < 2:
                try:
                    delay = max(1, float(retry))
                except ValueError:
                    delay = 1
                await asyncio.sleep(delay)
                continue
            raise XRocketError(status, data.get('type', 'unknown'))

    async def get_invoice(self, client_id):
        return await self.request('GET', '/api/v1/invoice', params={'clientInvoiceId': client_id})


client = XRocketClient()


async def create_invoice(*, bot_id, buyer_id, chat_id, recipient, product, quantity, usd, base_stars):
    if product not in ('stars', 'premium') or (product == 'stars' and quantity < 50) or (product == 'premium' and quantity not in (3, 6, 12)):
        raise ValueError('Invalid purchase')
    rates = await rate_cache.get()
    amount = quoted_amount(Decimal(str(usd)) * Decimal('1.02'), rates.usdt_usd, 'USDT')
    now = int(time.time())
    invoice = WalletInvoice(
        order_id=uuid4().hex, provider='xrocket', bot_id=bot_id, buyer_id=buyer_id, chat_id=chat_id,
        recipient=recipient, product=product, quantity=quantity, asset='USDT', receiver='',
        atomic_amount=amount, base_stars=Decimal(str(base_stars)), created=now, expires=now + 900, status='creating',
    )
    async with sessionmaker() as session:
        session.add(invoice)
        await session.commit()
    body = {'clientInvoiceId': invoice.order_id, 'priceAmount': f'{Decimal(amount) / 10**6:.2f}',
            'priceCurrency': 'USDT', 'payCurrencies': ['USDT'], 'numPayments': 1,
            'expiresIn': 900_000, 'isFeePaidByUser': False,
            'description': f'Syndicate Stars: {quantity} stars' if product == 'stars' else f'Telegram Premium: {quantity} months',
            'customer': {'id': str(buyer_id), 'telegramId': str(buyer_id)}}
    if settings.xrocket.callback_url:
        if urlsplit(settings.xrocket.callback_url).scheme != 'https':
            raise ValueError('HTTPS callback required')
        body['callback'] = {'callbackUrl': settings.xrocket.callback_url, 'payload': {'orderId': invoice.order_id}}
    try:
        dto = await client.request('POST', '/api/v1/invoices', body=body)
    except (aiohttp.ClientError, TimeoutError, XRocketError):
        # An uncertain POST is resolved by our stable clientInvoiceId, never a new POST.
        dto = await client.get_invoice(invoice.order_id)
    if dto.get('clientInvoiceId') != invoice.order_id:
        raise ValueError('Invoice identity mismatch')
    await apply_invoice(dto)
    pay_url = dto.get('links', {}).get('telegramBotLink', '')
    parsed = urlsplit(pay_url)
    if parsed.scheme != 'https' or parsed.hostname != 't.me' or parsed.path.casefold() != '/xrocket':
        raise ValueError('Invalid payment link')
    from bot.referrals import register_payment
    await register_payment('xrocket', invoice.order_id, buyer_id, base_stars)
    return invoice, pay_url


async def apply_invoice(dto):
    order_id, provider_id = dto.get('clientInvoiceId'), dto.get('id')
    if not isinstance(order_id, str) or not isinstance(provider_id, str) or not 0 < len(provider_id) <= 100:
        raise ValueError('Missing invoice identity')
    try:
        async with sessionmaker() as session, session.begin():
            row = await session.scalar(select(WalletInvoice).where(
                WalletInvoice.provider == 'xrocket', WalletInvoice.order_id == order_id,
            ).with_for_update())
            if row is None:
                return False
            try:
                amount = Decimal(str(dto.get('priceAmount', 'NaN')))
            except InvalidOperation:
                raise ValueError('Invalid invoice amount') from None
            if not amount.is_finite() or amount != Decimal(row.atomic_amount) / 10**6 or dto.get('priceCurrency') != 'USDT':
                raise ValueError('Invoice amount mismatch')
            if row.provider_invoice_id and row.provider_invoice_id != provider_id:
                raise ValueError('Provider identity mismatch')
            row.provider_invoice_id = provider_id
            if row.status not in ('creating', 'pending', 'expired'):
                return False
            status = dto.get('status')
            if status == 'paid':
                row.transaction = hashlib.sha256(('xrocket:' + provider_id).encode()).hexdigest()
                row.status = 'paid'
            elif status in ('expired', 'cancelled'):
                row.status = 'expired'
            elif status == 'active':
                row.status = 'pending'
            return True
    except IntegrityError:
        raise ValueError('Provider invoice already assigned') from None


def verify_signature(raw, headers, secret, *, now=None):
    if not secret or headers.get('Signature-Version') != 'v1':
        return False
    timestamp, signature = headers.get('Signature-Timestamp', ''), headers.get('Signature', '')
    try:
        if not timestamp.isdigit() or abs(int((time.time() if now is None else now) * 1000) - int(timestamp)) > 300_000:
            return False
    except (ValueError, OverflowError):
        return False
    expected = hmac.new(secret.encode(), timestamp.encode() + b'.' + raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected.encode(), signature.lower().encode())


async def recover_payments(bot):
    async with sessionmaker() as session, session.begin():
        await session.execute(update(WalletInvoice).where(
            WalletInvoice.provider == 'xrocket', WalletInvoice.bot_id == bot.id, WalletInvoice.status == 'processing',
        ).values(status='review'))
    cursor = 0
    while True:
        try:
            async with sessionmaker() as session:
                rows = (await session.scalars(select(WalletInvoice).where(
                    WalletInvoice.provider == 'xrocket', WalletInvoice.bot_id == bot.id,
                    WalletInvoice.status.in_(('creating', 'pending', 'paid')), WalletInvoice.id > cursor,
                ).order_by(WalletInvoice.id).limit(50))).all()
            if not rows:
                cursor = 0
            for row in rows:
                cursor = row.id
                try:
                    if row.status != 'paid':
                        await apply_invoice(await client.get_invoice(row.order_id))
                    await deliver(row, bot)
                except XRocketError as exc:
                    if exc.status == 404 and row.expires < time.time():
                        async with sessionmaker() as session, session.begin():
                            await session.execute(update(WalletInvoice).where(WalletInvoice.id == row.id, WalletInvoice.status == 'creating').values(status='expired'))
                    else:
                        logger.warning('xRocket poll deferred: HTTP %s', exc.status)
                except Exception as exc:
                    logger.warning('xRocket order check deferred: %s', type(exc).__name__)
        except Exception as exc:
            logger.warning('xRocket recovery deferred: %s', type(exc).__name__)
        await asyncio.sleep(10)
