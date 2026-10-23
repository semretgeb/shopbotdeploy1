"""Single source of truth for 'is this shop allowed to operate?' — used by bot AND API."""
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models import Shop, SubscriptionEvent, utcnow


def access_until(shop: Shop) -> datetime:
    return max(shop.trial_ends_at, shop.paid_until or shop.trial_ends_at)


def is_shop_open(shop: Shop, now: Optional[datetime] = None) -> bool:
    now = now or utcnow()
    return shop.status != "paused" and now < access_until(shop)


def days_left(shop: Shop, now: Optional[datetime] = None) -> int:
    now = now or utcnow()
    return max(0, (access_until(shop) - now).days)


def approve(db: Session, shop: Shop, months: int, admin_id: int, note: Optional[str] = None) -> Shop:
    """Extends paid access by N months (30 days each) from now or from current paid_until if later."""
    now = utcnow()
    base = max(now, shop.paid_until or now)
    shop.paid_until = base + timedelta(days=30 * months)
    shop.status = "active"
    db.add(SubscriptionEvent(shop_id=shop.id, action="approve", months=months, created_by=admin_id, note=note))
    db.flush()
    return shop


def extend_days(db: Session, shop: Shop, days: int, admin_id: int) -> Shop:
    now = utcnow()
    base = max(now, access_until(shop))
    shop.paid_until = base + timedelta(days=days)
    if shop.status == "paused":
        shop.status = "active"
    db.add(SubscriptionEvent(shop_id=shop.id, action="extend", note=f"{days} days", created_by=admin_id))
    db.flush()
    return shop


def pause(db: Session, shop: Shop, admin_id: int, note: Optional[str] = None) -> Shop:
    shop.status = "paused"
    db.add(SubscriptionEvent(shop_id=shop.id, action="pause", created_by=admin_id, note=note))
    db.flush()
    return shop


def resume(db: Session, shop: Shop, admin_id: int) -> Shop:
    shop.status = "active" if shop.paid_until and shop.paid_until > utcnow() else "trial"
    db.add(SubscriptionEvent(shop_id=shop.id, action="resume", created_by=admin_id))
    db.flush()
    return shop


# --- expiry job ------------------------------------------------------------------

WARN_DAYS = 3


def fmt_date(dt: Optional[datetime]) -> str:
    return dt.strftime("%d %b %Y") if dt else "-"


def _has_event(db: Session, shop_id: int, action: str, note: str) -> bool:
    from sqlalchemy import select

    return db.scalar(select(SubscriptionEvent.id).where(
        SubscriptionEvent.shop_id == shop_id, SubscriptionEvent.action == action, SubscriptionEvent.note == note)) is not None


def find_due(db: Session, now: Optional[datetime] = None) -> tuple[list[Shop], list[Shop]]:
    """Returns (shops to expire now, shops to warn). Idempotent: warned/expired once per access period."""
    from sqlalchemy import select

    now = now or utcnow()
    expire, warn = [], []
    for shop in db.scalars(select(Shop).where(Shop.status != "paused")):
        until = access_until(shop)
        if until <= now:
            expire.append(shop)
        elif until - now <= timedelta(days=WARN_DAYS) and not _has_event(db, shop.id, "warn", until.isoformat()):
            warn.append(shop)
    return expire, warn


def expire(db: Session, shop: Shop) -> None:
    shop.status = "paused"
    db.add(SubscriptionEvent(shop_id=shop.id, action="expire", created_by=0, note=access_until(shop).isoformat()))
    db.flush()


def mark_warned(db: Session, shop: Shop) -> None:
    db.add(SubscriptionEvent(shop_id=shop.id, action="warn", created_by=0, note=access_until(shop).isoformat()))
    db.flush()


async def run_expiry_cycle(bot) -> dict[str, int]:
    """Called hourly from the app. Pauses expired shops and warns those ending within WARN_DAYS."""
    from telegram.constants import ParseMode
    from telegram.error import TelegramError

    from app.config import get_settings
    from app.db.base import db_session
    from app.locales import norm_lang, t

    s = get_settings()
    counts = {"expired": 0, "warned": 0}
    with db_session() as db:
        to_expire, to_warn = find_due(db)
        for shop in to_expire:
            expire(db, shop)
            counts["expired"] += 1
            if bot is not None:
                lang = norm_lang(shop.owner.lang if shop.owner else "am")
                try:
                    await bot.send_message(shop.owner_id, t("subs.expired", lang, price=s.SUBSCRIPTION_PRICE_ETB, account=s.PAYMENT_ACCOUNT), parse_mode=ParseMode.MARKDOWN)
                except TelegramError:
                    pass
        for shop in to_warn:
            mark_warned(db, shop)
            counts["warned"] += 1
            if bot is not None:
                lang = norm_lang(shop.owner.lang if shop.owner else "am")
                try:
                    await bot.send_message(shop.owner_id, t("subs.expiring", lang, days=max(1, days_left(shop)), until=fmt_date(access_until(shop)),
                                                            price=s.SUBSCRIPTION_PRICE_ETB, account=s.PAYMENT_ACCOUNT), parse_mode=ParseMode.MARKDOWN)
                except TelegramError:
                    pass
    return counts
