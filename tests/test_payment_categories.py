from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.keyboards.inline import payment_method_keyboard, premium_payment_method_keyboard
from bot.utils.callback_factory.callback_factory import PayMethod, PremiumPayMethod, BuyStars


@pytest.mark.parametrize('premium', [False, True])
def test_root_has_three_categories_and_preserves_gift(premium):
    keyboard = premium_payment_method_keyboard if premium else payment_method_keyboard
    factory = PremiumPayMethod if premium else PayMethod
    quantity = 6 if premium else 123
    buttons = [b for row in keyboard(quantity, 'friend_user').inline_keyboard for b in row]
    assert [b.text for b in buttons] == ['Рубли / СБП / Карты', 'Криптовалюта', 'Другие способы', 'Вернуться']
    for button in buttons[:3]:
        data = factory.unpack(button.callback_data)
        assert data.recipient == 'friend_user'
        assert (data.months if premium else data.stars_count) == quantity


@pytest.mark.parametrize('premium', [False, True])
async def test_category_navigation_edits_same_message_and_preserves_order(monkeypatch, premium):
    from bot.handlers.users import buy_stars
    factory = PremiumPayMethod if premium else PayMethod
    data = {'months': 6} if premium else {'stars_count': 123}
    edit = AsyncMock()
    monkeypatch.setattr(buy_stars, 'get_editor', lambda q: edit)
    query = SimpleNamespace(from_user=SimpleNamespace(username='payer_user'), answer=AsyncMock())
    await buy_stars.payment_category(query, factory(method='category_crypto', recipient='friend_user', **data))
    assert 'friend_user' in edit.call_args.args[0]
    assert ('6' if premium else '123') in edit.call_args.args[0]
    buttons = [b for row in edit.call_args.kwargs['reply_markup'].inline_keyboard for b in row]
    assert any(b.text == 'TON' for b in buttons)
    back = factory.unpack(buttons[-1].callback_data)
    assert back.method == 'category_menu'
    assert back.recipient == 'friend_user'
    await buy_stars.payment_category(query, back)
    assert edit.call_args.kwargs['reply_markup'].inline_keyboard[0][0].text == 'Рубли / СБП / Карты'


@pytest.mark.parametrize('premium', [False, True])
def test_new_methods_are_present_and_explicitly_gated(premium):
    from bot.handlers.users.buy_stars import UNCONFIGURED_PAYMENTS
    keyboard = premium_payment_method_keyboard if premium else payment_method_keyboard
    factory = PremiumPayMethod if premium else PayMethod
    wanted = {'CodeePay · СБП', 'CodeePay · Карта', 'СБП · Platega', 'Криптовалюта · Platega', 'Ириски', 'Гривны'}
    found = set()
    for category in ('rub', 'crypto', 'other'):
        for row in keyboard(6 if premium else 123, 'a' * 32, category).inline_keyboard:
            for button in row:
                assert len(button.callback_data.encode()) <= 64
                if button.text in wanted:
                    assert factory.unpack(button.callback_data).method in UNCONFIGURED_PAYMENTS
                    assert button.icon_custom_emoji_id
                    found.add(button.text)
    assert found == wanted


async def test_back_to_star_quantity_does_not_drop_gift_recipient(monkeypatch):
    from bot.handlers.users import buy_stars
    edit = AsyncMock()
    monkeypatch.setattr(buy_stars, 'get_editor', lambda q: edit)
    query = SimpleNamespace(answer=AsyncMock())
    await buy_stars.buy_stars_show_amounts(query, BuyStars(action='buy', recipient='friend_user'))
    keyboard = edit.call_args.kwargs['reply_markup']
    assert BuyStars.unpack(keyboard.inline_keyboard[0][0].callback_data).recipient == 'friend_user'


async def test_gift_calculator_retains_return_to_gift_section(monkeypatch):
    from bot.handlers.users import buy_stars
    from bot.keyboards.inline import calculator_menu_keyboard
    from bot.utils.callback_factory.callback_factory import Calculator
    edit = AsyncMock()
    monkeypatch.setattr(buy_stars, 'get_editor', lambda q: edit)
    query = SimpleNamespace(answer=AsyncMock())
    await buy_stars.calc_menu(query, Calculator(action='gift_menu'))
    keyboard = edit.call_args.kwargs['reply_markup']
    assert Calculator.unpack(keyboard.inline_keyboard[0][0].callback_data).action == 'gift_usd_to_stars'
    assert BuyStars.unpack(keyboard.inline_keyboard[-1][0].callback_data).action == 'gift_menu'
    result_back = calculator_menu_keyboard(back=True, gift=True).inline_keyboard[0][0]
    assert Calculator.unpack(result_back.callback_data).action == 'gift_menu'
