# ShopBot — Design Pack (D1)

Multi-tenant Telegram shop SaaS. One shared bot, many shops, Mini App storefront, Groq assistant, ETB subscription.
Status: awaiting "go" before code delivery.

---

## 0. Architecture decisions (and why)

| Area | Decision | Why |
|---|---|---|
| Web app | One FastAPI process. PTB v20 `Application` runs in **webhook mode inside FastAPI** (`updater=None`, `await app.process_update(update)` from `POST /telegram/webhook`). | No polling, no worker, one deploy unit, matches EthioDeploy "deploy on push". |
| Webhook security | `setWebhook(secret_token=...)`; every webhook call must carry `X-Telegram-Bot-Api-Secret-Token`. | Blocks forged updates. |
| Conversation state | **DB-backed state machine** (`chat_states` table) instead of PTB `ConversationHandler` in memory. | Webhook + redeploys: in-memory state is lost on every push; DB state survives and works with multiple workers later. |
| DB | SQLAlchemy 2.0 + **Alembic**. `DATABASE_URL` = `sqlite:///./shopbot.db` locally, `postgresql+psycopg://…` in prod. Types kept portable (no Postgres-only columns; JSON stored as `JSON` type which works on both). | Same models, two engines, zero code change. |
| Photos | **Telegram `file_id` as the source of truth** + API image proxy `GET /api/img/{file_id}` with on-disk LRU cache and long `Cache-Control`. Store `file_unique_id` alongside. | Zero storage cost, survives redeploys (Telegram keeps the file), no S3 needed in Ethiopia. The proxy exists because the Mini App must never see the bot token. Cache is in `/tmp` (ephemeral is fine — it's only a cache). Images are re-encoded to WebP ≤ 640px thumbnails on first fetch (Pillow) to stay light on slow links. If Telegram ever returns 400 for a `file_id`, the owner is asked to re-send the photo (rare, handled). |
| Payment screenshots | Mini App uploads via `multipart` to the API → server sends the photo to the **owner's chat with the order card** via the bot → Telegram's returned `file_id` is persisted. | Same storage trick as products; the owner gets the proof instantly in the message they act on. |
| Mini App auth | `X-Telegram-Init-Data` header on **every** `/api/*` request. Server validates HMAC-SHA256 per Telegram spec, rejects if `auth_date` older than 24h, extracts `user` and `start_param`. Shop is resolved **only** from `start_param` → `shops.slug`. | Forged/replayed requests rejected; shop can't be chosen by the client arbitrarily — only a valid signed link gives access. |
| Tenant isolation | Every repo/query function takes `shop_id` as a required argument; API handlers get `shop` from a dependency and never from the body/query. | "Can't forget" the filter. Isolation tests in checklist. |
| AI | `services/ai.py` with a `Provider` interface; Groq `llama-3.3-70b-versatile` behind it. Context = shop profile + product list (name, price, stock, category) + delivery/payment info. System prompt forbids inventing; model must reply with a `{"answer":…}` or `{"forward":true,"question":…}` JSON. | Swappable provider (risk register), structured "I don't know" path → forwarded to owner. |
| AI rate limit | DB counters: per customer **10 / hour**, per shop **300 / day** (configurable). Over limit → fallback message + offer "Ask the owner". | Protects Groq quota and cost; survives restarts. |
| Subscription | `shops.trial_ends_at` (now+14d at creation), `shops.paid_until`, `shops.status` (`trial`/`active`/`paused`). Shop is *open* iff `status != paused AND now < max(trial_ends_at, paid_until)`. Gate is one function used by bot handlers **and** the API dependency. | One source of truth; paused shop blocks both chat and Mini App. |
| i18n | `locales/en.json`, `locales/am.json` (flat keys). Bot loads them in Python; Mini App fetches `GET /api/i18n/{lang}` (cached). `fmt_price(120000) → "1,200 ብር"` / `"ETB 1,200"`. | Spec: one set of translation files shared by both surfaces. |
| Money | Prices stored as **integer santim** (`price_santim`), displayed as birr. | No float rounding errors. |
| Front end | Vanilla HTML/CSS/JS, `telegram-web-app.js`, served from `/app/`. Products paginated (24/page), lazy-loaded thumbnails, skeletons, theme vars from `Telegram.WebApp.themeParams`. | No build step, mobile-first, light. |

Things I'd like you to confirm (not blocking Step 1):
1. **EthioDeploy build method**: Dockerfile, Procfile, or auto-detect `requirements.txt`? And what env var name exposes managed Postgres (`DATABASE_URL`?). I'll default to **Dockerfile + `DATABASE_URL`** and include a Procfile too.
2. **Shop slug**: auto-generated from name (`abebe-fashion`) with a random 3-char suffix on collision, owner cannot edit in MVP. OK?
3. Default AI limits above OK?

---

## 1. Folder structure

```
shopbot/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app, lifespan: init DB, build PTB app, set webhook
│   ├── config.py               # Settings from .env (pydantic-settings)
│   ├── logging_conf.py
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── application.py      # builds PTB Application, registers handlers
│   │   ├── router.py           # dispatch by chat_state + role (owner/customer/admin)
│   │   ├── keyboards.py        # inline keyboard builders (Back/Home everywhere)
│   │   ├── states.py           # state name constants
│   │   └── handlers/
│   │       ├── __init__.py
│   │       ├── start.py        # /start, deep link, language picker, role detection
│   │       ├── onboarding.py   # owner wizard (5 steps)
│   │       ├── products.py     # add/list/edit/delete, photo-caption shortcut
│   │       ├── share.py        # shop link + QR
│   │       ├── orders_owner.py # order cards, Confirm/Reject/Call, status changes
│   │       ├── shop_customer.py# customer menu, chat fallback ordering, status msgs
│   │       ├── assistant.py    # free-text → AI, forward-to-owner, owner reply
│   │       ├── subscription.py # trial/paused messages, "how to pay"
│   │       └── admin.py        # /admin … commands
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py             # verify initData, resolve shop, gate subscription
│   │   ├── shop.py             # GET /api/shop
│   │   ├── products.py         # GET /api/products, /api/products/{id}, /api/categories
│   │   ├── orders.py           # POST /api/orders, payment proof upload, GET my orders
│   │   ├── customer.py         # GET/PUT /api/me (saved checkout details)
│   │   ├── images.py           # GET /api/img/{file_id}
│   │   ├── i18n.py             # GET /api/i18n/{lang}
│   │   └── webhook.py          # POST /telegram/webhook
│   ├── db/
│   │   ├── __init__.py
│   │   ├── base.py             # engine, SessionLocal, Base
│   │   ├── models.py           # all SQLAlchemy models
│   │   └── repo/
│   │       ├── __init__.py
│   │       ├── shops.py
│   │       ├── products.py
│   │       ├── orders.py
│   │       ├── customers.py
│   │       ├── states.py
│   │       └── ai_usage.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── telegram_auth.py    # initData HMAC verification
│   │   ├── subscription.py     # is_shop_open(), trial/paid logic
│   │   ├── images.py           # file_id → cached WebP bytes
│   │   ├── qr.py               # QR PNG for shop link
│   │   ├── ai.py               # Provider interface + GroqProvider + prompt builder
│   │   ├── notifications.py    # send order card to owner, status msgs to customer
│   │   ├── slug.py
│   │   └── money.py            # fmt_price
│   ├── locales/
│   │   ├── __init__.py         # t(key, lang, **vars)
│   │   ├── en.json
│   │   └── am.json
│   └── webapp/                 # Mini App (static, no build)
│       ├── index.html
│       ├── css/app.css
│       ├── js/
│       │   ├── app.js          # router + state
│       │   ├── api.js          # fetch wrapper (adds initData header)
│       │   ├── i18n.js
│       │   ├── cart.js         # localStorage cart per shop
│       │   └── ui.js           # components: grid, detail, cart, checkout, skeletons
│       └── img/placeholder.svg
├── migrations/                 # Alembic
│   ├── env.py
│   └── versions/
├── alembic.ini
├── tests/
│   ├── test_initdata.py
│   ├── test_isolation.py
│   └── test_subscription.py
├── scripts/
│   └── set_webhook.py
├── Dockerfile
├── Procfile
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
└── docs/
    ├── DESIGN.md               # this file
    ├── TEST_CHECKLIST.md
    └── DEPLOY_CHECKLIST.md
```

---

## 2. Database schema (SQL)

Portable SQL (SQLite + PostgreSQL). Alembic generates the real migration from the models; this is the contract.

```sql
-- Every Telegram user who ever talked to the bot (owners, customers, admin)
CREATE TABLE tg_users (
  id              INTEGER PRIMARY KEY,            -- Telegram user id
  username        VARCHAR(64),
  first_name      VARCHAR(128),
  lang            VARCHAR(2) NOT NULL DEFAULT 'am', -- 'am' | 'en'
  created_at      TIMESTAMP NOT NULL,
  last_seen_at    TIMESTAMP NOT NULL
);

CREATE TABLE shops (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  slug            VARCHAR(48) NOT NULL UNIQUE,
  owner_id        INTEGER NOT NULL REFERENCES tg_users(id),
  name            VARCHAR(80) NOT NULL,
  description     TEXT,
  phone           VARCHAR(32),
  delivery_info   TEXT,                            -- areas, fees, times (free text)
  payment_info    TEXT,                            -- Telebirr/CBE account for customers
  logo_file_id    VARCHAR(256),
  status          VARCHAR(16) NOT NULL DEFAULT 'trial', -- trial | active | paused
  trial_ends_at   TIMESTAMP NOT NULL,
  paid_until      TIMESTAMP,
  onboarding_done BOOLEAN NOT NULL DEFAULT 0,
  ai_enabled      BOOLEAN NOT NULL DEFAULT 1,
  created_at      TIMESTAMP NOT NULL,
  updated_at      TIMESTAMP NOT NULL
);
CREATE UNIQUE INDEX ix_shops_owner ON shops(owner_id);   -- one shop per owner in MVP

CREATE TABLE categories (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  shop_id    INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  name       VARCHAR(48) NOT NULL,
  position   INTEGER NOT NULL DEFAULT 0,
  UNIQUE (shop_id, name)
);

CREATE TABLE products (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  shop_id         INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  category_id     INTEGER REFERENCES categories(id) ON DELETE SET NULL,
  name            VARCHAR(80) NOT NULL,
  description     TEXT,
  price_santim    INTEGER NOT NULL,                -- 1 birr = 100 santim
  stock           INTEGER,                         -- NULL = unlimited / "in stock"
  photo_file_id   VARCHAR(256),
  photo_unique_id VARCHAR(64),
  is_active       BOOLEAN NOT NULL DEFAULT 1,
  created_at      TIMESTAMP NOT NULL,
  updated_at      TIMESTAMP NOT NULL
);
CREATE INDEX ix_products_shop ON products(shop_id, is_active, category_id);

-- A Telegram user as a customer OF ONE SHOP (saved checkout details are per shop)
CREATE TABLE customers (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  shop_id       INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  tg_user_id    INTEGER NOT NULL REFERENCES tg_users(id),
  full_name     VARCHAR(80),
  phone         VARCHAR(32),
  address       TEXT,
  created_at    TIMESTAMP NOT NULL,
  UNIQUE (shop_id, tg_user_id)
);

CREATE TABLE orders (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  shop_id             INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  customer_id         INTEGER NOT NULL REFERENCES customers(id),
  code                VARCHAR(8) NOT NULL,         -- short human code e.g. "A7K3", unique per shop
  status              VARCHAR(16) NOT NULL DEFAULT 'pending',
                      -- pending | confirmed | on_the_way | delivered | rejected | cancelled
  source              VARCHAR(8) NOT NULL,         -- miniapp | chat
  payment_method      VARCHAR(16) NOT NULL,        -- cod | transfer
  payment_proof_file_id VARCHAR(256),
  full_name           VARCHAR(80) NOT NULL,
  phone               VARCHAR(32) NOT NULL,
  address             TEXT NOT NULL,
  note                TEXT,
  total_santim        INTEGER NOT NULL,
  owner_msg_id        INTEGER,                     -- owner's order-card message (for in-place edits)
  customer_msg_id     INTEGER,                     -- customer's status message
  created_at          TIMESTAMP NOT NULL,
  updated_at          TIMESTAMP NOT NULL,
  UNIQUE (shop_id, code)
);
CREATE INDEX ix_orders_shop_status ON orders(shop_id, status, created_at);

CREATE TABLE order_items (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id        INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  product_id      INTEGER REFERENCES products(id) ON DELETE SET NULL,
  name_snapshot   VARCHAR(80) NOT NULL,            -- survives product edits/deletes
  price_santim    INTEGER NOT NULL,
  qty             INTEGER NOT NULL
);

-- DB-backed conversation state (replaces in-memory ConversationHandler)
CREATE TABLE chat_states (
  tg_user_id  INTEGER PRIMARY KEY REFERENCES tg_users(id),
  shop_id     INTEGER,                              -- which shop the customer is "in"
  state       VARCHAR(48) NOT NULL DEFAULT 'idle',  -- e.g. onb_name, prod_add_price, cart
  data        JSON,                                 -- step scratchpad (draft product, chat cart…)
  updated_at  TIMESTAMP NOT NULL
);

-- Questions the AI could not answer, forwarded to the owner
CREATE TABLE forwarded_questions (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  shop_id       INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  customer_id   INTEGER NOT NULL REFERENCES customers(id),
  question      TEXT NOT NULL,
  answer        TEXT,
  owner_msg_id  INTEGER,
  created_at    TIMESTAMP NOT NULL,
  answered_at   TIMESTAMP
);

-- AI rate-limit counters (fixed windows)
CREATE TABLE ai_usage (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  shop_id       INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  tg_user_id    INTEGER,                            -- NULL row = shop-wide daily counter
  window_start  TIMESTAMP NOT NULL,
  count         INTEGER NOT NULL DEFAULT 0,
  UNIQUE (shop_id, tg_user_id, window_start)
);

-- Admin audit of subscription changes
CREATE TABLE subscription_events (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  shop_id     INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  action      VARCHAR(16) NOT NULL,                 -- approve | extend | pause | resume | trial
  months      INTEGER,
  note        TEXT,
  created_by  INTEGER NOT NULL,                     -- admin tg id
  created_at  TIMESTAMP NOT NULL
);
```

Isolation rule: every table that holds shop data has `shop_id`; every repo function signature is `fn(db, shop_id, …)`.

---

## 3. API endpoints

All `/api/*` routes require header `X-Telegram-Init-Data: <raw initData>`.
Dependency chain: `verify_init_data` → `current_tg_user` → `current_shop` (from `start_param`) → `require_open_shop` (subscription gate, returns `403 {"code":"shop_paused"}`).
Errors are JSON `{ "code": "...", "message": "..." }`; messages are already localized to the user's language.

| Method | Path | Purpose | Notes |
|---|---|---|---|
| POST | `/telegram/webhook` | Telegram updates → PTB | Checks secret-token header. Not under `/api`. |
| GET | `/healthz` | Liveness | For EthioDeploy. |
| GET | `/app/` | Mini App static | `index.html` + assets, `Cache-Control` on assets. |
| GET | `/api/i18n/{lang}` | Translation JSON | `lang ∈ {am,en}`. ETag cached. No auth needed. |
| GET | `/api/shop` | Shop profile for storefront header | `{name, description, phone, delivery_info, payment_info, logo_url, is_open, lang}` |
| GET | `/api/categories` | Categories of shop | `[{id,name,count}]` |
| GET | `/api/products?category_id=&page=&q=` | Paginated active products | 24/page; returns `thumb_url` (proxy) |
| GET | `/api/products/{id}` | Product detail | 404 if not in this shop |
| GET | `/api/me` | Saved checkout details | `{full_name, phone, address, lang}` |
| PUT | `/api/me` | Update saved details / lang | |
| POST | `/api/orders` | Place order | Body: `{items:[{product_id,qty}], full_name, phone, address, note, payment_method}`. Server re-prices from DB, checks stock, creates order, sends owner card + customer status msg. Returns `{order_id, code, total, payment_info}` |
| POST | `/api/orders/{id}/proof` | Upload payment screenshot | `multipart/form-data` (≤5 MB, image/*). Only the order's own customer. Sends photo to owner chat, stores file_id. |
| GET | `/api/orders` | My orders in this shop | Last 20, `{code,status,total,created_at,items}` |
| GET | `/api/img/{file_id}?w=640` | Image proxy | Public (file_ids are unguessable), `Cache-Control: public, max-age=604800`, WebP. |

---

## 4. Mini App screens

Served at `https://[SUBDOMAIN].ethiodeploy.com/app/`, opened via a **Menu/Inline "🛍 Open shop" button** with `web_app` URL; `start_param` carries the slug. Single page, hash-routed. Every screen: header with shop name, Back arrow (`BackButton` from SDK), 🏠 Home.

| # | Screen | Elements |
|---|---|---|
| S0 | Loading / Skeleton | Grey card skeletons while `/api/shop` + first products load. |
| S1 | Storefront (home) | Shop name + short description, horizontal category chips (All, …), 2-column product grid (thumb, name, `1,200 ብር`, "out of stock" badge), infinite scroll / "Load more", **sticky bottom cart bar** ("🛒 3 items · 3,600 ብር → View cart"). Language toggle (am/en) in header. |
| S2 | Product detail | Large photo, name, price, description, stock, category, quantity stepper (− 1 +), big "Add to cart" (SDK `MainButton`). |
| S3 | Cart | Line items with stepper and remove, subtotal, delivery note from shop, "Checkout" `MainButton`. Empty state: "🧺 Your cart is empty — browse products". |
| S4 | Checkout | Prefilled from `/api/me`: full name, phone (ET format hint), address, note. Payment method: "💵 Pay on delivery" / "🏦 Bank/Telebirr transfer". Order summary. "Place order" `MainButton`. Inline validation. |
| S5 | Payment proof (transfer only) | Shop's payment info in a copyable box, amount, "📎 Upload screenshot" (file input → `/proof`), "I'll send it later in chat" option. |
| S6 | Order confirmation | ✅ Order #A7K3 received, items, total, status badge, "Track in chat" (closes Mini App), "Continue shopping". |
| S7 | My orders | List of my orders in this shop with status badges; tap for details. |
| S8 | Shop closed | Friendly full-screen state when `is_open=false`: "This shop is temporarily closed" (no products shown). |
| S9 | Error / offline | Retry button; cart kept in localStorage. |

Perf rules: ≤ 60 KB JS+CSS total, thumbnails WebP 320px in grid / 640px in detail, `loading="lazy"`, products cached in memory per session, theme colors from `themeParams` with sensible fallbacks.

---

## 5. Conversation flows

### 5.1 Owner flow
```
/start (no param, unknown user)
 └ Language picker [🇪🇹 አማርኛ] [🇬🇧 English]
   └ "What would you like to do?" [🏪 Create my shop] [🛍 I'm a customer – paste a shop link]
      └ Onboarding wizard (DB state onb_*):
         Step 1/5 Shop name
         Step 2/5 Short description
         Step 3/5 Phone number (Share contact button or type)
         Step 4/5 Delivery info (areas / fee / time)       [⏭ Skip]
         Step 5/5 Payment info for customers (Telebirr/CBE)  [⏭ Skip]
         ✅ "Shop created! Trial ends on <date>." → Owner Home
Owner Home (one message, edited in place)
 [➕ Add product] [📦 Products (12)]
 [🧾 Orders (3 new)] [🔗 Share shop]
 [⚙️ Shop settings] [💳 Subscription] [🌐 Language]
Add product: send photo → name → price (ETB) → stock [∞ Unlimited] → category [existing… / ➕ New / Skip] → preview [✅ Save] [✏️ Edit] [❌ Cancel]
  Shortcut: photo with caption "Name - 1200" → skips name+price, asks stock/category only.
Products: paginated list (5/page) → tap → card [✏️ Name] [💰 Price] [📦 Stock] [🖼 Photo] [🏷 Category] [🗑 Delete (confirm)] [◀ Back] [🏠 Home]
Share shop: link + QR PNG + "Forward this to customers" + [📋 Copy link]
Orders: tabs [🆕 New] [✅ Confirmed] [🚚 On the way] [📜 History]
Order card (new): "🧾 Order #A7K3 · 3,600 ብር · 💵 COD · Abebe · 0911… · Bole, …" + items
  [✅ Confirm] [❌ Reject] [📞 Call] (tel: link / contact)
  after confirm → card edited: [🚚 On the way] [📦 Delivered] [📞 Call]
  reject → asks optional reason → customer notified
Forwarded question card: "❓ Customer asks: '…'" [✍️ Reply] → owner types → sent to customer; answer stored.
Subscription: status, trial/paid-until date, "How to pay: send ETB <PRICE> to <ACCOUNT> and message @admin / send screenshot here" → forwarded to admin.
Paused shop: any owner action → "⏸ Your shop is paused. Pay to continue." + how-to-pay.
```

### 5.2 Customer flow
```
/start <shop_slug>  (deep link / QR)
 └ language picker on first contact (remembered)
 └ shop open?  no → "⏸ <Shop> is temporarily closed."
 └ Shop Home (edited in place):
     "🏪 <Shop name> — <description>"
     [🛍 Open shop (Mini App)]        ← web_app button, start_param = slug
     [📋 Browse here] [🧾 My orders] [❓ Ask a question] [📞 Contact] [🌐 Language]
Browse here (chat fallback): category buttons → product cards (photo, name, price) 5/page
  [➕ Add] [◀] [▶] [🛒 Cart (2)] [🏠]
  Cart → [✅ Checkout] → name (reuse saved: [✅ Use "Abebe, 0911…"]) → phone → address
       → payment [💵 On delivery] [🏦 Transfer] → confirm [✅ Place order]
       → transfer: "Send <total> to <payment info>, then send the screenshot here" (photo → attached to order)
Free text anywhere while in a shop → AI assistant:
  answer (shop data only) | "I'm not sure, I've sent your question to the owner 📨" | rate-limited → "Please ask the owner directly" [📞]
Order status pushes (one message per order, edited in place):
  ⏳ Pending → ✅ Confirmed → 🚚 On the way → 📦 Delivered   /  ❌ Rejected (reason)
My orders: last 5 with status; tap → details.
```

### 5.3 Admin flow (only ADMIN_TELEGRAM_ID)
```
/admin                         → help + [📊 Stats] [🏪 Shops] [📣 Broadcast]
/admin shops [page]            → id · name · @owner · status · ends <date> · products · orders
/admin shop <id>               → full card + [✅ Approve 1m] [✅ 3m] [⏸ Pause] [▶ Resume]
/admin approve <shop_id> <months>   → paid_until = max(now, paid_until) + months; status=active; owner notified
/admin extend <shop_id> <days>      → paid_until += days
/admin pause <shop_id> [reason]     → status=paused; owner notified; mini app shows S8
/admin resume <shop_id>
/admin stats                   → shops (trial/active/paused), orders today/7d, AI calls today, forwarded q's
/admin broadcast <text>        → preview + [📣 Send to all owners] [❌]
Owner payment screenshots sent via "Subscription → I paid" land in admin chat with [✅ Approve 1m] [❌].
Daily job (APScheduler in-process): trial/paid expiry → status=paused + warning 3 days before.
```

---

## 6. Delivery order after "go"
1. Core + DB + auth (config, models, Alembic, initData verification, webhook plumbing, image proxy, subscription gate)
2. Owner module (onboarding, products, share/QR)
3. API
4. Mini App front end
5. Chat fallback ordering + notifications + owner order cards
6. AI assistant
7. Subscription + admin
8. Localization (am/en JSON, price formatting)
9. Deployment (Dockerfile, Procfile, EthioDeploy steps), README, .env.example, test + deploy checklists
