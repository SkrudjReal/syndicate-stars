from __future__ import annotations

from typing import Sequence
from aiogram.types import User as AiogramUser
from sqlalchemy import select, update, func
from sqlalchemy.dialects.postgresql import insert

from datetime import datetime

from .base import BaseRepo
from bot.database.models import (
    User, Stars, UserStars, UserWithdraws
)

import pytz

DEFAULT_TZ = pytz.timezone("Europe/Moscow")


class UsersRepo(BaseRepo):
    model = User

    async def get_or_create_user(self, user: AiogramUser, referrer_id: int | None = None) -> User:
        existing = (await self.session.execute(
            select(User).where(User.id == user.id)
        )).scalar()

        if existing:
            existing.username = user.username
            existing.full_name = user.full_name
            await self.session.commit()
            return existing

        if referrer_id == user.id or (referrer_id and await self.session.get(User, referrer_id) is None):
            referrer_id = None

        new_user = User(
            id=user.id,
            username=user.username,
            full_name=user.full_name,
            referrer_id=referrer_id if referrer_id != user.id else None,
        )
        self.session.add(new_user)
        await self.session.commit()
        return new_user

    async def get_user(self, user_id: int) -> User | None:
        return (await self.session.execute(
            select(User).where(User.id == user_id)
        )).scalar()

    async def count_referrals(self, user_id: int) -> int:
        result = (await self.session.execute(
            select(func.count()).where(User.referrer_id == user_id)
        )).scalar()
        return result or 0

    async def get_stars_course(self) -> float:
        q = select(Stars.course)
        result = (await self.session.execute(q)).scalar()
        if result is None:
            return 0.015
        return result / 10000

    async def set_stars_course(self, course: int):
        q = update(Stars).values(course=course)
        await self.session.execute(q)
        await self.session.commit()

    async def add_stars(self, user_id: int, stars: float, add_or_subtract: str = '+'):
        import operator
        ops = {"+": operator.add, "-": operator.sub}

        stmt = (
            insert(UserStars)
            .values(user_id=user_id, stars=stars)
            .on_conflict_do_update(
                index_elements=[UserStars.user_id],
                set_={"stars": ops[add_or_subtract](UserStars.stars, stars)}
            )
            .returning(UserStars.id, UserStars.user_id, UserStars.stars)
        )

        res = await self.session.execute(stmt)
        await self.session.commit()
        return res.mappings().one()

    async def get_stars_balance(self, user_id: int) -> float:
        q = select(UserStars.stars).where(UserStars.user_id == user_id)
        return (await self.session.execute(q)).scalar() or 0.0

    async def log_withdraw(self, user_id: int, stars: float, whom: str):
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        q = pg_insert(UserWithdraws).values(
            user_id=user_id,
            stars=stars,
            whom=whom,
            date=datetime.now(tz=DEFAULT_TZ)
        )
        await self.session.execute(q)
        await self.session.commit()

    async def select_all_withdraw_history(self):
        q = select(UserWithdraws).order_by(UserWithdraws.date.desc())
        return (await self.session.execute(q)).scalars().all()

    async def select_user_withdraw_history(self, user_id: int):
        q = select(UserWithdraws).where(UserWithdraws.user_id == user_id).order_by(UserWithdraws.date.desc())
        return (await self.session.execute(q)).scalars().all()

    async def top_user_stars(self) -> Sequence[UserStars]:
        q = select(UserStars).order_by(UserStars.stars.desc())
        return (await self.session.execute(q)).scalars().all()
