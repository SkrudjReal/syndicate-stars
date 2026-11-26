import hashlib
from html import escape
from zoneinfo import ZoneInfo

from aiogram import Router
from aiogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent

from bot.inline_rates import CURRENCIES, parse_query, rate_cache, number

router = Router()
ICONS = {'GRAM': '💎', 'USD': '💲', 'USDT': '💵', 'STARS': '⭐️', 'RUB': '🇷🇺'}


def help_result(unavailable=False):
    title = 'Курс временно недоступен' if unavailable else 'Как пользоваться конвертером'
    text = (f'<b>🔢 {title}</b>\n\n'
            'Пустой запрос — курс 1 GRAM и 1 STARS.\n'
            '<blockquote><b>Примеры запросов:</b>\n<code>100 stars</code>\n<code>10 рублей в грам</code>\n'
            '<code>5 долларов в звезды</code>\n<code>1 gram в rub</code></blockquote>\n\n'
            'Поддерживаются GRAM/TON, USD, USDT, STARS и RUB. '
            'Число без валюты означает STARS.')
    return InlineQueryResultArticle(id='unavailable' if unavailable else 'help', title=title,
                                    description='Например: 10 рублей в грам · 100 stars · 1 gram',
                                    input_message_content=InputTextMessageContent(message_text=text, parse_mode='HTML'))


def conversion_result(request, rates, stars_usd):
    values = rates.convert(request, stars_usd)
    source = f'{number(request.amount)} {request.source}'
    if request.target:
        title = f'{source} ≈ {number(values[request.target], request.target)} {request.target}'
    else:
        title = f'Курс {source}'
    summary = f'Конвертация <b>{escape(source)}</b>'
    if request.target:
        summary += f' ≈ <b>{escape(number(values[request.target], request.target))} {request.target}</b>'
    lines = ['<b>🔢 Калькулятор</b>\n', f'<blockquote>{summary}</blockquote>',
             '<blockquote><b>Результат конвертации:</b>']
    for unit in CURRENCIES:
        lines.append(f'{ICONS[unit]} <b>{unit}</b>: <b>{escape(number(values[unit], unit))}</b>')
    lines[-1] += '</blockquote>'
    timestamp = rates.fetched_at.astimezone(ZoneInfo('Europe/Warsaw'))
    lines.append(f'\n<i>Приблизительно, без комиссий. Курс на {timestamp:%H:%M %Z}.</i>')
    digest = hashlib.sha256(f'{source}:{request.target}:{rates.fetched_at.isoformat()}:{stars_usd}'.encode()).hexdigest()[:32]
    return InlineQueryResultArticle(
        id=digest, title=title,
        description=' · '.join(f'{number(values[u], u)} {u}' for u in ('GRAM', 'STARS', 'RUB', 'USD')),
        input_message_content=InputTextMessageContent(message_text='\n'.join(lines), parse_mode='HTML'),
    )


@router.inline_query(flags={'user': False})
async def inline_convert(query: InlineQuery, repo):
    if query.offset:
        await query.answer([], cache_time=15)
        return
    try:
        requests = parse_query(query.query)
    except ValueError:
        await query.answer([help_result()], cache_time=15, is_personal=False)
        return
    try:
        stars_usd = await repo.users.get_stars_course()
        rates = await rate_cache.get()
        results = [conversion_result(request, rates, stars_usd) for request in requests]
    except Exception:
        results = [help_result(unavailable=True)]
    await query.answer(results, cache_time=15, is_personal=False)
