"""FastAPI dependencies. Chain: db -> init_data -> tg_user -> shop -> open_shop.

Shop resolution: `start_param` from the VERIFIED initData is used when present (direct Mini App
links `t.me/<bot>/<app>?startapp=<slug>`). When the Mini App is opened from a keyboard
`web_app` button Telegram does not populate start_param, so we fall back to the `shop` query
parameter the server itself put in the button URL. This is safe because a storefront is
public by design: what matters is that (a) the user's identity is proven by the HMAC, and
(b) every query is scoped to exactly one shop_id — a client can pick WHICH public shop to
view, never read across shops or act as another user.
"""
from typing import Iterator, Optional

from fastapi import Depends, Header, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.base import SessionLocal
from app.db.models import Customer, Shop, TgUser
from app.db.repo import customers as customers_repo
from app.db.repo import shops as shops_repo
from app.db.repo import users as users_repo
from app.services.subscription import is_shop_open
from app.services.telegram_auth import InitData, InitDataError, verify_init_data


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def api_error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def get_init_data(
    x_telegram_init_data: Optional[str] = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> InitData:
    try:
        return verify_init_data(x_telegram_init_data or "", settings.BOT_TOKEN, settings.INITDATA_MAX_AGE_SECONDS)
    except InitDataError as e:
        raise api_error(401, f"auth_{e}", "Invalid Telegram authentication") from e


def get_tg_user(init: InitData = Depends(get_init_data), db: Session = Depends(get_db)) -> TgUser:
    u = init.user
    return users_repo.upsert_tg_user(db, init.user_id, u.get("username"), u.get("first_name"))


def get_shop(
    request: Request,
    init: InitData = Depends(get_init_data),
    db: Session = Depends(get_db),
    shop_q: Optional[str] = Query(default=None, alias="shop"),
) -> Shop:
    slug = init.start_param or shop_q
    if not slug:
        raise api_error(400, "shop_missing", "No shop specified")
    shop = shops_repo.get_by_slug(db, slug)
    if shop is None:
        raise api_error(404, "shop_not_found", "Shop not found")
    request.state.shop_id = shop.id
    return shop


def get_open_shop(shop: Shop = Depends(get_shop)) -> Shop:
    """Subscription gate for everything except the read-only shop header."""
    if not is_shop_open(shop):
        raise api_error(403, "shop_paused", "This shop is temporarily closed")
    return shop


def get_customer(
    shop: Shop = Depends(get_open_shop),
    user: TgUser = Depends(get_tg_user),
    db: Session = Depends(get_db),
) -> Customer:
    return customers_repo.get_or_create(db, shop.id, user.id)
