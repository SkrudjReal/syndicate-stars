from __future__ import annotations
import logging
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from aiogram import BaseMiddleware, Dispatcher
from aiogram.dispatcher.flags import get_flag

from bot.database import get_repo

if TYPE_CHECKING:
    from aiogram.types import TelegramObject
    from aiogram.types import User as AiogramUser

    from bot.database.engine import Repositories

IGNORED_NAMES = ["Group", "Channel"]

logger = logging.getLogger("DatabaseMiddleware")


class GetRepo(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        us = data["event_from_user"]

        if us.first_name in IGNORED_NAMES:
            return

        async with get_repo() as repo:
            data["repo"] = repo

            await handler(event, data)


class GetUser(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        repo: Repositories = data["repo"]
        user_: AiogramUser = data["event_from_user"]

        if user_.first_name in IGNORED_NAMES:
            return None

        user_flag = get_flag(data, "user", default=True)

        if not user_flag:
            data["user"] = None
            return await handler(event, data)

        user = await repo.users.get_user(user_.id)

        if not user:
            user = await repo.users.get_or_create_user(user_)
            logger.info("New user %s", user_.id)

        data["user"] = user
        await handler(event, data)
        return None


def setup_get_repo_middleware(dp: Dispatcher):
    dp.message.middleware.register(GetRepo())
    dp.callback_query.middleware.register(GetRepo())
    dp.inline_query.middleware.register(GetRepo())
    dp.my_chat_member.middleware.register(GetRepo())
    dp.chat_member.middleware.register(GetRepo())


def setup_get_user_middleware(dp: Dispatcher):
    dp.message.middleware.register(GetUser())
    dp.callback_query.middleware.register(GetUser())
    dp.inline_query.middleware.register(GetUser())
    dp.my_chat_member.middleware.register(GetUser())
    dp.chat_member.middleware.register(GetUser())


def setup_get_chat_middleware(dp: Dispatcher):
    pass  # Chat middleware removed — no chat model
