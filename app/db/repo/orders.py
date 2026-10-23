"""Orders repo. Every function is scoped by shop_id; customer-facing reads are scoped by customer too."""
import secrets
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Order, OrderItem, Product, utcnow

STATUSES = ("pending", "confirmed", "on_the_way", "delivered", "rejected", "cancelled")
ACTIVE_STATUSES = ("pending", "confirmed", "on_the_way")
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I


class OrderError(Exception):
    def __init__(self, code: str, product_id: Optional[int] = None):
        super().__init__(code)
        self.code = code
        self.product_id = product_id


def _new_code(db: Session, shop_id: int) -> str:
    for _ in range(20):
        code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(4))
        if db.scalar(select(func.count()).where(Order.shop_id == shop_id, Order.code == code)) == 0:
            return code
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(6))


def count_by_status(db: Session, shop_id: int, status: str) -> int:
    return db.scalar(select(func.count()).where(Order.shop_id == shop_id, Order.status == status)) or 0


def get(db: Session, shop_id: int, order_id: int) -> Optional[Order]:
    return db.scalar(select(Order).where(Order.shop_id == shop_id, Order.id == order_id))


def get_for_customer(db: Session, shop_id: int, customer_id: int, order_id: int) -> Optional[Order]:
    return db.scalar(select(Order).where(Order.shop_id == shop_id, Order.customer_id == customer_id, Order.id == order_id))


def list_for_customer(db: Session, shop_id: int, customer_id: int, limit: int = 20) -> list[Order]:
    return list(db.scalars(
        select(Order).where(Order.shop_id == shop_id, Order.customer_id == customer_id).order_by(Order.id.desc()).limit(limit)
    ))


def list_for_owner(db: Session, shop_id: int, status: Optional[str], page: int, page_size: int) -> tuple[list[Order], int]:
    q = select(Order).where(Order.shop_id == shop_id)
    if status == "history":
        q = q.where(Order.status.in_(("delivered", "rejected", "cancelled")))
    elif status:
        q = q.where(Order.status == status)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    items = list(db.scalars(q.order_by(Order.id.desc()).offset(page * page_size).limit(page_size)))
    return items, total


def create(
    db: Session,
    shop_id: int,
    customer_id: int,
    items: list[tuple[int, int]],  # (product_id, qty)
    full_name: str,
    phone: str,
    address: str,
    payment_method: str,
    source: str,
    note: Optional[str] = None,
) -> Order:
    """Re-prices every line from the DB, checks and decrements stock, snapshots names.
    Raises OrderError(code, product_id): empty | bad_qty | product_unavailable | out_of_stock."""
    if not items:
        raise OrderError("empty")
    merged: dict[int, int] = {}
    for pid, qty in items:
        if qty < 1 or qty > 99:
            raise OrderError("bad_qty", pid)
        merged[pid] = merged.get(pid, 0) + qty

    order_items: list[OrderItem] = []
    total = 0
    for pid, qty in merged.items():
        p = db.scalar(select(Product).where(Product.shop_id == shop_id, Product.id == pid, Product.is_active.is_(True)))
        if p is None:
            raise OrderError("product_unavailable", pid)
        if p.stock is not None:
            if p.stock < qty:
                raise OrderError("out_of_stock", pid)
            p.stock -= qty
        total += p.price_santim * qty
        order_items.append(OrderItem(product_id=p.id, name_snapshot=p.name, price_santim=p.price_santim, qty=qty))

    order = Order(
        shop_id=shop_id,
        customer_id=customer_id,
        code=_new_code(db, shop_id),
        status="pending",
        source=source,
        payment_method=payment_method,
        full_name=full_name.strip()[:80],
        phone=phone.strip()[:32],
        address=address.strip(),
        note=(note or "").strip()[:500] or None,
        total_santim=total,
        items=order_items,
    )
    db.add(order)
    db.flush()
    return order


def set_status(db: Session, shop_id: int, order_id: int, status: str) -> Optional[Order]:
    if status not in STATUSES:
        return None
    o = get(db, shop_id, order_id)
    if o is None:
        return None
    if status in ("rejected", "cancelled") and o.status not in ("rejected", "cancelled"):
        _restock(db, o)
    o.status = status
    o.updated_at = utcnow()
    db.flush()
    return o


def _restock(db: Session, order: Order) -> None:
    for it in order.items:
        if it.product_id is None:
            continue
        p = db.get(Product, it.product_id)
        if p is not None and p.stock is not None:
            p.stock += it.qty


def set_proof(db: Session, shop_id: int, order_id: int, file_id: str) -> Optional[Order]:
    o = get(db, shop_id, order_id)
    if o is None:
        return None
    o.payment_proof_file_id = file_id
    db.flush()
    return o


def stats_today(db: Session, shop_id: Optional[int] = None) -> dict[str, int]:
    start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    q = select(func.count()).where(Order.created_at >= start)
    if shop_id is not None:
        q = q.where(Order.shop_id == shop_id)
    return {"orders_today": db.scalar(q) or 0}
