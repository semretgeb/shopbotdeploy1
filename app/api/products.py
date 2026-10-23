from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import api_error, get_db, get_open_shop, get_tg_user
from app.api.schemas import CategoryOut, ProductOut, ProductPage
from app.db.models import Product, Shop, TgUser
from app.db.repo import products as repo
from app.locales import norm_lang
from app.services.images import image_url
from app.services.money import fmt_price

router = APIRouter(prefix="/api")


def to_out(p: Product, lang: str) -> ProductOut:
    return ProductOut(
        id=p.id,
        name=p.name,
        description=p.description,
        price_santim=p.price_santim,
        price_text=fmt_price(p.price_santim, lang),
        stock=p.stock,
        in_stock=p.stock is None or p.stock > 0,
        category_id=p.category_id,
        thumb_url=image_url(p.photo_file_id, 320),
        image_url=image_url(p.photo_file_id, 640),
    )


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(shop: Shop = Depends(get_open_shop), db: Session = Depends(get_db)) -> list[CategoryOut]:
    counts = repo.category_counts(db, shop.id)
    return [CategoryOut(id=c.id, name=c.name, count=counts.get(c.id, 0)) for c in repo.list_categories(db, shop.id) if counts.get(c.id, 0) > 0]


@router.get("/products", response_model=ProductPage)
def list_products(
    shop: Shop = Depends(get_open_shop),
    user: TgUser = Depends(get_tg_user),
    db: Session = Depends(get_db),
    category_id: Optional[int] = Query(default=None),
    page: int = Query(default=0, ge=0),
    q: Optional[str] = Query(default=None, max_length=60),
) -> ProductPage:
    lang = norm_lang(user.lang)
    items, total = repo.list_page(db, shop.id, page=page, page_size=repo.PAGE_SIZE_API, category_id=category_id, active_only=True, query=q)
    return ProductPage(
        items=[to_out(p, lang) for p in items],
        page=page,
        page_size=repo.PAGE_SIZE_API,
        total=total,
        has_more=(page + 1) * repo.PAGE_SIZE_API < total,
    )


@router.get("/products/{product_id}", response_model=ProductOut)
def get_product(
    product_id: int,
    shop: Shop = Depends(get_open_shop),
    user: TgUser = Depends(get_tg_user),
    db: Session = Depends(get_db),
) -> ProductOut:
    p = repo.get(db, shop.id, product_id)
    if p is None or not p.is_active:
        raise api_error(404, "product_not_found", "Product not found")
    return to_out(p, norm_lang(user.lang))
