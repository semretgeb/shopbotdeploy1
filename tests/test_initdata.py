import time

import pytest

from app.services.telegram_auth import InitDataError, build_init_data, verify_init_data
from tests.conftest import BOT_TOKEN, signed_init_data


def test_valid_init_data_round_trip():
    raw = signed_init_data(user_id=42, start_param="abebe-fashion")
    data = verify_init_data(raw, BOT_TOKEN)
    assert data.user_id == 42
    assert data.start_param == "abebe-fashion"


def test_tampered_user_is_rejected():
    raw = signed_init_data(user_id=42)
    tampered = raw.replace("%22id%22%3A42", "%22id%22%3A43")
    assert tampered != raw
    with pytest.raises(InitDataError):
        verify_init_data(tampered, BOT_TOKEN)


def test_wrong_bot_token_is_rejected():
    raw = signed_init_data(user_id=42)
    with pytest.raises(InitDataError):
        verify_init_data(raw, "999:OTHER-TOKEN")


def test_expired_auth_date_is_rejected():
    raw = build_init_data({"auth_date": int(time.time()) - 100_000, "user": {"id": 1}}, BOT_TOKEN)
    with pytest.raises(InitDataError, match="expired"):
        verify_init_data(raw, BOT_TOKEN, max_age_seconds=3600)


@pytest.mark.parametrize("raw", ["", "hash=abc", "auth_date=1&user=%7B%7D", "not=a&valid=hash&hash=zz"])
def test_garbage_is_rejected(raw):
    with pytest.raises(InitDataError):
        verify_init_data(raw, BOT_TOKEN)


def test_api_rejects_missing_and_forged_header(client, two_shops):
    a, _ = two_shops
    # Future shop endpoints use get_shop; verify the dependency chain via a throwaway route.
    from fastapi import Depends

    from app.api.deps import get_open_shop
    from app.main import app

    @app.get("/api/_test_shop")
    def _t(shop=Depends(get_open_shop)):
        return {"id": shop.id, "slug": shop.slug}

    assert client.get("/api/_test_shop", params={"shop": a.slug}).status_code == 401
    assert client.get("/api/_test_shop", params={"shop": a.slug}, headers={"X-Telegram-Init-Data": "hash=bad"}).status_code == 401
    ok = client.get("/api/_test_shop", headers={"X-Telegram-Init-Data": signed_init_data(start_param=a.slug)})
    assert ok.status_code == 200 and ok.json()["slug"] == a.slug
