# Operations

Telegram bot for buying Stars and Premium, with referrals and support at
[@maneramur](https://t.me/maneramur). Python 3.15.2, managed with uv.

Tasks, earning Stars and the advertising cabinet are removed from the application.
Their historical database tables and migration history are retained to preserve data.

The purchase menu also offers gifts of Stars and Premium to a friend. Enter an
`@username` (numeric IDs and links are rejected); Fragment checks the recipient
before showing amounts or subscription periods. The input can be cancelled.
The recipient stays attached to that order through CryptoBot or SBP payment.

Section photos are uploaded once and their Telegram `file_id` is cached in
PostgreSQL (`telegram_photos`) across chats and restarts. Cache keys include the
bot ID and file SHA-256; replacing an image triggers a new upload. Invalid cached
file IDs are refreshed automatically.

The first `/start` sends an introduction with a “Продолжить?” button. The main
menu opens only after the button is pressed. `users.welcome_accepted` records
this confirmation across restarts; delivery alone does not set it. Existing users
also confirm once, since the historical `welcome_sent` flag only recorded delivery.

## Referrals

An invitation is attributed on a user's first registration, to an existing user;
self-referrals and later reassignment are rejected. Each confirmed purchase earns
the referrer 15% of the Stars quantity. Premium uses its USD price before payment
fees divided by the bot's Stars/USD course when the invoice is created. Rewards
are rounded down to 0.01 Stars and credited to the internal Stars balance.

`referral_payments` records the provider and invoice ID with the reward snapshot.
Crediting this record and updating the exact decimal balance happen atomically;
duplicate checks cannot credit it again. Pending referral invoices are rechecked
after restarts. The existing product-delivery polling remains separate from this
reward recovery.

The Referrals screen shows invited users, total earned and the available internal
balance. Whole-Star withdrawals start at 50; the fractional remainder is retained.
Withdrawals reserve the amount and record the Telegram request before sending.
Uncertain transfers remain `pending` or `review` and block another withdrawal
until reconciled; they must not be automatically retried or refunded, since a
network timeout does not establish whether TON was sent. Confirmed sends include
their transaction hash in `user_withdraws`.

Web page previews are disabled globally. Run the database tests against a
dedicated, disposable PostgreSQL database by setting
`REFERRAL_TEST_DATABASE_URL`; without it, those integration tests are skipped.

## Setup

Use uv 0.13.9 or newer for Python 3.15.2 downloads. The project has its own `.venv`.

```bash
uv python install 3.15.2
uv sync --frozen --all-groups
```

Configure `.env` using `.env.example` as a reference. PostgreSQL is required.
Redis is optional. Existing payment credentials must be reviewed before sales.

```bash
uv run --frozen alembic upgrade head
uv run --frozen python scripts/init_db.py
uv run --frozen python -m bot
```

`init_db.py` creates model tables absent from the initial migration.
Python is pinned in `.python-version`; dependencies are locked in `uv.lock`.

## Docker

```bash
docker compose up --build -d
```

The optional shared database configuration remains in `docker-compose.shared.yml`.
Review its network and database credentials before use.

## Checks

```bash
uv run --frozen pytest
uv pip check
uv run --frozen python -m compileall -q bot scripts migrations
```

## Optional user service

A user systemd unit can run `uv run --frozen python -m bot` with its
`WorkingDirectory` set to your checkout. Keep the unit and runtime credentials
outside version control. Logs are written to `logs/`.
