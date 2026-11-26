import asyncio
import contextlib
import logging
import re
from uuid import uuid4

from aiogram import Router, types, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from bot.database.engine import Repositories
from bot.utils.callback_factory.callback_factory import (
    BuyStars, BuyPremium, PayMethod, RubPayMethod,
    PremiumPayMethod, PremiumRubPayMethod,
    Calculator, AccountBalance,
)
from bot.keyboards.inline import (
    buy_stars_section_keyboard, gift_section_keyboard, stars_sell_count_keyboard,
    payment_method_keyboard, rub_payment_keyboard, payment_redirect_keyboard,
    premium_months_keyboard, premium_payment_method_keyboard,
    premium_rub_payment_keyboard, premium_payment_redirect_keyboard,
    calculator_menu_keyboard, withdraw_keyboard, gift_cancel_keyboard, referrals_keyboard,
)
from bot.utils.misc import get_editor, send_section
from bot.cryptopay import crypto, fragment_api, ton_wallet, FragmentAPI
from bot import funcs, messages, referrals, withdrawals

router = Router(name=__name__)
logger = logging.getLogger(__name__)

_P = messages.PREMIUM_EMOJI_DICT

# ── Messages ──

STARS_SECTION_MENU = (
    f'{_P["white_star"]} <b>Покупка звёзд и Telegram Premium</b>\n\n'
    f'Внутренний баланс в боте: <b>{{stars}}</b> {_P["white_star"]}\n\n'
    '<blockquote>'
    f'{_P["white_star"]} <b>Telegram Stars</b> — после оплаты отправляются напрямую выбранному получателю. '
    'Если отправка не удастся, звёзды зачислятся на резервный баланс в боте.\n'
    '🎁 <b>Telegram Premium</b> — оформляется подарком на выбранный срок через Fragment.'
    '</blockquote>\n\n'
    'Выберите действие:'
)

BUY_STARS_MENU = (
    f'{_P["white_star"]} <b>Купить звёзды</b>\n\n'
    '<blockquote>Выберите количество звёзд для покупки.\n'
    'Нажмите «Ввести количество», чтобы указать нужное число (от 50).</blockquote>'
)

BUY_STARS_CUSTOM = (
    f'{_P["white_star"]} <b>Введите количество звёзд</b>\n'
    'Минимум — <b>50</b>\n'
    'После ввода вы сможете выбрать способ оплаты.'
)

BUY_STARS_AMOUNT_CHOSEN = (
    f'{_P["white_star"]} <b>Вы выбрали {{stars}}</b> звёзд\n\n'
    'Выберите категорию оплаты:'
)

BUY_STARS_LIMIT = '❌ Минимум — <b>50</b> звёзд. Введите корректное значение.'

BUY_PREMIUM_MENU = (
    '🎁 <b>Купить Telegram Premium</b>\n\n'
    '<blockquote>Выберите срок подписки.\n'
    'После оплаты подарок отправится выбранному получателю через Fragment '
    '(у аккаунта должен быть установлен @username).</blockquote>'
)

BUY_PREMIUM_CHOSEN = (
    '🎁 <b>Telegram Premium на {months}</b>\n\n'
    'Выберите категорию оплаты:'
)

REDIRECT_TO_PAYMENT = (
    'Оплата через <b>{pay_service}</b>\n\n'
    '⏳ Время на оплату: <b>5 минут</b>\n\n'
    'Перейдите по кнопке ниже и оплатите счёт.\n'
    'После оплаты бот автоматически отправит звёзды выбранному получателю '
    '(если отправка не удастся, они зачислятся на резервный баланс в боте).\n\n'
    f'<blockquote>{_P["question"]} Выберите валюту оплаты в счёте, подтвердите перевод и дождитесь подтверждения.</blockquote>\n\n'
    f'Ваш заказ: {{stars}} {_P["white_star"]}'
)

WITHDRAW_STARS = (
    f'💸 <b>Введите количество звёзд для вывода</b>\n'
    'Например: <code>100</code>\n'
    'Минимум — <b>50</b>'
)

WITHDRAW_STARS_FOR_FRIEND = (
    f'🎁 <b>Вывод звёзд для друга</b>\n'
    'Укажите <b>@username</b> получателя:'
)

WITHDRAW_INSUFFICIENT = '❌ <b>На балансе недостаточно звёзд.</b>'

WITHDRAW_SUCCESS = (
    f'{_P["confirm"]} <b>Готово!</b> Вывод выполнен.\n\n'
    f'{_P["white_star"]} <b>{{stars}}</b> звёзд отправлены!'
)

CALCULATOR_MENU = (
    '<b>🔢 Калькулятор</b>\n\n'
    '<blockquote>Выберите, что хотите рассчитать:\n'
    '💳 Сумма в долларах — узнать количество звёзд\n'
    f'{_P["white_star"]} Сумма в звёздах — узнать стоимость</blockquote>'
)

CALCULATOR_INPUT_USD = (
    '<b>🔢 Калькулятор</b>\n\n'
    '✍️ Введите сумму в долларах\n'
    '📒 Например: 100'
)

CALCULATOR_INPUT_STARS = (
    '<b>🔢 Калькулятор</b>\n\n'
    '✍️ Введите количество звёзд\n'
    '📒 Например: 1000'
)

CALCULATOR_RESULT = (
    '<b>🔢 Калькулятор</b>\n\n'
    '<blockquote>{input_val} ≈ {output_val}</blockquote>\n'
    '<blockquote><b>Текущий курс звезды:</b>\n'
    f'1 {_P["white_star"]} = {{course_rub}}₽\n'
    f'1 {_P["white_star"]} ≈ {{course_usd}} USDT\n'
    f'1 {_P["white_star"]} ≈ {{course_ton}} TON</blockquote>'
)

PREMIUM_MONTH_LABELS = {
    3: '3 месяца',
    6: '6 месяцев',
    12: '12 месяцев',
}


class GiftRecipient(StatesGroup):
    username = State()


class CustomStarsAmount(StatesGroup):
    amount = State()


class CalculatorInput(StatesGroup):
    amount = State()


class StarsWithdraw(StatesGroup):
    amount = State()


class FriendUser(StatesGroup):
    username = State()


def _premium_months_label(months: int) -> str:
    return PREMIUM_MONTH_LABELS.get(months, f'{months} мес.')


def _get_premium_quote(username: str, months: int) -> dict:
    if not fragment_api or not ton_wallet:
        return {'ok': False, 'error': 'Fragment Premium временно недоступен.'}

    quote = fragment_api.create_premium_gift_invoice(months, username)
    if not quote.get('ok') and 'transaction' not in quote:
        return quote

    invoice = FragmentAPI.parse_invoice(quote)
    if not invoice:
        return {'ok': False, 'error': 'Не удалось получить ссылку на подарок Telegram Premium в Fragment.'}

    ton_amount = invoice['ton_amount']

    ton_price = funcs.get_ton_price()
    if not ton_price:
        return {'ok': False, 'error': 'Не удалось получить текущий курс TON.'}

    usd_amount = ton_amount * ton_price
    rub_amount = funcs.usd_to_rub(usd_amount)
    if not rub_amount:
        return {'ok': False, 'error': 'Не удалось получить курс RUB.'}

    return {
        'ok': True,
        'quote': quote,
        'ton_amount': ton_amount,
        'usd_amount': usd_amount,
        'rub_amount': rub_amount,
    }


# ── Section Menu (balance + buy + withdraw + calc) ──

@router.callback_query(BuyStars.filter(F.action == 'menu'))
async def stars_section_menu(query: types.CallbackQuery, repo: Repositories, state: FSMContext) -> None:
    await state.clear()
    stars = await repo.users.get_stars_balance(query.from_user.id) or 0
    await send_section(
        query, 'buy_stars',
        STARS_SECTION_MENU.format(stars=stars),
        reply_markup=buy_stars_section_keyboard(),
    )
    await query.answer()


@router.callback_query(BuyStars.filter(F.action == 'gift_menu'))
async def gift_section_menu(query: types.CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await send_section(
        query, 'buy_stars',
        '🎁 <b>Купить другу</b>\n\n'
        'Подарите Telegram Stars или Telegram Premium другу.\n'
        'Выберите подарок и количество звёзд или срок Premium, затем укажите <b>@username</b> получателя.\n'
        'Подарки по числовому ID недоступны.',
        reply_markup=gift_section_keyboard(),
    )
    await query.answer()


@router.callback_query(BuyStars.filter(F.action == 'gift'))
@router.callback_query(BuyPremium.filter(F.action == 'gift'))
async def gift_product_chosen(query: types.CallbackQuery, callback_data: BuyStars | BuyPremium, state: FSMContext) -> None:
    await state.clear()
    premium = isinstance(callback_data, BuyPremium)
    await get_editor(query)(
        BUY_PREMIUM_MENU if premium else BUY_STARS_MENU,
        reply_markup=premium_months_keyboard(gift=True) if premium else stars_sell_count_keyboard(gift=True),
    )
    await query.answer()


def _gift_prompt(product: str, quantity: int) -> str:
    product_text = f'Telegram Premium на {quantity} мес.' if product == 'premium' else f'{quantity} звёзд'
    return f'🎁 Вы выбрали {product_text}.\n\nУкажите <b>@username</b> друга. Числовой ID не принимается.\nСебя указывать нельзя.'


async def _edit_gift_message(msg: types.Message, data: dict, text: str, reply_markup=None):
    kwargs = dict(chat_id=data['gift_chat_id'], message_id=data['gift_message_id'], reply_markup=reply_markup)
    if data['gift_caption']:
        return await msg.bot.edit_message_caption(caption=text, **kwargs)
    return await msg.bot.edit_message_text(text=text, **kwargs)


@router.callback_query(BuyStars.filter(F.action == 'gift_amount'))
@router.callback_query(BuyPremium.filter(F.action == 'gift_period'))
async def gift_recipient_start(query: types.CallbackQuery, callback_data: BuyStars | BuyPremium, state: FSMContext) -> None:
    premium = isinstance(callback_data, BuyPremium)
    quantity = callback_data.months if premium else callback_data.stars_count
    if (premium and quantity not in (3, 6, 12)) or (not premium and quantity < 50):
        await query.answer('Выберите корректное количество или срок.', show_alert=True)
        return
    await state.clear()
    await state.set_state(GiftRecipient.username)
    await state.update_data(
        gift_product='premium' if premium else 'stars', gift_quantity=quantity,
        gift_chat_id=query.message.chat.id, gift_message_id=query.message.message_id,
        gift_caption=query.message.caption is not None, gift_request=uuid4().hex,
    )
    await get_editor(query)(
        _gift_prompt('premium' if premium else 'stars', quantity),
        reply_markup=gift_cancel_keyboard(),
    )
    await query.answer()


@router.message(GiftRecipient.username)
async def gift_recipient_entered(msg: types.Message, state: FSMContext) -> None:
    data = await state.get_data()
    async def invalid(text):
        current = await state.get_data()
        if await state.get_state() == GiftRecipient.username.state and current.get('gift_request') == data.get('gift_request'):
            await _edit_gift_message(msg, data, text, gift_cancel_keyboard())
    value = (msg.text or '').strip()
    if not re.fullmatch(r'@[A-Za-z][A-Za-z0-9_]{3,30}[A-Za-z0-9]', value):
        await invalid('Укажите @username: 5–32 латинских символа. ID и ссылки не принимаются.')
        return
    if value[1:].casefold() == (msg.from_user.username or '').casefold():
        await invalid('Себя указывать нельзя. Укажите @username друга.')
        await msg.delete()
        return
    if not fragment_api:
        await invalid('Проверка получателя временно недоступна.')
        return
    product = data['gift_product']
    quantity = data['gift_quantity']
    username = value[1:]
    try:
        if product == 'premium':
            result = await asyncio.to_thread(fragment_api.search_premium_gift_recipient, username, quantity)
        else:
            result = await asyncio.to_thread(fragment_api.search_recipient, username)
    except Exception:
        await invalid('Не удалось проверить получателя. Попробуйте позже.')
        return
    # Cancelling or choosing another order while Fragment responds invalidates this result.
    if await state.get_state() != GiftRecipient.username.state or (await state.get_data()).get('gift_request') != data['gift_request']:
        return
    if not result.get('found', {}).get('recipient'):
        await invalid('Получатель недоступен для этого подарка. Проверьте @username.')
        return
    normalized = str(result.get('found', {}).get('username') or username).lstrip('@')
    if normalized.casefold() == (msg.from_user.username or '').casefold():
        await invalid('Себя указывать нельзя. Укажите @username друга.')
        await msg.delete()
        return
    keyboard = premium_payment_method_keyboard(quantity, username) if product == 'premium' else payment_method_keyboard(quantity, username)
    text = (BUY_PREMIUM_CHOSEN.format(months=_premium_months_label(quantity)) if product == 'premium'
            else BUY_STARS_AMOUNT_CHOSEN.format(stars=quantity))
    await _edit_gift_message(msg, data, text + f'\nПолучатель: @{username}', keyboard)
    await msg.delete()
    await state.clear()


# ── Buy Stars ──

@router.callback_query(BuyStars.filter(F.action == 'buy'))
async def buy_stars_show_amounts(query: types.CallbackQuery, callback_data: BuyStars) -> None:
    edit = get_editor(query)
    with contextlib.suppress(TelegramBadRequest):
        await edit(BUY_STARS_MENU, reply_markup=stars_sell_count_keyboard(callback_data.recipient))
    await query.answer()


@router.callback_query(BuyPremium.filter(F.action == 'menu'))
async def buy_premium_show_periods(query: types.CallbackQuery, callback_data: BuyPremium) -> None:
    edit = get_editor(query)
    with contextlib.suppress(TelegramBadRequest):
        await edit(BUY_PREMIUM_MENU, reply_markup=premium_months_keyboard(callback_data.recipient))
    await query.answer()


@router.callback_query(BuyPremium.filter(F.action == ''))
async def buy_premium_period_chosen(query: types.CallbackQuery, callback_data: BuyPremium) -> None:
    months = callback_data.months
    edit = get_editor(query)
    with contextlib.suppress(TelegramBadRequest):
        await edit(
            BUY_PREMIUM_CHOSEN.format(months=_premium_months_label(months)) + (f'\nПолучатель: @{callback_data.recipient}' if callback_data.recipient else ''),
            reply_markup=premium_payment_method_keyboard(months, callback_data.recipient),
        )
    await query.answer()


@router.callback_query(BuyStars.filter(F.action == ''))
async def buy_stars_amount_chosen(query: types.CallbackQuery, callback_data: BuyStars) -> None:
    stars = callback_data.stars_count
    edit = get_editor(query)
    with contextlib.suppress(TelegramBadRequest):
        await edit(
            BUY_STARS_AMOUNT_CHOSEN.format(stars=stars) + (f'\nПолучатель: @{callback_data.recipient}' if callback_data.recipient else ''),
            reply_markup=payment_method_keyboard(stars, callback_data.recipient),
        )
    await query.answer()


@router.callback_query(BuyStars.filter(F.action == 'custom'))
@router.callback_query(BuyStars.filter(F.action == 'gift_custom'))
async def buy_stars_custom(query: types.CallbackQuery, state: FSMContext, callback_data: BuyStars) -> None:
    edit = get_editor(query)
    with contextlib.suppress(TelegramBadRequest):
        await edit(BUY_STARS_CUSTOM, reply_markup=gift_cancel_keyboard() if callback_data.action == 'gift_custom' else None)
    await state.set_state(CustomStarsAmount.amount)
    await state.update_data(
        purchase_recipient=callback_data.recipient, purchase_gift=callback_data.action == 'gift_custom',
        gift_chat_id=query.message.chat.id, gift_message_id=query.message.message_id,
        gift_caption=query.message.caption is not None,
    )
    await query.answer()


@router.message(CustomStarsAmount.amount, F.text.regexp(r'^\d+$'))
async def buy_stars_custom_entered(msg: types.Message, state: FSMContext) -> None:
    amount = int(msg.text)
    data = await state.get_data()
    if amount < 50:
        if data.get('purchase_gift'):
            await _edit_gift_message(msg, data, BUY_STARS_LIMIT, gift_cancel_keyboard())
        else:
            await msg.answer(BUY_STARS_LIMIT)
        return
    if data.get('purchase_gift'):
        await state.set_state(GiftRecipient.username)
        await state.update_data(gift_product='stars', gift_quantity=amount, gift_request=uuid4().hex)
        await _edit_gift_message(msg, data, _gift_prompt('stars', amount), gift_cancel_keyboard())
        await msg.delete()
        return

    await msg.answer(
        BUY_STARS_AMOUNT_CHOSEN.format(stars=amount),
        reply_markup=payment_method_keyboard(amount, (await state.get_data()).get('purchase_recipient', '')),
    )
    await state.clear()


@router.message(CustomStarsAmount.amount)
async def buy_stars_custom_invalid(msg: types.Message, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get('purchase_gift'):
        await _edit_gift_message(msg, data, BUY_STARS_LIMIT, gift_cancel_keyboard())
    else:
        await msg.answer(BUY_STARS_LIMIT)


# ── Payment Methods ──

@router.callback_query(PayMethod.filter(F.method.in_({'category_menu', 'category_rub', 'category_crypto', 'category_other'})))
@router.callback_query(PremiumPayMethod.filter(F.method.in_({'category_menu', 'category_rub', 'category_crypto', 'category_other'})))
async def payment_category(query: types.CallbackQuery, callback_data: PayMethod | PremiumPayMethod) -> None:
    from html import escape
    category = callback_data.method.removeprefix('category_')
    category = '' if category == 'menu' else category
    titles = {'': 'Выберите категорию оплаты:', 'rub': 'Рубли / СБП / Карты',
              'crypto': 'Криптовалюта', 'other': 'Другие способы оплаты'}
    if isinstance(callback_data, PremiumPayMethod):
        product = f'Telegram Premium на {_premium_months_label(callback_data.months)}'
        keyboard = premium_payment_method_keyboard(callback_data.months, callback_data.recipient, category)
    else:
        product = f'{callback_data.stars_count} звёзд'
        keyboard = payment_method_keyboard(callback_data.stars_count, callback_data.recipient, category)
    recipient = callback_data.recipient or query.from_user.username
    text = f'<b>{titles[category]}</b>\n\nЗаказ: {product}'
    if recipient:
        text += f'\nПолучатель: @{escape(recipient)}'
    await query.answer()
    await get_editor(query)(text, reply_markup=keyboard)


UNCONFIGURED_PAYMENTS = {'pay_lolzteam', 'pay_codeesbp', 'pay_codeecard',
                       'pay_plategasbp', 'pay_plategacrypto', 'pay_iris', 'pay_uah'}


@router.callback_query(PayMethod.filter(F.method.in_(UNCONFIGURED_PAYMENTS)))
@router.callback_query(PremiumPayMethod.filter(F.method.in_(UNCONFIGURED_PAYMENTS)))
async def payment_not_configured(query: types.CallbackQuery) -> None:
    await query.answer('Этот способ оплаты пока недоступен. Выберите другой.', show_alert=True)


@router.callback_query(PayMethod.filter(F.method == 'pay_xrocket'))
@router.callback_query(PremiumPayMethod.filter(F.method == 'pay_xrocket'))
async def pay_xrocket(query: types.CallbackQuery, callback_data: PayMethod | PremiumPayMethod, repo: Repositories) -> None:
    from decimal import Decimal
    from html import escape
    from bot.settings import settings
    from bot.xrocket_payments import create_invoice
    if not settings.xrocket.token:
        await query.answer('Оплата через xRocket временно недоступна.', show_alert=True)
        return
    recipient = callback_data.recipient or query.from_user.username
    if not recipient:
        await query.answer('Для покупки установите @username в Telegram.', show_alert=True)
        return
    await query.answer()
    premium = isinstance(callback_data, PremiumPayMethod)
    quantity = callback_data.months if premium else callback_data.stars_count
    try:
        if premium:
            quote = await asyncio.to_thread(_get_premium_quote, recipient, quantity)
            if not quote.get('ok'):
                raise ValueError('Premium quote unavailable')
            usd = Decimal(str(quote['usd_amount']))
            base = await referrals.premium_stars(usd)
        else:
            base = quantity
            usd = Decimal(str(await repo.users.get_stars_course())) * quantity
        invoice, url = await create_invoice(
            bot_id=query.bot.id, buyer_id=query.from_user.id, chat_id=query.message.chat.id,
            recipient=recipient, product='premium' if premium else 'stars', quantity=quantity,
            usd=usd, base_stars=base,
        )
    except Exception as exc:
        logging.getLogger(__name__).warning('xRocket invoice creation failed: %s', type(exc).__name__)
        keyboard = (premium_payment_method_keyboard(quantity, callback_data.recipient, 'crypto') if premium
                    else payment_method_keyboard(quantity, callback_data.recipient, 'crypto'))
        await get_editor(query)('Не удалось создать счёт xRocket. Попробуйте позже или выберите другой способ оплаты.', reply_markup=keyboard)
        return
    product = f'Telegram Premium на {quantity} мес.' if premium else f'{quantity} звёзд'
    markup = (premium_payment_redirect_keyboard(quantity, url, callback_data.recipient) if premium
              else payment_redirect_keyboard(quantity, url, callback_data.recipient))
    await get_editor(query)(
        f'<b>Оплата через xRocket</b>\n\nЗаказ: {product}\nПолучатель: @{escape(recipient)}\n'
        f'К оплате: <b>{Decimal(invoice.atomic_amount) / 10**6} USDT</b> (комиссия 2%)\n\n'
        'Время на оплату: 15 минут.\nНажмите кнопку ниже и оплатите счёт. '
        'После подтверждения оплаты заказ будет обработан автоматически.', reply_markup=markup,
    )


@router.callback_query(PayMethod.filter(F.method.in_({'pay_ton', 'pay_usdt_ton'})))
@router.callback_query(PremiumPayMethod.filter(F.method.in_({'pay_ton', 'pay_usdt_ton'})))
async def pay_wallet(query: types.CallbackQuery, callback_data: PayMethod | PremiumPayMethod, repo: Repositories) -> None:
    from decimal import Decimal
    from html import escape
    from bot.settings import settings
    from bot.wallet_payments import create_invoice, UNITS
    from bot.keyboards.inline import wallet_payment_keyboard

    if not settings.ton_api.receive_address or not settings.ton_api.api_key:
        await query.answer('Оплата на TON-кошелёк временно недоступна.', show_alert=True)
        return
    recipient = callback_data.recipient or query.from_user.username
    if not recipient:
        await query.answer('Для покупки установите @username в Telegram.', show_alert=True)
        return
    await query.answer()
    premium = isinstance(callback_data, PremiumPayMethod)
    quantity = callback_data.months if premium else callback_data.stars_count
    try:
        if premium:
            quote = await asyncio.to_thread(_get_premium_quote, recipient, quantity)
            if not quote.get('ok'):
                await query.message.answer('Не удалось получить стоимость Premium. Попробуйте позже.')
                return
            usd = Decimal(str(quote['usd_amount']))
            base = await referrals.premium_stars(usd)
        else:
            base = quantity
            usd = Decimal(str(await repo.users.get_stars_course())) * quantity
        invoice = await create_invoice(
            bot_id=query.bot.id, buyer_id=query.from_user.id, chat_id=query.message.chat.id,
            recipient=recipient, product='premium' if premium else 'stars', quantity=quantity,
            asset='TON' if callback_data.method == 'pay_ton' else 'USDT', usd=usd, base_stars=base,
        )
    except Exception as exc:
        logging.getLogger(__name__).warning('Wallet invoice creation failed: %s', type(exc).__name__)
        await query.message.answer('Не удалось создать счёт. Попробуйте позже или выберите другой способ оплаты.')
        return
    label = 'TON' if invoice.asset == 'TON' else 'USDT (TON)'
    product = f'Premium на {quantity} мес.' if premium else f'{quantity} звёзд'
    value = Decimal(invoice.atomic_amount) / UNITS[invoice.asset]
    await get_editor(query)(
        f'<b>Счёт {label}</b>\n\nПолучатель: @{escape(recipient)}\nТовар: {product}\n\n'
        f'Переведите точную сумму: <code>{value}</code> {label}\n'
        f'На кошелёк: <code>{invoice.receiver}</code>\n\n'
        f'Обязательный комментарий (TAG/MEMO):\n<code>{invoice.order_id}</code>\n\n'
        'Сеть — TON. Срок оплаты — 15 минут. Комиссию сети оплачивает отправитель.\n'
        'После подтверждения перевода заказ будет обработан автоматически. '
        'Не отправляйте повторно; если срок истёк или возникли вопросы — @maneramur или @velunae.',
        reply_markup=wallet_payment_keyboard(invoice, callback_data.recipient),
    )

@router.callback_query(BuyStars.filter(F.action == 'dismiss_invoice'))
async def dismiss_invoice_message(query: types.CallbackQuery) -> None:
    await query.message.delete()
    await query.answer()


@router.callback_query(PayMethod.filter(F.method == 'pay_cryptobot'))
async def pay_cryptobot(query: types.CallbackQuery, callback_data: PayMethod, repo: Repositories) -> None:
    if not crypto:
        await query.answer('❌ Оплата через CryptoBot временно недоступна.', show_alert=True)
        return

    username = callback_data.recipient or query.from_user.username
    if not username:
        await query.answer('Для покупки установите @username в Telegram.', show_alert=True)
        return

    amount = callback_data.stars_count
    stars_course = await repo.users.get_stars_course()
    total_usd = amount * stars_course
    commission = total_usd * (messages.COMMISSION_PERCENT / 100)
    pay_amount = round(total_usd + commission, 2)

    fiat_invoice = await crypto.create_invoice(
        amount=pay_amount,
        fiat='USD',
        accepted_assets=['USDT', 'TON', 'BTC', 'ETH', 'LTC', 'TRX'],
        currency_type='fiat',
        hidden_message='Спасибо за покупку!',
        expires_in=300,
    )

    await referrals.register_payment('cryptobot', fiat_invoice.invoice_id, query.from_user.id, amount)

    edit = get_editor(query)
    await edit(
        REDIRECT_TO_PAYMENT.format(pay_service='CryptoBot', stars=amount) + f'\nПолучатель: @{username}',
        reply_markup=payment_redirect_keyboard(amount, fiat_invoice.bot_invoice_url, callback_data.recipient),
    )
    await query.answer()

    asyncio.create_task(funcs.check_cryptobot_invoice_status(
        user_id=query.from_user.id,
        amount=amount,
        invoice_id=fiat_invoice.invoice_id,
        stars_course=stars_course,
        message=query.message,
        username=username,
    ))


@router.callback_query(PayMethod.filter(F.method == 'pay_crypto'))
async def pay_crypto(query: types.CallbackQuery) -> None:
    await query.answer('🚧 Прямая оплата криптовалютой пока в разработке.', show_alert=True)


async def _wait_fragment_stars(user_id: int, amount: int, message: types.Message):
    from bot.database.engine import sessionmaker
    from bot.database.repos import Repositories

    await asyncio.sleep(15)

    async with sessionmaker() as session:
        repo = Repositories.get_repo(session=session)
        await repo.users.add_stars(user_id, amount)
        await session.commit()

    await message.answer(
        f'{_P["confirm"]} Оплата прошла успешно!\n\n'
        f'{_P["white_star"]} <b>{amount}</b> звёзд зачислено на ваш баланс!'
    )


@router.callback_query(PremiumPayMethod.filter(F.method == 'pay_cryptobot'))
async def pay_premium_cryptobot(query: types.CallbackQuery, callback_data: PremiumPayMethod) -> None:
    if not crypto:
        await query.answer('❌ Оплата через CryptoBot временно недоступна.', show_alert=True)
        return

    username = callback_data.recipient or query.from_user.username
    if not username:
        await query.answer('❌ Для покупки Premium установите @username в Telegram.', show_alert=True)
        return

    months = callback_data.months
    quote_data = _get_premium_quote(username, months)
    if not quote_data.get('ok'):
        await query.answer(f'❌ {quote_data["error"]}', show_alert=True)
        return

    referral_base = await referrals.premium_stars(quote_data['usd_amount'])

    usd_amount = quote_data['usd_amount']
    ton_amount = quote_data['ton_amount']
    commission = usd_amount * (messages.COMMISSION_PERCENT / 100)
    pay_amount = round(usd_amount + commission, 2)

    fiat_invoice = await crypto.create_invoice(
        amount=pay_amount,
        fiat='USD',
        accepted_assets=['USDT', 'TON', 'BTC', 'ETH', 'LTC', 'TRX'],
        currency_type='fiat',
        hidden_message='Спасибо за покупку Telegram Premium!',
        expires_in=300,
    )

    await referrals.register_payment('cryptobot', fiat_invoice.invoice_id, query.from_user.id, referral_base)

    edit = get_editor(query)
    await edit(
        '🎁 <b>Оплата Telegram Premium через CryptoBot</b>\n\n'
        f'Срок: <b>{_premium_months_label(months)}</b>\nПолучатель: @{username}\n'
        f'Стоимость Fragment: <b>{ton_amount:.2f} TON</b>\n'
        f'К оплате: <b>{pay_amount:.2f} USD</b> (комиссия {messages.COMMISSION_PERCENT}%)\n\n'
        'После оплаты бот автоматически отправит подарок получателю через Fragment.',
        reply_markup=premium_payment_redirect_keyboard(months, fiat_invoice.bot_invoice_url, callback_data.recipient),
    )
    await query.answer()

    asyncio.create_task(funcs.check_cryptobot_premium_invoice_status(
        user_id=query.from_user.id,
        username=username,
        months=months,
        invoice_id=fiat_invoice.invoice_id,
        message=query.message,
    ))


@router.callback_query(PremiumPayMethod.filter(F.method == 'pay_rub'))
async def pay_premium_rub(query: types.CallbackQuery, callback_data: PremiumPayMethod) -> None:
    await pay_premium_frekassa(
        query, PremiumRubPayMethod(method='frekassa_sbp', months=callback_data.months, recipient=callback_data.recipient),
    )


@router.callback_query(PayMethod.filter(F.method == 'pay_rub'))
async def pay_rub(query: types.CallbackQuery, callback_data: PayMethod, repo: Repositories) -> None:
    await pay_frekassa(
        query, RubPayMethod(method='frekassa_sbp', stars_count=callback_data.stars_count, recipient=callback_data.recipient), repo,
    )


@router.callback_query(RubPayMethod.filter(F.method == 'unitpay'))
async def pay_unitpay(query: types.CallbackQuery) -> None:
    await query.answer('🚧 Оплата через UnitPay пока в разработке.', show_alert=True)


@router.callback_query(RubPayMethod.filter(F.method.in_({'frekassa_sbp', 'frekassa_card'})))
async def pay_frekassa(
    query: types.CallbackQuery,
    callback_data: RubPayMethod,
    repo: Repositories,
) -> None:
    from bot.cryptopay import frekassa as fk_client, FrekassaClient
    if not fk_client:
        await query.answer('❌ Оплата в рублях временно недоступна.', show_alert=True)
        return

    username = callback_data.recipient or query.from_user.username
    if not username:
        await query.answer('Для покупки установите @username в Telegram.', show_alert=True)
        return

    method = callback_data.method  # frekassa_sbp or frekassa_card
    system_key = method.replace('frekassa_', '')  # sbp or card
    system_id = FrekassaClient.PAYMENT_SYSTEMS.get(system_key, 36)

    edit = get_editor(query)
    stars_count = callback_data.stars_count
    stars_course = await repo.users.get_stars_course()
    commission = messages.COMMISSION_PERCENT_FK
    amount_rub = round(stars_count * stars_course * 100 * (1 + commission / 100), 2)

    order_id = uuid4().hex
    email = f'{query.from_user.id}@telegram.org'

    pay_url = await fk_client.create_order(
        payment_id=order_id,
        amount=amount_rub,
        email=email,
        payment_system_id=system_id,
    )

    if not pay_url:
        await query.answer('❌ Не удалось создать ссылку на оплату. Попробуйте позже.', show_alert=True)
        return

    await referrals.register_payment('frekassa', order_id, query.from_user.id, stars_count)

    method_name = 'СБП' if system_key == 'sbp' else 'Банковская карта'
    await edit(
        f'💳 <b>Оплата через {method_name}</b>\n\n'
        f'Сумма: <b>{amount_rub} ₽</b> (комиссия {commission}%)\n'
        f'Звёзды: <b>{stars_count}</b>\nПолучатель: @{username}\n\n'
        'Нажмите кнопку ниже для оплаты.\n'
        '⏳ После оплаты бот автоматически отправит звёзды выбранному получателю '
        '(если отправка не удастся, они зачислятся на резервный баланс в боте).',
        reply_markup=payment_redirect_keyboard(stars_count, pay_url, callback_data.recipient, category='rub'),
    )
    await query.answer()

    from bot.funcs import check_frekassa_payment_status
    asyncio.create_task(check_frekassa_payment_status(
        user_id=query.from_user.id,
        amount=stars_count,
        order_id=order_id,
        message=query.message,
        username=username,
    ))


@router.callback_query(PremiumRubPayMethod.filter(F.method.in_({'frekassa_sbp', 'frekassa_card'})))
async def pay_premium_frekassa(
    query: types.CallbackQuery,
    callback_data: PremiumRubPayMethod,
) -> None:
    from bot.cryptopay import frekassa as fk_client, FrekassaClient

    if not fk_client:
        await query.answer('❌ Оплата в рублях временно недоступна.', show_alert=True)
        return

    username = callback_data.recipient or query.from_user.username
    if not username:
        await query.answer('❌ Для покупки Premium установите @username в Telegram.', show_alert=True)
        return

    months = callback_data.months
    quote_data = _get_premium_quote(username, months)
    if not quote_data.get('ok'):
        await query.answer(f'❌ {quote_data["error"]}', show_alert=True)
        return

    referral_base = await referrals.premium_stars(quote_data['usd_amount'])

    method = callback_data.method
    system_key = method.replace('frekassa_', '')
    system_id = FrekassaClient.PAYMENT_SYSTEMS.get(system_key, 36)

    rub_amount = quote_data['rub_amount']
    ton_amount = quote_data['ton_amount']
    commission = messages.COMMISSION_PERCENT_FK
    amount_rub = round(rub_amount * (1 + commission / 100), 2)
    order_id = uuid4().hex
    email = f'{query.from_user.id}@telegram.org'

    pay_url = await fk_client.create_order(
        payment_id=order_id,
        amount=amount_rub,
        email=email,
        payment_system_id=system_id,
    )

    if not pay_url:
        await query.answer('❌ Не удалось создать ссылку на оплату. Попробуйте позже.', show_alert=True)
        return

    await referrals.register_payment('frekassa', order_id, query.from_user.id, referral_base)

    method_name = 'СБП' if system_key == 'sbp' else 'Банковская карта'
    edit = get_editor(query)
    await edit(
        f'🎁 <b>Оплата Telegram Premium через {method_name}</b>\n\n'
        f'Срок: <b>{_premium_months_label(months)}</b>\nПолучатель: @{username}\n'
        f'Стоимость Fragment: <b>{ton_amount:.2f} TON</b>\n'
        f'К оплате: <b>{amount_rub:.2f} ₽</b> (комиссия {commission}%)\n\n'
        'После оплаты бот автоматически отправит подарок получателю через Fragment.',
        reply_markup=premium_payment_redirect_keyboard(months, pay_url, callback_data.recipient, category='rub'),
    )
    await query.answer()

    asyncio.create_task(funcs.check_frekassa_premium_payment_status(
        user_id=query.from_user.id,
        username=username,
        months=months,
        order_id=order_id,
        message=query.message,
    ))


@router.callback_query(PremiumPayMethod.filter(F.method == 'pay_usd'))
@router.callback_query(PayMethod.filter(F.method == 'pay_usd'))
async def pay_usd(query: types.CallbackQuery) -> None:
    await query.answer('🚧 Оплата в USD/EUR пока в разработке.', show_alert=True)


# ── Withdraw Stars ──

@router.callback_query(AccountBalance.filter(F.action == 'menu'))
async def withdraw_menu(query: types.CallbackQuery, repo: Repositories, state: FSMContext) -> None:
    await state.clear()
    stars = await repo.users.get_stars_balance(query.from_user.id) or 0
    edit = get_editor(query)
    with contextlib.suppress(TelegramBadRequest):
        await edit(
            f'{_P["white_star"]} <b>Вывод звёзд</b>\n\n'
            f'Внутренний баланс: <b>{stars:.2f}</b> {_P["white_star"]}\n\n'
            'Выберите, кому вывести звёзды:',
            reply_markup=withdraw_keyboard(),
        )
    await query.answer()


@router.callback_query(AccountBalance.filter(F.action == 'withdraw'))
async def withdraw_start(query: types.CallbackQuery, state: FSMContext) -> None:
    if not query.from_user.username:
        await query.answer('❌ Установите @username в Telegram.', show_alert=True)
        return

    edit = get_editor(query)
    with contextlib.suppress(TelegramBadRequest):
        await edit(WITHDRAW_STARS, reply_markup=referrals_keyboard())
    await state.clear()
    await state.set_state(StarsWithdraw.amount)
    await state.update_data(withdraw_username=query.from_user.username)
    await query.answer()


@router.callback_query(AccountBalance.filter(F.action == 'withdraw_friend'))
async def withdraw_friend_start(query: types.CallbackQuery, state: FSMContext) -> None:
    edit = get_editor(query)
    with contextlib.suppress(TelegramBadRequest):
        await edit(WITHDRAW_STARS_FOR_FRIEND, reply_markup=referrals_keyboard())
    await state.clear()
    await state.set_state(FriendUser.username)
    await query.answer()


@router.message(FriendUser.username, F.text.regexp(r'^@[A-Za-z][A-Za-z0-9_]{3,30}[A-Za-z0-9]$'))
async def withdraw_friend_username(msg: types.Message, state: FSMContext) -> None:
    username = msg.text.lstrip('@')
    await state.update_data(withdraw_username=username)
    await state.set_state(StarsWithdraw.amount)
    await msg.answer(WITHDRAW_STARS)


@router.message(FriendUser.username)
async def withdraw_friend_invalid(msg: types.Message) -> None:
    await msg.answer('❌ Укажите корректный @username.')


@router.message(StarsWithdraw.amount)
async def withdraw_amount(msg: types.Message, repo: Repositories, state: FSMContext) -> None:
    if not msg.text or not msg.text.isdigit():
        await msg.answer('❌ Введите корректное число.')
        return

    amount = int(msg.text)
    if amount < 50:
        await msg.answer(BUY_STARS_LIMIT)
        return

    user_stars = await repo.users.get_stars_balance(msg.from_user.id) or 0
    if user_stars < amount:
        await msg.answer(WITHDRAW_INSUFFICIENT, reply_markup=referrals_keyboard())
        await state.clear()
        return

    data = await state.get_data()
    username = data.get('withdraw_username') or msg.from_user.username
    if not username or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{3,30}[A-Za-z0-9]', username):
        await msg.answer('Укажите корректный @username получателя.', reply_markup=referrals_keyboard())
        await state.clear()
        return

    if not fragment_api or not ton_wallet:
        await msg.answer('❌ Вывод временно недоступен.')
        await state.clear()
        return

    withdrawal_id = None
    await msg.answer(f'⏳ Выводим <b>{amount}</b> {_P["white_star"]} на @{username}...')

    try:
        result = await asyncio.to_thread(fragment_api.create_star_buy_invoice, amount, username)
        if not result.get('ok') and 'transaction' not in result:
            await msg.answer(f'❌ Пользователь @{username} не найден на Fragment.')
            await state.clear()
            return

        invoice = FragmentAPI.parse_invoice(result)
        if not invoice:
            await msg.answer('❌ Не удалось получить данные для отправки. Попробуйте позже.')
            await state.clear()
            return

        balance = await ton_wallet.get_balance()
        if balance < invoice['ton_amount']:
            await msg.answer('❌ Вывод сейчас недоступен. Обратитесь в поддержку — @maneramur.')
            await state.clear()
            return

        withdrawal_id = await withdrawals.reserve(msg.from_user.id, msg.message_id, amount, username)
        if withdrawal_id is None:
            await msg.answer('Недостаточно звёзд или предыдущий вывод ещё обрабатывается.', reply_markup=referrals_keyboard())
            await state.clear()
            return

        tx_hash = await ton_wallet.send_ton(
            destination=invoice['ton_address'],
            amount=invoice['ton_amount'],
            comment=invoice.get('comment'),
        )

        await withdrawals.finish(withdrawal_id, tx_hash=tx_hash)

    except Exception as e:
        logger.error('Withdraw error: %s', e)
        if withdrawal_id is not None:
            await withdrawals.finish(withdrawal_id)
            await msg.answer('Вывод отправлен на проверку. Не повторяйте оплату: обратитесь в поддержку — @maneramur.', reply_markup=referrals_keyboard())
        else:
            await msg.answer('❌ Не удалось подготовить вывод. Баланс не списан. Поддержка — @maneramur.', reply_markup=referrals_keyboard())
    else:
        await msg.answer(WITHDRAW_SUCCESS.format(stars=amount), reply_markup=referrals_keyboard())

    await state.clear()


# ── Calculator ──

@router.callback_query(Calculator.filter(F.action.in_({'menu', 'gift_menu'})))
async def calc_menu(query: types.CallbackQuery, callback_data: Calculator) -> None:
    edit = get_editor(query)
    with contextlib.suppress(TelegramBadRequest):
        await edit(CALCULATOR_MENU, reply_markup=calculator_menu_keyboard(gift=callback_data.action == 'gift_menu'))
    await query.answer()


@router.callback_query(Calculator.filter(F.action.in_({'usd_to_stars', 'stars_to_usd', 'gift_usd_to_stars', 'gift_stars_to_usd'})))
async def calc_choose_action(query: types.CallbackQuery, callback_data: Calculator, state: FSMContext) -> None:
    action = callback_data.action.removeprefix('gift_')
    text = CALCULATOR_INPUT_USD if action == 'usd_to_stars' else CALCULATOR_INPUT_STARS

    edit = get_editor(query)
    with contextlib.suppress(TelegramBadRequest):
        await edit(text)
    await state.set_state(CalculatorInput.amount)
    await state.update_data(calc_action=action, calc_gift=callback_data.action.startswith('gift_'))
    await query.answer()


@router.message(CalculatorInput.amount)
async def calc_entered_amount(msg: types.Message, state: FSMContext, repo: Repositories) -> None:
    if not funcs.is_number(msg.text):
        await msg.answer('❌ Введите корректное число.')
        return

    data = await state.get_data()
    action = data.get('calc_action', 'stars_to_usd')
    amount = float(msg.text)
    stars_course = await repo.users.get_stars_course()

    course_rub = funcs.usd_to_rub(stars_course)
    course_ton = funcs.usd_to_ton(stars_course)
    course_ton_str = f'{course_ton:.4f}' if course_ton else 'н/д'

    commission = messages.COMMISSION_PERCENT / 100
    if action == 'usd_to_stars':
        effective_course = stars_course * (1 + commission)
        stars_amount = int(amount / effective_course) if stars_course else 0
        input_val = f'{amount}💲'
        output_val = f'{stars_amount} {_P["white_star"]}'
    else:
        usd_amount = stars_course * amount * (1 + commission)
        input_val = f'{int(amount)} {_P["white_star"]}'
        output_val = f'{usd_amount:.2f}💲'

    text = CALCULATOR_RESULT.format(
        input_val=input_val,
        output_val=output_val,
        course_rub=course_rub,
        course_usd=stars_course,
        course_ton=course_ton_str,
    )

    await msg.answer(text, reply_markup=calculator_menu_keyboard(back=True, gift=data.get('calc_gift', False)))
    await state.clear()
