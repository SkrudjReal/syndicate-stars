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


def start_keyboard(user_id: int | None = None):
    kb = InlineKeyboardBuilder()
    kb.button(text='Купить Звёзды', callback_data=BuyStars(action='menu'), icon_custom_emoji_id=_ICON_IDS['white_star'], style='primary')
    kb.button(text='Купить Звёзды другу', callback_data=BuyStars(action='gift_menu'), icon_custom_emoji_id=_ICON_IDS['white_star'])
    kb.button(text='Рефералы', callback_data=Partners(action='menu'), icon_custom_emoji_id=_ICON_IDS['partners'])
    kb.button(text='Поддержка', callback_data=Support(action='support'), icon_custom_emoji_id=_ICON_IDS['support'])
    from bot.settings import settings
    if user_id in settings.admins:
        kb.button(text='Админ-панель', callback_data='admin:panel', icon_custom_emoji_id='5276398496008663230')
    kb.adjust(1, 1, 2)
    return kb.as_markup()


def main_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text='Вернуться', callback_data=MainMenu(), icon_custom_emoji_id=_BACK_ID, style='danger')
    return kb.as_markup()


def support_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text='@maneramur', url='https://t.me/maneramur', icon_custom_emoji_id=_ICON_IDS['support'])
    kb.button(text='@velunae', url='https://t.me/velunae', icon_custom_emoji_id=_ICON_IDS['support'])
    kb.button(text='Вернуться', callback_data=MainMenu(), icon_custom_emoji_id=_BACK_ID, style='danger')
    kb.adjust(1)
    return kb.as_markup()


def buy_stars_section_keyboard(gift: bool = False):
    kb = InlineKeyboardBuilder()

    kb.button(text='Купить звёзды', callback_data=BuyStars(action='gift' if gift else 'buy'), icon_custom_emoji_id=_ICON_IDS['white_star'], style='primary')
    kb.button(text='Купить Premium', callback_data=BuyPremium(action='gift' if gift else 'menu'), icon_custom_emoji_id='6037175527846975726', style='primary')
    kb.button(text='Калькулятор', callback_data=Calculator(action='gift_menu' if gift else 'menu'), icon_custom_emoji_id=_ICON_IDS['calc'])
    kb.button(text='Вернуться', callback_data=MainMenu(), icon_custom_emoji_id=_BACK_ID, style='danger')

    kb.adjust(2, 1, 1)
    return kb.as_markup()


def gift_section_keyboard():
    return buy_stars_section_keyboard(gift=True)


def withdraw_keyboard():
    kb = InlineKeyboardBuilder()

    kb.button(text='Вывести себе', callback_data=AccountBalance(action='withdraw'), icon_custom_emoji_id=_ICON_IDS['withdraw_stars'])
    kb.button(text='Вывести другу', callback_data=AccountBalance(action='withdraw_friend'), icon_custom_emoji_id=_ICON_IDS['withdraw_stars'])
    kb.button(text='Вернуться', callback_data=Partners(), icon_custom_emoji_id=_BACK_ID, style='danger')

    kb.adjust(1)
    return kb.as_markup()


def stars_sell_count_keyboard(recipient: str = '', *, gift: bool = False):
    kb = InlineKeyboardBuilder()
    action = 'gift_amount' if gift and not recipient else ''

    kb.button(text='50', callback_data=BuyStars(action=action, stars_count=50, recipient=recipient), icon_custom_emoji_id=_ICON_IDS['white_star'], style='primary')
    kb.button(text='100', callback_data=BuyStars(action=action, stars_count=100, recipient=recipient), icon_custom_emoji_id=_ICON_IDS['white_star'])
    kb.button(text='500', callback_data=BuyStars(action=action, stars_count=500, recipient=recipient), icon_custom_emoji_id=_ICON_IDS['white_star'])
    kb.button(text='1000', callback_data=BuyStars(action=action, stars_count=1000, recipient=recipient), icon_custom_emoji_id=_ICON_IDS['white_star'])
    kb.button(text='Ввести количество', callback_data=BuyStars(action='gift_custom' if gift else 'custom', recipient=recipient))
    kb.button(text='Вернуться', callback_data=BuyStars(action='gift_menu') if gift or recipient else MainMenu(), icon_custom_emoji_id=_BACK_ID, style='danger')

    kb.adjust(4, 1, 1)
    return kb.as_markup()


def _payment_keyboard(quantity: int, recipient: str, premium: bool, category: str):
    kb = InlineKeyboardBuilder()
    data = {'months': quantity} if premium else {'stars_count': quantity}
    pay_type = PremiumPayMethod if premium else PayMethod
    rub_type = PremiumRubPayMethod if premium else RubPayMethod
    groups = {
        'rub': [
            ('СБП • 3%', 'frekassa_sbp', 'sbp', 'primary'),
            ('Банковская карта • 3%', 'frekassa_card', 'payment_wallet', None),
            ('CodeePay · СБП', 'pay_codeesbp', 'payment_wallet', None),
            ('CodeePay · Карта', 'pay_codeecard', 'payment_wallet', None),
            ('СБП · Platega', 'pay_plategasbp', 'payment_wallet', None),
        ],
        'crypto': [
            ('CryptoBot • 2%', 'pay_cryptobot', 'cryptobot', 'primary'),
            ('TON', 'pay_ton', 'ton', None),
            ('USDT (TON)', 'pay_usdt_ton', 'usdt_ton', None),
            ('xRocket', 'pay_xrocket', 'xrocket', None),
            ('Криптовалюта · Platega', 'pay_plategacrypto', 'payment_wallet', None),
        ],
        'other': [
            ('LolzTeam', 'pay_lolzteam', 'lolzteam', None),
            ('Ириски', 'pay_iris', 'iris', None),
            ('Гривны', 'pay_uah', 'payment_wallet', None),
            ('USD/EUR (в разработке)', 'pay_usd', 'payment_wallet', None),
        ],
    }
    if category:
        for label, method, icon, style in groups[category]:
            factory = rub_type if method.startswith('frekassa_') else pay_type
            kb.button(text=label, callback_data=factory(method=method, recipient=recipient, **data),
                      icon_custom_emoji_id=_ICON_IDS[icon], style=style)
        back = pay_type(method='category_menu', recipient=recipient, **data)
        kb.button(text='К категориям', callback_data=back, icon_custom_emoji_id=_BACK_ID, style='danger')
        kb.adjust(1, 2, 2, 1)
    else:
        for label, group, icon in [('Рубли / СБП / Карты', 'rub', 'sbp'), ('Криптовалюта', 'crypto', 'ton'), ('Другие способы', 'other', 'payment_wallet')]:
            kb.button(text=label, callback_data=pay_type(method=f'category_{group}', recipient=recipient, **data),
                      icon_custom_emoji_id=_ICON_IDS[icon], style='primary' if group != 'other' else None)
        back = BuyPremium(action='menu', recipient=recipient) if premium else BuyStars(action='buy', recipient=recipient)
        kb.button(text='Вернуться', callback_data=back, icon_custom_emoji_id=_BACK_ID, style='danger')
        kb.adjust(1)
    return kb.as_markup()


def payment_method_keyboard(stars_count: int, recipient: str = '', category: str = ''):
    return _payment_keyboard(stars_count, recipient, False, category)


def premium_months_keyboard(recipient: str = '', *, gift: bool = False):
    kb = InlineKeyboardBuilder()
    action = 'gift_period' if gift and not recipient else ''

    kb.button(text='3 месяца', callback_data=BuyPremium(action=action, months=3, recipient=recipient), style='primary')
    kb.button(text='6 месяцев', callback_data=BuyPremium(action=action, months=6, recipient=recipient))
    kb.button(text='12 месяцев', callback_data=BuyPremium(action=action, months=12, recipient=recipient))
    kb.button(text='Вернуться', callback_data=BuyStars(action='gift_menu' if gift or recipient else 'menu'), icon_custom_emoji_id=_BACK_ID, style='danger')

    kb.adjust(1)
    return kb.as_markup()


def premium_payment_method_keyboard(months: int, recipient: str = '', category: str = ''):
    return _payment_keyboard(months, recipient, True, category)


def premium_rub_payment_keyboard(months: int, recipient: str = ''):
    kb = InlineKeyboardBuilder()

    kb.button(text='🇷🇺 СБП • 3%', callback_data=PremiumRubPayMethod(method='frekassa_sbp', months=months, recipient=recipient), style='primary')
    kb.button(text='💳 Банковская карта • 3%', callback_data=PremiumRubPayMethod(method='frekassa_card', months=months, recipient=recipient))
    kb.button(text='Вернуться', callback_data=BuyPremium(months=months, recipient=recipient), icon_custom_emoji_id=_BACK_ID, style='danger')

    kb.adjust(1)
    return kb.as_markup()


def wallet_payment_keyboard(invoice, recipient: str = ''):
    from bot.wallet_payments import transfer_url
    kb = InlineKeyboardBuilder()
    kb.button(text='Оплатить', url=transfer_url(invoice), icon_custom_emoji_id=_ICON_IDS['pay'])
    back = (PayMethod(method='category_crypto', stars_count=invoice.quantity, recipient=recipient) if invoice.product == 'stars'
            else PremiumPayMethod(method='category_crypto', months=invoice.quantity, recipient=recipient))
    kb.button(text='Вернуться', callback_data=back, icon_custom_emoji_id=_BACK_ID, style='danger')
    kb.adjust(1)
    return kb.as_markup()


def premium_payment_redirect_keyboard(months: int, pay_url: str, recipient: str = '', *, category: str = 'crypto'):
    kb = InlineKeyboardBuilder()

    kb.button(text=f'Оплатить Premium {months} мес.', url=pay_url)
    kb.button(text='Вернуться', callback_data=PremiumPayMethod(method=f'category_{category}', months=months, recipient=recipient), icon_custom_emoji_id=_BACK_ID, style='danger')

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


def payment_redirect_keyboard(stars_count: int, pay_url: str, recipient: str = '', *, category: str = 'crypto'):
    kb = InlineKeyboardBuilder()

    kb.button(text=f'Оплатить {stars_count}', url=pay_url, icon_custom_emoji_id=_ICON_IDS['white_star'])
    kb.button(text='Вернуться', callback_data=PayMethod(method=f'category_{category}', stars_count=stars_count, recipient=recipient), icon_custom_emoji_id=_BACK_ID, style='danger')

    kb.adjust(1)
    return kb.as_markup()


def calculator_menu_keyboard(back: bool = False, *, gift: bool = False):
    kb = InlineKeyboardBuilder()
    prefix = 'gift_' if gift else ''

    if back:
        kb.button(text='Вернуться', callback_data=Calculator(action=prefix + 'menu'), icon_custom_emoji_id=_BACK_ID, style='danger')
    else:
        kb.button(text='💳 Сумма в долларах', callback_data=Calculator(action=prefix + 'usd_to_stars'))
        kb.button(text='Сумма в звёздах', callback_data=Calculator(action=prefix + 'stars_to_usd'), icon_custom_emoji_id=_ICON_IDS['white_star'])
        kb.button(text='Вернуться', callback_data=BuyStars(action='gift_menu') if gift else MainMenu(), icon_custom_emoji_id=_BACK_ID, style='danger')

    kb.adjust(2, 1)
    return kb.as_markup()


def gift_cancel_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text='Отменить', callback_data=BuyStars(action='gift_menu'), icon_custom_emoji_id=_BACK_ID)
    return kb.as_markup()


def referrals_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text='Вывести звёзды', callback_data=AccountBalance(action='menu'), icon_custom_emoji_id=_ICON_IDS['withdraw_stars'])
    kb.button(text='Вернуться', callback_data=MainMenu(), icon_custom_emoji_id=_BACK_ID, style='danger')
    kb.adjust(1)
    return kb.as_markup()
