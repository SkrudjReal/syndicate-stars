"""FreeKassa receipts. This process records payments; the bot handles delivery."""
import hashlib
import hmac
from decimal import Decimal, InvalidOperation

from aiohttp import web
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from bot.database.engine import sessionmaker
from bot.database.models import NotificationOrder
from bot.settings import settings

FREKASSA = web.AppKey('frekassa', object)
RETURN_URL = web.AppKey('return_url', str)

async def register_order(payment_id, shop_id, amount, currency):
    async with sessionmaker() as session:
        session.add(NotificationOrder(
            payment_id=payment_id, shop_id=shop_id,
            amount=Decimal(str(amount)), currency=currency,
        ))
        await session.commit()


async def is_confirmed(payment_id, shop_id):
    async with sessionmaker() as session:
        return bool(await session.scalar(select(NotificationOrder.confirmed).where(
            NotificationOrder.payment_id == payment_id,
            NotificationOrder.shop_id == shop_id,
        )))


async def record_receipt(payment_id, shop_id, amount, transaction):
    try:
        async with sessionmaker() as session:
            async with session.begin():
                order = await session.scalar(select(NotificationOrder).where(
                    NotificationOrder.payment_id == payment_id,
                ).with_for_update())
                if order is None:
                    raise web.HTTPNotFound(text='Unknown order')
                if order.shop_id != shop_id or order.amount != amount or order.currency != 'RUB':
                    raise web.HTTPBadRequest(text='Order mismatch')
                if order.confirmed and order.provider_payment_id != transaction:
                    raise web.HTTPConflict(text='Transaction mismatch')
                order.provider_payment_id = transaction
                order.confirmed = True
    except IntegrityError:
        raise web.HTTPConflict(text='Transaction already recorded') from None


async def payment(request):
    config = request.app[FREKASSA]
    if not config.secret_word_2 or not config.shop_id:
        raise web.HTTPServiceUnavailable(text='Not configured')
    if request.method == 'POST':
        if request.content_type not in ('application/x-www-form-urlencoded', 'multipart/form-data'):
            raise web.HTTPUnsupportedMediaType()
        values = await request.post()
    else:
        values = request.query
    required = ('MERCHANT_ID', 'AMOUNT', 'MERCHANT_ORDER_ID', 'intid', 'SIGN')
    if any(len(values.getall(key, [])) != 1 for key in required):
        raise web.HTTPBadRequest(text='Invalid fields')
    if any(not isinstance(values[key], str) or not 0 < len(values[key]) <= 100 for key in required):
        raise web.HTTPBadRequest(text='Invalid fields')
    merchant, raw_amount, order_id = (values[key] for key in required[:3])
    expected = hashlib.md5(
        f'{merchant}:{raw_amount}:{config.secret_word_2}:{order_id}'.encode(),
    ).hexdigest()
    if not hmac.compare_digest(expected.encode(), values['SIGN'].lower().encode()):
        raise web.HTTPForbidden(text='Invalid signature')
    if merchant != str(config.shop_id):
        raise web.HTTPForbidden(text='Invalid merchant')
    try:
        amount = Decimal(raw_amount)
        if not amount.is_finite() or not 0 < amount < Decimal('1000000000000000000'):
            raise ValueError
        if amount != amount.quantize(Decimal('.01')):
            raise ValueError
    except (InvalidOperation, ValueError):
        raise web.HTTPBadRequest(text='Invalid amount') from None
    await record_receipt(order_id, config.shop_id, amount, values['intid'])
    return web.Response(text='YES')


async def return_to_bot(request):
    raise web.HTTPSeeOther(location=request.app[RETURN_URL])


async def health(request):
    return web.json_response({'status': 'ok'})


def create_app(config=None, return_url=None):
    app = web.Application(client_max_size=16384)
    app[FREKASSA] = config or settings.frekassa
    app[RETURN_URL] = return_url or settings.notifications.return_url
    app.router.add_route('POST', '/notifications/payment', payment)
    app.router.add_route('GET', '/notifications/payment', payment)
    for path in ('/return/success', '/return/failure'):
        app.router.add_route('GET', path, return_to_bot)
        app.router.add_route('POST', path, return_to_bot)
    app.router.add_get('/health', health)
    return app


if __name__ == '__main__':
    web.run_app(create_app(), host=settings.notifications.host,
                port=settings.notifications.port, access_log=None)
