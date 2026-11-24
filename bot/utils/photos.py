import asyncio
import hashlib
from pathlib import Path

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import FSInputFile, InputMediaPhoto, Message
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from bot.database.engine import sessionmaker
from bot.database.models.telegram_photo import TelegramPhoto


_upload_lock = asyncio.Lock()


async def _load(bot_id: int, digest: str) -> str | None:
    async with sessionmaker() as session:
        return await session.scalar(select(TelegramPhoto.file_id).where(
            TelegramPhoto.bot_id == bot_id, TelegramPhoto.sha256 == digest,
        ))


async def _store(bot_id: int, digest: str, file_id: str) -> None:
    async with sessionmaker() as session:
        statement = insert(TelegramPhoto).values(bot_id=bot_id, sha256=digest, file_id=file_id)
        await session.execute(statement.on_conflict_do_update(
            index_elements=['bot_id', 'sha256'], set_={'file_id': file_id},
        ))
        await session.commit()


async def send_photo(message: Message, path: str, caption: str, reply_markup=None, *, edit: bool = False,
                     message_effect_id: str | None = None):
    digest = hashlib.sha256(await asyncio.to_thread(Path(path).read_bytes)).hexdigest()
    # Serialize the first upload so concurrent chats reuse the same file ID.
    async with _upload_lock:
        file_id = await _load(message.bot.id, digest)

        async def send(photo):
            if edit:
                return await message.edit_media(
                    media=InputMediaPhoto(media=photo, caption=caption), reply_markup=reply_markup,
                )
            return await message.answer_photo(
                photo, caption=caption, reply_markup=reply_markup, message_effect_id=message_effect_id,
            )

        try:
            result = await send(file_id or FSInputFile(path))
        except TelegramBadRequest as exc:
            # Expired/invalid IDs need one fresh upload; other API errors must propagate.
            if not file_id or not any(part in exc.message.lower() for part in (
                'wrong file identifier', 'wrong remote file identifier', 'file_reference_expired',
            )):
                raise
            result = await send(FSInputFile(path))
        if isinstance(result, Message) and result.photo:
            latest_id = result.photo[-1].file_id
            if latest_id != file_id:
                await _store(message.bot.id, digest, latest_id)
        return result
