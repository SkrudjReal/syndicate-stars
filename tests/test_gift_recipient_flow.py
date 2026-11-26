from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from bot.utils.callback_factory.callback_factory import BuyStars, BuyPremium, PayMethod


@pytest_asyncio.fixture
async def flow(monkeypatch):
    from bot.handlers.users import buy_stars as module
    storage = MemoryStorage()
    state = FSMContext(storage, StorageKey(bot_id=1, chat_id=1, user_id=1))
    edit = AsyncMock()
    monkeypatch.setattr(module, 'get_editor', lambda q: edit)
    bot = NS(edit_message_caption=AsyncMock(), edit_message_text=AsyncMock())
    query = NS(message=NS(chat=NS(id=1), message_id=42, caption='photo'), answer=AsyncMock())
    def incoming(text):
        return NS(text=text, bot=bot, from_user=NS(username='payer_user'), answer=AsyncMock(), delete=AsyncMock())
    api = NS(search_recipient=Mock(return_value={'found': {'recipient': 'verified'}}))
    monkeypatch.setattr(module, 'fragment_api', api)
    yield state, query, incoming, bot, api, edit
    await storage.close()


@pytest.mark.parametrize('premium', [False, True])
async def test_product_selection_precedes_username_fsm(flow, premium):
    from bot.handlers.users import buy_stars as module
    state, query, _, _, _, edit = flow
    callback = BuyPremium(action='gift') if premium else BuyStars(action='gift')
    await module.gift_product_chosen(query, callback, state)
    assert await state.get_state() is None
    button = edit.call_args.kwargs['reply_markup'].inline_keyboard[0][0]
    selected = (BuyPremium if premium else BuyStars).unpack(button.callback_data)
    assert selected.action == ('gift_period' if premium else 'gift_amount')
    assert 'Укажите' not in edit.call_args.args[0]


async def test_self_username_rejected_case_insensitively_before_fragment(flow):
    from bot.handlers.users import buy_stars as module
    state, query, incoming, bot, api, _ = flow
    await module.gift_recipient_start(query, BuyStars(action='gift_amount', stars_count=100), state)
    msg = incoming('@PaYeR_UsEr')
    await module.gift_recipient_entered(msg, state)
    api.search_recipient.assert_not_called()
    msg.delete.assert_awaited_once()
    msg.answer.assert_not_awaited()
    assert 'Себя указывать нельзя' in bot.edit_message_caption.call_args.kwargs['caption']
    assert await state.get_state() == module.GiftRecipient.username.state


async def test_custom_gift_amount_and_username_both_edit_original_photo(flow):
    from bot.handlers.users import buy_stars as module
    state, query, incoming, bot, _, _ = flow
    await module.buy_stars_custom(query, state, BuyStars(action='gift_custom'))
    amount = incoming('777')
    await module.buy_stars_custom_entered(amount, state)
    assert await state.get_state() == module.GiftRecipient.username.state
    assert (await state.get_data())['gift_quantity'] == 777
    amount.delete.assert_awaited_once()
    assert '777' in bot.edit_message_caption.call_args.kwargs['caption']
    username = incoming('@friend_user')
    await module.gift_recipient_entered(username, state)
    args = bot.edit_message_caption.call_args.kwargs
    assert (args['chat_id'], args['message_id']) == (1, 42)
    selected = PayMethod.unpack(args['reply_markup'].inline_keyboard[0][0].callback_data)
    assert (selected.stars_count, selected.recipient) == (777, 'friend_user')
    username.delete.assert_awaited_once()
    username.answer.assert_not_awaited()
    assert await state.get_state() is None


async def test_unknown_recipient_stays_in_fsm_and_edits_error_in_place(flow):
    from bot.handlers.users import buy_stars as module
    state, query, incoming, bot, api, _ = flow
    await module.gift_recipient_start(query, BuyStars(action='gift_amount'), state)
    api.search_recipient.return_value = {'found': {}}
    msg = incoming('@missing_user')
    await module.gift_recipient_entered(msg, state)
    assert await state.get_state() == module.GiftRecipient.username.state
    assert bot.edit_message_caption.call_args.kwargs['message_id'] == 42
    msg.answer.assert_not_awaited()
    msg.delete.assert_not_awaited()


async def test_cancel_during_fragment_check_cannot_restore_old_payment_menu(flow, monkeypatch):
    from bot.handlers.users import buy_stars as module
    state, query, incoming, bot, _, _ = flow
    await module.gift_recipient_start(query, BuyStars(action='gift_amount'), state)
    async def cancelled_lookup(*args):
        await state.clear()
        return {'found': {'recipient': 'verified'}}
    monkeypatch.setattr(module.asyncio, 'to_thread', cancelled_lookup)
    msg = incoming('@friend_user')
    await module.gift_recipient_entered(msg, state)
    bot.edit_message_caption.assert_not_awaited()
    msg.delete.assert_not_awaited()


async def test_text_anchor_is_edited_without_sending_new_messages(flow):
    from bot.handlers.users import buy_stars as module
    state, query, incoming, bot, _, _ = flow
    query.message.caption = None
    await module.gift_recipient_start(query, BuyStars(action='gift_amount'), state)
    msg = incoming('@friend_user')
    await module.gift_recipient_entered(msg, state)
    bot.edit_message_caption.assert_not_awaited()
    assert bot.edit_message_text.call_args.kwargs['message_id'] == 42
    msg.answer.assert_not_awaited()
    msg.delete.assert_awaited_once()
