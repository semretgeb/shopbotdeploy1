# ShopBot — multi-shop Telegram SaaS for small shops in Ethiopia

One shared Telegram bot serves many shops. Owners set up a shop and manage products and orders **in chat**;
customers open the shop's link, browse a **Telegram Mini App storefront** (or order with chat buttons),
and ask a bilingual **AI assistant** that only knows that shop's data. Revenue: monthly ETB subscription
after a 14-day trial, approved manually by the admin.

```
Owner  ──chat──▶  🤖 @YourShopBot  ◀──chat/Mini App──  Customer
                        │
          FastAPI (webhook + API + static Mini App)
                        │
        SQLite (local) / PostgreSQL (EthioDeploy)
```

## Features (MVP)
| Area | What |
|---|---|
| Onboarding | 5-step wizard (name, description, phone, delivery, payment), resumable, Amharic/English |
| Products | Add (photo first, caption shortcut `Name - 1200`), list, edit any field, hide/show, delete, categories |
| Sharing | Deep link `t.me/<bot>?start=<slug>` + QR code |
| Mini shop | Grid, categories, search, detail, cart, checkout, pay on delivery / transfer + screenshot, order confirmation, my orders |
| Chat fallback | Same ordering flow with buttons only |
| Orders | Owner card with Confirm / Reject (reason) / On the way / Delivered / Call; customer status edited in place |
| AI | Groq LLaMA 3.3 70B, shop-only context, forwards unknowns to the owner, rate-limited (customer/shop/global) |
| Subscription | 14-day trial → paused; owner sends payment screenshot → admin approves; hourly expiry + 3-day warning |
| Admin | `/admin shops · shop · approve · extend · pause · resume · stats · broadcast` |
| i18n | `app/locales/{am,en}.json` shared by bot and Mini App; prices as `1,200 ብር` / `ETB 1,200` |

## Project layout
```
app/
  main.py            FastAPI app: webhook, API, static Mini App, hourly expiry loop
  config.py          settings from .env
  bot/               python-telegram-bot v21 in webhook mode
    router.py        DB-backed state dispatch (@on_state / @on_callback)
    context.py       per-update Ctx (db session, user, lang, render-in-place helpers)
    handlers/        start, onboarding, products, share, orders_owner, shop_customer, assistant, subscription, admin
  api/               deps (initData HMAC → shop → subscription gate), shop, products, customer, orders, images, i18n, webhook
  db/                SQLAlchemy models + repo/ (every function takes shop_id)
  services/          telegram_auth, subscription, notifications, ai, images (file_id → WebP proxy), qr, money, slug
  locales/           am.json, en.json
  webapp/            Mini App (plain HTML/CSS/JS, no build step)
migrations/          Alembic
tests/               pytest (51 tests, no network)
docs/                DESIGN.md, PART*_RUN.md, TEST_CHECKLIST.md, DEPLOY_CHECKLIST.md
```

## Run locally (Windows PowerShell)
```powershell
py -3.11 -m venv venv        # or: python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env       # then fill in the values (see below)
python -m alembic upgrade head
python -m pytest -q
uvicorn app.main:app --reload --port 8000
```
Telegram needs a public HTTPS URL for the webhook: `ngrok http 8000`, put the https URL in `.env` as `PUBLIC_URL`,
restart uvicorn (the webhook is set on startup). Then `/start` the bot.

## Environment variables
| Name | Purpose |
|---|---|
| `BOT_TOKEN`, `BOT_USERNAME` | from @BotFather (username without `@`) |
| `WEBHOOK_SECRET` | any long random string; Telegram echoes it on every webhook call |
| `PUBLIC_URL` | `https://<subdomain>.ethiodeploy.com` (no trailing slash) |
| `ADMIN_TELEGRAM_ID` | your Telegram user id (from @userinfobot) |
| `DATABASE_URL` | default SQLite; EthioDeploy's Postgres add-on injects it |
| `SUBSCRIPTION_PRICE_ETB`, `PAYMENT_ACCOUNT`, `TRIAL_DAYS` | business settings shown to owners |
| `GROQ_API_KEY`, `GROQ_MODEL` | AI assistant (`llama-3.3-70b-versatile`) |
| `AI_PER_CUSTOMER_HOURLY`, `AI_PER_SHOP_DAILY`, `AI_GLOBAL_DAILY` | rate limits |
| `IMAGE_CACHE_DIR`, `IMAGE_CACHE_MAX_MB` | image proxy cache (ephemeral is fine) |
| `ENV` | `production` keeps pending updates on restart |

## Deploy on EthioDeploy
Nixpacks auto-detects Python (`requirements.txt`, `.python-version` = 3.11). In **Settings → Build** set the start command:
```
alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers
```
Add the env vars above, attach the Postgres add-on, push to `main`. See `docs/DEPLOY_CHECKLIST.md`.

## How the pieces fit
- **Tenant isolation** — every table that holds shop data has `shop_id`; every repo function requires it; the API
  resolves the shop from the verified `start_param` (or the `?shop=` the bot itself put in the button URL) and
  never from the request body. `tests/test_isolation.py` and `tests/test_api.py` prove two shops cannot see each other.
- **Mini App auth** — `X-Telegram-Init-Data` is HMAC-verified on every `/api/*` request (24 h max age).
- **Photos** — Telegram `file_id` is the source of truth; `/api/img/{file_id}?w=320|640` re-encodes to WebP with a
  disk LRU cache. Payment screenshots uploaded from the Mini App are sent to the owner's chat and the returned
  `file_id` is stored. Nothing needs object storage.
- **Conversation state** — `chat_states` table, so redeploys never lose a wizard in progress.
- **Money** — integer santim in the DB, formatted per language on output.

## Known limitations / next
- One shop per owner; no staff accounts; no owner web dashboard (by design for MVP).
- Amharic copy has not yet been reviewed by a native speaker (see proposal D8) — all strings are in
  `app/locales/am.json`, edit freely; `tests/test_locales.py` keeps both files in sync.
- Image cache lives on the dyno's disk (cleared on redeploy, refilled on demand).
- Expiry job runs inside the single web process; fine for one instance.
