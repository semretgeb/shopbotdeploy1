"""AI assistant in chat: customer free text -> answer from shop data, or forward to the owner.
Owner replies to forwarded questions with a button; the reply goes straight to the customer."""
from telegram.constants import ChatAction, ParseMode
from telegram.error import TelegramError

from app.bot import states as S
from app.bot.context import Ctx
from app.bot.keyboards import Btn, cancel_only, kb, nav_row, web_app_button
from app.bot.router import arg, on_callback, on_state
from app.config import get_settings
from app.db.repo import ai_usage as usage_repo
from app.db.repo import customers as customers_repo
from app.db.repo import forwarded as fq_repo
from app.db.repo import shops as shops_repo
from app.locales import norm_lang, t
from app.services import ai
from app.services import subscription as sub
from app.services.notifications import _md


def _phone(shop) -> str:
    return shop.phone or "-"


async def answer_customer(ctx: Ctx, shop, question: str) -> None:
    """Entry point for any customer free text while idle (or in CUST_ASK)."""
    s = get_settings()
    if not shop.ai_enabled:
        await ctx.send(ctx.t("ai.disabled", phone=_phone(shop)), kb([nav_row(ctx.lang)]))
        return
    limit = usage_repo.check_and_count(ctx.db, shop.id, ctx.user.id, s.AI_PER_CUSTOMER_HOURLY, s.AI_PER_SHOP_DAILY, s.AI_GLOBAL_DAILY)
    if limit:
        await ctx.send(ctx.t("ai.rate_limited", phone=_phone(shop)), kb([[Btn(ctx.t("customer.contact"), callback_data="cust:contact")], nav_row(ctx.lang)]))
        return
    try:
        await ctx.tg.bot.send_chat_action(ctx.chat_id, ChatAction.TYPING)
    except TelegramError:
        pass
    history = ctx.data.get("chat_hist") or []
    result = await ai.ask(ctx.db, shop, question, ctx.lang, history)
    if result.forward:
        if result.reason in ("provider_error", "no_provider"):
            await ctx.send(ctx.t("ai.error", phone=_phone(shop)), kb([nav_row(ctx.lang)]))
            return
        await forward_to_owner(ctx, shop, question)
        return
    hist = (history + [{"role": "user", "content": question[:500]}, {"role": "assistant", "content": result.answer[:500]}])[-ai.MAX_HISTORY:]
    ctx.set_state(S.CUST_ASK, {**ctx.data, "chat_hist": hist})
    open_btn = web_app_button(ctx.t("customer.open_shop"), f"{s.webapp_url}?shop={shop.slug}")
    await ctx.send(_md(result.answer), kb([[open_btn, Btn(ctx.t("customer.browse"), callback_data="cust:browse")], nav_row(ctx.lang)]))


async def forward_to_owner(ctx: Ctx, shop, question: str) -> None:
    customer = customers_repo.get_or_create(ctx.db, shop.id, ctx.user.id)
    fq = fq_repo.create(ctx.db, shop.id, customer.id, question)
    ctx.db.commit()
    owner_lang = norm_lang(shop.owner.lang if shop.owner else "am")
    name = ctx.user.first_name or customer.full_name or str(ctx.user.id)
    try:
        m = await ctx.tg.bot.send_message(
            shop.owner_id,
            t("fq.owner_card", owner_lang, name=_md(name), question=_md(question)),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb([[Btn(t("fq.reply_btn", owner_lang), callback_data=f"fq:reply:{fq.id}")]]),
        )
        fq.owner_msg_id = m.message_id
        ctx.db.flush()
    except TelegramError:
        pass
    await ctx.send(ctx.t("ai.forwarded"), kb([[Btn(ctx.t("customer.contact"), callback_data="cust:contact")], nav_row(ctx.lang)]))


@on_state(S.CUST_ASK)
async def cust_ask_input(ctx: Ctx) -> None:
    shop = shops_repo.get(ctx.db, ctx.state.shop_id) if ctx.state.shop_id else None
    if shop is None or not sub.is_shop_open(shop):
        ctx.reset()
        return
    if ctx.msg.photo:
        from app.bot.handlers.shop_customer import photo_while_idle
        if await photo_while_idle(ctx, shop):
            return
    if not ctx.text:
        return
    await answer_customer(ctx, shop, ctx.text)


@on_callback("ask")
async def ask_cb(ctx: Ctx) -> None:
    await ctx.answer()
    shop = shops_repo.get(ctx.db, ctx.state.shop_id) if ctx.state.shop_id else None
    if shop is None:
        return
    ctx.set_state(S.CUST_ASK, ctx.data)
    await ctx.render(ctx.t("ai.ask_prompt", shop=shop.name), kb([nav_row(ctx.lang)]))


# --- owner side ------------------------------------------------------------------

@on_callback("fq")
async def fq_cb(ctx: Ctx) -> None:
    if not ctx.owner_shop:
        await ctx.answer()
        return
    fq = fq_repo.get(ctx.db, ctx.owner_shop.id, int(arg(ctx, 2, "0")))
    if fq is None:
        await ctx.answer(ctx.t("fq.not_found"), alert=True)
        return
    await ctx.answer()
    customer = customers_repo.get(ctx.db, ctx.owner_shop.id, fq.customer_id)
    name = (customer.tg_user.first_name if customer and customer.tg_user else None) or (customer.full_name if customer else "") or "?"
    ctx.set_state(S.FQ_REPLY, {"fq_id": fq.id})
    await ctx.send(ctx.t("fq.reply_prompt", name=_md(name)) + f"\n\n_{_md(fq.question)}_", cancel_only(ctx.lang))


@on_state(S.FQ_REPLY)
async def fq_reply_input(ctx: Ctx) -> None:
    shop = ctx.owner_shop
    fq = fq_repo.get(ctx.db, shop.id, int(ctx.data.get("fq_id", 0))) if shop else None
    if fq is None:
        ctx.reset()
        await ctx.send(ctx.t("fq.not_found"))
        return
    if not ctx.text:
        return
    fq_repo.answer(ctx.db, shop.id, fq.id, ctx.text)
    ctx.db.commit()
    customer = customers_repo.get(ctx.db, shop.id, fq.customer_id)
    if customer:
        cust_lang = norm_lang(customer.tg_user.lang if customer.tg_user else "am")
        try:
            await ctx.tg.bot.send_message(
                customer.tg_user_id, t("fq.customer_reply", cust_lang, shop=_md(shop.name), answer=_md(ctx.text)),
                parse_mode=ParseMode.MARKDOWN,
            )
        except TelegramError:
            pass
    if fq.owner_msg_id:
        name = (customer.tg_user.first_name if customer and customer.tg_user else None) or "?"
        try:
            await ctx.tg.bot.edit_message_text(
                ctx.t("fq.owner_card_answered", name=_md(name), question=_md(fq.question), answer=_md(ctx.text)),
                chat_id=ctx.chat_id, message_id=fq.owner_msg_id, parse_mode=ParseMode.MARKDOWN,
            )
        except TelegramError:
            pass
    ctx.reset()
    await ctx.send(ctx.t("fq.sent"))
