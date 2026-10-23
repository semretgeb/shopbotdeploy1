# Deploy checklist — EthioDeploy

## Before the first push
- [ ] `python -m pytest -q` is green locally.
- [ ] `.env` is git-ignored (`git status` must not list it); `.env.example` has placeholders only.
- [ ] Old single-shop files are gone (`main.py`, `setup_flow.py`, `chat_handler.py`, `claude_api.py`, `database.py`, `shopbot.db`).
- [ ] `.python-version` = `3.11`; `requirements.txt` present; `Procfile` present (fallback only).

## EthioDeploy project settings
- [ ] Repo `semretgeb/shopbot`, branch `main`, auto-deploy on push.
- [ ] **Settings → Build → Start command**:
      `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers`
- [ ] Postgres add-on attached (injects `DATABASE_URL`).
- [ ] Environment variables set:
      `BOT_TOKEN` `BOT_USERNAME` `WEBHOOK_SECRET` `PUBLIC_URL` (`https://<subdomain>.ethiodeploy.com`) `ADMIN_TELEGRAM_ID`
      `SUBSCRIPTION_PRICE_ETB` `PAYMENT_ACCOUNT` `GROQ_API_KEY` `ENV=production`
      (optional: `TRIAL_DAYS`, `GROQ_MODEL`, `AI_PER_CUSTOMER_HOURLY`, `AI_PER_SHOP_DAILY`, `AI_GLOBAL_DAILY`, `IMAGE_CACHE_MAX_MB`)
- [ ] `WEBHOOK_SECRET` is a fresh random string (e.g. `python -c "import secrets;print(secrets.token_hex(24))"`).

## Push
```powershell
git add -A
git commit -m "Deploy"
git push origin main
```
- [ ] Build log shows `pip install -r requirements.txt` succeeded and `alembic upgrade head` ran (`Running upgrade -> 0001_initial`).
- [ ] Health check passed; app log line `Webhook set to https://…/telegram/webhook (env=production, db=postgres)`.

## After deploy
- [ ] `https://<subdomain>.ethiodeploy.com/healthz` → `{"ok":true}`.
- [ ] `python -m scripts.set_webhook` (locally, with prod `.env` values) prints `url` = your webhook and `pending_update_count` ≈ 0.
- [ ] `/start` in Telegram answers within 2 s.
- [ ] Create a test shop, add a product with photo, open the link from a second account → image loads via `/api/img/…`.
- [ ] Place a transfer order from the Mini App and upload a screenshot → owner receives card + photo.
- [ ] `/admin stats` from the admin account works; from another account it's denied.
- [ ] BotFather (optional polish): `/setdescription`, `/setabouttext`, `/setuserpic`, `/setcommands` → `start - Open ShopBot`.

## Every later deploy
- [ ] Tests green → push → watch build → `/healthz` → one `/start`.
- [ ] Schema change? Add an Alembic revision (`python -m alembic revision --autogenerate -m "…"`), commit it; the start command applies it.
- [ ] Never run two instances against one Postgres with the expiry loop enabled (it's designed for a single instance).

## Rollback
- [ ] `git revert <commit>` and push; migrations are forward-only, so avoid destructive schema changes.

## Keys & secrets hygiene
- [ ] If a token ever appears in a commit, rotate it in BotFather (`/revoke`) and update the env var.
