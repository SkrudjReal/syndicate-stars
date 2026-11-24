from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.utils.callback_factory.callback_factory import (
    MainMenu, AccountBalance, Support, Partners,
    BuyStars, BuyPremium, PayMethod, RubPayMethod,
    PremiumPayMethod, PremiumRubPayMethod, Calculator,
)
from bot import messages

_BACK_ID = messages.ICON_EMOJI_IDS['back_arrow']
_ICON_IDS = messages.ICON_EMOJI_IDS


def welcome_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text='Продолжить?', callback_data=MainMenu(action='continue'))
    return kb.as_markup()


def start_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text='Купить Звёзды', callback_data=BuyStars(action='menu'), icon_custom_emoji_id=_ICON_IDS['white_star'], style='primary')
    kb.button(text='Рефералы', callback_data=Partners(action='menu'), icon_custom_emoji_id=_ICON_IDS['partners'])
    kb.button(text='Поддержка', callback_data=Support(action='support'), icon_custom_emoji_id=_ICON_IDS['support'])
    kb.adjust(1, 2)
    return kb.as_markup()


def main_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text='Вернуться', callback_data=MainMenu(), icon_custom_emoji_id=_BACK_ID, style='danger')
    return kb.as_markup()


def support_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text='@maneramur', url='https://t.me/maneramur', icon_custom_emoji_id=_ICON_IDS['support'])
    kb.button(text='Вернуться', callback_data=MainMenu(), icon_custom_emoji_id=_BACK_ID, style='danger')
    kb.adjust(1)
    return kb.as_markup()


def buy_stars_section_keyboard():
    kb = InlineKeyboardBuilder()

    kb.button(text='Купить звёзды', callback_data=BuyStars(action='buy'), icon_custom_emoji_id=_ICON_IDS['white_star'], style='primary')
    kb.button(text='Купить Premium', callback_data=BuyPremium(action='menu'), icon_custom_emoji_id='6037175527846975726', style='primary')
    kb.button(text='Подарить звёзды', callback_data=BuyStars(action='gift'), icon_custom_emoji_id=_ICON_IDS['white_star'])
    kb.button(text='Подарить Premium', callback_data=BuyPremium(action='gift'), icon_custom_emoji_id='6037175527846975726')
    kb.button(text='Калькулятор', callback_data=Calculator(action='menu'), icon_custom_emoji_id=_ICON_IDS['calc'])
    kb.button(text='Вернуться', callback_data=MainMenu(), icon_custom_emoji_id=_BACK_ID, style='danger')

    kb.adjust(2, 2, 1, 1)
    return kb.as_markup()


def withdraw_keyboard():
    kb = InlineKeyboardBuilder()

    kb.button(text='Вывести себе', callback_data=AccountBalance(action='withdraw'), icon_custom_emoji_id=_ICON_IDS['withdraw_stars'])
    kb.button(text='Вывести другу', callback_data=AccountBalance(action='withdraw_friend'), icon_custom_emoji_id=_ICON_IDS['withdraw_stars'])
    kb.button(text='Вернуться', callback_data=Partners(), icon_custom_emoji_id=_BACK_ID, style='danger')

    kb.adjust(1)
    return kb.as_markup()


def stars_sell_count_keyboard(recipient: str = ''):
    kb = InlineKeyboardBuilder()

    kb.button(text='50', callback_data=BuyStars(stars_count=50, recipient=recipient), icon_custom_emoji_id=_ICON_IDS['white_star'], style='primary')
    kb.button(text='100', callback_data=BuyStars(stars_count=100, recipient=recipient), icon_custom_emoji_id=_ICON_IDS['white_star'])
    kb.button(text='500', callback_data=BuyStars(stars_count=500, recipient=recipient), icon_custom_emoji_id=_ICON_IDS['white_star'])
    kb.button(text='1000', callback_data=BuyStars(stars_count=1000, recipient=recipient), icon_custom_emoji_id=_ICON_IDS['white_star'])
    kb.button(text='Ввести количество', callback_data=BuyStars(action='custom', recipient=recipient))
    kb.button(text='Вернуться', callback_data=MainMenu(), icon_custom_emoji_id=_BACK_ID, style='danger')

    kb.adjust(4, 1, 1)
    return kb.as_markup()


def payment_method_keyboard(stars_count: int, recipient: str = ''):
    kb = InlineKeyboardBuilder()

    kb.button(text='CryptoBot • 2%', callback_data=PayMethod(method='pay_cryptobot', stars_count=stars_count, recipient=recipient), icon_custom_emoji_id=_ICON_IDS['cryptobot'], style='primary')
    kb.button(text='🇷🇺 СБП / Рубли', callback_data=RubPayMethod(method='frekassa_sbp', stars_count=stars_count, recipient=recipient), style='primary')
    kb.button(text='💲 USD/EUR (в разработке)', callback_data=PayMethod(method='pay_usd', stars_count=stars_count, recipient=recipient))
    kb.button(text='Вернуться', callback_data=MainMenu(), icon_custom_emoji_id=_BACK_ID, style='danger')

    kb.adjust(1)
    return kb.as_markup()


def premium_months_keyboard(recipient: str = ''):
    kb = InlineKeyboardBuilder()

    kb.button(text='3 месяца', callback_data=BuyPremium(months=3, recipient=recipient), style='primary')
    kb.button(text='6 месяцев', callback_data=BuyPremium(months=6, recipient=recipient))
    kb.button(text='12 месяцев', callback_data=BuyPremium(months=12, recipient=recipient))
    kb.button(text='Вернуться', callback_data=BuyStars(action='menu', recipient=recipient), icon_custom_emoji_id=_BACK_ID, style='danger')

    kb.adjust(1)
    return kb.as_markup()


def premium_payment_method_keyboard(months: int, recipient: str = ''):
    kb = InlineKeyboardBuilder()

    kb.button(text='CryptoBot • 2%', callback_data=PremiumPayMethod(method='pay_cryptobot', months=months, recipient=recipient), icon_custom_emoji_id=_ICON_IDS['cryptobot'], style='primary')
    kb.button(text='🇷🇺 СБП / Рубли', callback_data=PremiumRubPayMethod(method='frekassa_sbp', months=months, recipient=recipient), style='primary')
    kb.button(text='💲 USD/EUR (в разработке)', callback_data=PremiumPayMethod(method='pay_usd', months=months, recipient=recipient))
    kb.button(text='Вернуться', callback_data=BuyPremium(action='menu', recipient=recipient), icon_custom_emoji_id=_BACK_ID, style='danger')

    kb.adjust(1)
    return kb.as_markup()


def premium_rub_payment_keyboard(months: int, recipient: str = ''):
    kb = InlineKeyboardBuilder()

    kb.button(text='🇷🇺 СБП • 3%', callback_data=PremiumRubPayMethod(method='frekassa_sbp', months=months, recipient=recipient), style='primary')
    kb.button(text='💳 Банковская карта • 3%', callback_data=PremiumRubPayMethod(method='frekassa_card', months=months, recipient=recipient))
    kb.button(text='Вернуться', callback_data=BuyPremium(months=months, recipient=recipient), icon_custom_emoji_id=_BACK_ID, style='danger')

    kb.adjust(1)
    return kb.as_markup()


def premium_payment_redirect_keyboard(months: int, pay_url: str, recipient: str = ''):
    kb = InlineKeyboardBuilder()

    kb.button(text=f'Оплатить Premium {months} мес.', url=pay_url)
    kb.button(text='Отменить', callback_data=BuyPremium(action='menu', recipient=recipient), icon_custom_emoji_id=_BACK_ID, style='danger')

    kb.adjust(1)
    return kb.as_markup()


def rub_payment_keyboard(stars_count: int, recipient: str = ''):
    kb = InlineKeyboardBuilder()

    kb.button(text='🇷🇺 СБП • 3%', callback_data=RubPayMethod(method='frekassa_sbp', stars_count=stars_count, recipient=recipient), style='primary')
    kb.button(text='💳 Банковская карта • 3%', callback_data=RubPayMethod(method='frekassa_card', stars_count=stars_count, recipient=recipient))
    # kb.button(text='UnitPay СБП • 0.7%', callback_data=RubPayMethod(method='unitpay', stars_count=stars_count, recipient=recipient))
    kb.button(text='Вернуться', callback_data=BuyStars(stars_count=stars_count, recipient=recipient), icon_custom_emoji_id=_BACK_ID, style='danger')

    kb.adjust(1)
    return kb.as_markup()


def payment_redirect_keyboard(stars_count: int, pay_url: str, recipient: str = ''):
    kb = InlineKeyboardBuilder()

    kb.button(text=f'Оплатить {stars_count}', url=pay_url, icon_custom_emoji_id=_ICON_IDS['white_star'])
    kb.button(text='Вернуться', callback_data=BuyStars(stars_count=stars_count, recipient=recipient), icon_custom_emoji_id=_BACK_ID, style='danger')

    kb.adjust(1)
    return kb.as_markup()


def calculator_menu_keyboard(back: bool = False):
    kb = InlineKeyboardBuilder()

    if back:
        kb.button(text='Вернуться', callback_data=Calculator(action='menu'), icon_custom_emoji_id=_BACK_ID, style='danger')
    else:
        kb.button(text='💳 Сумма в долларах', callback_data=Calculator(action='usd_to_stars'))
        kb.button(text='Сумма в звёздах', callback_data=Calculator(action='stars_to_usd'), icon_custom_emoji_id=_ICON_IDS['white_star'])
        kb.button(text='Вернуться', callback_data=MainMenu(), icon_custom_emoji_id=_BACK_ID, style='danger')

    kb.adjust(2, 1)
    return kb.as_markup()


def gift_cancel_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text='Отменить', callback_data=BuyStars(action='menu'), icon_custom_emoji_id=_BACK_ID)
    return kb.as_markup()


def referrals_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text='Вывести звёзды', callback_data=AccountBalance(action='menu'), icon_custom_emoji_id=_ICON_IDS['withdraw_stars'])
    kb.button(text='Вернуться', callback_data=MainMenu(), icon_custom_emoji_id=_BACK_ID, style='danger')
    kb.adjust(1)
    return kb.as_markup()
