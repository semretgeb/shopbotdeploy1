"""Place orders, upload payment proof, list my orders — all scoped to (shop, customer)."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import api_error, get_customer, get_db, get_open_shop, get_tg_user
from app.api.schemas import OrderIn, OrderItemOut, OrderOut, ProofOut
from app.db.models import Customer, Order, Shop, TgUser
from app.db.repo import customers as customers_repo
from app.db.repo import orders as repo
from app.locales import norm_lang, t
from app.services import notifications
from app.services.money import fmt_price

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

MAX_PROOF_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


def get_bot(request: Request):
    ptb = getattr(request.app.state, "ptb", None)
    return ptb.bot if ptb else None


def to_out(o: Order, shop: Shop, lang: str) -> OrderOut:
    return OrderOut(
        id=o.id,
        code=o.code,
        status=o.status,
        payment_method=o.payment_method,
        has_proof=bool(o.payment_proof_file_id),
        total_santim=o.total_santim,
        total_text=fmt_price(o.total_santim, lang),
        items=[
            OrderItemOut(product_id=it.product_id, name=it.name_snapshot, price_santim=it.price_santim, qty=it.qty,
                         line_total_text=fmt_price(it.price_santim * it.qty, lang))
            for it in o.items
        ],
        full_name=o.full_name,
        phone=o.phone,
        address=o.address,
        note=o.note,
        payment_info=shop.payment_info if o.payment_method == "transfer" else None,
        created_at=o.created_at,
    )


@router.post("/orders", response_model=OrderOut, status_code=201)
async def place_order(
    body: OrderIn,
    request: Request,
    shop: Shop = Depends(get_open_shop),
    customer: Customer = Depends(get_customer),
    user: TgUser = Depends(get_tg_user),
    db: Session = Depends(get_db),
) -> OrderOut:
    lang = norm_lang(user.lang)
    try:
        order = repo.create(
            db, shop.id, customer.id,
            items=[(i.product_id, i.qty) for i in body.items],
            full_name=body.full_name, phone=body.phone, address=body.address,
            payment_method=body.payment_method, source="miniapp", note=body.note,
        )
    except repo.OrderError as e:
        raise api_error(409, e.code, t(f"order.err_{e.code}", lang)) from e

    if body.save_details:
        customers_repo.save_details(db, shop.id, user.id, body.full_name, body.phone, body.address)
    db.commit()  # order must be durable before we message anyone

    await notifications.notify_new_order(get_bot(request), db, shop, order, customer)
    db.commit()
    return to_out(order, shop, lang)


@router.post("/orders/{order_id}/proof", response_model=ProofOut)
async def upload_proof(
    order_id: int,
    request: Request,
    file: UploadFile = File(...),
    shop: Shop = Depends(get_open_shop),
    customer: Customer = Depends(get_customer),
    db: Session = Depends(get_db),
) -> ProofOut:
    order = repo.get_for_customer(db, shop.id, customer.id, order_id)
    if order is None:
        raise api_error(404, "order_not_found", "Order not found")
    if order.payment_method != "transfer":
        raise api_error(400, "not_transfer", "This order is pay-on-delivery")
    if (file.content_type or "").lower() not in ALLOWED_IMAGE_TYPES:
        raise api_error(415, "bad_image", "Please upload a JPG, PNG or WebP image")
    data = await file.read(MAX_PROOF_BYTES + 1)
    if len(data) > MAX_PROOF_BYTES:
        raise api_error(413, "too_large", "Image must be under 5 MB")
    if len(data) < 100:
        raise api_error(400, "bad_image", "Empty image")

    file_id = await notifications.send_proof_to_owner(get_bot(request), db, shop, order, data, file.filename or "proof.jpg")
    if file_id is None:
        # No bot (tests) or Telegram failure: keep a marker so the UI can show "received", retry later.
        repo.set_proof(db, shop.id, order.id, "pending-upload")
    db.commit()
    return ProofOut(ok=True, order_id=order.id, has_proof=bool(order.payment_proof_file_id))


@router.get("/orders", response_model=list[OrderOut])
def my_orders(
    shop: Shop = Depends(get_open_shop),
    customer: Customer = Depends(get_customer),
    user: TgUser = Depends(get_tg_user),
    db: Session = Depends(get_db),
) -> list[OrderOut]:
    lang = norm_lang(user.lang)
    return [to_out(o, shop, lang) for o in repo.list_for_customer(db, shop.id, customer.id)]


@router.get("/orders/{order_id}", response_model=OrderOut)
def my_order(
    order_id: int,
    shop: Shop = Depends(get_open_shop),
    customer: Customer = Depends(get_customer),
    user: TgUser = Depends(get_tg_user),
    db: Session = Depends(get_db),
) -> OrderOut:
    o = repo.get_for_customer(db, shop.id, customer.id, order_id)
    if o is None:
        raise api_error(404, "order_not_found", "Order not found")
    return to_out(o, shop, norm_lang(user.lang))
