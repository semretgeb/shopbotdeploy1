from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Category, Product

PAGE_SIZE_CHAT = 5
PAGE_SIZE_API = 24


# --- categories -------------------------------------------------------------

def list_categories(db: Session, shop_id: int) -> list[Category]:
    return list(db.scalars(select(Category).where(Category.shop_id == shop_id).order_by(Category.position, Category.name)))


def get_category(db: Session, shop_id: int, category_id: int) -> Optional[Category]:
    return db.scalar(select(Category).where(Category.shop_id == shop_id, Category.id == category_id))


def get_or_create_category(db: Session, shop_id: int, name: str) -> Category:
    name = name.strip()[:48]
    cat = db.scalar(select(Category).where(Category.shop_id == shop_id, func.lower(Category.name) == name.lower()))
    if cat is None:
        position = db.scalar(select(func.count()).where(Category.shop_id == shop_id)) or 0
        cat = Category(shop_id=shop_id, name=name, position=position)
        db.add(cat)
        db.flush()
    return cat


def category_counts(db: Session, shop_id: int) -> dict[Optional[int], int]:
    rows = db.execute(
        select(Product.category_id, func.count())
        .where(Product.shop_id == shop_id, Product.is_active.is_(True))
        .group_by(Product.category_id)
    ).all()
    return {cid: n for cid, n in rows}


# --- products ---------------------------------------------------------------

def count(db: Session, shop_id: int, active_only: bool = False) -> int:
    q = select(func.count()).where(Product.shop_id == shop_id)
    if active_only:
        q = q.where(Product.is_active.is_(True))
    return db.scalar(q) or 0


def get(db: Session, shop_id: int, product_id: int) -> Optional[Product]:
    return db.scalar(select(Product).where(Product.shop_id == shop_id, Product.id == product_id))


def list_page(
    db: Session,
    shop_id: int,
    page: int = 0,
    page_size: int = PAGE_SIZE_CHAT,
    category_id: Optional[int] = None,
    active_only: bool = False,
    query: Optional[str] = None,
) -> tuple[list[Product], int]:
    """Returns (items, total). Pages are 0-based."""
    base = select(Product).where(Product.shop_id == shop_id)
    if active_only:
        base = base.where(Product.is_active.is_(True))
    if category_id is not None:
        base = base.where(Product.category_id == category_id)
    if query:
        base = base.where(Product.name.ilike(f"%{query.strip()}%"))
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    items = list(db.scalars(base.order_by(Product.created_at.desc(), Product.id.desc()).offset(page * page_size).limit(page_size)))
    return items, total


def create(
    db: Session,
    shop_id: int,
    name: str,
    price_santim: int,
    stock: Optional[int],
    photo_file_id: Optional[str],
    photo_unique_id: Optional[str],
    category_id: Optional[int] = None,
    description: Optional[str] = None,
) -> Product:
    p = Product(
        shop_id=shop_id,
        name=name.strip()[:80],
        price_santim=price_santim,
        stock=stock,
        photo_file_id=photo_file_id,
        photo_unique_id=photo_unique_id,
        category_id=category_id,
        description=(description or None),
    )
    db.add(p)
    db.flush()
    return p


def update(db: Session, shop_id: int, product_id: int, **fields) -> Optional[Product]:
    p = get(db, shop_id, product_id)
    if p is None:
        return None
    for k, v in fields.items():
        setattr(p, k, v)
    db.flush()
    return p


def delete(db: Session, shop_id: int, product_id: int) -> bool:
    p = get(db, shop_id, product_id)
    if p is None:
        return False
    db.delete(p)
    db.flush()
    return True


def decrement_stock(db: Session, shop_id: int, product_id: int, qty: int) -> bool:
    """Returns False if not enough stock. NULL stock = unlimited."""
    p = get(db, shop_id, product_id)
    if p is None or not p.is_active:
        return False
    if p.stock is None:
        return True
    if p.stock < qty:
        return False
    p.stock -= qty
    db.flush()
    return True
