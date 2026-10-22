"""Shop-to-shop isolation at the repo and API-dependency level."""
from fastapi import Depends

from app.db.models import Customer, Product
from app.db.repo import customers as customers_repo
from app.db.repo import shops as shops_repo
from app.db.repo import users as users_repo
from app.services.slug import make_slug, slugify
from tests.conftest import signed_init_data


def test_slugs_are_ascii_unique_and_handle_amharic(two_shops, db):
    a, b = two_shops
    assert a.slug == "abebe-fashion" and b.slug == "bethel-cosmetics"
    assert slugify("አበበ ሱቅ") == ""  # no ASCII letters -> random id path
    s = make_slug("አበበ ሱቅ", taken=set())
    assert s.startswith("shop-") and len(s) == 11
    dup = make_slug("Abebe Fashion", taken={"abebe-fashion"})
    assert dup != "abebe-fashion" and dup.startswith("abebe-fashion-")
    assert all(c.isascii() for c in dup)


def test_customer_details_are_per_shop(two_shops, db):
    a, b = two_shops
    users_repo.upsert_tg_user(db, 7, "hana", "Hana")
    customers_repo.save_details(db, a.id, 7, full_name="Hana", phone="0911", address="Bole")
    cb = customers_repo.get_or_create(db, b.id, 7)
    assert cb.full_name is None and cb.phone is None  # same person, different shop, nothing leaks
    assert db.query(Customer).filter_by(tg_user_id=7).count() == 2


def test_customer_lookup_cannot_cross_shops(two_shops, db):
    a, b = two_shops
    users_repo.upsert_tg_user(db, 8, "kebede", "Kebede")
    ca = customers_repo.get_or_create(db, a.id, 8)
    assert customers_repo.get(db, b.id, ca.id) is None


def test_one_shop_per_owner(two_shops, db):
    import pytest
    from sqlalchemy.exc import IntegrityError

    a, _ = two_shops
    with pytest.raises(IntegrityError):
        shops_repo.create(db, a.owner_id, "Second shop", 14)
        db.flush()
    db.rollback()


def test_api_resolves_shop_only_from_verified_start_param(client, two_shops):
    a, b = two_shops
    from app.api.deps import get_open_shop
    from app.main import app

    @app.get("/api/_iso")
    def _t(shop=Depends(get_open_shop)):
        return {"slug": shop.slug}

    # start_param (signed) wins over ?shop= (unsigned) when both are present
    r = client.get("/api/_iso", params={"shop": b.slug}, headers={"X-Telegram-Init-Data": signed_init_data(start_param=a.slug)})
    assert r.json()["slug"] == a.slug
    # unknown shop
    r = client.get("/api/_iso", headers={"X-Telegram-Init-Data": signed_init_data(start_param="nope")})
    assert r.status_code == 404
    # no shop at all
    r = client.get("/api/_iso", headers={"X-Telegram-Init-Data": signed_init_data()})
    assert r.status_code == 400


def test_products_cascade_with_shop(two_shops, db):
    a, b = two_shops
    db.add(Product(shop_id=a.id, name="Shoe", price_santim=120000))
    db.add(Product(shop_id=b.id, name="Lipstick", price_santim=35000))
    db.commit()
    db.delete(a)
    db.commit()
    names = [p.name for p in db.query(Product).all()]
    assert names == ["Lipstick"]
