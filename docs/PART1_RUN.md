# Part 1 — run, test, deploy

## Run locally
```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # fill BOT_TOKEN, WEBHOOK_SECRET, ADMIN_TELEGRAM_ID
alembic upgrade head                                   # creates shopbot.db (SQLite)
uvicorn app.main:app --reload --port 8000
```
Telegram needs a public HTTPS URL for the webhook. For local testing:
```bash
ngrok http 8000            # or: cloudflared tunnel --url http://localhost:8000
# put the https URL in .env as PUBLIC_URL, restart uvicorn (it re-sets the webhook on start)
```
Then send `/ping` to the bot → "ShopBot core is alive ✅". `GET http://localhost:8000/healthz` → `{"ok":true}`.

## Test
```bash
pytest -q
```
Covers: initData HMAC (valid / tampered / wrong token / expired / garbage), API dependency chain
(401 / 404 / 400 / 403 shop_paused), slug rules, per-shop customer isolation, cascade delete,
subscription math, money formatting.

## Push & deploy (EthioDeploy auto-detects requirements.txt + Procfile)
```bash
git add -A
git commit -m "Part 1: core, DB, migrations, initData auth, webhook"
git push origin main
```
Set these env vars in the EthioDeploy dashboard (same names as .env.example):
`BOT_TOKEN BOT_USERNAME WEBHOOK_SECRET PUBLIC_URL ADMIN_TELEGRAM_ID DATABASE_URL ENV=production`
(`DATABASE_URL` comes from the managed Postgres; the `release:` line in the Procfile runs migrations on every deploy.)
Verify: `https://<SUBDOMAIN>.ethiodeploy.com/healthz` and `/ping` in Telegram.
