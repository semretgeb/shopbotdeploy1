"""Fixed-window AI call counters: per customer/hour, per shop/day, global/day.

Rows live in ai_usage. (shop_id, tg_user_id) = (S, U) customer window, (S, NULL) shop window,
(NULL, NULL) global window. Counters survive restarts (DB) and are cheap (one row per window).
"""
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AiUsage, utcnow


def _window(now: datetime, hours: bool) -> datetime:
    return now.replace(minute=0, second=0, microsecond=0) if hours else now.replace(hour=0, minute=0, second=0, microsecond=0)


def _row(db: Session, shop_id: Optional[int], tg_user_id: Optional[int], window_start: datetime) -> AiUsage:
    row = db.scalar(select(AiUsage).where(AiUsage.shop_id.is_(shop_id) if shop_id is None else AiUsage.shop_id == shop_id,
                                          AiUsage.tg_user_id.is_(tg_user_id) if tg_user_id is None else AiUsage.tg_user_id == tg_user_id,
                                          AiUsage.window_start == window_start))
    if row is None:
        row = AiUsage(shop_id=shop_id, tg_user_id=tg_user_id, window_start=window_start, count=0)
        db.add(row)
        db.flush()
    return row


def check_and_count(
    db: Session,
    shop_id: int,
    tg_user_id: int,
    per_customer_hourly: int,
    per_shop_daily: int,
    global_daily: int,
    now: Optional[datetime] = None,
) -> Optional[str]:
    """Increments all three counters and returns None, or the limit that was hit:
    'customer' | 'shop' | 'global'. Nothing is counted when a limit is hit."""
    now = now or utcnow()
    cust = _row(db, shop_id, tg_user_id, _window(now, hours=True))
    shop = _row(db, shop_id, None, _window(now, hours=False))
    glob = _row(db, None, None, _window(now, hours=False))
    if cust.count >= per_customer_hourly:
        return "customer"
    if shop.count >= per_shop_daily:
        return "shop"
    if glob.count >= global_daily:
        return "global"
    cust.count += 1
    shop.count += 1
    glob.count += 1
    db.flush()
    return None


def calls_today(db: Session, shop_id: Optional[int] = None, now: Optional[datetime] = None) -> int:
    now = now or utcnow()
    row = db.scalar(select(AiUsage).where(
        AiUsage.shop_id.is_(None) if shop_id is None else AiUsage.shop_id == shop_id,
        AiUsage.tg_user_id.is_(None), AiUsage.window_start == _window(now, hours=False)))
    return row.count if row else 0


def purge_old(db: Session, older_than_days: int = 7) -> int:
    cutoff = utcnow() - timedelta(days=older_than_days)
    rows = list(db.scalars(select(AiUsage).where(AiUsage.window_start < cutoff)))
    for r in rows:
        db.delete(r)
    db.flush()
    return len(rows)
