import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest

from bot.inline_rates import Conversion, Rates, RateCache, parse_query, number


@pytest.mark.parametrize('query,amount,source,target', [
    ('10 рублей в грам','10','RUB','GRAM'),
    ('100 звёзд в рубли','100','STARS','RUB'),
    ('5 долларов в звезды','5','USD','STARS'),
    ('1 GRAM','1','GRAM',None),
    ('1 ton to stars','1','GRAM','STARS'),
    ('1,5 usdt -> rub','1.5','USDT','RUB'),
    ('1 000,5 ₽','1000.5','RUB',None),
    ('$10','10','USD',None),
    ('.5 gram','0.5','GRAM',None),
    ('50','50','STARS',None),
    ('курс грамм','1','GRAM',None),
])
def test_russian_and_english_conversion_queries(query, amount, source, target):
    assert parse_query(query) == [Conversion(Decimal(amount), source, target)]


def test_empty_query_includes_one_gram_and_one_star():
    assert [(q.amount,q.source) for q in parse_query('')] == [(1,'GRAM'),(1,'STARS')]


@pytest.mark.parametrize('query', ['-1 stars','1 btc','1 rub в btc','NaN','Infinity','1e9 rub','$10 rub','<b>10</b>','1000000000001 rub','0.000000001 stars'])
def test_bad_queries_are_rejected(query):
    with pytest.raises(ValueError): parse_query(query)


def sample_rates():
    return Rates(Decimal('2'),Decimal('100'),Decimal('.99'),datetime(2026,11,26,tzinfo=timezone.utc))


def test_cross_currency_math_and_usd_usdt_are_distinct():
    rates = sample_rates()
    values = rates.convert(Conversion(Decimal('10'),'RUB','GRAM'),'.015')
    assert values['GRAM'] == Decimal('.05')
    assert values['USD'] == Decimal('.1')
    assert values['USDT'] == Decimal('.1') / Decimal('.99')
    assert values['STARS'] == Decimal('.1') / Decimal('.015')
    assert rates.convert(Conversion(Decimal('1'),'GRAM'),'.015')['RUB'] == 200
    assert number(Decimal('.015'),'USD') == '0.015'
    assert number(Decimal('0.000000001'),'GRAM') == '<0.00000001'


async def test_parallel_queries_share_one_rates_fetch():
    cache = RateCache()
    cache.fetch = AsyncMock(return_value=sample_rates())
    results = await asyncio.gather(*(cache.get() for _ in range(10)))
    cache.fetch.assert_awaited_once()
    assert all(r == sample_rates() for r in results)


async def test_recent_cache_survives_provider_error_but_old_rates_are_rejected(monkeypatch):
    from bot import inline_rates
    cache = RateCache()
    cache.fetch = AsyncMock(side_effect=ValueError('No rates'))
    cache.snapshot = sample_rates()
    cache.updated = 100
    monkeypatch.setattr(inline_rates.time,'monotonic',lambda:200)
    assert await cache.get() == sample_rates()
    monkeypatch.setattr(inline_rates.time,'monotonic',lambda:500)
    with pytest.raises(ValueError): await cache.get()


@pytest.mark.parametrize('query,count', [('',2),('10 рублей в грам',1),('wrong',1)])
async def test_inline_response_is_conversion_only(monkeypatch, query, count):
    from bot.handlers.users import inline_converter as module
    monkeypatch.setattr(module.rate_cache,'get',AsyncMock(return_value=sample_rates()))
    inline = NS(query=query,offset='',answer=AsyncMock())
    repo = NS(users=NS(get_stars_course=AsyncMock(return_value=.015)))
    await module.inline_convert(inline,repo)
    results=inline.answer.call_args.args[0]
    assert len(results)==count
    assert all(r.type=='article' and r.input_message_content.parse_mode=='HTML' for r in results)
    assert all(r.reply_markup is None for r in results)
    if query == '10 рублей в грам':
        assert results[0].title == '10 RUB ≈ 0.05 GRAM'
        assert '<b>STARS</b>' in results[0].input_message_content.message_text


async def test_provider_failure_returns_explanation_without_zero_quotes(monkeypatch):
    from bot.handlers.users import inline_converter as module
    monkeypatch.setattr(module.rate_cache,'get',AsyncMock(side_effect=TimeoutError))
    inline=NS(query='1 gram',offset='',answer=AsyncMock())
    await module.inline_convert(inline,NS(users=NS(get_stars_course=AsyncMock(return_value=.015))))
    assert inline.answer.call_args.args[0][0].id == 'unavailable'
