# CLAUDE.md — ShopBot (multi-shop Telegram SaaS, Ethiopia)

Read this first. `README.md` has the user-facing overview; `docs/DESIGN.md` is the architecture contract.

## What this is
One shared Telegram bot serving many shops. Owners manage products/orders **in chat**; customers use a
**Telegram Mini App** (`app/webapp/`, plain HTML/JS) or button-only chat fallback; a Groq LLaMA assistant answers
from that shop's data only; monthly ETB subscription after a 14-day trial, approved manually by the admin.
All 9 delivery parts are complete (core → owner → API → Mini App → chat ordering → AI → subscription/admin → i18n → docs).

## Stack
Python 3.11 · FastAPI · python-telegram-bot v21/22 in **webhook mode inside FastAPI** (no polling, no worker) ·
SQLAlchemy 2 + Alembic · SQLite locally / Postgres in prod · Groq SDK · Pillow · qrcode · pytest.
Entry point: `app/main.py` (lifespan builds the PTB app, sets the webhook, starts an hourly expiry loop).

## Commands (Windows PowerShell, venv is `venv\`, Python 3.14 locally — fine)
```powershell
venv\Scripts\activate
pip install -r requirements.txt
python -m alembic upgrade head          # local SQLite shopbot.db
python -m pytest -q                      # 51 tests, no network, Groq never called
uvicorn app.main:app --reload --port 8000   # needs a public https PUBLIC_URL (ngrok) for the webhook
```
Settings come from `.env` (never commit it; `.env.example` is the template). Required: `BOT_TOKEN BOT_USERNAME
WEBHOOK_SECRET PUBLIC_URL ADMIN_TELEGRAM_ID`; optional: `DATABASE_URL` (default SQLite), `GROQ_API_KEY`, `AI_*`,
`SUBSCRIPTION_PRICE_ETB`, `PAYMENT_ACCOUNT`, `TRIAL_DAYS`, `ENV`.

## Deploy (EthioDeploy, Nixpacks)
- Git remotes: `origin` = `semretgeb/shopbot` (source of truth), `deploy` = `semretgeb/shopbotdeploy1`
  (**what EthioDeploy actually builds**). Always push both: `git push origin main && git push deploy main`.
  If `deploy` is missing: `git remote add deploy git@github.com:semretgeb/shopbotdeploy1.git`.
- Start command is set in EthioDeploy **Settings → Build** (Procfile is only a fallback):
  `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers`
- Live URL: `https://shopbotdeploy1.ethiodeploy.com` · health: `/healthz` · webhook: `/telegram/webhook`
- `.python-version` pins 3.11; Postgres add-on injects `DATABASE_URL`; migrations run on every start.
- Diagnostic: `GET /debug/webhook?key=<WEBHOOK_SECRET>` → bot username, registered vs expected webhook,
  pending updates, Telegram's last_error_message. Use it before guessing.
- The Bot API (`api.telegram.org`) is often unreachable from Ethiopian networks: local scripts that call
  Telegram time out. Diagnose from the server (the endpoint above or the Logs tab), not from the PC.
- An old **Render** service once hosted the hello-world bot and re-registers the webhook to its own URL on
  restart. It must stay deleted/suspended.

## Current status (as of 2026-10-23)
- Live on EthioDeploy and serving `@yene_sukbot`; `/start` replies, webhook healthy.
- Earlier the deploy was silent because EthioDeploy's `BOT_TOKEN` pointed to a different bot (`ool90_bot`), so
  Telegram was delivering updates for `@yene_sukbot` to whoever else held that token. Fix was to set
  `BOT_TOKEN` + `BOT_USERNAME` in EthioDeploy env to the `yene_sukbot` values and restart. Found via
  `/debug/webhook` (`bot_username` ≠ expected); this is still the first thing to check if updates stop.
- Remaining non-code work from the proposal: native Amharic review of `app/locales/am.json`; pilot kit.

## Architecture rules (do not break)
1. **Tenant isolation**: every table with shop data has `shop_id`; every `app/db/repo/*` function takes `shop_id`
   explicitly; API handlers get the shop from `app/api/deps.py` (verified initData `start_param`, or `?shop=` the bot
   itself put in the button URL — storefronts are public, identity is what's signed), never from the body.
2. **Mini App auth**: `X-Telegram-Init-Data` HMAC-verified on every `/api/*` request (`services/telegram_auth.py`).
3. **Subscription gate**: `services/subscription.is_shop_open()` is the single source of truth for bot and API.
4. **Conversation state** lives in the `chat_states` table (`bot/router.py` dispatches by `@on_state` / `@on_callback`
   namespace). No PTB `ConversationHandler`, no in-memory state — redeploys must not lose wizards.
5. **Money** = integer santim in DB; format with `services/money.fmt_price(santim, lang)` → `1,200 ብር` / `ETB 1,200`.
6. **Photos** = Telegram `file_id`; served via `/api/img/{file_id}?w=320|640` (WebP, disk LRU cache). Payment
   screenshots uploaded from the Mini App are sent to the owner's chat and the returned `file_id` is stored.
7. **i18n**: every user-facing string is a key in `app/locales/{en,am}.json` (same keys, same placeholders —
   `tests/test_locales.py` enforces it). Bot uses `ctx.t(key)`, Mini App fetches `/api/i18n/{lang}`.
   Escape user text in Markdown with `services/notifications._md()`.
8. **Callback data** format `ns:action:arg…`, ≤ 64 bytes. Namespaces in use: start lang home cancel noop skip onb prod
   prodw share settings ord ordp cust custp custw ask fq subs adm.
9. UX: buttons over typing, edit messages in place (`ctx.render`), every screen has Back + Home.

## Layout
```
app/main.py  config.py  logging_conf.py
app/bot/      application.py router.py context.py keyboards.py states.py
              handlers/ start onboarding products share orders_owner shop_customer assistant subscription admin
app/api/      deps.py schemas.py shop products customer orders images i18n webhook
app/db/       base.py models.py repo/ users shops products customers orders states forwarded ai_usage
app/services/ telegram_auth subscription notifications ai images qr money slug
app/locales/  en.json am.json           app/webapp/ index.html css/ js/(api i18n cart ui app) img/
migrations/   Alembic (0001_initial)    tests/ 51 tests (FakeBot / FakeProvider, SQLite file db)
docs/         DESIGN.md PART1..7_RUN.md TEST_CHECKLIST.md DEPLOY_CHECKLIST.md
```

## Conventions
- Small functions, comments only where logic is non-obvious, type hints, no new deps without need.
- Schema change → new Alembic revision (`python -m alembic revision --autogenerate -m "…"`), commit it.
- New user-facing text → add to **both** locale files in the same change.
- Tests: add to the matching `tests/test_*.py`; never call Telegram or Groq in tests (use the fakes in
  `tests/test_api.py` / `tests/test_ai.py`). Run `python -m pytest -q` before every commit.
- Commit message style: `Part N: …` for feature chunks, otherwise imperative one-liners.
- LF line endings (`.gitattributes`); ignore the CRLF warnings on Windows.
