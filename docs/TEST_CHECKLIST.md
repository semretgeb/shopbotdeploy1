# Manual test checklist

Needs: the admin account (A), two other Telegram accounts — Owner 1 (O1), Owner 2 (O2) — and one more as Customer (C).
Run on at least two devices (one Android, one iOS if possible). Tick each line.

## 1. Onboarding and language
- [ ] C `/start` with no link → language picker → "Create my shop / I'm a customer" screen.
- [ ] O1 `/start` → አማርኛ → 🏪 Create my shop → completes 5 steps; "Step 2 of 5" visible; Skip works on steps 4–5; phone via 📱 Share my number.
- [ ] O1 sees home with `Trial · 14 days left`; A receives "🆕 New shop" notice.
- [ ] Kill the app mid-wizard (or redeploy) → O1 `/start` → wizard resumes at the right step.
- [ ] O2 creates "Bethel Cosmetics" in English. Slug is ASCII (`bethel-cosmetics`); an Amharic-only name gets `shop-xxxxxx`.
- [ ] 🌐 Language switches every screen; prices show as `1,200 ብር` in Amharic and `ETB 1,200` in English.

## 2. Products (O1 and O2 each add 3)
- [ ] Photo with caption `Red Shoes - 1200` skips name/price; stock ♾ Unlimited; new category "Shoes".
- [ ] Photo without caption → asks name → price (`99.5`, `1,200`, `1200 ብር` all accepted; `free` rejected).
- [ ] Owner adds 3 products in under 5 minutes (proposal success metric).
- [ ] Products list paginates (add 6+); tap → card; edit price → card updates; 👁 Hide → list shows 👁 and customers don't see it; Delete asks confirmation.
- [ ] Sending a photo while idle starts "Add product" directly.

## 3. Sharing
- [ ] 🔗 Share shop → QR image + link; 📋 Copy link copies; "Forward…" gives a clean message.
- [ ] Scanning the QR on another phone opens the bot with the shop.

## 4. Customer — Mini App
- [ ] C opens O1's link → shop card → 🛍 Open shop → storefront loads in < 3 s on mobile data; skeletons shown while loading.
- [ ] Category chips filter; search filters; out-of-stock product shows badge and has no + button.
- [ ] Add from grid (+) and from detail (stepper); sticky cart bar shows count + total; MainButton on cart/checkout.
- [ ] Checkout validates name/phone/address; pay on delivery → confirmation screen with order code.
- [ ] Transfer order → payment info box (tap copies), upload screenshot (JPG/PNG < 5 MB) → "Screenshot sent".
- [ ] Second order: checkout form is prefilled from the first.
- [ ] 🧾 My orders lists both; tapping opens details; status badge matches.
- [ ] Opening `/app/` in a desktop browser shows "Please open this shop from Telegram".
- [ ] Dark theme in Telegram → Mini App follows.

## 5. Customer — chat fallback
- [ ] 📋 Browse here → categories → products → ➕ Add → 🛒 Cart → ✅ Checkout → saved details offered as buttons → 🏦 Transfer → ✅ Place order.
- [ ] Customer sends a photo later → attached to the unpaid order; owner gets it as a reply to the card.
- [ ] Stock: order the last unit from two accounts — second gets "Not enough stock".

## 6. Owner — orders and notifications
- [ ] O1 receives the order card instantly with Confirm / Reject / Call; 📞 Call sends a contact card.
- [ ] ✅ Confirm → C's status message edits to "Confirmed" + one-line ping; 🚚 On the way; 📦 Delivered.
- [ ] ❌ Reject with a reason → C sees the reason; product stock restored.
- [ ] 🧾 Orders tabs show the right counts; History holds delivered/rejected.

## 7. AI assistant
- [ ] C asks "how much are the red shoes?" (English) → correct price from shop data, in English.
- [ ] C asks in Amharic → answer in Amharic.
- [ ] "Can I get a discount?" → "📨 sent to the shop"; O1 gets ❓ card → ✍️ Reply → C receives the reply; card marked answered.
- [ ] Ask about a product that exists only in O2's shop → assistant does NOT know it (forwards or says not available).
- [ ] 11th question within an hour → "⏳ Too many questions".
- [ ] O1: ⚙️ Shop settings → 🤖 Assistant OFF → C's text gets the contact message.

## 8. Shop-to-shop isolation (must all pass)
- [ ] C opens O1's link then O2's link: product lists differ; cart in the Mini App is separate per shop.
- [ ] C's saved checkout details entered in O1's shop are NOT prefilled in O2's shop.
- [ ] Mini App request with O1's `?shop=` but O2's product id in the URL → 404 (`/api/products/<id>`).
- [ ] Forged `X-Telegram-Init-Data` (edit one character) → 401 on every `/api/*` call.
- [ ] O2 never receives O1's orders, questions, or payment screenshots.
- [ ] O1's 🧾 Orders never lists O2's orders; `/admin shop <id>` counts match each shop.
- [ ] Automated: `python -m pytest -q tests/test_isolation.py tests/test_api.py tests/test_products.py` → all green.

## 9. Subscription and admin
- [ ] O1: 💳 Subscription → I paid → photo → A receives card → ✅ Approve 1m → O1 notified; home shows "Active · 30 days".
- [ ] A: `/admin pause <id>` → O1's home becomes the paused screen; C's Mini App shows "Temporarily closed"; chat shows closed message. `/admin resume <id>` restores.
- [ ] A: `/admin stats` numbers match; `/admin broadcast test` → preview → 📣 Send reaches O1 and O2.
- [ ] Non-admin sends `/admin` → "⛔ Admin only".
- [ ] Expiry: set a shop's `trial_ends_at` to yesterday in the DB → within an hour it's paused and the owner is messaged.

## 10. Robustness
- [ ] Redeploy during a chat checkout → the customer can continue from the same step.
- [ ] Bot restarted: owner's old order card buttons still work.
- [ ] Very long product name/description is truncated, never crashes; `*` `_` in names render safely.
- [ ] `/healthz` returns `{"ok":true}` after deploy.
