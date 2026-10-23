"""Product repo isolation + the chat helpers (caption shortcut, i18n, QR)."""
from app.bot.handlers.products import CAPTION_RE, _parse_caption
from app.db.repo import products as repo
from app.locales import load, t
from app.services.qr import qr_png, shop_link
from app.services.slug import slugify


def test_products_are_scoped_by_shop(two_shops, db):
    a, b = two_shops
    pa = repo.create(db, a.id, "Shoe", 120000, 5, "fid_a", "uid_a")
    pb = repo.create(db, b.id, "Lipstick", 35000, None, "fid_b", "uid_b")
    assert repo.get(db, a.id, pa.id) is not None
    assert repo.get(db, b.id, pa.id) is None  # shop B cannot see A's product by id
    assert repo.update(db, b.id, pa.id, name="hacked") is None
    assert repo.delete(db, b.id, pa.id) is False
    items, total = repo.list_page(db, a.id)
    assert total == 1 and items[0].id == pa.id
    assert repo.count(db, b.id) == 1 and repo.get(db, b.id, pb.id).name == "Lipstick"


def test_categories_are_scoped_and_case_insensitive(two_shops, db):
    a, b = two_shops
    c1 = repo.get_or_create_category(db, a.id, "Shoes")
    c2 = repo.get_or_create_category(db, a.id, "shoes")
    c3 = repo.get_or_create_category(db, b.id, "Shoes")
    assert c1.id == c2.id and c3.id != c1.id
    assert repo.get_category(db, b.id, c1.id) is None


def test_stock_decrement(two_shops, db):
    a, _ = two_shops
    p = repo.create(db, a.id, "Bag", 50000, 2, None, None)
    assert repo.decrement_stock(db, a.id, p.id, 2) and p.stock == 0
    assert not repo.decrement_stock(db, a.id, p.id, 1)
    u = repo.create(db, a.id, "Water", 1000, None, None, None)
    assert repo.decrement_stock(db, a.id, u.id, 999)  # unlimited


def test_caption_shortcut_parsing():
    assert _parse_caption("Red Shoes - 1200") == ("Red Shoes", 120000)
    assert _parse_caption("ቀይ ጫማ – 1,200 ብር") == ("ቀይ ጫማ", 120000)
    assert _parse_caption("Bag: 99.5") == ("Bag", 9950)
    assert _parse_caption("just a caption") is None
    assert _parse_caption("Shoes - free") is None
    assert CAPTION_RE.match("Shoes - 0") and _parse_caption("Shoes - 0") is None


def test_locales_have_same_keys_and_format():
    en, am = load("en"), load("am")
    assert set(en) == set(am), set(en) ^ set(am)
    assert t("onb.step", "en", n=2) == "Step 2 of 5"
    assert "2" in t("onb.step", "am", n=2)
    assert t("missing.key", "am") == "missing.key"


def test_qr_and_link():
    link = shop_link("TestShopBot", "abebe-fashion")
    assert link == "https://t.me/TestShopBot?start=abebe-fashion"
    png = qr_png(link)
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) > 500
    assert slugify("Abebe Fashion") == "abebe-fashion"
