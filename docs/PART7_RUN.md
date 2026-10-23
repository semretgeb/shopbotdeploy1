# Part 7 — subscription + admin

## What's new
- **Owner**: 💳 Subscription screen (trial/active/paused, access-until date, price, account) → *✅ I paid — send screenshot*
  → the photo lands in **your** chat with ✅ Approve 1m · ✅ Approve 3m · ❌ Reject buttons.
- **Admin** (`ADMIN_TELEGRAM_ID` only):
  `/admin` (help + buttons) · `/admin shops [page]` · `/admin shop <id>` · `/admin approve <id> <months>` ·
  `/admin extend <id> <days>` · `/admin pause <id> [reason]` · `/admin resume <id>` · `/admin stats` · `/admin broadcast <text>` (preview → 📣 Send).
  Every shop card has Approve / Pause / Resume buttons. You're notified when a new shop is created.
- **Expiry job**: runs hourly inside the web process — pauses shops whose trial/paid period ended (owner notified with
  payment instructions) and warns owners 3 days before (once per period).
- Owners are notified on approve / extend / pause / resume / reject.

## Test
```powershell
python -m pytest -q        # expect 48 passed
```

## Manual test
1. Owner: 💳 Subscription → I paid → send any photo. Admin account receives the card → ✅ Approve 1m →
   owner gets "🎉 Payment confirmed… until <date>", home shows "✅ Active · 30 days left".
2. `/admin shops` → tap a shop → ⏸ Pause → owner's home turns into the paused screen; Mini App shows "Temporarily closed";
   ▶️ Resume restores it.
3. `/admin stats`, `/admin broadcast Hello owners!` → 📣 Send.
4. To test expiry quickly: in SQLite set `trial_ends_at` to the past for a shop, restart the app, wait ~30 s.

## Deploy
```powershell
git add -A
git commit -m "Part 7: subscription and admin"
git push origin main
```
