from datetime import datetime, timezone
from types import SimpleNamespace as NS

import pytest
from aiogram import Bot, types
from aiogram.client.session.base import BaseSession
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.methods import SendMessage, SendPhoto, SendMediaGroup
from aiogram_broadcaster.mailer.status import MailerStatus

from bot import broadcasts


def post(message_id=1, *, photo=False, group=None):
    entities = [types.MessageEntity(type='custom_emoji', offset=0, length=2, custom_emoji_id='5208968969750330825')]
    return types.Message(
        message_id=message_id, date=datetime.now(timezone.utc), chat=types.Chat(id=11, type='private'),
        from_user=types.User(id=11, first_name='Admin', is_bot=False), media_group_id=group,
        text=None if photo else '⭐️ Тест', entities=None if photo else entities,
        photo=[types.PhotoSize(file_id=f'photo-{message_id}', file_unique_id=f'unique-{message_id}', width=100, height=100)] if photo else None,
        caption='⭐️ Тест' if photo else None, caption_entities=entities if photo else None,
    )


class FakeSession(BaseSession):
    def __init__(self):
        super().__init__()
        self.calls = []
        self.errors = {}

    async def close(self):
        pass

    async def stream_content(self, *args, **kwargs):
        yield b''

    async def make_request(self, bot, method, timeout=None):
        self.calls.append(method)
        errors = self.errors.get(method.chat_id, [])
        if errors:
            raise errors.pop(0)(method)
        if isinstance(method, SendMediaGroup):
            return [post(i + 100, photo=True).model_copy(update={'chat': types.Chat(id=method.chat_id, type='private')}) for i in range(len(method.media))]
        return post(len(self.calls) + 100).model_copy(update={'chat': types.Chat(id=method.chat_id, type='private')})


@pytest.mark.parametrize('photo', [False, True])
async def test_premium_entities_are_preserved_without_reparsing_and_media_uses_file_id(photo):
    content, _ = broadcasts.content_from_messages([post(photo=photo)])
    method = await content.as_method(chat_id=22)
    assert method.parse_mode is None
    entities = method.caption_entities if photo else method.entities
    assert entities[0].custom_emoji_id == '5208968969750330825'
    assert (entities[0].offset, entities[0].length) == (0, 2)
    if photo:
        assert method.photo == 'photo-1'


async def test_album_order_and_captions_are_retained():
    content, _ = broadcasts.content_from_messages([post(2, photo=True, group='album'), post(1, photo=True, group='album')])
    method = await content.as_method(chat_id=22)
    assert [m.media for m in method.media] == ['photo-1', 'photo-2']
    assert all(m.caption_entities[0].custom_emoji_id == '5208968969750330825' for m in method.media)
    assert method.allow_paid_broadcast is False


async def test_forwarded_callback_buttons_are_removed_but_url_icons_preserved():
    original = post().model_copy(update={'reply_markup': types.InlineKeyboardMarkup(inline_keyboard=[[
        types.InlineKeyboardButton(text='Secret action', callback_data='admin:send:1'),
        types.InlineKeyboardButton(text='Сайт', url='https://example.com', icon_custom_emoji_id='5208968969750330825'),
    ]])})
    content, _ = broadcasts.content_from_messages([original])
    method = await content.as_method(chat_id=22)
    assert len(method.reply_markup.inline_keyboard[0]) == 1
    assert method.reply_markup.inline_keyboard[0][0].icon_custom_emoji_id == '5208968969750330825'


@pytest.mark.parametrize('text', ['Button | javascript:alert(1)', 'Button | https://user:pass@example.com', 'missing separator'])
def test_url_button_validation_rejects_bad_links(text):
    with pytest.raises(ValueError): broadcasts.parse_buttons(text)


@pytest.mark.parametrize('admin,expected', [(11, True), (22, False)])
async def test_admin_filter_uses_callback_actor_not_message_author(monkeypatch, admin, expected):
    from bot.filters import IsAdmin
    from bot.settings import settings
    monkeypatch.setattr(settings, 'admins', [11])
    query = types.CallbackQuery(id='test', from_user=types.User(id=admin, is_bot=False, first_name='Actor'),
                                chat_instance='test', data='admin:panel', message=post())
    assert await IsAdmin()(query) is expected


def test_only_configured_admin_ids_see_panel(monkeypatch):
    from bot.keyboards.inline import start_keyboard
    from bot.settings import settings
    monkeypatch.setattr(settings, 'admins', [11, 33])
    def has_panel(user):
        return any(b.callback_data == 'admin:panel' for r in start_keyboard(user).inline_keyboard for b in r)
    assert has_panel(11) and has_panel(33)
    assert not has_panel(22) and not has_panel(None)


async def test_retry_after_counts_as_success_and_forbidden_does_not_loop():
    session = FakeSession()
    session.errors[22] = [lambda method: TelegramRetryAfter(method=method, message='Flood', retry_after=0)]
    session.errors[33] = [lambda method: TelegramForbiddenError(method=method, message='Blocked')]
    bot = Bot('123456789:TEST_TOKEN_FOR_TESTS_ONLY', session=session)
    manager = broadcasts.PersistentBroadcaster(bot)
    content, _ = broadcasts.content_from_messages([post(photo=True)])
    job = await manager.create_mailer(chats=[22, 33], content=content)
    await job.start()
    assert job.status is MailerStatus.COMPLETED
    assert job.chats.success.ids == {22}
    assert job.chats.failed.ids == {33}
    assert sum(m.chat_id == 22 for m in session.calls) == 2
    assert sum(m.chat_id == 33 for m in session.calls) == 1


async def test_ordinary_user_cannot_invoke_admin_callback(monkeypatch):
    from aiogram import Dispatcher
    from aiogram.dispatcher.event.bases import UNHANDLED
    from bot.handlers.admins import broadcast_panel
    from bot.settings import settings
    monkeypatch.setattr(settings, 'admins', [11])
    query = types.CallbackQuery(id='test', from_user=types.User(id=22, is_bot=False, first_name='User'),
                                chat_instance='test', data='admin:panel', message=post())
    # Filters reject the forged callback before any handler, database or API call.
    bot = Bot('123456789:TEST_TOKEN_FOR_TESTS_ONLY', session=FakeSession())
    result = await broadcast_panel.router.propagate_event('callback_query', query, bot=bot)
    assert result is UNHANDLED
    assert bot.session.calls == []
