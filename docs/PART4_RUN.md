# Part 4 — Mini App storefront: run, test, deploy

## What's new
`app/webapp/` — plain HTML/CSS/JS, no build step, served at `/app/`:
- Storefront: search, category chips, 2-col grid (3 on wide screens), stock badges, lazy WebP thumbnails, skeletons
- Product detail with quantity stepper; sticky cart bar; Telegram `MainButton`/`BackButton` used on cart/checkout
- Cart in `localStorage` keyed by shop slug; checkout prefilled from `/api/me`; pay on delivery or transfer
- Confirmation screen with payment info (tap to copy), screenshot upload, "Track in chat" (closes the Mini App)
- My orders; closed-shop and error/offline screens; language toggle (AM/EN) using the same translation files as the bot
- Theme from Telegram's `--tg-theme-*` CSS variables (light/dark follow the client)

## Test
```powershell
python -m pytest -q        # expect 34 passed
```

## Try it in Telegram
1. Run the app with a public HTTPS URL (ngrok locally, or push to EthioDeploy).
2. In BotFather: `/setmenubutton` is optional; the "🛍 Open shop" button in the customer shop card already opens `/app/?shop=<slug>`.
3. From a second Telegram account open `t.me/<bot>?start=<slug>` → tap **🛍 Open shop**.
4. Add products, checkout with *Transfer*, upload any screenshot → the owner receives the order card + the photo.

Opening `/app/` in a normal browser shows "Please open this shop from Telegram" (no initData → 401), which is expected.

## Deploy
```powershell
git add -A
git commit -m "Part 4: Mini App storefront"
git push origin main
```
