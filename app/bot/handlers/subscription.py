"""Owner subscription screen and the 'I paid' screenshot that goes to the admin."""
from telegram.constants import ParseMode
from telegram.error import TelegramError

from app.bot import states as S
from app.bot.context import Ctx
from app.bot.keyboards import Btn, cancel_only, kb, nav_row
from app.bot.router import arg, on_callback, on_state
from app.config import get_settings
from app.locales import norm_lang, t
from app.services import subscription as sub
from app.services.notifications import _md


def status_line(ctx: Ctx, shop) -> str:
    if not sub.is_shop_open(shop):
        return ctx.t("subs.status_paused")
    key = "subs.status_trial" if shop.status == "trial" else "subs.status_active"
    return ctx.t(key, days=sub.days_left(shop))


async def show(ctx: Ctx) -> None:
    s = get_settings()
    shop = ctx.owner_shop
    text = ctx.t("subs.title", status=status_line(ctx, shop), until=sub.fmt_date(sub.access_until(shop)),
                 price=s.SUBSCRIPTION_PRICE_ETB, account=_md(s.PAYMENT_ACCOUNT))
    await ctx.render(text, kb([[Btn(ctx.t("subs.i_paid"), callback_data="subs:paid")], nav_row(ctx.lang)]))


@on_callback("subs")
async def subs_cb(ctx: Ctx) -> None:
    await ctx.answer()
    if not ctx.owner_shop:
        return
    if arg(ctx, 1) == "paid":
        ctx.set_state(S.SUBS_PROOF, {})
        await ctx.render(ctx.t("subs.send_proof"), cancel_only(ctx.lang))
    else:
        await show(ctx)


@on_state(S.SUBS_PROOF)
async def subs_proof_input(ctx: Ctx) -> None:
    shop = ctx.owner_shop
    if shop is None:
        ctx.reset()
        return
    if not ctx.msg.photo:
        await ctx.send(ctx.t("subs.send_proof"), cancel_only(ctx.lang))
        return
    s = get_settings()
    admin_lang = "en"
    owner = ctx.user.username and f"@{ctx.user.username}" or (ctx.user.first_name or "?")
    caption = t("adm.payment_card", admin_lang, id=shop.id, name=_md(shop.name), owner=_md(owner), owner_id=shop.owner_id,
                until=sub.fmt_date(sub.access_until(shop)))
    markup = kb([
        [Btn(t("adm.approve_1", admin_lang), callback_data=f"adm:approve:{shop.id}:1"), Btn(t("adm.approve_3", admin_lang), callback_data=f"adm:approve:{shop.id}:3")],
        [Btn(t("adm.reject", admin_lang), callback_data=f"adm:reject:{shop.id}")],
    ])
    try:
        await ctx.tg.bot.send_photo(s.ADMIN_TELEGRAM_ID, ctx.msg.photo[-1].file_id, caption=caption, parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
    except TelegramError:
        pass
    ctx.reset()
    await ctx.send(ctx.t("subs.proof_sent"))
    await show(ctx)


async def notify_owner(bot, shop, key: str, **kw) -> None:
    """Send a subscription notice to a shop owner in their language."""
    lang = norm_lang(shop.owner.lang if shop.owner else "am")
    try:
        await bot.send_message(shop.owner_id, t(key, lang, **kw), parse_mode=ParseMode.MARKDOWN)
    except TelegramError:
        pass
