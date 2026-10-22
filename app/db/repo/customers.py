from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Customer


def get_or_create(db: Session, shop_id: int, tg_user_id: int) -> Customer:
    cust = db.scalar(select(Customer).where(Customer.shop_id == shop_id, Customer.tg_user_id == tg_user_id))
    if cust is None:
        cust = Customer(shop_id=shop_id, tg_user_id=tg_user_id)
        db.add(cust)
        db.flush()
    return cust


def get(db: Session, shop_id: int, customer_id: int) -> Optional[Customer]:
    return db.scalar(select(Customer).where(Customer.shop_id == shop_id, Customer.id == customer_id))


def save_details(
    db: Session,
    shop_id: int,
    tg_user_id: int,
    full_name: Optional[str] = None,
    phone: Optional[str] = None,
    address: Optional[str] = None,
) -> Customer:
    cust = get_or_create(db, shop_id, tg_user_id)
    if full_name is not None:
        cust.full_name = full_name.strip()[:80]
    if phone is not None:
        cust.phone = phone.strip()[:32]
    if address is not None:
        cust.address = address.strip()
    db.flush()
    return cust
