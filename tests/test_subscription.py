from datetime import timedelta

from fastapi import Depends

from app.db.models import utcnow
from app.services import subscription as sub
from app.services.money import fmt_price, parse_price
from tests.conftest import signed_init_data


def test_trial_then_expiry(two_shops, db):
    a, _ = two_shops
    assert a.status == "trial" and sub.is_shop_open(a)
    assert 13 <= sub.days_left(a) <= 14
    assert not sub.is_shop_open(a, now=utcnow() + timedelta(days=15))


def test_approve_extends_from_later_of_now_or_paid_until(two_shops, db):
    a, _ = two_shops
    sub.approve(db, a, months=1, admin_id=999)
    first = a.paid_until
    assert a.status == "active" and first > utcnow() + timedelta(days=29)
    sub.approve(db, a, months=2, admin_id=999)
    assert a.paid_until == first + timedelta(days=60)  # stacks, doesn't restart from today


def test_pause_blocks_even_during_trial_and_resume_restores(two_shops, db):
    a, _ = two_shops
    sub.pause(db, a, admin_id=999)
    assert not sub.is_shop_open(a)
    sub.resume(db, a, admin_id=999)
    assert a.status == "trial" and sub.is_shop_open(a)


def test_api_gate_returns_403_for_paused_shop(client, two_shops, db):
    a, _ = two_shops
    from app.api.deps import get_open_shop, get_shop
    from app.main import app

    @app.get("/api/_gate_open")
    def _o(shop=Depends(get_open_shop)):
        return {"ok": True}

    @app.get("/api/_gate_any")
    def _a(shop=Depends(get_shop)):
        return {"ok": True}

    h = {"X-Telegram-Init-Data": signed_init_data(start_param=a.slug)}
    assert client.get("/api/_gate_open", headers=h).status_code == 200
    sub.pause(db, a, admin_id=999)
    db.commit()
    r = client.get("/api/_gate_open", headers=h)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "shop_paused"
    assert client.get("/api/_gate_any", headers=h).status_code == 200  # header info still readable


def test_money_formatting_and_parsing():
    assert fmt_price(120000, "am") == "1,200 ብር"
    assert fmt_price(120050, "en") == "ETB 1,200.50"
    assert parse_price("1,200") == 120000
    assert parse_price("ETB 99.5") == 9950
    assert parse_price("1200 ብር") == 120000
    assert parse_price("free") is None and parse_price("0") is None
