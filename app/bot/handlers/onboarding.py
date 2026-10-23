"""Owner onboarding wizard: name -> description -> phone -> delivery -> payment (5 steps)."""
import html
import re

from telegram.constants import ParseMode

from app.bot import states as S
from app.bot.context import Ctx
from app.bot.keyboards import REMOVE, cancel_only, phone_request, skip_cancel
from app.bot.router import arg, on_callback, on_state
from app.config import get_settings
from app.db.repo import shops as shops_repo
from app.services.qr import shop_link

PHONE_RE = re.compile(r"^\+?[0-9][0-9 \-]{7,15}$")
STEP_INDEX = {s: i + 1 for i, s in enumerate(S.ONB_STEPS)}


def _step(ctx: Ctx, state: str) -> str:
    return ctx.t("onb.step", n=STEP_INDEX[state])


async def prompt(ctx: Ctx, state: str) -> None:
    ctx.set_state(state, ctx.data)
    step = _step(ctx, state)
    if state == S.ONB_NAME:
        await ctx.send(ctx.t("onb.name", step=step), cancel_only(ctx.lang) if not ctx.owner_shop else None)
    elif state == S.ONB_DESC:
        await ctx.send(ctx.t("onb.desc", step=step), skip_cancel(ctx.lang))
    elif state == S.ONB_PHONE:
        await ctx.send(ctx.t("onb.phone", step=step), None, )
        await ctx.tg.bot.send_message(ctx.chat_id, "👇", reply_markup=phone_request(ctx.lang))
    elif state == S.ONB_DELIVERY:
        await ctx.send(ctx.t("onb.delivery", step=step), skip_cancel(ctx.lang))
    elif state == S.ONB_PAYMENT:
        await ctx.send(ctx.t("onb.payment", step=step), skip_cancel(ctx.lang))


@on_callback("onb")
async def onb_cb(ctx: Ctx) -> None:
    await ctx.answer()
    if arg(ctx, 1) == "start":
        if ctx.owner_shop:
            await resume_onboarding(ctx)
        else:
            await prompt(ctx, S.ONB_NAME)


async def resume_onboarding(ctx: Ctx) -> None:
    """Shop row exists but onboarding_done is False (owner left mid-wizard or app redeployed)."""
    shop = ctx.owner_shop
    await ctx.send(ctx.t("onb.resume"))
    if not shop.description:
        await prompt(ctx, S.ONB_DESC)
    elif not shop.phone:
        await prompt(ctx, S.ONB_PHONE)
    elif shop.delivery_info is None:
        await prompt(ctx, S.ONB_DELIVERY)
    else:
        await prompt(ctx, S.ONB_PAYMENT)


@on_state(S.ONB_NAME)
async def onb_name(ctx: Ctx) -> None:
    name = ctx.text
    if not 2 <= len(name) <= 80:
        await ctx.send(ctx.t("onb.name_invalid"))
        return
    if ctx.owner_shop is None:
        ctx.owner_shop = shops_repo.create(ctx.db, ctx.user.id, name, get_settings().TRIAL_DAYS)
    else:
        ctx.owner_shop.name = name
    await prompt(ctx, S.ONB_DESC)


@on_state(S.ONB_DESC)
async def onb_desc(ctx: Ctx) -> None:
    desc = ctx.text
    if len(desc) > 300:
        await ctx.send(ctx.t("onb.desc_invalid"))
        return
    ctx.owner_shop.description = desc or ""
    await prompt(ctx, S.ONB_PHONE)


@on_state(S.ONB_PHONE)
async def onb_phone(ctx: Ctx) -> None:
    phone = ctx.msg.contact.phone_number if ctx.msg.contact else ctx.text
    if not phone or not PHONE_RE.match(phone):
        await ctx.send(ctx.t("onb.phone_invalid"))
        return
    ctx.owner_shop.phone = phone
    await ctx.tg.bot.send_message(ctx.chat_id, "✅", reply_markup=REMOVE)
    await prompt(ctx, S.ONB_DELIVERY)


@on_state(S.ONB_DELIVERY)
async def onb_delivery(ctx: Ctx) -> None:
    ctx.owner_shop.delivery_info = ctx.text[:500]
    await prompt(ctx, S.ONB_PAYMENT)


@on_state(S.ONB_PAYMENT)
async def onb_payment(ctx: Ctx) -> None:
    ctx.owner_shop.payment_info = ctx.text[:500]
    await finish(ctx)


@on_callback("skip")
async def skip_cb(ctx: Ctx) -> None:
    """Skip is only meaningful inside wizards; each wizard owns its own skip semantics."""
    await ctx.answer()
    st = ctx.state.state
    if st == S.ONB_DESC:
        ctx.owner_shop.description = ""
        await prompt(ctx, S.ONB_PHONE)
    elif st == S.ONB_DELIVERY:
        ctx.owner_shop.delivery_info = ""
        await prompt(ctx, S.ONB_PAYMENT)
    elif st == S.ONB_PAYMENT:
        ctx.owner_shop.payment_info = ""
        await finish(ctx)
    elif st == S.ORD_REJECT_REASON:
        from app.bot.handlers.orders_owner import skip_reject_reason
        await skip_reject_reason(ctx)
    else:
        from app.bot.handlers.products import skip_in_product_wizard
        await skip_in_product_wizard(ctx)


async def finish(ctx: Ctx) -> None:
    from app.bot.handlers.start import owner_home

    shop = ctx.owner_shop
    shop.onboarding_done = True
    ctx.db.flush()
    link = shop_link(get_settings().BOT_USERNAME, shop.slug)
    # HTML parse mode: the shop link contains "_" (yene_sukbot) which breaks legacy Markdown.
    await ctx.tg.bot.send_message(
        ctx.chat_id,
        ctx.t("onb.done", shop=html.escape(shop.name), link=html.escape(link), date=shop.trial_ends_at.strftime("%d %b %Y")),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )
    from app.bot.handlers.admin import notify_admin_new_shop
    await notify_admin_new_shop(ctx.tg.bot, shop)
    await owner_home(ctx)
