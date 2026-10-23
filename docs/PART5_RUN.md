# Part 5 — chat ordering, owner order handling, status notifications

## What's new
- **Owner**: 🧾 Orders with tabs (New / Confirmed / On the way / History), order card with
  ✅ Confirm · ❌ Reject (asks an optional reason) · 🚚 On the way · 📦 Delivered · 📞 Call customer (sends a contact card).
  The pushed order card is edited in place as the status changes; transfer orders show the screenshot as the card photo.
- **Customer (chat fallback)**: 📋 Browse → categories → products (5/page) → product card with ➕ Add to cart →
  🛒 Cart (remove / clear / checkout) → name → phone → address → payment → confirm → order.
  Saved details are offered as one-tap buttons. Transfer orders wait for a screenshot; any photo the customer
  sends later is attached to their newest unpaid transfer order (or they pick which).
- **Status pushes**: the customer's status message is edited in place and a one-line ping is sent on every change;
  rejected orders restock automatically.
- 🧾 My orders for customers.

## Test
```powershell
python -m pytest -q        # expect 38 passed
```

## Manual test (owner + a second account)
1. Second account: open the shop link → 📋 Browse here → add two products → 🛒 Cart → ✅ Checkout → fill in → 🏦 Transfer → ✅ Place order.
2. Owner receives the card; customer gets "⏳ Pending" + transfer instructions. Customer sends any photo → owner gets it as a reply to the card, card now says "📎 screenshot attached".
3. Owner taps ✅ Confirm → customer's message updates to "✅ Confirmed". 🚚 On the way → 📦 Delivered.
4. Place another order, tap ❌ Reject, type a reason → customer sees it; product stock is restored (check 📦 Products).
5. Owner home → 🧾 Orders → History shows both.

## Deploy
```powershell
git add -A
git commit -m "Part 5: chat ordering, owner order handling, status notifications"
git push origin main
```
