# Part 2 — owner module: run, test, deploy

## What's new
- `/start` with language picker on first contact, owner/customer role choice
- 5-step onboarding wizard with "Step n of 5", skip on optional steps, resume after redeploy
- Owner home (edited in place): Add product · Products · Orders · Share · Settings · Subscription · Language
- Products: add (photo first → name → price → stock → category → preview), caption shortcut `Name - 1200`,
  paginated list, product card with edit buttons (name/price/stock/photo/category/description), hide/show, delete with confirm
- Share: QR code + link, copy button, forwardable customer message
- Shop settings editing
- Customer deep link `t.me/<bot>?start=<slug>` shows the shop card (Browse/Orders/Ask arrive in Parts 5–6; the
  "Open shop" Mini App button points at `/app/`, which Part 4 delivers)

## Run locally
```powershell
venv\Scripts\activate
pip install -r requirements.txt      # no new packages, safe to skip
python -m pytest -q                  # expect 26 passed
uvicorn app.main:app --reload --port 8000
```
Expose port 8000 with ngrok (`ngrok http 8000`), put the https URL in `.env` as `PUBLIC_URL`, restart uvicorn.

## Manual test (5 minutes)
1. `/start` → language picker → *Create my shop* → complete the 5 steps (try *Skip* on step 4).
2. Home shows "Trial · 14 days left". Tap *➕ Add product*, send a photo with caption `Test Shoe - 1200` → stock *Unlimited* → category *➕ New* → `Shoes` → *Save*.
3. Send another photo with no caption → walks through name/price.
4. *Products* → tap one → edit price → card updates; *Hide* → list shows 👁; *Delete* → confirm.
5. *Share shop* → QR appears; *Copy link* copies; *Forward…* sends the clean message.
6. From a second Telegram account open the shop link → shop card appears; a wrong slug → "doesn't exist".

## Deploy (EthioDeploy)
EthioDeploy builds with Nixpacks and reads the start command from **Settings → Build**. Set it to:
```
alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers
```
`.python-version` pins Python 3.11. The Procfile carries the same command as a fallback.
Env vars (Settings → Environment): `BOT_TOKEN BOT_USERNAME WEBHOOK_SECRET PUBLIC_URL ADMIN_TELEGRAM_ID ENV=production`
(+ `GROQ_API_KEY SUBSCRIPTION_PRICE_ETB PAYMENT_ACCOUNT`). `DATABASE_URL` is injected by the Postgres add-on.

```powershell
git add -A
git commit -m "Part 2: owner onboarding, product management, share/QR"
git push origin main
```
After the deploy is healthy: open `https://<subdomain>.ethiodeploy.com/healthz`, then `/start` in Telegram.
