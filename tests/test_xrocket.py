import hashlib
import hmac
import json
import time
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio
from aiohttp.test_utils import TestClient, TestServer

from bot import xrocket_payments as rocket
from bot.notifications import create_app


def event():
    return {'id': 'delivery-1', 'type': 'invoice', 'data': {'event': 'invoice_status_changed', 'invoice': {
        'id': 'invoice-1', 'clientInvoiceId': 'order-1', 'priceAmount': '0.77', 'priceCurrency': 'USDT', 'status': 'paid',
    }}}


def signed(raw, offset=0):
    timestamp = str(int(time.time() * 1000) + offset)
    signature = hmac.new(b'test-hook-key', timestamp.encode() + b'.' + raw, hashlib.sha256).hexdigest()
    return {'Content-Type': 'application/json', 'Signature-Version': 'v1', 'Signature-Timestamp': timestamp, 'Signature': signature}


@pytest_asyncio.fixture
async def client(monkeypatch):
    monkeypatch.setattr(rocket, 'apply_invoice', AsyncMock(return_value=True))
    async with TestClient(TestServer(create_app(xrocket_config=NS(webhook_token='test-hook-key')))) as c:
        yield c


async def test_signed_hook_accepts_once_durable_transition(client):
    raw = json.dumps(event()).encode()
    response = await client.post('/notifications/xrocket', data=raw, headers=signed(raw))
    assert response.status == 200
    rocket.apply_invoice.assert_awaited_once_with(event()['data']['invoice'])


@pytest.mark.parametrize('defect', ['signature', 'timestamp', 'version', 'body', 'legacy'])
async def test_webhook_verification_precedes_invoice_processing(client, defect):
    raw = json.dumps(event()).encode()
    headers = signed(raw)
    if defect == 'signature': headers['Signature'] = '0' * 64
    elif defect == 'timestamp': headers = signed(raw, offset=-301_000)
    elif defect == 'version': headers['Signature-Version'] = 'v2'
    elif defect == 'body': raw += b' '
    elif defect == 'legacy': headers = {'Rocket-Pay-Signature': '0' * 64}
    response = await client.post('/notifications/xrocket', data=raw, headers=headers)
    assert response.status == 401
    rocket.apply_invoice.assert_not_awaited()


@pytest.mark.parametrize('kind', ['payout', 'unknown', 'payment_status_changed'])
async def test_non_completion_events_do_not_credit_orders(client, kind):
    data = event()
    if kind == 'payment_status_changed': data['data']['event'] = kind
    else: data['type'] = kind
    raw = json.dumps(data).encode()
    response = await client.post('/notifications/xrocket', data=raw, headers=signed(raw))
    assert response.status == 200
    rocket.apply_invoice.assert_not_awaited()


@pytest.mark.parametrize('product', ['stars', 'premium'])
async def test_xrocket_handler_keeps_gift_recipient_and_selected_product(monkeypatch, product):
    from bot.handlers.users import buy_stars as module
    from bot.utils.callback_factory.callback_factory import PayMethod, PremiumPayMethod
    monkeypatch.setattr(rocket.settings.xrocket, 'token', 'configured-token')
    create = AsyncMock(return_value=(NS(atomic_amount=770_000), 'https://t.me/xRocket?start=test'))
    monkeypatch.setattr(rocket, 'create_invoice', create)
    monkeypatch.setattr(module, '_get_premium_quote', Mock(return_value={'ok': True, 'usd_amount': 1}))
    monkeypatch.setattr(module.referrals, 'premium_stars', AsyncMock(return_value=100))
    edit = AsyncMock()
    monkeypatch.setattr(module, 'get_editor', lambda q: edit)
    query = NS(bot=NS(id=123), from_user=NS(id=2, username='payer_user'), message=NS(chat=NS(id=2)), answer=AsyncMock())
    callback = (PremiumPayMethod(method='pay_xrocket', months=6, recipient='friend_user') if product == 'premium'
                else PayMethod(method='pay_xrocket', stars_count=50, recipient='friend_user'))
    await module.pay_xrocket(query, callback, NS(users=NS(get_stars_course=AsyncMock(return_value=.015))))
    assert create.call_args.kwargs['product'] == product
    assert create.call_args.kwargs['recipient'] == 'friend_user'
    assert create.call_args.kwargs['quantity'] == (6 if product == 'premium' else 50)
    assert '0.77 USDT' in edit.call_args.args[0]
    button = edit.call_args.kwargs['reply_markup'].inline_keyboard[0][0]
    assert button.url == 'https://t.me/xRocket?start=test'


async def test_current_api_uses_bearer_and_accepts_201_without_legacy_envelope(monkeypatch):
    monkeypatch.setattr(rocket.settings.xrocket, 'token', 'configured-token')
    seen = []
    class Response:
        status = 201
        headers = {}
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def json(self): return {'id': 'invoice-1'}
    class Session:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        def request(self, method, url, **kwargs):
            seen.append((method, url, kwargs))
            return Response()
    monkeypatch.setattr(rocket.aiohttp, 'ClientSession', Session)
    assert await rocket.XRocketClient().request('POST', '/api/v1/invoices', body={'clientInvoiceId': 'stable-id'}) == {'id': 'invoice-1'}
    assert seen[0][1] == 'https://pay.api.xrocket.exchange/api/v1/invoices'
    assert seen[0][2]['headers'] == {'Authorization': 'Bearer configured-token'}
