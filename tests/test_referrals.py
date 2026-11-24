import asyncio
import os
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from bot import referrals, withdrawals
from bot.database.models import Base, ReferralPayment, Stars, User, UserStars, UserWithdraws


@pytest.mark.parametrize('base, expected', [(50, '7.50'), (100, '15.00'), (333, '49.95'), ('333.399', '50.00')])
def test_fifteen_percent_uses_decimal_and_rounds_down(base, expected):
    assert referrals.referral_reward(base) == Decimal(expected)


@pytest.mark.parametrize('base', [0, -1, 'NaN', 'Infinity'])
def test_invalid_reward_bases_rejected(base):
    with pytest.raises(ValueError):
        referrals.referral_reward(base)


@pytest_asyncio.fixture
async def db(monkeypatch):
    url = os.getenv('REFERRAL_TEST_DATABASE_URL')
    if not url:
        pytest.skip('Dedicated PostgreSQL test database not configured')
    engine = create_async_engine(url, poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    monkeypatch.setattr(referrals, 'sessionmaker', sessions)
    monkeypatch.setattr(withdrawals, 'sessionmaker', sessions)
    async with sessions() as session:
        session.add_all([
            User(id=1, full_name='Referrer'),
            User(id=2, full_name='Buyer', referrer_id=1),
            User(id=3, full_name='No referrer'),
            Stars(id=1, course=150),
        ])
        await session.commit()
    try:
        yield sessions
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest.mark.asyncio
async def test_rewards_are_atomic_once_and_persist_between_sessions(db):
    await referrals.register_payment('cryptobot', 100, 2, 100)
    async with db() as s:
        assert await s.scalar(select(UserStars.stars).where(UserStars.user_id == 1)) is None
    # Re-registering or checking one invoice concurrently must not multiply the reward.
    await referrals.register_payment('cryptobot', 100, 2, 999)
    results = await asyncio.gather(*(referrals.credit_payment('cryptobot', 100) for _ in range(5)))
    assert sum(results) == Decimal('15')
    async with db() as s:
        assert await s.scalar(select(UserStars.stars).where(UserStars.user_id == 1)) == 15
        payment = await s.scalar(select(ReferralPayment))
        assert payment.status == 'credited'
        assert payment.base_stars == 100
    assert await referrals.total_rewards(1) == 15
    # Providers have independent invoice ID namespaces.
    await referrals.register_payment('frekassa', 100, 2, 50)
    assert await referrals.credit_payment('frekassa', 100) == Decimal('7.50')
    assert await referrals.total_rewards(1) == Decimal('22.50')


@pytest.mark.asyncio
async def test_parallel_invoices_accumulate_exactly_without_lost_updates(db):
    for invoice in range(20):
        await referrals.register_payment('cryptobot', invoice, 2, 51)
    await asyncio.gather(*(referrals.credit_payment('cryptobot', i) for i in range(20)))
    async with db() as s:
        assert await s.scalar(select(UserStars.stars).where(UserStars.user_id == 1)) == Decimal('153.00')
    assert await referrals.total_rewards(1) == Decimal('153.00')


@pytest.mark.asyncio
async def test_referral_profile_shows_balance_total_and_withdraw_button(monkeypatch):
    from bot.handlers.users import partners
    from bot.utils.callback_factory.callback_factory import AccountBalance

    monkeypatch.setattr(partners.referrals, 'total_rewards', AsyncMock(return_value=Decimal('60.00')))
    sender = AsyncMock()
    monkeypatch.setattr(partners, 'send_section', sender)
    repo = SimpleNamespace(users=SimpleNamespace(
        count_referrals=AsyncMock(return_value=2), get_stars_balance=AsyncMock(return_value=Decimal('52.50')),
    ))
    bot = SimpleNamespace(me=AsyncMock(return_value=SimpleNamespace(username='syndicatestars_bot')))
    query = SimpleNamespace(from_user=SimpleNamespace(id=1), answer=AsyncMock())
    await partners.partners_menu(query, repo, bot)
    text = sender.call_args.args[2]
    assert '15%' in text and '52.50' in text and '60.00' in text and '50 звёзд' in text
    button = sender.call_args.kwargs['reply_markup'].inline_keyboard[0][0]
    assert button.text == 'Вывести звёзды'
    assert AccountBalance.unpack(button.callback_data).action == 'menu'


@pytest.mark.asyncio
async def test_withdrawal_below_minimum_never_contacts_payment_providers(monkeypatch):
    from bot.handlers.users import buy_stars

    reserve = AsyncMock()
    monkeypatch.setattr(buy_stars.withdrawals, 'reserve', reserve)
    balance = AsyncMock()
    query = SimpleNamespace(text='49', answer=AsyncMock())
    await buy_stars.withdraw_amount(query, SimpleNamespace(users=SimpleNamespace(get_stars_balance=balance)), object())
    reserve.assert_not_called()
    balance.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('transfer_fails', [False, True])
async def test_withdrawal_handler_tracks_sent_or_review_without_double_debit(monkeypatch, transfer_fails):
    from unittest.mock import Mock
    from bot.handlers.users import buy_stars as module

    monkeypatch.setattr(module, 'fragment_api', SimpleNamespace(create_star_buy_invoice=Mock(return_value={'ok': True})))
    monkeypatch.setattr(module.FragmentAPI, 'parse_invoice', lambda r: {'ton_address': 'test', 'ton_amount': 1, 'comment': 'body'})
    wallet = SimpleNamespace(get_balance=AsyncMock(return_value=2), send_ton=AsyncMock(
        side_effect=TimeoutError() if transfer_fails else None, return_value='tx',
    ))
    monkeypatch.setattr(module, 'ton_wallet', wallet)
    reserve = AsyncMock(return_value=42)
    finish = AsyncMock()
    monkeypatch.setattr(module.withdrawals, 'reserve', reserve)
    monkeypatch.setattr(module.withdrawals, 'finish', finish)
    message = SimpleNamespace(text='50', message_id=123, from_user=SimpleNamespace(id=1, username='referrer'), answer=AsyncMock())
    repo = SimpleNamespace(users=SimpleNamespace(get_stars_balance=AsyncMock(return_value=Decimal('52.50'))))
    state = SimpleNamespace(get_data=AsyncMock(return_value={'withdraw_username': 'referrer'}), clear=AsyncMock())
    await module.withdraw_amount(message, repo, state)
    reserve.assert_awaited_once_with(1, 123, 50, 'referrer')
    wallet.send_ton.assert_awaited_once()
    if transfer_fails:
        finish.assert_awaited_once_with(42)
        assert 'проверку' in message.answer.call_args.args[0]
    else:
        finish.assert_awaited_once_with(42, tx_hash='tx')
        assert 'Готово!' in message.answer.call_args.args[0]
    state.clear.assert_awaited_once()


@pytest.mark.asyncio
async def test_confirmed_paid_only_credits_referral_once_before_delivery(monkeypatch):
    from bot import funcs, cryptopay

    credit = AsyncMock()
    monkeypatch.setattr(referrals, 'credit_payment', credit)
    monkeypatch.setattr(cryptopay.CryptoPay, 'get_status', AsyncMock(return_value='expired'))
    monkeypatch.setattr(asyncio, 'sleep', AsyncMock())
    message = SimpleNamespace(answer=AsyncMock())
    await funcs.check_cryptobot_invoice_status(2, 50, 123, 0.015, message, 'recipient')
    credit.assert_awaited_once_with('cryptobot', 123, expired=True)


@pytest.mark.asyncio
async def test_expired_self_and_invalid_referrals_do_not_credit(db):
    await referrals.register_payment('cryptobot', 1, 2, 50)
    assert await referrals.credit_payment('cryptobot', 1, expired=True) == 0
    assert await referrals.credit_payment('cryptobot', 1) == 0
    await referrals.register_payment('cryptobot', 2, 3, 50)
    async with db() as s:
        user = await s.get(User, 3)
        user.referrer_id = 3
        await s.commit()
    await referrals.register_payment('cryptobot', 3, 3, 50)
    async with db() as s:
        user = await s.get(User, 3)
        user.referrer_id = 9999
        await s.commit()
    await referrals.register_payment('cryptobot', 4, 3, 50)
    async with db() as s:
        assert await s.scalar(select(func.count()).select_from(ReferralPayment)) == 1
        assert await s.scalar(select(func.count()).select_from(UserStars)) == 0


@pytest.mark.asyncio
async def test_premium_bonus_uses_price_without_fee_and_snapshot_course(db):
    base = await referrals.premium_stars(10)
    await referrals.register_payment('cryptobot', 'premium', 2, base)
    async with db() as s:
        course = await s.get(Stars, 1)
        course.course = 300
        await s.commit()
    assert await referrals.credit_payment('cryptobot', 'premium') == Decimal('100.00')
    assert await referrals.total_rewards(1) == Decimal('100.00')


@pytest.mark.asyncio
async def test_referrer_only_set_on_first_registration_and_must_exist(db):
    from aiogram.types import User as TelegramUser
    from bot.database.repos.users import UsersRepo

    async with db() as s:
        repo = UsersRepo(s)
        for user_id, referrer_id, expected in [(10, 1, 1), (11, 999, None), (12, 12, None)]:
            created = await repo.get_or_create_user(TelegramUser(id=user_id, first_name='New buyer', is_bot=False), referrer_id)
            assert created.referrer_id == expected
        existing = await repo.get_or_create_user(TelegramUser(id=10, first_name='Buyer', is_bot=False), 3)
        assert existing.referrer_id == 1


@pytest.mark.asyncio
async def test_concurrent_withdrawals_cannot_overdraw_or_repeat(db):
    async with db() as s:
        s.add(UserStars(user_id=1, stars=100.5))
        await s.commit()
    with pytest.raises(ValueError):
        await withdrawals.reserve(1, 1, 49, 'referrer')
    attempts = await asyncio.gather(
        withdrawals.reserve(1, 10, 60, 'referrer'),
        withdrawals.reserve(1, 11, 60, 'referrer'),
    )
    assert sum(value is not None for value in attempts) == 1
    withdrawal_id = next(value for value in attempts if value is not None)
    await withdrawals.finish(withdrawal_id, tx_hash='mock-transaction')
    async with db() as s:
        row = await s.get(UserWithdraws, withdrawal_id)
        assert row.status == 'sent' and row.tx_hash == 'mock-transaction'
        assert await s.scalar(select(UserStars.stars).where(UserStars.user_id == 1)) == 40.5
        assert await withdrawals.reserve(1, row.request_id, 50, 'referrer') is None


@pytest.mark.asyncio
async def test_uncertain_withdrawal_retains_reservation_and_requires_review(db):
    async with db() as s:
        s.add(UserStars(user_id=1, stars=150))
        await s.commit()
    withdrawal_id = await withdrawals.reserve(1, 10, 50, 'referrer')
    await withdrawals.finish(withdrawal_id)
    assert await withdrawals.reserve(1, 11, 50, 'referrer') is None
    async with db() as s:
        assert (await s.get(UserWithdraws, withdrawal_id)).status == 'review'
        assert await s.scalar(select(UserStars.stars).where(UserStars.user_id == 1)) == 100


@pytest.mark.asyncio
async def test_pending_reward_is_recovered_after_restart(db, monkeypatch):
    from bot import cryptopay

    await referrals.register_payment('cryptobot', 123, 2, 400)
    monkeypatch.setattr(cryptopay, 'crypto', object())
    monkeypatch.setattr(cryptopay.CryptoPay, 'get_status', AsyncMock(return_value='paid'))
    task = asyncio.create_task(referrals.recover_payments())
    try:
        async def wait_for_credit():
            while await referrals.total_rewards(1) != Decimal('60'):
                await asyncio.sleep(0.02)
        await asyncio.wait_for(wait_for_credit(), timeout=10)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert await referrals.credit_payment('cryptobot', 123) == 0


@pytest.mark.asyncio
async def test_wallet_transfers_ton_once_without_double_conversion():
    from bot.cryptopay import TonWallet, FragmentAPI
    from pytoniq_core import begin_cell, Cell
    import base64

    payload = begin_cell().store_uint(0, 32).store_snake_string('Fragment order').end_cell()
    invoice = FragmentAPI.parse_invoice({'transaction': {'messages': [{
        'address': 'test', 'amount': '1500000000',
        'payload': base64.b64encode(payload.to_boc()).decode(),
    }]}})
    assert isinstance(invoice['comment'], Cell)
    assert invoice['comment'].hash == payload.hash
    wallet = object.__new__(TonWallet)
    wallet._transfer_lock = asyncio.Lock()
    wallet.wallet = SimpleNamespace(transfer=AsyncMock(return_value='tx'))
    assert await wallet.send_ton('test', invoice['ton_amount'], invoice['comment']) == 'tx'
    wallet.wallet.transfer.assert_awaited_once_with(destination='test', amount=1.5, body=invoice['comment'])
