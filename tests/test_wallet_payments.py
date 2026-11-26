from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlsplit

import pytest
from pytoniq_core import Address, begin_cell
from pytoniq_core.tlb.transaction import InternalMsgInfo
from pytoniq_core.tlb.block import CurrencyCollection

from bot import wallet_payments as wallet
from bot.keyboards.inline import payment_method_keyboard, premium_payment_method_keyboard, wallet_payment_keyboard

ADDRESS = Address((0, b'\x11' * 32)).to_str(is_bounceable=False)
MEMO = 'a' * 32


def transaction(asset='TON', referenced=True):
    comment = begin_cell().store_uint(0, 32).store_snake_string(MEMO).end_cell()
    if asset == 'TON':
        body = comment
    else:
        b = (begin_cell().store_uint(0x178D4519, 32).store_uint(1, 64).store_coins(1_000_000)
             .store_address(Address(ADDRESS)).store_address(None).store_coins(1).store_bit(referenced))
        body = (b.store_ref(comment) if referenced else b.store_cell(comment)).end_cell()
    info = InternalMsgInfo(True, False, False, Address(ADDRESS), Address(ADDRESS), CurrencyCollection(1_000_000), 0, 0, 1, 100)
    return NS(
        account_addr=Address(ADDRESS).hash_part, in_msg=NS(info=info, body=body),
        description=NS(type_='ordinary', aborted=False, compute_ph=NS(type_='vm', success=True, exit_code=0), action=None),
        now=100, out_msgs=[], cell=comment,
    )


@pytest.mark.parametrize('asset', ['TON', 'USDT'])
def test_raw_inbound_receipt_with_exact_memo(asset):
    receipt = wallet.extract_receipt(transaction(asset), asset, ADDRESS)
    assert receipt['memo'] == MEMO
    assert receipt['amount'] == 1_000_000
    assert receipt['timestamp'] == 100


def test_usdt_inline_forward_payload_supported():
    assert wallet.extract_receipt(transaction('USDT', False), 'USDT', ADDRESS)['memo'] == MEMO


@pytest.mark.parametrize('defect', ['aborted', 'bounced', 'wrong_account', 'failed_vm', 'failed_action', 'no_comment', 'wrong_opcode'])
def test_unrelated_or_failed_raw_transfers_rejected(defect):
    tx = transaction('USDT')
    if defect == 'aborted': tx.description.aborted = True
    elif defect == 'bounced': tx.in_msg.info.bounced = True
    elif defect == 'wrong_account': tx.account_addr = b'\x00' * 32
    elif defect == 'failed_vm': tx.description.compute_ph.success = False
    elif defect == 'failed_action': tx.description.action = NS(success=False, result_code=37)
    elif defect == 'no_comment': tx.in_msg.body = begin_cell().end_cell()
    elif defect == 'wrong_opcode': tx.in_msg.body = begin_cell().store_uint(0, 32).store_snake_string(MEMO).end_cell()
    assert wallet.extract_receipt(tx, 'USDT', ADDRESS) is None


def test_undeployed_wallet_requires_nonbounceable_actual_ton_credit():
    tx = transaction()
    tx.description.aborted = True
    tx.description.compute_ph = NS(type_='skipped', reason=NS(type_='no_state'))
    tx.description.credit_ph = NS(credit=CurrencyCollection(1_000_000))
    assert wallet.extract_receipt(tx, 'TON', ADDRESS)
    tx.in_msg.info.bounce = True
    assert wallet.extract_receipt(tx, 'TON', ADDRESS) is None


def test_amounts_round_up_and_links_preserve_token_units():
    assert wallet.quoted_amount('.75', '2', 'TON') == 375_000_000
    assert wallet.quoted_amount('.751', '1', 'USDT') == 760_000
    invoice = NS(asset='USDT', atomic_amount=760_000, receiver=ADDRESS, order_id=MEMO, quantity=50, product='stars')
    url = wallet.transfer_url(invoice)
    params = parse_qs(urlsplit(url).query)
    assert params == {'amount': ['760000'], 'text': [MEMO], 'jetton': [wallet.USDT_MASTER]}
    keyboard = wallet_payment_keyboard(invoice, 'friend_user')
    assert keyboard.inline_keyboard[0][0].url == url
    assert 'friend_user' in keyboard.inline_keyboard[1][0].callback_data


@pytest.mark.parametrize('price,rate', [('NaN',1),(1,'Infinity'),(0,1),(1,0),(-1,1)])
def test_invalid_quotes_fail_closed(price, rate):
    with pytest.raises(ValueError): wallet.quoted_amount(price, rate, 'TON')


@pytest.mark.parametrize('keyboard,args', [(payment_method_keyboard,(50,'friend_user')), (premium_payment_method_keyboard,(6,'friend_user'))])
def test_payment_buttons_preserve_existing_methods_and_exact_reference_icons(keyboard, args):
    buttons={b.text:b for group in ('rub','crypto','other') for row in keyboard(*args, category=group).inline_keyboard for b in row}
    expected={'TON':'5370546279375982437','USDT (TON)':'5280846677673010353', 'LolzTeam':'5280957144231846453', 'xRocket':'5415897719522744378', 'CryptoBot • 2%':'5397597950501204351', 'СБП • 3%':'5294247005701292072'}
    for label,icon in expected.items():
        assert buttons[label].icon_custom_emoji_id == icon
        assert 'friend_user' in buttons[label].callback_data
    assert 'USD/EUR (в разработке)' in buttons


async def test_unconfigured_providers_explicitly_unavailable():
    from bot.handlers.users.buy_stars import payment_not_configured
    query=NS(answer=AsyncMock())
    await payment_not_configured(query)
    assert query.answer.call_args.kwargs['show_alert'] is True


@pytest.mark.parametrize('product', ['stars', 'premium'])
async def test_wallet_handler_captures_friend_and_product(monkeypatch, product):
    from bot.handlers.users import buy_stars as module
    from bot.utils.callback_factory.callback_factory import PayMethod, PremiumPayMethod
    monkeypatch.setattr(wallet.settings.ton_api, 'receive_address', ADDRESS)
    monkeypatch.setattr(wallet.settings.ton_api, 'api_key', 'test-key')
    invoice=NS(asset='USDT', atomic_amount=1_000_000, receiver=ADDRESS, order_id=MEMO, quantity=6 if product == 'premium' else 50, product=product)
    create=AsyncMock(return_value=invoice)
    monkeypatch.setattr(wallet,'create_invoice',create)
    from unittest.mock import Mock
    monkeypatch.setattr(module,'_get_premium_quote',Mock(return_value={'ok':True,'usd_amount':1}))
    monkeypatch.setattr(module.referrals,'premium_stars',AsyncMock(return_value=100))
    edit=AsyncMock()
    monkeypatch.setattr(module,'get_editor',lambda query:edit)
    query=NS(bot=NS(id=123),from_user=NS(id=2,username='payer_user'),message=NS(chat=NS(id=2)),answer=AsyncMock())
    callback=(PremiumPayMethod(method='pay_usdt_ton',months=6,recipient='friend_user') if product == 'premium' else PayMethod(method='pay_usdt_ton',stars_count=50,recipient='friend_user'))
    await module.pay_wallet(query,callback,NS(users=NS(get_stars_course=AsyncMock(return_value=.015))))
    assert create.call_args.kwargs['recipient'] == 'friend_user'
    assert create.call_args.kwargs['product'] == product
    assert create.call_args.kwargs['quantity'] == invoice.quantity
    assert create.call_args.kwargs['asset'] == 'USDT'
    assert MEMO in edit.call_args.args[0]
