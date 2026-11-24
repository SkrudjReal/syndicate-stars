from datetime import datetime, timezone

from sqlalchemy import select, update

from bot.database.engine import sessionmaker
from bot.database.models import User, UserStars, UserWithdraws


async def reserve(user_id: int, request_id: int, amount: int, username: str) -> int | None:
    if amount < 50:
        raise ValueError('Minimum withdrawal is 50 Stars')
    async with sessionmaker() as session, session.begin():
        # Serialize reservations for a user, including duplicate Telegram updates.
        user = await session.scalar(select(User).where(User.id == user_id).with_for_update())
        if user is None:
            return None
        existing = await session.scalar(select(UserWithdraws.id).where(
            UserWithdraws.user_id == user_id,
            (UserWithdraws.request_id == request_id) | UserWithdraws.status.in_(['pending', 'review']),
        ).limit(1))
        if existing is not None:
            return None
        balance = await session.scalar(update(UserStars).where(
            UserStars.user_id == user_id, UserStars.stars >= amount,
        ).values(stars=UserStars.stars - amount).returning(UserStars.stars))
        if balance is None:
            return None
        withdrawal = UserWithdraws(
            user_id=user_id, request_id=request_id, stars=amount, whom=username,
            date=datetime.now(timezone.utc), status='pending',
        )
        session.add(withdrawal)
        await session.flush()
        return withdrawal.id


async def finish(withdrawal_id: int, *, tx_hash: str | None = None) -> None:
    async with sessionmaker() as session, session.begin():
        await session.execute(update(UserWithdraws).where(
            UserWithdraws.id == withdrawal_id, UserWithdraws.status == 'pending',
        ).values(status='sent' if tx_hash else 'review', tx_hash=tx_hash))
