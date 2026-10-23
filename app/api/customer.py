from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_customer, get_db, get_tg_user
from app.api.schemas import MeIn, MeOut
from app.db.models import Customer, TgUser
from app.db.repo import customers as customers_repo
from app.db.repo import users as users_repo
from app.locales import norm_lang

router = APIRouter(prefix="/api")


@router.get("/me", response_model=MeOut)
def get_me(customer: Customer = Depends(get_customer), user: TgUser = Depends(get_tg_user)) -> MeOut:
    return MeOut(full_name=customer.full_name, phone=customer.phone, address=customer.address, lang=norm_lang(user.lang))


@router.put("/me", response_model=MeOut)
def update_me(
    body: MeIn,
    customer: Customer = Depends(get_customer),
    user: TgUser = Depends(get_tg_user),
    db: Session = Depends(get_db),
) -> MeOut:
    customers_repo.save_details(db, customer.shop_id, user.id, body.full_name, body.phone, body.address)
    if body.lang:
        users_repo.set_lang(db, user.id, body.lang)
        user.lang = body.lang
    db.refresh(customer)
    return MeOut(full_name=customer.full_name, phone=customer.phone, address=customer.address, lang=norm_lang(user.lang))
