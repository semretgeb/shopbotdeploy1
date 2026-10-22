from datetime import timedelta
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Shop, SubscriptionEvent, utcnow
from app.services.slug import make_slug


def get_by_slug(db: Session, slug: str) -> Optional[Shop]:
    return db.scalar(select(Shop).where(Shop.slug == slug))


def get_by_owner(db: Session, owner_id: int) -> Optional[Shop]:
    return db.scalar(select(Shop).where(Shop.owner_id == owner_id))


def get(db: Session, shop_id: int) -> Optional[Shop]:
    return db.get(Shop, shop_id)


def create(db: Session, owner_id: int, name: str, trial_days: int) -> Shop:
    """Creates a shop with a unique ASCII slug and a trial that starts now."""
    existing = {s for (s,) in db.execute(select(Shop.slug)).all()}
    slug = make_slug(name, taken=existing)
    now = utcnow()
    shop = Shop(
        owner_id=owner_id,
        name=name,
        slug=slug,
        status="trial",
        trial_ends_at=now + timedelta(days=trial_days),
    )
    db.add(shop)
    db.flush()
    db.add(SubscriptionEvent(shop_id=shop.id, action="trial", created_by=owner_id, note=f"{trial_days} days"))
    db.flush()
    return shop


def list_all(db: Session, offset: int = 0, limit: int = 20) -> list[Shop]:
    return list(db.scalars(select(Shop).order_by(Shop.id.desc()).offset(offset).limit(limit)))


def count_by_status(db: Session) -> dict[str, int]:
    rows = db.execute(select(Shop.status, func.count()).group_by(Shop.status)).all()
    return {status: n for status, n in rows}
