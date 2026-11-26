import hashlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from aiohttp.test_utils import TestClient, TestServer

from bot import notifications


def fields(**overrides):
    values = dict(MERCHANT_ID='123', AMOUNT='250.00', MERCHANT_ORDER_ID='order1', intid='1001')
    values.update(overrides)
    values['SIGN'] = hashlib.md5(
        f"{values['MERCHANT_ID']}:{values['AMOUNT']}:test-secret:{values['MERCHANT_ORDER_ID']}".encode(),
    ).hexdigest()
    return values


@pytest_asyncio.fixture
async def client(monkeypatch):
    monkeypatch.setattr(notifications, 'record_receipt', AsyncMock())
    app = notifications.create_app(SimpleNamespace(shop_id=123, secret_word_2='test-secret'))
    async with TestClient(TestServer(app)) as client:
        yield client


async def test_valid_signed_receipt_commits_before_yes(client):
    response = await client.post('/notifications/payment', data=fields())
    assert response.status == 200
    assert await response.text() == 'YES'
    notifications.record_receipt.assert_awaited_once()


async def test_forged_signature_never_touches_database(client):
    data = fields()
    data['SIGN'] = '0' * 32
    response = await client.post('/notifications/payment', data=data)
    assert response.status == 403
    notifications.record_receipt.assert_not_awaited()


@pytest.mark.parametrize('overrides', [dict(MERCHANT_ID='124'), dict(AMOUNT='NaN'), dict(AMOUNT='-1'), dict(AMOUNT='1.001')])
async def test_invalid_signed_data_rejected(client, overrides):
    response = await client.post('/notifications/payment', data=fields(**overrides))
    assert response.status in (400, 403)
    notifications.record_receipt.assert_not_awaited()


async def test_duplicate_fields_rejected(client):
    data = list(fields().items()) + [('AMOUNT', '1')]
    response = await client.post('/notifications/payment', data=data)
    assert response.status == 400
    notifications.record_receipt.assert_not_awaited()


async def test_commit_failure_is_not_acknowledged(client):
    notifications.record_receipt.side_effect = RuntimeError('test commit failure')
    response = await client.post('/notifications/payment', data=fields())
    assert response.status == 500
    assert await response.text() != 'YES'


@pytest.mark.parametrize('path', ['/return/success', '/return/failure'])
async def test_browser_redirect_cannot_confirm_payment(client, path):
    response = await client.get(path, allow_redirects=False)
    assert response.status == 303
    assert response.headers['Location'] == 'https://t.me/syndicatestars_bot'
    notifications.record_receipt.assert_not_awaited()


async def test_missing_secret_is_unavailable(client):
    client.app[notifications.FREKASSA].secret_word_2 = ''
    assert (await client.post('/notifications/payment', data=fields())).status == 503


async def test_get_receipt_supported(client):
    response = await client.get('/notifications/payment', params=fields())
    assert response.status == 200
    notifications.record_receipt.assert_awaited_once()
