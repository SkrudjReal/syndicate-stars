import re
import socket
import time
import base64
import logging

import ipaddress
import requests
import pytz
from datetime import datetime
from tonsdk.boc import Cell

from aiogram import Bot, types
from bot.keyboards import inline
from bot import messages

DEFAULT_TZ = pytz.timezone("Europe/Moscow")

deep_links = {
    'tag': '@',
    'link': 'https://t.me/',
    'mention': 'tg://openmessage?user_id=',
    'mention_click': 'tg://user?id='
}
re_link_sup = r'(http(|s)://t\.me/|tg://openmessage\?user_id=|@)(\d{6,14}|[\w\d]{5,32})'


def entity_create_full_name(id: int, fname: str, lname: str = None, entity: str = deep_links['mention']) -> str:
    full_name = f'{fname} {lname}' if lname else fname
    return f'<a href="{entity}{id}">{full_name}</a>'


def entity_create(id: int | str, name: str, entity: str = deep_links['mention']) -> str:
    return f'<a href="{entity}{id}">{name}</a>'


async def test_bot_token(bot_token: str) -> types.user.User | None:
    try:
        bot = Bot(token=bot_token)
        bot_me = await bot.get_me()
    except Exception:
        return None
    else:
        return bot_me


def isfloat(s: str) -> bool:
    return bool(re.fullmatch(r'[+-]?\d+(\.\d+)?', s))


def is_number(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


def is_user_mention(part_text: str) -> bool:
    return re.search(re_link_sup, part_text) is not None


def link_getter(text: str) -> str | int | None:
    expression = r'((http(|s)://t\.me/|@)[\w\d]{5,32}|tg://openmessage\?user_id=\d{6,14})'
    result = re.search(expression, text)
    if result:
        result = result[0].replace('https://t.me/', '').replace('tg://openmessage?user_id=', '').strip('@').replace('http://t.me/', '')
        if result.isdigit():
            return int(result)
        return str(result)
    return None


def _outbound_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return None
    finally:
        s.close()


def _public_ip():
    try:
        return requests.get("https://api.ipify.org", timeout=3).text.strip()
    except Exception:
        return None


def _check_port_external(ip, port=22, max_nodes=2, timeout=12):
    try:
        r = requests.get("https://check-host.net/check-tcp", params={"host": f"{ip}:{port}", "max_nodes": max_nodes}, timeout=5)
        r.raise_for_status()
        req_id = r.json().get("request_id")
        if not req_id:
            return None
        deadline = time.time() + timeout
        while time.time() < deadline:
            rr = requests.get(f"https://check-host.net/check-result/{req_id}", timeout=5)
            rr.raise_for_status()
            data = rr.json()
            if all(v is not None for v in data.values()):
                for node, res in data.items():
                    if isinstance(res, list) and res and isinstance(res[0], dict) and not res[0].get("error"):
                        return True
                return False
            time.sleep(1.0)
    except Exception:
        return None


def is_running_on_server():
    import os
    env = os.getenv("RUN_ENV")
    if env:
        return {"where": env, "reasons": ["env_override"], "local": None, "public": None}

    local = _outbound_local_ip()
    public = _public_ip()
    reasons = []
    if local:
        reasons.append(f"local={local}")
    if public:
        reasons.append(f"public={public}")

    try:
        pub_global = bool(public and ipaddress.ip_address(public).is_global)
    except Exception:
        pub_global = False

    if public and local and public == local and pub_global:
        port_ok = _check_port_external(public, 22)
        reasons.append("public==local and public is global")
        return {"where": "server", "reasons": reasons, "local": local, "public": public}

    if public and local and public != local:
        reasons.append("public != local -> behind NAT/CGNAT")
        return {"where": "local", "reasons": reasons, "local": local, "public": public}

    reasons.append("couldn't determine; assume local/isolated")
    return {"where": "local", "reasons": reasons, "local": local, "public": public}


def format_withdraw_history(operations: list) -> str:
    if not operations:
        return 'Ещё не было выводов.'

    text = ''
    for num, op in enumerate(operations, 1):
        mention = entity_create(op.user_id, op.user_id)
        date_str = op.date.strftime('%Y-%m-%d %H:%M:%S')
        text += f'{num}. {mention} снятие {op.stars}зв > @{op.whom} {date_str} [{op.status}]\n'
    return text


def format_top_user_stars(stars: list) -> str:
    if not stars:
        return 'Ещё нет пользователей со звёздами.'

    text = '🌟 <b>Топ пользователей по звёздам:</b>\n'
    for num, user in enumerate(stars, 1):
        mention = entity_create(user.user_id, user.user_id)
        text += f"{num}. {mention} - {user.stars}зв\n"
    return text


def get_ton_price() -> float | None:
    url = 'https://scanner.tradingview.com/crypto/scan'
    payload = {
        'symbols': {'tickers': ['BINANCE:TONUSDT'], 'query': {'types': []}},
        'columns': ['close'],
    }
    try:
        res = requests.post(url, json=payload, timeout=5).json()
        return float(res['data'][0]['d'][0])
    except Exception:
        return None


def usd_to_ton(amount_usd: float) -> float | None:
    ton_price = get_ton_price()
    if not ton_price:
        return None
    return amount_usd / ton_price


def usd_to_rub(amount: float) -> float:
    try:
        res = requests.get('https://open.er-api.com/v6/latest/USD', timeout=5).json()
        rate = res['rates']['RUB']
        return round(amount * rate, 2)
    except Exception:
        return 0.0


logger = logging.getLogger(__name__)


def fix_base64_padding(data: str) -> str:
    missing_padding = len(data) % 4
    if missing_padding:
        data += '=' * (4 - missing_padding)
    return data


def extract_ton_comment(boc_base64: str) -> str | None:
    try:
        boc_base64 = fix_base64_padding(boc_base64)
        raw = base64.b64decode(boc_base64)
        cell = Cell.one_from_boc(raw)
        bits = cell.bits.get_top_upped_array()
        decoded_text = bits.decode('utf-8', errors='ignore').strip()
        return decoded_text if decoded_text else None
    except Exception:
        return None


def fragment_buy_stars_pretty(response: dict) -> dict:
    trans = response.get('transaction')
    msgs = trans.get('messages')
    valid_until = datetime.strftime(
        datetime.fromtimestamp(trans.get('validUntil')),
        '%Y-%m-%d %H:%M:%S'
    )
    ton_address = msgs[0].get('address')
    ton_amount = int(msgs[0].get('amount')) / 1000000000
    from bot.cryptopay import FragmentAPI
    invoice = FragmentAPI.parse_invoice(response)
    if invoice is None:
        raise ValueError('Invalid Fragment transaction payload')
    return {
        'expire_date': valid_until,
        'ton_address': ton_address,
        'ton_amount': float(ton_amount),
        'comment': invoice['comment'],
    }


async def check_cryptobot_invoice_status(user_id, amount, invoice_id, stars_course, message, username):
    from bot.cryptopay import CryptoPay
    from bot.database.engine import sessionmaker
    from bot.database.repos import Repositories
    from bot.cryptopay import fragment_api, ton_wallet
    import asyncio
    from bot.referrals import credit_payment

    while True:
        await asyncio.sleep(3)
        status = await CryptoPay.get_status(invoice_id)

        if status == 'paid':
            await credit_payment('cryptobot', invoice_id)
            # Выводим звёзды через Fragment на аккаунт юзера
            try:
                result = fragment_api.create_star_buy_invoice(amount, username)
                invoice = fragment_buy_stars_pretty(result)

                await ton_wallet.send_ton(
                    destination=invoice['ton_address'],
                    amount=invoice['ton_amount'],
                    comment=invoice.get('comment'),
                )

                await message.answer(
                    f'{messages.PREMIUM_EMOJI_DICT["confirm"]} Оплата прошла успешно!\n\n'
                    f'{messages.PREMIUM_EMOJI_DICT["white_star"]} <b>{amount}</b> звёзд отправлены получателю @{username}!\n\n'
                    '⏳ Зачисление обычно занимает 1–5 минут.'
                )

                async with sessionmaker() as session:
                    repo = Repositories.get_repo(session=session)
                    await repo.users.log_withdraw(user_id, amount, whom=username)
                    await session.commit()

            except Exception as e:
                logger.error('Fragment withdraw error user=%s amount=%s: %s', user_id, amount, e)
                async with sessionmaker() as session:
                    repo = Repositories.get_repo(session=session)
                    await repo.users.add_stars(user_id, amount)
                    await session.commit()

                await message.answer(
                    '❌ <b>Не удалось отправить звёзды автоматически</b>\n\n'
                    f'Оплата получена: <b>{amount}</b> звёзд зачислены на ваш резервный баланс в боте.\n'
                    'Если нужна помощь, обратитесь в поддержку — @maneramur'
                )
            break

        elif status == 'expired':
            await credit_payment('cryptobot', invoice_id, expired=True)
            await message.answer('❌ Время оплаты истекло. Попробуйте снова.')
            break


async def check_frekassa_payment_status(user_id, amount, order_id, message, username):
    from bot.cryptopay import frekassa as fk_client, fragment_api, ton_wallet
    from bot.database.engine import sessionmaker
    from bot.database.repos import Repositories
    import asyncio
    from bot.referrals import credit_payment

    # Polling 60 раз по 5 секунд = 5 минут
    for _ in range(60):
        await asyncio.sleep(5)
        status = await fk_client.get_order_status(order_id)

        if status in ('completed', 'success', 1, 'paid'):
            await credit_payment('frekassa', order_id)
            try:
                result = fragment_api.create_star_buy_invoice(amount, username)
                invoice = fragment_buy_stars_pretty(result)

                await ton_wallet.send_ton(
                    destination=invoice['ton_address'],
                    amount=invoice['ton_amount'],
                    comment=invoice.get('comment'),
                )

                await message.answer(
                    f'{messages.PREMIUM_EMOJI_DICT["confirm"]} Оплата прошла успешно!\n\n'
                    f'{messages.PREMIUM_EMOJI_DICT["white_star"]} <b>{amount}</b> звёзд отправлены получателю @{username}!\n\n'
                    '⏳ Зачисление обычно занимает 1–5 минут.'
                )

                async with sessionmaker() as session:
                    repo = Repositories.get_repo(session=session)
                    await repo.users.log_withdraw(user_id, amount, whom=username)
                    await session.commit()

            except Exception as e:
                logger.error('Frekassa+Fragment withdraw error user=%s amount=%s: %s', user_id, amount, e)
                async with sessionmaker() as session:
                    repo = Repositories.get_repo(session=session)
                    await repo.users.add_stars(user_id, amount)
                    await session.commit()

                await message.answer(
                    '❌ <b>Не удалось отправить звёзды автоматически</b>\n\n'
                    f'Оплата получена: <b>{amount}</b> звёзд зачислены на ваш резервный баланс в боте.\n'
                    'Если нужна помощь, обратитесь в поддержку — @maneramur'
                )
            return

    await message.answer('❌ Оплата не найдена. Если вы уже оплатили заказ, обратитесь в поддержку — @maneramur.')


async def check_cryptobot_premium_invoice_status(user_id, username, months, invoice_id, message):
    from bot.cryptopay import CryptoPay
    from bot.cryptopay import fragment_api, ton_wallet
    import asyncio
    from bot.referrals import credit_payment

    while True:
        await asyncio.sleep(3)
        status = await CryptoPay.get_status(invoice_id)

        if status == 'paid':
            await credit_payment('cryptobot', invoice_id)
            try:
                result = fragment_api.create_premium_gift_invoice(months, username)
                if not result.get('ok') and 'transaction' not in result:
                    raise RuntimeError(result.get('error') or 'Failed to create premium gift invoice')

                invoice = fragment_api.parse_invoice(result)
                if not invoice:
                    raise RuntimeError('Failed to parse premium invoice')

                await ton_wallet.send_ton(
                    destination=invoice['ton_address'],
                    amount=invoice['ton_amount'],
                    comment=invoice.get('comment'),
                )

                await message.answer(
                    f'{messages.PREMIUM_EMOJI_DICT["confirm"]} Оплата прошла успешно!\n\n'
                    f'🎁 Telegram Premium на <b>{months} мес.</b> отправлен получателю @{username}!\n\n'
                    '⏳ Подарок обычно приходит в течение 1-5 минут.'
                )
            except Exception as e:
                logger.error('Fragment premium gift error user=%s months=%s: %s', user_id, months, e)
                await message.answer(
                    '❌ <b>Ошибка при отправке Telegram Premium</b>\n\n'
                    'Оплата получена, но подарок не удалось отправить автоматически.\n'
                    'Обратитесь в поддержку — @maneramur'
                )
            break

        elif status == 'expired':
            await credit_payment('cryptobot', invoice_id, expired=True)
            await message.answer('❌ Время оплаты истекло. Попробуйте снова.')
            break


async def check_frekassa_premium_payment_status(user_id, username, months, order_id, message):
    from bot.cryptopay import frekassa as fk_client, fragment_api, ton_wallet
    import asyncio
    from bot.referrals import credit_payment

    for _ in range(60):
        await asyncio.sleep(5)
        status = await fk_client.get_order_status(order_id)

        if status in ('completed', 'success', 1, 'paid'):
            await credit_payment('frekassa', order_id)
            try:
                result = fragment_api.create_premium_gift_invoice(months, username)
                if not result.get('ok') and 'transaction' not in result:
                    raise RuntimeError(result.get('error') or 'Failed to create premium gift invoice')

                invoice = fragment_api.parse_invoice(result)
                if not invoice:
                    raise RuntimeError('Failed to parse premium invoice')

                await ton_wallet.send_ton(
                    destination=invoice['ton_address'],
                    amount=invoice['ton_amount'],
                    comment=invoice.get('comment'),
                )

                await message.answer(
                    f'{messages.PREMIUM_EMOJI_DICT["confirm"]} Оплата прошла успешно!\n\n'
                    f'🎁 Telegram Premium на <b>{months} мес.</b> отправлен получателю @{username}!\n\n'
                    '⏳ Подарок обычно приходит в течение 1-5 минут.'
                )
            except Exception as e:
                logger.error('Frekassa+Fragment premium gift error user=%s months=%s: %s', user_id, months, e)
                await message.answer(
                    '❌ <b>Ошибка при отправке Telegram Premium</b>\n\n'
                    'Оплата получена, но подарок не удалось отправить автоматически.\n'
                    'Обратитесь в поддержку — @maneramur'
                )
            return

    await message.answer('❌ Оплата не найдена. Если вы уже оплатили заказ, обратитесь в поддержку — @maneramur.')
