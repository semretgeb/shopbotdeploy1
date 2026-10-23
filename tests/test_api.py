"""Mini App API: products, me, orders, proof upload, isolation, notifications (with a fake bot)."""
import io
from types import SimpleNamespace

import pytest

from app.db.repo import products as products_repo
from tests.conftest import signed_init_data


class FakeBot:
    """Records what the API would send to Telegram."""

    def __init__(self):
        self.sent: list[dict] = []
        self._id = 100

    async def _record(self, kind, **kw):
        self._id += 1
        self.sent.append({"kind": kind, **kw})
        photo = [SimpleNamespace(file_id=f"fake-file-{self._id}")] if kind == "send_photo" else []
        return SimpleNamespace(message_id=self._id, photo=photo)

    async def send_message(self, chat_id, text, **kw):
        return await self._record("send_message", chat_id=chat_id, text=text)

    async def send_photo(self, chat_id, photo, **kw):
        return await self._record("send_photo", chat_id=chat_id, caption=kw.get("caption"))

    async def edit_message_text(self, text, chat_id, message_id, **kw):
        return await self._record("edit_message_text", chat_id=chat_id, message_id=message_id, text=text)

    async def edit_message_caption(self, chat_id, message_id, caption, **kw):
        return await self._record("edit_message_caption", chat_id=chat_id, message_id=message_id, caption=caption)


@pytest.fixture
def fake_bot(client):
    from app.main import app

    bot = FakeBot()
    app.state.ptb = SimpleNamespace(bot=bot)
    yield bot
    app.state.ptb = None


@pytest.fixture
def stocked(two_shops, db):
    a, b = two_shops
    pa1 = products_repo.create(db, a.id, "Shoe", 120000, 3, "fid1", "u1", category_id=products_repo.get_or_create_category(db, a.id, "Shoes").id)
    pa2 = products_repo.create(db, a.id, "Bag", 50000, None, None, None)
    hidden = products_repo.create(db, a.id, "Secret", 1, None, None, None)
    hidden.is_active = False
    pb = products_repo.create(db, b.id, "Lipstick", 35000, 10, "fid2", "u2")
    db.commit()
    return SimpleNamespace(a=a, b=b, pa1=pa1, pa2=pa2, hidden=hidden, pb=pb)


def H(slug, user_id=5001):
    return {"X-Telegram-Init-Data": signed_init_data(user_id=user_id, start_param=slug)}


def test_shop_profile_and_i18n(client, stocked):
    r = client.get("/api/shop", headers=H(stocked.a.slug))
    assert r.status_code == 200 and r.json()["name"] == "Abebe Fashion" and r.json()["is_open"] is True
    r = client.get("/api/i18n/am")
    assert r.status_code == 200 and "ብር" in r.text
    r2 = client.get("/api/i18n/am", headers={"If-None-Match": r.headers["ETag"]})
    assert r2.status_code == 304


def test_products_scoped_and_hidden_excluded(client, stocked):
    r = client.get("/api/products", headers=H(stocked.a.slug))
    names = {p["name"] for p in r.json()["items"]}
    assert names == {"Shoe", "Bag"} and r.json()["total"] == 2
    assert r.json()["items"][0]["price_text"].endswith("ብር")
    # Shop B's product is invisible through shop A, and vice versa
    assert client.get(f"/api/products/{stocked.pb.id}", headers=H(stocked.a.slug)).status_code == 404
    assert client.get(f"/api/products/{stocked.pa1.id}", headers=H(stocked.b.slug)).status_code == 404
    assert client.get(f"/api/products/{stocked.hidden.id}", headers=H(stocked.a.slug)).status_code == 404
    cats = client.get("/api/categories", headers=H(stocked.a.slug)).json()
    assert [c["name"] for c in cats] == ["Shoes"] and cats[0]["count"] == 1


def test_me_is_per_shop(client, stocked):
    client.put("/api/me", json={"full_name": "Hana", "phone": "0911223344", "address": "Bole", "lang": "en"}, headers=H(stocked.a.slug))
    assert client.get("/api/me", headers=H(stocked.a.slug)).json()["full_name"] == "Hana"
    assert client.get("/api/me", headers=H(stocked.b.slug)).json()["full_name"] is None
    assert client.get("/api/products", headers=H(stocked.a.slug)).json()["items"][0]["price_text"].startswith("ETB")


def test_place_order_reprices_decrements_and_notifies(client, stocked, fake_bot, db):
    body = {
        "items": [{"product_id": stocked.pa1.id, "qty": 2}, {"product_id": stocked.pa2.id, "qty": 1}],
        "full_name": "Hana", "phone": "0911223344", "address": "Bole, Addis", "payment_method": "cod",
    }
    r = client.post("/api/orders", json=body, headers=H(stocked.a.slug))
    assert r.status_code == 201, r.text
    o = r.json()
    assert o["total_santim"] == 2 * 120000 + 50000 and len(o["code"]) == 4 and o["status"] == "pending"
    db.expire_all()
    assert products_repo.get(db, stocked.a.id, stocked.pa1.id).stock == 1
    kinds = [(m["kind"], m["chat_id"]) for m in fake_bot.sent]
    assert ("send_message", stocked.a.owner_id) in kinds  # owner card
    assert ("send_message", 5001) in kinds  # customer status
    owner_card = next(m for m in fake_bot.sent if m["chat_id"] == stocked.a.owner_id)
    assert o["code"] in owner_card["text"] and "Shoe × 2" in owner_card["text"]
    # saved details reused
    assert client.get("/api/me", headers=H(stocked.a.slug)).json()["phone"] == "0911223344"
    # my orders lists it; another user in the same shop does not see it
    assert [x["code"] for x in client.get("/api/orders", headers=H(stocked.a.slug)).json()] == [o["code"]]
    assert client.get("/api/orders", headers=H(stocked.a.slug, user_id=7777)).json() == []
    assert client.get(f"/api/orders/{o['id']}", headers=H(stocked.a.slug, user_id=7777)).status_code == 404


def test_order_rejects_out_of_stock_and_cross_shop_products(client, stocked, fake_bot):
    base = {"full_name": "Hana", "phone": "0911223344", "address": "Bole", "payment_method": "cod"}
    r = client.post("/api/orders", json={**base, "items": [{"product_id": stocked.pa1.id, "qty": 5}]}, headers=H(stocked.a.slug))
    assert r.status_code == 409 and r.json()["detail"]["code"] == "out_of_stock"
    r = client.post("/api/orders", json={**base, "items": [{"product_id": stocked.pb.id, "qty": 1}]}, headers=H(stocked.a.slug))
    assert r.status_code == 409 and r.json()["detail"]["code"] == "product_unavailable"
    r = client.post("/api/orders", json={**base, "items": [{"product_id": stocked.hidden.id, "qty": 1}]}, headers=H(stocked.a.slug))
    assert r.status_code == 409
    assert fake_bot.sent == []  # nothing sent for failed orders


def test_transfer_order_and_proof_upload(client, stocked, fake_bot):
    body = {"items": [{"product_id": stocked.pa2.id, "qty": 1}], "full_name": "Hana", "phone": "0911223344",
            "address": "Bole", "payment_method": "transfer", "note": "call before"}
    o = client.post("/api/orders", json=body, headers=H(stocked.a.slug)).json()
    assert o["payment_info"] is None or isinstance(o["payment_info"], str)
    cust_msg = next(m for m in fake_bot.sent if m["chat_id"] == 5001)
    assert "🏦" in cust_msg["text"]  # transfer instructions shown while proof is missing
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 200
    r = client.post(f"/api/orders/{o['id']}/proof", files={"file": ("shot.png", io.BytesIO(png), "image/png")}, headers=H(stocked.a.slug))
    assert r.status_code == 200 and r.json()["has_proof"] is True
    assert any(m["kind"] == "send_photo" and m["chat_id"] == stocked.a.owner_id for m in fake_bot.sent)
    assert client.get(f"/api/orders/{o['id']}", headers=H(stocked.a.slug)).json()["has_proof"] is True
    # wrong type / someone else's order
    r = client.post(f"/api/orders/{o['id']}/proof", files={"file": ("x.txt", io.BytesIO(b"hello"), "text/plain")}, headers=H(stocked.a.slug))
    assert r.status_code == 415
    r = client.post(f"/api/orders/{o['id']}/proof", files={"file": ("shot.png", io.BytesIO(png), "image/png")}, headers=H(stocked.a.slug, user_id=7777))
    assert r.status_code == 404


def test_paused_shop_blocks_products_but_not_profile(client, stocked, db):
    from app.services import subscription as sub

    sub.pause(db, stocked.a, admin_id=999)
    db.commit()
    assert client.get("/api/products", headers=H(stocked.a.slug)).status_code == 403
    r = client.get("/api/shop", headers=H(stocked.a.slug))
    assert r.status_code == 200 and r.json()["is_open"] is False


def test_webapp_is_served(client):
    r = client.get("/app/")
    assert r.status_code == 200 and "telegram-web-app.js" in r.text
    for path in ("css/app.css", "js/app.js", "js/api.js", "js/ui.js", "js/cart.js", "js/i18n.js", "img/placeholder.svg"):
        assert client.get(f"/app/{path}").status_code == 200, path
