import asyncio
import logging
from decimal import Decimal, ROUND_DOWN

from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert

from bot.database.engine import sessionmaker
from bot.database.models import ReferralPayment, Stars, User, UserStars

logger = logging.getLogger(__name__)


def referral_reward(base_stars) -> Decimal:
    base = Decimal(str(base_stars))
    if not base.is_finite() or base <= 0:
        raise ValueError('Referral base must be positive')
    return (base * Decimal('0.15')).quantize(Decimal('0.01'), rounding=ROUND_DOWN)


async def premium_stars(usd_amount) -> Decimal:
    async with sessionmaker() as session:
        course = await session.scalar(select(Stars.course))
    price = Decimal(str(usd_amount))
    rate = Decimal(str(course if course is not None else 150)) / 10000
    if not price.is_finite() or price <= 0 or rate <= 0:
        raise ValueError('Invalid Premium price or Stars course')
    return price / rate


async def register_payment(provider: str, payment_id, buyer_id: int, base_stars) -> None:
    reward = referral_reward(base_stars)
    async with sessionmaker() as session, session.begin():
        referrer = await session.scalar(select(User.referrer_id).where(User.id == buyer_id))
        if not referrer or referrer == buyer_id or await session.get(User, referrer) is None:
            return
        await session.execute(insert(ReferralPayment).values(
            provider=provider, payment_id=str(payment_id), buyer_id=buyer_id,
            referrer_id=referrer, base_stars=base_stars, reward_stars=reward,
        ).on_conflict_do_nothing(index_elements=['provider', 'payment_id']))


async def credit_payment(provider: str, payment_id, *, expired: bool = False) -> Decimal:
    async with sessionmaker() as session, session.begin():
        payment = await session.scalar(select(ReferralPayment).where(
            ReferralPayment.provider == provider, ReferralPayment.payment_id == str(payment_id),
        ).with_for_update())
        if payment is None or payment.status != 'pending':
            return Decimal('0')
        if expired:
            payment.status = 'expired'
            return Decimal('0')
        # Reward ledger and balance change commit in the same transaction.
        await session.execute(insert(UserStars).values(
            user_id=payment.referrer_id, stars=payment.reward_stars,
        ).on_conflict_do_update(
            index_elements=['user_id'],
            set_={'stars': UserStars.stars + payment.reward_stars},
        ))
        payment.status = 'credited'
        return payment.reward_stars


async def total_rewards(referrer_id: int) -> Decimal:
    async with sessionmaker() as session:
        total = await session.scalar(select(func.sum(ReferralPayment.reward_stars)).where(
            ReferralPayment.referrer_id == referrer_id, ReferralPayment.status == 'credited',
        ))
        return total or Decimal('0')


async def recover_payments() -> None:
    """Recheck persisted pending rewards, including invoices created before a restart."""
    from bot.cryptopay import CryptoPay, crypto, frekassa

    cursor = 0
    while True:
        try:
            async with sessionmaker() as session:
                pending = (await session.execute(select(
                    ReferralPayment.id, ReferralPayment.provider, ReferralPayment.payment_id,
                ).where(
                    ReferralPayment.status == 'pending', ReferralPayment.id > cursor,
                ).order_by(ReferralPayment.id).limit(50))).all()
            if not pending:
                cursor = 0
            for row_id, provider, payment_id in pending:
                cursor = row_id
                try:
                    if provider == 'cryptobot' and crypto:
                        status = await CryptoPay.get_status(int(payment_id))
                    elif provider == 'frekassa' and frekassa:
                        status = await frekassa.get_order_status(payment_id)
                    else:
                        continue
                    if status in ('paid', 'completed', 'success', 1):
                        await credit_payment(provider, payment_id)
                    elif status in ('expired', 'cancelled', 'canceled'):
                        await credit_payment(provider, payment_id, expired=True)
                except Exception as exc:
                    logger.warning('Referral payment check failed (%s): %s', provider, type(exc).__name__)
                await asyncio.sleep(1)
        except Exception as exc:
            logger.warning('Referral recovery failed: %s', type(exc).__name__)
        await asyncio.sleep(30)
