from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import SendPhoto
from aiogram.types import Chat, FSInputFile, Message, PhotoSize


def photo_message(file_id='telegram-file-id'):
    return Message(
        message_id=1, date=datetime.now(timezone.utc), chat=Chat(id=1, type='private'),
        photo=[PhotoSize(file_id=file_id, file_unique_id='unique', width=100, height=100)],
    )


@pytest.mark.asyncio
async def test_photo_is_uploaded_once_then_reused_across_chats_and_edits(monkeypatch, tmp_path):
    from bot.utils import photos

    path = tmp_path / 'photo.jpeg'
    path.write_bytes(b'original photo')
    cache = {}

    async def load(bot_id, digest):
        return cache.get((bot_id, digest))

    async def store(bot_id, digest, file_id):
        cache[bot_id, digest] = file_id

    monkeypatch.setattr(photos, '_load', load)
    monkeypatch.setattr(photos, '_store', store)
    first = SimpleNamespace(bot=SimpleNamespace(id=10), answer_photo=AsyncMock(return_value=photo_message()))
    other_chat = SimpleNamespace(bot=first.bot, answer_photo=AsyncMock(return_value=photo_message()), edit_media=AsyncMock(return_value=photo_message()))
    await photos.send_photo(first, str(path), 'caption', message_effect_id='5159385139981059251')
    assert isinstance(first.answer_photo.call_args.args[0], FSInputFile)
    assert first.answer_photo.call_args.kwargs['message_effect_id'] == '5159385139981059251'
    await photos.send_photo(other_chat, str(path), 'caption')
    assert other_chat.answer_photo.call_args.args[0] == 'telegram-file-id'
    await photos.send_photo(other_chat, str(path), 'updated', edit=True)
    assert other_chat.edit_media.call_args.kwargs['media'].media == 'telegram-file-id'
    path.write_bytes(b'replacement photo')
    await photos.send_photo(other_chat, str(path), 'caption')
    assert isinstance(other_chat.answer_photo.call_args.args[0], FSInputFile)
    other_chat.bot = SimpleNamespace(id=20)
    await photos.send_photo(other_chat, str(path), 'caption')
    assert isinstance(other_chat.answer_photo.call_args.args[0], FSInputFile)


@pytest.mark.asyncio
async def test_invalid_cached_id_is_refreshed_but_other_errors_propagate(monkeypatch, tmp_path):
    from bot.utils import photos

    path = tmp_path / 'photo.jpeg'
    path.write_bytes(b'photo')
    monkeypatch.setattr(photos, '_load', AsyncMock(return_value='expired-id'))
    store = AsyncMock()
    monkeypatch.setattr(photos, '_store', store)
    method = SendPhoto(chat_id=1, photo='expired-id')
    msg = SimpleNamespace(bot=SimpleNamespace(id=10), answer_photo=AsyncMock(side_effect=[
        TelegramBadRequest(method=method, message='wrong file identifier'), photo_message('new-id'),
    ]))
    await photos.send_photo(msg, str(path), 'caption')
    assert isinstance(msg.answer_photo.call_args.args[0], FSInputFile)
    assert store.call_args.args[-1] == 'new-id'
    msg.answer_photo = AsyncMock(side_effect=TelegramBadRequest(method=method, message='caption is too long'))
    with pytest.raises(TelegramBadRequest):
        await photos.send_photo(msg, str(path), 'caption')
    assert msg.answer_photo.await_count == 1
