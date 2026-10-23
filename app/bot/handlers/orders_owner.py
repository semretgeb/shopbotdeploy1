"""Owner side of orders: list by status, order card, Confirm / Reject (+reason) / On the way / Delivered / Call."""
from app.bot import states as S
from app.bot.context import Ctx
from app.bot.keyboards import Btn, kb, nav_row, paginator, skip_cancel
from app.bot.router import arg, on_callback, on_state
from app.db.repo import orders as repo
from app.services import notifications as notif
from app.services.money import fmt_price

PAGE = 6
TABS = ("pending", "confirmed", "on_the_way", "history")


async def show_tabs(ctx: Ctx, tab: str = "pending", page: int = 0) -> None:
    shop = ctx.owner_shop
    counts = {s: repo.count_by_status(ctx.db, shop.id, s) for s in ("pending", "confirmed", "on_the_way")}
    items, total = repo.list_for_owner(ctx.db, shop.id, tab, page, PAGE)
    text = ctx.t("ord.tabs_title", counts=ctx.t("ord.counts", **counts))
    tab_row = [Btn(("• " if t == tab else "") + ctx.t(f"ord.tab_{t}"), callback_data=f"ord:list:{t}:0") for t in TABS]
    rows = [tab_row[:2], tab_row[2:]]
    if not items:
        text += "\n\n" + ctx.t("ord.list_empty")
    for o in items:
        rows.append([Btn(ctx.t("ord.row", code=o.code, total=fmt_price(o.total_santim, ctx.lang), name=o.full_name)[:60], callback_data=f"ord:view:{o.id}:{tab}:{page}")])
    rows.append(paginator(ctx.lang, "ordp", page, total, PAGE, tab))
    rows.append(nav_row(ctx.lang))
    await ctx.render(text, kb(rows))


def card_kb(ctx: Ctx, order, back: str):
    base = notif.owner_card_kb(order, ctx.lang)
    rows = list(base.inline_keyboard) if base else []
    rows.append(nav_row(ctx.lang, back=back))
    return kb(rows)


async def show_card(ctx: Ctx, order, back: str) -> None:
    text = notif.owner_card_text(order, ctx.lang)
    if order.payment_proof_file_id and not order.payment_proof_file_id.startswith("pending"):
        await ctx.edit_photo_card(order.payment_proof_file_id, text, card_kb(ctx, order, back))
    else:
        await ctx.render(text, card_kb(ctx, order, back))


@on_callback("ordp")
async def ord_page_cb(ctx: Ctx) -> None:
    await ctx.answer()
    if ctx.owner_shop:
        await show_tabs(ctx, arg(ctx, 3, "pending"), int(arg(ctx, 2, "0")))


@on_callback("ord")
async def ord_cb(ctx: Ctx) -> None:
    if not ctx.owner_shop:
        await ctx.answer()
        return
    shop = ctx.owner_shop
    action = arg(ctx, 1)

    if action == "list":
        await ctx.answer()
        ctx.reset()
        await show_tabs(ctx, arg(ctx, 2, "pending"), int(arg(ctx, 3, "0")))
        return

    order = repo.get(ctx.db, shop.id, int(arg(ctx, 2, "0")))
    if order is None:
        await ctx.answer(ctx.t("ord.not_found"), alert=True)
        return

    if action == "view":
        await ctx.answer()
        back = f"ord:list:{arg(ctx, 3, 'pending')}:{arg(ctx, 4, '0')}"
        await show_card(ctx, order, back)

    elif action == "call":
        await ctx.answer()
        try:
            await ctx.tg.bot.send_contact(ctx.chat_id, phone_number=order.phone, first_name=order.full_name[:64])
        except Exception:
            await ctx.send(ctx.t("ord.call_text", name=order.full_name, phone=order.phone))

    elif action == "status":
        new = arg(ctx, 3)
        if new == "rejected":
            await ctx.answer()
            ctx.set_state(S.ORD_REJECT_REASON, {"order_id": order.id})
            await ctx.send(ctx.t("ord.reject_reason", code=order.code), skip_cancel(ctx.lang))
            return
        await apply_status(ctx, order, new)


async def apply_status(ctx: Ctx, order, new: str, reason: str | None = None) -> None:
    allowed = {"pending": ("confirmed", "rejected"), "confirmed": ("on_the_way", "delivered", "rejected"), "on_the_way": ("delivered",)}
    if new not in allowed.get(order.status, ()):
        await ctx.answer(ctx.t("ord.already", status=ctx.t(notif.STATUS_KEYS[order.status])), alert=True)
        return
    repo.set_status(ctx.db, ctx.owner_shop.id, order.id, new)
    ctx.db.commit()
    await ctx.answer(ctx.t("ord.updated", code=order.code, status=ctx.t(notif.STATUS_KEYS[new])))
    await notif.notify_status_change(ctx.tg.bot, ctx.db, ctx.owner_shop, order, reason)
    # Re-render whichever message the owner is looking at (the pushed card or the list view).
    q = ctx.update.callback_query
    if q and q.message and q.message.message_id == order.owner_msg_id:
        await notif.refresh_owner_card(ctx.tg.bot, ctx.owner_shop, order)
    elif q and q.message:
        await show_card(ctx, order, "ord:list:pending:0")
    else:
        await notif.refresh_owner_card(ctx.tg.bot, ctx.owner_shop, order)
        await ctx.send(ctx.t("ord.updated", code=order.code, status=ctx.t(notif.STATUS_KEYS[new])))


@on_state(S.ORD_REJECT_REASON)
async def reject_reason_input(ctx: Ctx) -> None:
    await _finish_reject(ctx, ctx.text[:200] or None)


async def _finish_reject(ctx: Ctx, reason: str | None) -> None:
    order = repo.get(ctx.db, ctx.owner_shop.id, int(ctx.data.get("order_id", 0))) if ctx.owner_shop else None
    ctx.reset()
    if order is None:
        await ctx.send(ctx.t("ord.not_found"))
        return
    await apply_status(ctx, order, "rejected", reason)


async def skip_reject_reason(ctx: Ctx) -> None:
    """Called from the shared skip handler when state == ORD_REJECT_REASON."""
    await _finish_reject(ctx, None)
