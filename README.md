<div align="center">

# ✦ Syndicate Stars

### Telegram Stars and Premium for yourself or a friend

[![Issues](https://img.shields.io/github/issues/SkrudjReal/syndicate-stars?style=for-the-badge&color=c4b5fd&labelColor=19152e)](https://github.com/SkrudjReal/syndicate-stars/issues)
[![Pull requests](https://img.shields.io/github/issues-pr/SkrudjReal/syndicate-stars?style=for-the-badge&color=a5b4fc&labelColor=19152e)](https://github.com/SkrudjReal/syndicate-stars/pulls)
[![Stars](https://img.shields.io/github/stars/SkrudjReal/syndicate-stars?style=for-the-badge&color=f0abfc&labelColor=19152e)](https://github.com/SkrudjReal/syndicate-stars/stargazers)
[![Forks](https://img.shields.io/github/forks/SkrudjReal/syndicate-stars?style=for-the-badge&color=c4b5fd&labelColor=19152e)](https://github.com/SkrudjReal/syndicate-stars/forks)

<img src="media/syndicate_main_page.jpeg" alt="Syndicate Stars Telegram shop" width="100%">

[Quick start](#quick-start) · [Features](#features) · [Documentation](docs/operations.md) · [Report an issue](https://github.com/SkrudjReal/syndicate-stars/issues/new)

</div>

---

Buy Telegram Stars or gift Stars and Premium to a friend by `@username`.
The bot uses Python 3.15.2, uv, aiogram and PostgreSQL.

## Features

| Feature | Behavior |
| :--- | :--- |
| Purchases | Stars from 50; Premium for 3, 6 or 12 months |
| Gifts | Recipient validation through Fragment; usernames only |
| Payments | CryptoBot and FreeKassa SBP integrations; provider credentials required |
| Referrals | 15% credited to the internal balance with duplicate protection |
| Withdrawals | From 50 Stars, with persistent reservations and transfer review |
| Welcome | One-time confirmation, premium emoji and cached Telegram photo IDs |

## Quick start

Requirements: uv 0.13.9 or newer, PostgreSQL, a Telegram bot token and configured
payment/delivery credentials. Redis is optional.

```bash
git clone https://github.com/SkrudjReal/syndicate-stars.git
cd syndicate-stars
cp .env.example .env
uv python install 3.15.2
uv sync --frozen --all-groups
```

Fill in `.env`, create the configured PostgreSQL database, then run:

```bash
uv run --frozen alembic upgrade head
uv run --frozen python -m bot
```

Docker setup, referral calculations, transfer reconciliation and operating limits
are described in [Operations](docs/operations.md).

## Checks

```bash
uv run --frozen pytest
uv pip check
```

PostgreSQL integration tests require a disposable database configured via
`REFERRAL_TEST_DATABASE_URL`; otherwise those tests are skipped.

> [!IMPORTANT]
> Pending referral rewards recover after restarts; product-delivery polling is
> separate. Never automatically retry or refund a transfer with an uncertain
> outcome. Reconcile its recorded status and transaction first.

## License and attribution

[MIT](LICENSE). Based on the original bot template by Bupyc; its copyright notice
is preserved. Support: [@maneramur](https://t.me/maneramur).
