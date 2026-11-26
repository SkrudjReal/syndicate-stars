"""Inline conversion only: never creates invoices or moves balances."""
import asyncio
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal


CURRENCIES = ('GRAM', 'USD', 'USDT', 'STARS', 'RUB')
ALIASES = {
    'GRAM': ('gram', 'grams', 'грам', 'грамм', 'грамма', 'граммов', 'грамы', 'ton', 'тон', 'тона', 'тонов', '💎'),
    'STARS': ('stars', 'star', 'st', 'старс', 'старсов', 'звезда', 'звезды', 'звёзды', 'звезд', 'звёзд', '⭐', '⭐️'),
    'RUB': ('rub', 'rur', 'руб', 'рубль', 'рубля', 'рубли', 'рублей', 'р', '₽'),
    'USD': ('usd', 'доллар', 'доллара', 'доллары', 'долларов', 'дол', 'долл', 'бакс', 'баксов', '$'),
    'USDT': ('usdt', 'tether', 'юсдт', '💵'),
}
_units = {alias: currency for currency, aliases in ALIASES.items() for alias in aliases}


@dataclass(frozen=True)
class Conversion:
    amount: Decimal
    source: str
    target: str | None = None


def currency(value):
    try:
        return _units[value.strip().rstrip('.').casefold()]
    except KeyError:
        raise ValueError('Unknown currency') from None


def parse_query(query: str) -> list[Conversion]:
    text = query.strip().casefold()
    if text in ('', 'курс', 'курсы', 'rate', 'rates'):
        return [Conversion(Decimal(1), 'GRAM'), Conversion(Decimal(1), 'STARS')]
    if len(text) > 200:
        raise ValueError('Query too long')
    text = re.sub(r'^(?:курс|конвертация|convert)\s+', '', text)
    parts = re.split(r'\s+(?:в|to)\s+|\s*(?:->|→|=)\s*', text, maxsplit=1)
    target = currency(parts[1]) if len(parts) == 2 else None
    match = re.fullmatch(r'\s*([$₽⭐💎]?)\s*((?:\d+(?:[ \u00a0]\d{3})*(?:[.,]\d+)?|[.,]\d+))\s*([^\d]*)', parts[0])
    if not match:
        # A currency name alone means one unit.
        return [Conversion(Decimal(1), currency(parts[0]), target)]
    prefix, number, suffix = match.groups()
    source = currency(suffix) if suffix.strip() else currency(prefix) if prefix else 'STARS'
    if prefix and currency(prefix) != source:
        raise ValueError('Conflicting units')
    amount = Decimal(number.replace(' ', '').replace('\u00a0', '').replace(',', '.'))
    if not amount.is_finite() or not 0 <= amount <= Decimal('1000000000000') or amount.as_tuple().exponent < -8:
        raise ValueError('Invalid amount')
    return [Conversion(amount, source, target)]


def positive(value):
    result = Decimal(str(value))
    if not result.is_finite() or result <= 0:
        raise ValueError('Invalid exchange rate')
    return result


@dataclass(frozen=True)
class Rates:
    gram_usd: Decimal
    usd_rub: Decimal
    usdt_usd: Decimal
    fetched_at: datetime

    def convert(self, request: Conversion, stars_usd) -> dict[str, Decimal]:
        prices = {'GRAM': positive(self.gram_usd), 'USD': Decimal(1),
                  'USDT': positive(self.usdt_usd), 'STARS': positive(stars_usd),
                  'RUB': Decimal(1) / positive(self.usd_rub)}
        usd = request.amount * prices[request.source]
        return {unit: usd / price for unit, price in prices.items()}


class RateCache:
    def __init__(self):
        self.snapshot = None
        self.updated = 0.0
        self.lock = asyncio.Lock()

    async def fetch(self):
        from bot.wallet_payments import chain_client, USDT_MASTER
        data = await chain_client()._get('/rates', params={'tokens': 'ton,' + USDT_MASTER, 'currencies': 'usd,rub'})
        gram = data['rates']['TON']['prices']
        gram_usd = positive(gram['USD'])
        return Rates(gram_usd, positive(gram['RUB']) / gram_usd,
                     positive(data['rates'][USDT_MASTER]['prices']['USD']), datetime.now(timezone.utc))

    async def get(self):
        if self.snapshot and time.monotonic() - self.updated < 60:
            return self.snapshot
        # Concurrent inline requests share one request, with a bounded response time.
        async with asyncio.timeout(6):
            async with self.lock:
                if self.snapshot and time.monotonic() - self.updated < 60:
                    return self.snapshot
                try:
                    result = await asyncio.wait_for(self.fetch(), timeout=4)
                except Exception:
                    if self.snapshot and time.monotonic() - self.updated < 300:
                        return self.snapshot
                    raise
                self.snapshot, self.updated = result, time.monotonic()
                return result


def number(value: Decimal, unit: str = '') -> str:
    precision = {'RUB': 2, 'USD': 6, 'USDT': 6, 'STARS': 4}.get(unit, 8)
    step = Decimal(1).scaleb(-precision)
    rounded = value.quantize(step)
    if value > 0 and rounded == 0:
        return '<' + format(step, 'f')
    text = format(rounded, 'f')
    return text.rstrip('0').rstrip('.') if '.' in text else text


rate_cache = RateCache()
