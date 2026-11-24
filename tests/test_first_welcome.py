from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


def test_welcome_fits_photo_caption():
    from html.parser import HTMLParser
    from bot.messages import FIRST_WELCOME_MESSAGE

    class VisibleText(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts = []

        def handle_data(self, text):
            self.parts.append(text)

    parser = VisibleText()
    parser.feed(FIRST_WELCOME_MESSAGE)
    assert len(''.join(parser.parts).encode('utf-16-le')) // 2 <= 1024


def make_repo(user):
    @asynccontextmanager
    async def transaction():
        yield
    return SimpleNamespace(session=SimpleNamespace(begin=transaction, scalar=AsyncMock(return_value=user)))


@pytest.mark.asyncio
async def test_delivery_does_not_confirm_welcome(monkeypatch):
    from bot.handlers.users.start_help import send_first_welcome
    from bot import messages
    from bot.utils.callback_factory.callback_factory import MainMenu

    photo = AsyncMock()
    monkeypatch.setattr('bot.handlers.users.start_help.send_photo', photo)
    user = SimpleNamespace(welcome_accepted=False)
    repo = make_repo(user)
    msg = SimpleNamespace(from_user=SimpleNamespace(id=1), answer=AsyncMock())
    assert await send_first_welcome(msg, repo) is True
    assert not user.welcome_accepted
    assert await send_first_welcome(msg, repo) is True
    msg.answer.assert_not_awaited()
    assert photo.await_count == 2
    args = photo.call_args
    assert args.kwargs['caption'] == messages.FIRST_WELCOME_MESSAGE
    assert args.kwargs['message_effect_id'] == '5159385139981059251'
    button = args.kwargs['reply_markup'].inline_keyboard[0][0]
    assert button.text == 'Продолжить?'
    assert MainMenu.unpack(button.callback_data).action == 'continue'
    assert args.args == (msg, messages.IMAGE_PATHS['welcome'])


@pytest.mark.asyncio
async def test_confirmed_user_does_not_receive_welcome(monkeypatch):
    from bot.handlers.users.start_help import send_first_welcome

    photo = AsyncMock()
    monkeypatch.setattr('bot.handlers.users.start_help.send_photo', photo)
    msg = SimpleNamespace(from_user=SimpleNamespace(id=1), answer=AsyncMock())
    assert await send_first_welcome(msg, make_repo(SimpleNamespace(welcome_accepted=True))) is False
    photo.assert_not_awaited()
    msg.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_waits_for_continue_before_showing_menu(monkeypatch):
    from aiogram.types import User
    from bot.handlers.users import start_help

    monkeypatch.setattr(start_help, 'send_first_welcome', AsyncMock(return_value=True))
    photo = AsyncMock()
    monkeypatch.setattr(start_help, 'send_photo', photo)
    msg = SimpleNamespace(text='/start', from_user=User(id=1, first_name='Test', is_bot=False))
    repo = SimpleNamespace(users=SimpleNamespace(get_or_create_user=AsyncMock()))
    await start_help.start(msg, repo, object(), SimpleNamespace(clear=AsyncMock()), SimpleNamespace(reset_stack=AsyncMock()))
    photo.assert_not_awaited()


@pytest.mark.asyncio
async def test_continue_confirms_clicking_user_then_opens_menu(monkeypatch):
    from bot.handlers.users import start_help
    from bot import messages

    photo = AsyncMock()
    monkeypatch.setattr(start_help, 'send_photo', photo)
    session = SimpleNamespace(execute=AsyncMock(), commit=AsyncMock())
    message = SimpleNamespace(edit_reply_markup=AsyncMock(), delete=AsyncMock())
    query = SimpleNamespace(from_user=SimpleNamespace(id=123), answer=AsyncMock(), message=message)
    await start_help.continue_welcome(query, SimpleNamespace(session=session), SimpleNamespace(clear=AsyncMock()), SimpleNamespace(reset_stack=AsyncMock()))
    statement = session.execute.call_args.args[0].compile()
    assert statement.params['welcome_accepted'] is True
    assert statement.params['id_1'] == 123
    session.commit.assert_awaited_once()
    message.edit_reply_markup.assert_awaited_once_with(reply_markup=None)
    message.delete.assert_not_awaited()
    assert photo.call_args.args == (message, messages.IMAGE_PATHS['main_menu'])
    assert photo.call_args.kwargs['caption'] == messages.WELCOME_MESSAGE
    query.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_failed_delivery_does_not_mark_welcome_as_accepted(monkeypatch):
    from bot.handlers.users.start_help import send_first_welcome
    monkeypatch.setattr('bot.handlers.users.start_help.send_photo', AsyncMock(side_effect=RuntimeError('network failed')))

    user = SimpleNamespace(welcome_accepted=False)
    msg = SimpleNamespace(from_user=SimpleNamespace(id=1), answer=AsyncMock(side_effect=RuntimeError('network failed')))
    with pytest.raises(RuntimeError):
        await send_first_welcome(msg, make_repo(user))
    assert not user.welcome_accepted
