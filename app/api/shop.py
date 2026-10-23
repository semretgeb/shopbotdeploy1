from fastapi import APIRouter, Depends

from app.api.deps import get_shop, get_tg_user
from app.api.schemas import ShopOut
from app.db.models import Shop, TgUser
from app.locales import norm_lang
from app.services.images import image_url
from app.services.subscription import is_shop_open

router = APIRouter(prefix="/api")


@router.get("/shop", response_model=ShopOut)
def get_shop_profile(shop: Shop = Depends(get_shop), user: TgUser = Depends(get_tg_user)) -> ShopOut:
    # Uses get_shop (not the open gate) so a paused shop can still render its "closed" screen.
    return ShopOut(
        id=shop.id,
        slug=shop.slug,
        name=shop.name,
        description=shop.description,
        phone=shop.phone,
        delivery_info=shop.delivery_info,
        payment_info=shop.payment_info,
        logo_url=image_url(shop.logo_file_id, 320),
        is_open=is_shop_open(shop),
        lang=norm_lang(user.lang),
    )
