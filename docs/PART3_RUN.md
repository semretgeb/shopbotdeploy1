# Part 3 — Mini App API: run, test, deploy

## Endpoints (all under /api, header `X-Telegram-Init-Data` required unless noted)
| Method | Path | Notes |
|---|---|---|
| GET | /shop | works for paused shops too (`is_open:false`) |
| GET | /categories | only categories with visible products |
| GET | /products?category_id=&page=&q= | 24 per page, hidden products excluded |
| GET | /products/{id} | 404 if not this shop's or hidden |
| GET / PUT | /me | saved checkout details + language, per shop |
| POST | /orders | re-prices from DB, checks/decrements stock, sends owner card + customer status |
| POST | /orders/{id}/proof | multipart image ≤5 MB → forwarded to owner, file_id stored |
| GET | /orders, /orders/{id} | only the caller's orders in this shop |
| GET | /i18n/{lang} | no auth; ETag cached |

Errors: `{"detail":{"code":"out_of_stock","message":"…localized…"}}` — codes: `shop_paused`, `product_not_found`,
`order_not_found`, `empty`, `bad_qty`, `product_unavailable`, `out_of_stock`, `not_transfer`, `bad_image`, `too_large`.

## Test
```powershell
python -m pytest -q        # expect 33 passed
```
`tests/test_api.py` uses a FakeBot so order notifications are asserted without touching Telegram.

## Try it by hand (optional)
```powershell
# build a signed initData for shop "abebe-fashion" as user 5001
python -c "from app.services.telegram_auth import build_init_data; from app.config import get_settings; import time; print(build_init_data({'auth_date': int(time.time()), 'user': {'id': 5001, 'first_name': 'Test'}, 'start_param': 'abebe-fashion'}, get_settings().BOT_TOKEN))"
curl -H "X-Telegram-Init-Data: <paste>" http://localhost:8000/api/products
```

## Deploy
```powershell
git add -A
git commit -m "Part 3: Mini App API (shop, products, me, orders, proof, i18n)"
git push origin main
```
Nothing new to configure on EthioDeploy.
