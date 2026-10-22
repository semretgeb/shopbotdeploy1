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
