# Operations

Telegram bot for buying Stars and Premium, with referrals and support at
[@maneramur](https://t.me/maneramur). Python 3.15.2, managed with uv.

Tasks, earning Stars and the advertising cabinet are removed from the application.
Their historical database tables and migration history are retained to preserve data.

The main menu has a separate "Купить Звёзды другу" section for gifts of Stars
and Premium; the regular purchase section contains only purchases for yourself
and the calculator. In the gift section choose a Stars amount (including custom
amounts) or Premium period before entering an `@username`. Numeric IDs, links and
the payer's own username are rejected; Fragment checks the recipient using the
selected Premium period where applicable. The input can be cancelled.
The FSM stores the original message ID and caption/text type. Valid user input
is deleted, and payment categories replace that original bot message. Validation
errors edit the same message and retain the FSM; no additional bot message is
sent. A cancelled or replaced prompt invalidates an in-flight Fragment result.
The recipient stays attached to that order through CryptoBot or SBP payment.
Cancelling recipient input or returning from gift amounts/subscription periods
opens the gift section and clears unfinished recipient input.
The gift entry in the main menu is neutral. Inside, both sections use matching
labels and styles: primary Stars/Premium buttons, a neutral calculator and a red
return button. Only the gift section starts recipient username input; its
calculator returns to the gift section.

Section photos are uploaded once and their Telegram `file_id` is cached in
PostgreSQL (`telegram_photos`) across chats and restarts. Cache keys include the
bot ID and file SHA-256; replacing an image triggers a new upload. Invalid cached
file IDs are refreshed automatically.

The first `/start` sends an introduction with a “Продолжить?” button. The main
menu opens only after the button is pressed. `users.welcome_accepted` records
this confirmation across restarts; delivery alone does not set it. Existing users
also confirm once, since the historical `welcome_sent` flag only recorded delivery.

## Inline converter

On the bot owner's Telegram account, use BotFather `/setinline`, select your
bot and set a placeholder such as "Сумма и валюта: 10 рублей в грам или 100 stars".
This setting cannot be enabled with the Bot API token alone. The running bot
must receive `inline_query` updates; no webhook is needed when polling.

An empty inline query offers conversions for one GRAM and one STARS. Examples:
`@syndistars_bot 10 рублей в грам`, `100 звёзд в рубли`, `5 долларов в звезды`,
`1 ton to stars`, `1,5 usdt -> rub`. An amount without a currency means Stars.
GRAM and TON are aliases for the native coin in this converter. USD and USDT
are separate units. Results use the configured Stars/USD course and TonAPI's
USD/RUB/native coin/USDT rates, without payment commissions or invoice creation.

External rates are shared across queries for 60 seconds, with a bounded fetch
timeout and a fallback to a cached snapshot up to five minutes old. Results
display the snapshot time; unavailable or older rates produce an explanatory
article instead of a fabricated conversion. Inline usage does not register a
new user or assign a referrer. Selecting a result sends only its conversion text.
Inline results match the calculator's style: a bold heading, separate blockquotes
for the conversion and currency breakdown, highlighted values and ordinary emoji.

## Admin panel and broadcasting

Set `ADMINS` in the private `.env` to a JSON list of Telegram user IDs. The main
menu's admin button is rendered only for those IDs; `/admin`, callbacks and
draft messages independently check the actor's ID and require a private chat.
Callback authentication uses the clicking user, never the author of the bot's
message. Usernames are not used as authorization credentials.

Broadcasting uses [aiogram_broadcaster](https://github.com/loRes228/aiogram_broadcaster)
0.6.8 (MIT). The panel supports composing one post or album, previewing only to
the current admin, optional URL buttons, recipient-count confirmation, statistics
and stopping a running mailing. There is no scheduled or automatic mass send.

Text, custom emoji entities, formatting and media file IDs are retained using
`MessageSendContent`; albums use `MediaGroupContent` with ordered file IDs and
original caption entities. Source callback buttons are removed; URL buttons
retain their icons. Album URL buttons are attached to the last delivered item.
Supported post types are text, photo, video, animation, document, audio, voice,
video note and sticker. Protected posts and unsupported service/payment posts
are rejected. URL buttons can be configured as `Label | https://example.com`,
one per line, or removed with `-`.

Recipients are snapshotted from the bot's user table when a draft becomes a
mailer. Merely composing or previewing does not deliver to that audience.
Sending requires the separate confirmation action. Only one mailing runs at a
time, throttled to roughly 20 messages/second, accounting for album size. Paid
broadcasts are disabled. A small adapter retries explicit `RetryAfter` responses
before recording delivery statistics; blocked users and ambiguous network errors
are not automatically retried.

The library's records are stored in `broadcast_mailers` in PostgreSQL, including
content, recipient snapshot and progress, without bot tokens. After a restart,
unfinished mailers are restored paused and require manual confirmation to resume.
Telegram sending and database progress persistence are separate operations: a
crash between them can leave the last recipient uncertain. Review interrupted
mailings before resuming; exactly-once delivery is not guaranteed by Telegram.

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

## PM2 and payment notifications

### Direct wallet payments

Stars and Premium both offer TON and USDT on TON, alongside the existing
CryptoBot and FreeKassa methods. Set `TONAPI_RECEIVE_ADDRESS` to the receiving
mainnet wallet. `TONAPI_API_KEY` is used for rates and transaction lookup; it
shares the Fragment wallet client's 1 request/second limiter and 429 retries.
The payment selector is grouped into rubles/SBP/cards, cryptocurrency and other
methods, for both Stars and Premium. Category navigation edits the current
message and preserves gift recipients, quantities and subscription periods.
CodeePay SBP/cards, Platega SBP/crypto, Iris, UAH and LolzTeam buttons
show an unavailable alert until their integrations and credentials are added.
No payment links or unverified prices are issued for those methods yet. Existing
FreeKassa SBP/card and CryptoBot routes remain available inside their categories.

xRocket uses the [current Pay API](https://docs.xrocket.exchange/api/pay/pay-api-overview),
not the deprecated Legacy API or its installed historical SDK. Set private
`XROCKET_TOKEN` (Bearer authorization) and `XROCKET_WEBHOOK_TOKEN` (webhook HMAC
secret). These credentials are different and must never be put in Git or logs.
Both Stars and Premium, including gifts, use a fixed-price USDT invoice. The
2% markup is included in the quoted amount; the provider's own fee is paid by
the application, not added again to the payer. The USD quote is converted using
the cached USDT/USD rate and rounded up to cents. Invoices expire in 15 minutes;
the API's `expiresIn` value is milliseconds.

Expected amount, product, gift recipient and reward base are committed before
creating a remote invoice. `clientInvoiceId` is stable across an ambiguous POST:
the client reads the invoice back by that same ID rather than creating another.
The shared durable invoice/delivery ledger uses `provider=xrocket`; direct-chain
scans cannot confirm a hosted invoice. Only exact `paid` status with matching
invoice ID, client ID, USDT currency and amount enables the existing atomic
delivery claim. Duplicate API checks and webhooks cannot repeat fulfillment or
referral credit. Pending orders recover after restart. Only explicit HTTP 429
responses are retried with `Retry-After`; no payouts or withdrawals are exposed.

Polling works locally without any public callback. When deploying the receiver,
optionally set `XROCKET_CALLBACK_URL` to your public HTTPS origin followed by
`/notifications/xrocket`. Include the updated nginx location and restart the
receiver. Do not set this URL to an old deployment that lacks the handler or to
a receiver using a different database from the bot. Alternatively configure the
same URL in the app's xRocket settings.

The receiver verifies the raw-body HMAC-SHA256 (`Signature`, `Signature-Version:
v1`, and a millisecond `Signature-Timestamp` within five minutes) before parsing
or accessing orders. It commits verified invoice status before returning HTTP
200. Non-completion and unknown events are acknowledged without delivery;
expiry is detected by polling. Out-of-order `active` events cannot downgrade a
paid or fulfilled order. See [signature verification](https://docs.xrocket.exchange/api/pay/webhooks/signature).

Direct invoices last 15 minutes and contain a unique mandatory memo. Amounts
are rounded up to 4 decimals for TON or 2 for USDT using TonAPI's USD quote.
The transfer link uses token atomic units (9/6 decimals). The sender pays
network fees. Existing CryptoBot/FreeKassa commissions are unchanged.

`wallet_invoices` captures the bot, payer, gift recipient, product, amount,
receiving wallet, referral reward base and expiry before showing an invoice.
The worker checks raw inbound transaction BOCs, not mutable event actions:
destination, successful execution, exact memo and amount, and creation time.
Non-bounceable native TON credits to undeployed wallets are accepted only
with a credit phase, `no_state` compute result and no outgoing messages.
USDT transactions must arrive at the wallet derived from the official Tether
master and contain a successful TEP-74 `internal_transfer` with a text memo.
Unknown tokens, bounced/failed transfers and wrong amounts are not credited.
Transaction hashes are unique and delivery requires an atomic database claim.

Pending invoices are scanned for 24 hours, including after restarts. Transfers
after invoice expiry are held for manual review. Unmatched transfers (wrong
memo/amount, no comment, older than the scan window) require reconciliation.
At most 1,000 transactions per receiving account are scanned in one pass;
high-volume accounts require a persistent chain cursor before wider rollout.

Delivery claims are durable: after restart, interrupted `processing` orders
become `review` and never send automatically again. Fragment failures before
attempting a TON transfer credit purchased Stars to the payer's reserve once;
Premium failures and ambiguous transfer results go to review. A successful
transfer stores its delivery hash. Do not automatically retry review orders
or refund uncertain sends without checking the chain.

Reference: [TON wallet links](https://docs.ton.org/onboarding/wallet-apps/deep-links),
[TEP-74](https://github.com/ton-blockchain/TEPs/blob/master/text/0074-jettons-standard.md),
[TonAPI guidance on event actions](https://docs.tonapi.io/tonapi/rest-api/accounts).

### HTTP receiver

Install the locked environment and apply migrations before starting the processes:

```bash
uv sync --frozen --no-dev --no-group test
.venv/bin/python -m alembic upgrade head
mkdir -p logs
pm2 start ecosystem.config.cjs
pm2 save
```

The manifest runs one bot process (`syndicate-stars`) and one HTTP receiver
(`payment-notifications`). Stop the old bot before switching hosts. Transfer a
consistent PostgreSQL dump, `.env` with mode 600, and the two current media files;
the database includes welcome confirmations, referral balances and cached file IDs.
Keep dump files private. Configure PM2's systemd startup service for reboot recovery.

The receiver binds to `127.0.0.1:8789`. The supplied
`deploy/payment-notifications.conf` exposes only its routes on a second loopback
listener (`8790`), suitable for Tailscale Funnel HTTPS termination. Existing Funnel
ports can be retained by publishing this listener on a separate HTTPS port.
Neither process requires the development machine after migration.

Configure these URLs on your public HTTPS origin in FreeKassa:

| Setting | Path | Method |
| --- | --- | --- |
| Notification | `/notifications/payment` | POST |
| Successful return | `/return/success` | GET |
| Failed return | `/return/failure` | GET |

`/health` returns HTTP 200 when the receiver is running. It does not validate
Telegram credentials or claim that payment providers are operational.

Set `FREKASSA_SECRET_WORD_2` to the same secret word 2 configured in the merchant
dashboard. This is separate from the API key. Without a configured secret and
merchant ID the notification route responds with 503. Keep access logging disabled
for these routes; callbacks may contain payer information and signatures.

Orders are recorded before their payment URL is issued. The receiver verifies the
signature, merchant and saved RUB amount before committing a receipt. It returns
`YES` only after commit; repeated transaction IDs cannot confirm another order.
Browser return URLs redirect to the bot and never confirm a payment. The existing
payment poller reads verified receipts before querying FreeKassa's status API.

Receipt persistence does not add product-delivery recovery: the existing delivery
poller still runs for about five minutes and is lost on bot restart. Reconcile
paid but undelivered orders after downtime before retrying any transfers.
