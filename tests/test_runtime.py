"""Offline compatibility checks for the project's Python and payment SDKs."""
import asyncio
import sys
import pytest


@pytest.fixture(autouse=True)
def isolate_referral_database_calls(monkeypatch):
    from unittest.mock import AsyncMock
    from bot import referrals

    monkeypatch.setattr(referrals, 'register_payment', AsyncMock())
    monkeypatch.setattr(referrals, 'credit_payment', AsyncMock(return_value=0))
    monkeypatch.setattr(referrals, 'premium_stars', AsyncMock(return_value=1000))


@pytest.mark.asyncio
@pytest.mark.parametrize('provider', ['cryptobot', 'frekassa'])
async def test_paid_stars_are_delivered_to_captured_recipient(monkeypatch, provider):
    from types import SimpleNamespace
    from contextlib import asynccontextmanager
    from unittest.mock import AsyncMock, Mock
    from bot import funcs, cryptopay
    import importlib
    engine_module = importlib.import_module('bot.database.engine')
    repo_module = importlib.import_module('bot.database.repos')

    fragment = SimpleNamespace(create_star_buy_invoice=Mock(return_value={'transaction': {}}))
    monkeypatch.setattr(cryptopay, 'fragment_api', fragment)
    transfer = AsyncMock()
    monkeypatch.setattr(cryptopay, 'ton_wallet', SimpleNamespace(send_ton=transfer))
    monkeypatch.setattr(funcs, 'fragment_buy_stars_pretty', lambda r: {'ton_address': 'test', 'ton_amount': 1, 'comment': 'test'})
    monkeypatch.setattr(cryptopay.CryptoPay, 'get_status', AsyncMock(return_value='paid'))
    monkeypatch.setattr(cryptopay, 'frekassa', SimpleNamespace(get_order_status=AsyncMock(return_value='paid')))
    monkeypatch.setattr(asyncio, 'sleep', AsyncMock())
    session = SimpleNamespace(commit=AsyncMock())
    @asynccontextmanager
    async def sessions():
        yield session
    monkeypatch.setattr(engine_module, 'sessionmaker', sessions)
    log = AsyncMock()
    monkeypatch.setattr(repo_module.Repositories, 'get_repo', lambda **kwargs: SimpleNamespace(users=SimpleNamespace(log_withdraw=log)))
    message = SimpleNamespace(answer=AsyncMock())
    if provider == 'cryptobot':
        await funcs.check_cryptobot_invoice_status(1, 50, 42, 0.015, message, 'friend_user')
    else:
        await funcs.check_frekassa_payment_status(1, 50, 'test', message, 'friend_user')
    fragment.create_star_buy_invoice.assert_called_once_with(50, 'friend_user')
    transfer.assert_awaited_once()
    log.assert_awaited_once_with(1, 50, whom='friend_user')


@pytest.mark.asyncio
@pytest.mark.parametrize('provider', ['cryptobot', 'frekassa'])
async def test_premium_gift_invoice_and_polling_use_friend(monkeypatch, provider):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock
    from bot.handlers.users import buy_stars as module
    from bot import cryptopay
    from bot.utils.callback_factory.callback_factory import PremiumPayMethod, PremiumRubPayMethod

    quote = Mock(return_value={'ok': True, 'usd_amount': 10, 'ton_amount': 2, 'rub_amount': 1000})
    monkeypatch.setattr(module, '_get_premium_quote', quote)
    monkeypatch.setattr(module, 'get_editor', lambda q: AsyncMock())
    monkeypatch.setattr(module.asyncio, 'create_task', lambda c: c.close())
    query = SimpleNamespace(from_user=SimpleNamespace(id=1, username='payer_user'), answer=AsyncMock(), message=object())
    if provider == 'cryptobot':
        monkeypatch.setattr(module, 'crypto', SimpleNamespace(create_invoice=AsyncMock(return_value=SimpleNamespace(invoice_id=1, bot_invoice_url='https://example.com/invoice'))))
        poll = AsyncMock()
        monkeypatch.setattr(module.funcs, 'check_cryptobot_premium_invoice_status', poll)
        await module.pay_premium_cryptobot(query, PremiumPayMethod(method='pay_cryptobot', months=6, recipient='friend_user'))
    else:
        monkeypatch.setattr(cryptopay, 'frekassa', SimpleNamespace(create_order=AsyncMock(return_value='https://example.com/invoice')))
        poll = AsyncMock()
        monkeypatch.setattr(module.funcs, 'check_frekassa_premium_payment_status', poll)
        await module.pay_premium_frekassa(query, PremiumRubPayMethod(method='frekassa_sbp', months=6, recipient='friend_user'))
    quote.assert_called_once_with('friend_user', 6)
    assert poll.call_args.kwargs['username'] == 'friend_user'
    assert poll.call_args.kwargs['months'] == 6


@pytest.mark.asyncio
@pytest.mark.parametrize('product', ['stars', 'premium'])
async def test_gift_fsm_rejects_ids_and_checks_username(monkeypatch, product):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock
    from aiogram.fsm.storage.memory import MemoryStorage
    from aiogram.fsm.storage.base import StorageKey
    from aiogram.fsm.context import FSMContext
    from bot.handlers.users import buy_stars as module
    from bot.utils.callback_factory.callback_factory import BuyStars, BuyPremium

    storage = MemoryStorage()
    state = FSMContext(storage, StorageKey(bot_id=1, chat_id=1, user_id=1))
    query = SimpleNamespace(answer=AsyncMock())
    monkeypatch.setattr(module, 'get_editor', lambda q: AsyncMock())
    callback = BuyPremium(action='gift') if product == 'premium' else BuyStars(action='gift')
    await module.gift_recipient_start(query, callback, state)
    assert await state.get_state() == module.GiftRecipient.username.state
    api = SimpleNamespace(search_recipient=Mock(return_value={'found': {'recipient': 'verified'}}), search_premium_gift_recipient=Mock(return_value={'found': {'recipient': 'verified'}}))
    monkeypatch.setattr(module, 'fragment_api', api)
    for invalid in ('123456789', '@123456789', 'https://t.me/friend_user', '@abc', None):
        msg = SimpleNamespace(text=invalid, answer=AsyncMock())
        await module.gift_recipient_entered(msg, state)
        assert await state.get_state() == module.GiftRecipient.username.state
    api.search_recipient.assert_not_called()
    api.search_premium_gift_recipient.assert_not_called()
    msg = SimpleNamespace(text='@friend_user', answer=AsyncMock())
    await module.gift_recipient_entered(msg, state)
    assert await state.get_state() is None
    keyboard = msg.answer.call_args.kwargs['reply_markup']
    selected = (BuyPremium if product == 'premium' else BuyStars).unpack(keyboard.inline_keyboard[0][0].callback_data)
    assert selected.recipient == 'friend_user'
    await storage.close()


def test_gift_menu_buttons_are_not_highlighted_and_callback_fits():
    from bot.keyboards.inline import buy_stars_section_keyboard, payment_method_keyboard, premium_payment_method_keyboard
    from bot.utils.callback_factory.callback_factory import PayMethod
    from pydantic import ValidationError

    row = buy_stars_section_keyboard().inline_keyboard[1]
    assert [b.text for b in row] == ['Подарить звёзды', 'Подарить Premium']
    assert all(b.style is None for b in row)
    for keyboard in (payment_method_keyboard(1000, 'a' * 32), premium_payment_method_keyboard(12, 'a' * 32)):
        assert all(len(b.callback_data.encode()) <= 64 for r in keyboard.inline_keyboard for b in r)
    with pytest.raises(ValidationError):
        PayMethod(method='pay_cryptobot', stars_count=50, recipient='123456789')


@pytest.mark.asyncio
async def test_gift_cancel_clears_fsm(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from bot.handlers.users import buy_stars as module

    state = SimpleNamespace(clear=AsyncMock())
    query = SimpleNamespace(answer=AsyncMock(), from_user=SimpleNamespace(id=1))
    repo = SimpleNamespace(users=SimpleNamespace(get_stars_balance=AsyncMock(return_value=0)))
    monkeypatch.setattr(module, 'send_section', AsyncMock())
    await module.stars_section_menu(query, repo, state)
    state.clear.assert_awaited_once()


@pytest.mark.asyncio
async def test_gift_cryptobot_captures_recipient_for_payment_task(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock
    from bot.handlers.users import buy_stars as module
    from bot.utils.callback_factory.callback_factory import PayMethod

    monkeypatch.setattr(module, 'crypto', SimpleNamespace(create_invoice=AsyncMock(return_value=SimpleNamespace(invoice_id=1, bot_invoice_url='https://example.com/invoice'))))
    monkeypatch.setattr(module, 'get_editor', lambda q: AsyncMock())
    poll = AsyncMock()
    monkeypatch.setattr(module.funcs, 'check_cryptobot_invoice_status', poll)
    monkeypatch.setattr(module.asyncio, 'create_task', lambda c: c.close())
    query = SimpleNamespace(from_user=SimpleNamespace(id=1, username='payer_user'), answer=AsyncMock(), message=object())
    repo = SimpleNamespace(users=SimpleNamespace(get_stars_course=AsyncMock(return_value=0.015)))
    await module.pay_cryptobot(query, PayMethod(method='pay_cryptobot', stars_count=50, recipient='friend_user'), repo)
    assert poll.call_args.kwargs['username'] == 'friend_user'
    assert poll.call_args.kwargs['user_id'] == 1


@pytest.mark.asyncio
async def test_ton_wallet_enables_rate_limit_and_bounded_retries(monkeypatch):
    from unittest.mock import Mock
    from bot.cryptopay import TonWallet
    from tonutils.client import TonapiClient
    from tonutils.wallet import WalletV4R2

    monkeypatch.setattr(WalletV4R2, 'from_mnemonic', Mock(return_value=(object(), b'', b'', [])))
    wallet = TonWallet('test-api-key', [])
    assert isinstance(wallet.client, TonapiClient)
    assert wallet.client.rps == 1
    assert wallet.client.max_retries == 3
    assert wallet.client._limiter.max_rate == 1


@pytest.mark.asyncio
async def test_ton_client_retries_429_and_limits_each_attempt(monkeypatch):
    from contextlib import asynccontextmanager
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from tonutils.client import TonapiClient

    client = TonapiClient('test-api-key', rps=1, max_retries=3)
    responses = iter([
        SimpleNamespace(status=429, ok=False),
        SimpleNamespace(status=200, ok=True),
    ])
    @asynccontextmanager
    async def request(**kwargs):
        yield next(responses)
    @asynccontextmanager
    async def session():
        yield SimpleNamespace(request=request)
    monkeypatch.setattr(client, '_get_session', session)
    monkeypatch.setattr(client, '_parse_response', AsyncMock(return_value={'balance': 0}))
    delay = AsyncMock()
    monkeypatch.setattr(client, '_apply_retry_delay', delay)
    limiter = SimpleNamespace(acquire=AsyncMock())
    monkeypatch.setattr(client, '_limiter', limiter)
    assert await client._get('/test') == {'balance': 0}
    assert limiter.acquire.await_count == 2
    delay.assert_awaited_once()


@pytest.mark.asyncio
async def test_fragment_refreshes_expired_hash_and_explains_existing_premium(monkeypatch):
    from unittest.mock import Mock
    from bot.cryptopay import FragmentAPI
    import requests

    post = Mock(side_effect=[
        Mock(json=lambda: {'error': 'Bad request'}),
        Mock(json=lambda: {'error': 'This account is already subscribed to Telegram Premium.'}),
    ])
    get = Mock(return_value=Mock(text='apiUrl: "/api?hash=abcdef123"'))
    monkeypatch.setattr(requests, 'post', post)
    monkeypatch.setattr(requests, 'get', get)
    client = FragmentAPI('test-cookie', 'expired')
    result = client.search_premium_gift_recipient('test_user', 3)
    assert 'уже есть Telegram Premium' in result['error']
    assert client.hash_value == 'abcdef123'
    assert post.call_count == 2
    assert post.call_args.kwargs['params']['hash'] == 'abcdef123'


@pytest.mark.asyncio
async def test_fragment_premium_request_parameters_match_ton_flow(monkeypatch):
    from unittest.mock import Mock
    from bot.cryptopay import FragmentAPI

    client = FragmentAPI('', '')
    post = Mock(return_value={})
    monkeypatch.setattr(client, '_post', post)
    client.init_gift_premium('recipient', 3)
    assert post.call_args.args[0]['payment_method'] == 'ton'
    client.get_gift_premium_link('request', 3)
    assert post.call_args.args[0]['transaction'] == '1'


@pytest.mark.asyncio
async def test_cryptobot_payment_edits_existing_message(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from bot.handlers.users import buy_stars
    from bot.utils.callback_factory.callback_factory import PayMethod

    invoice = SimpleNamespace(bot_invoice_url='https://example.com/invoice', invoice_id=42)
    crypto = SimpleNamespace(create_invoice=AsyncMock(return_value=invoice))
    monkeypatch.setattr(buy_stars, 'crypto', crypto)
    edit = AsyncMock()
    query = SimpleNamespace(message=SimpleNamespace(answer=AsyncMock()), answer=AsyncMock(), from_user=SimpleNamespace(id=1, username='buyer_user'))
    monkeypatch.setattr(buy_stars, 'get_editor', lambda actual: edit if actual is query else None)
    # Verify UI without starting payment polling or calling a provider.
    monkeypatch.setattr(buy_stars.asyncio, 'create_task', lambda coro: coro.close())
    repo = SimpleNamespace(users=SimpleNamespace(get_stars_course=AsyncMock(return_value=0.015)))
    await buy_stars.pay_cryptobot(query, PayMethod(method='pay_cryptobot', stars_count=50), repo)
    edit.assert_awaited_once()
    assert '50' in edit.call_args.args[0]
    assert edit.call_args.kwargs['reply_markup'].inline_keyboard[0][0].url == invoice.bot_invoice_url
    query.message.answer.assert_not_awaited()
    query.answer.assert_awaited_once()


def test_payment_buttons_route_directly_to_sbp_and_back_preserves_amount():
    from bot.keyboards.inline import payment_method_keyboard, premium_payment_method_keyboard, rub_payment_keyboard
    from bot.utils.callback_factory.callback_factory import RubPayMethod, PremiumRubPayMethod, PremiumPayMethod, BuyStars

    buttons = [b for row in payment_method_keyboard(123).inline_keyboard for b in row]
    assert buttons[0].style == 'primary'
    sbp = RubPayMethod.unpack(buttons[1].callback_data)
    assert (sbp.method, sbp.stars_count) == ('frekassa_sbp', 123)
    premium = [b for row in premium_payment_method_keyboard(6).inline_keyboard for b in row]
    assert [b.text for b in premium] == [b.text for b in buttons]
    assert [b.style for b in premium] == [b.style for b in buttons]
    usd_premium = PremiumPayMethod.unpack(premium[2].callback_data)
    assert (usd_premium.method, usd_premium.months) == ('pay_usd', 6)
    assert premium[0].style == 'primary'
    sbp_premium = PremiumRubPayMethod.unpack(premium[1].callback_data)
    assert (sbp_premium.method, sbp_premium.months) == ('frekassa_sbp', 6)
    back = BuyStars.unpack(rub_payment_keyboard(123).inline_keyboard[-1][0].callback_data)
    assert (back.action, back.stars_count) == ('', 123)


@pytest.mark.asyncio
async def test_legacy_ruble_buttons_skip_submenus(monkeypatch):
    from unittest.mock import AsyncMock
    from bot.handlers.users import buy_stars
    from bot.utils.callback_factory.callback_factory import PayMethod, PremiumPayMethod, RubPayMethod, PremiumRubPayMethod

    stars = AsyncMock()
    premium = AsyncMock()
    monkeypatch.setattr(buy_stars, 'pay_frekassa', stars)
    monkeypatch.setattr(buy_stars, 'pay_premium_frekassa', premium)
    query, repo = object(), object()
    await buy_stars.pay_rub(query, PayMethod(method='pay_rub', stars_count=123), repo)
    stars.assert_awaited_once_with(query, RubPayMethod(method='frekassa_sbp', stars_count=123), repo)
    await buy_stars.pay_premium_rub(query, PremiumPayMethod(method='pay_rub', months=6))
    premium.assert_awaited_once_with(query, PremiumRubPayMethod(method='frekassa_sbp', months=6))


def test_invoice_back_preserves_amount_and_recipient():
    from bot.keyboards.inline import payment_redirect_keyboard
    from bot.utils.callback_factory.callback_factory import BuyStars

    keyboard = payment_redirect_keyboard(123, 'https://example.com/invoice', 'friend_user')
    back = keyboard.inline_keyboard[-1][0]
    assert back.text == 'Вернуться'
    callback = BuyStars.unpack(back.callback_data)
    assert (callback.action, callback.stars_count, callback.recipient) == ('', 123, 'friend_user')



def test_runtime_imports():
    assert sys.version_info[:2] == (3, 15)
    with asyncio.Runner() as runner:
        asyncio.set_event_loop(runner.get_loop())
        from aiogram import Bot, Dispatcher
        from aiogram_dialog import setup_dialogs
        from aiocryptopay import AioCryptoPay, Networks, utils
        from crypto_cloud_py import CryptoCloudApi
        from tonutils.client import TonapiClient
        from tonutils.wallet import WalletV4R2
        from xrocket import PayAPI
        from fkassa import FreeKassa
        from pydantic import BaseModel
        from pydantic_settings import BaseSettings
        import asyncpg
        import sqlalchemy
        from sqlalchemy.ext.asyncio import create_async_engine
        assert callable(WalletV4R2.from_mnemonic)
        assert callable(TonapiClient)


def test_entrypoint_initializes_event_loop_before_runtime_import(monkeypatch):
    import builtins
    from types import SimpleNamespace
    from bot.__main__ import main

    original_import = builtins.__import__
    started = []

    async def run():
        started.append(True)

    def import_with_loop_check(name, *args, **kwargs):
        if name == "bot.runtime":
            assert asyncio.get_running_loop().is_running()
            return SimpleNamespace(_main=run)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_with_loop_check)
    main()
    assert started == [True]


def test_main_menu_and_section_keyboards():
    from bot.keyboards import inline

    for build in (
        inline.start_keyboard,
        inline.support_keyboard,
        inline.buy_stars_section_keyboard,
        inline.withdraw_keyboard,
    ):
        keyboard = build()
        assert keyboard.inline_keyboard
        for row in keyboard.inline_keyboard:
            for button in row:
                assert button.callback_data or button.url
                if button.icon_custom_emoji_id:
                    assert isinstance(button.icon_custom_emoji_id, str)


def test_storefront_menu_keeps_primary_star_icon_and_support_contact():
    from bot.keyboards.inline import start_keyboard, support_keyboard
    from bot.utils.callback_factory.callback_factory import BuyStars
    from bot.messages import ICON_EMOJI_IDS

    menu = start_keyboard().inline_keyboard
    assert [len(row) for row in menu] == [1, 2]
    primary = menu[0][0]
    assert primary.text.casefold() == 'купить звёзды'
    assert BuyStars.unpack(primary.callback_data).action == 'menu'
    assert primary.icon_custom_emoji_id == ICON_EMOJI_IDS['white_star']
    assert [button.text for button in menu[1]] == ['Рефералы', 'Поддержка']
    support = support_keyboard().inline_keyboard
    assert [button.url for row in support for button in row if button.url] == ['https://t.me/maneramur']


@pytest.mark.asyncio
async def test_task_and_advertising_code_is_not_registered():
    from bot.handlers.users import routers
    from bot.handlers.events import routers as event_routers
    from bot.database.models import Base
    from bot.database.repos import Repositories

    removed = {'earn', 'earn_dialog', 'buy_subscribers', 'create_tasks', 'tasks', 'bot_review', 'auto_tasks', 'channel_post'}
    for router in [*routers, *event_routers]:
        assert router.name.rsplit('.', 1)[-1] not in removed
    assert set(Base.metadata.tables) == {'users', 'stars', 'user_stars', 'user_withdraws', 'telegram_photos', 'referral_payments'}
    assert set(Repositories.__dataclass_fields__) == {'session', 'users'}


@pytest.mark.asyncio
async def test_start_sends_menu_without_requesting_bot_profile(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from aiogram.types import User

    for key, value in {
        'BOT_TOKEN': '123456789:TEST_TOKEN_FOR_TESTS_ONLY',
        'DB_IP': '127.0.0.1', 'DB_USER': 'test', 'DB_PASSWORD': 'test',
        'DB_NAME': 'test', 'REDIS_USE': 'False', 'REDIS_IP': '127.0.0.1',
        'REDIS_PORT': '6379', 'REDIS_PASSWORD': '', 'ADMINS': '[]',
        'DEBUG_MODE': 'False', 'CRYPTOPAY_TOKEN': '', 'TONAPI_API_KEY': '',
        'FRAGMENT_COOKIES': '', 'FREKASSA_SHOP_ID': '0',
    }.items():
        monkeypatch.setenv(key, value)

    from bot.handlers.users.start_help import start
    monkeypatch.setattr('bot.handlers.users.start_help.send_photo', lambda msg, path, **kw: msg.answer_photo(path, **kw))
    monkeypatch.setattr('bot.handlers.users.start_help.send_first_welcome', AsyncMock(return_value=False))
    from bot import messages

    user = User(id=1, first_name='Test', is_bot=False)
    message = SimpleNamespace(from_user=user, text='/start', answer_photo=AsyncMock())
    users = SimpleNamespace(get_or_create_user=AsyncMock())
    await start(
        message, SimpleNamespace(users=users), SimpleNamespace(),
        SimpleNamespace(clear=AsyncMock()), SimpleNamespace(reset_stack=AsyncMock()),
    )
    users.get_or_create_user.assert_awaited_once_with(user, referrer_id=None)
    message.answer_photo.assert_awaited_once()
    assert message.answer_photo.call_args.kwargs['caption'] == messages.WELCOME_MESSAGE


@pytest.mark.asyncio
async def test_support_command_uses_current_contact(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from bot.handlers.users.support import support_command
    monkeypatch.setattr('bot.handlers.users.support.send_photo', lambda msg, path, **kw: msg.answer_photo(path, **kw))
    from bot import messages

    msg = SimpleNamespace(answer_photo=AsyncMock())
    await support_command(msg)
    msg.answer_photo.assert_awaited_once()
    assert msg.answer_photo.call_args.kwargs['caption'] == messages.SUPPORT_MESSAGE
    keyboard = msg.answer_photo.call_args.kwargs['reply_markup']
    assert [button.url for row in keyboard.inline_keyboard for button in row if button.url] == ['https://t.me/maneramur']
