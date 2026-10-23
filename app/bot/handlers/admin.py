"""/admin commands and buttons. Only ADMIN_TELEGRAM_ID can use any of this."""
import asyncio
from datetime import timedelta
from typing import Optional

from sqlalchemy import func, select
from telegram import Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from app.bot import states as S
from app.bot.context import Ctx, build_ctx
from app.bot.handlers.subscription import notify_owner
from app.bot.keyboards import Btn, cancel_only, kb, nav_row
from app.bot.router import arg, on_callback, on_state
from app.config import get_settings
from app.db.base import db_session
from app.db.models import Order, Shop, utcnow
from app.db.repo import ai_usage, forwarded as fq_repo, orders as orders_repo, products as products_repo, shops as shops_repo
from app.services import subscription as sub
from app.services.notifications import _md

PAGE = 10
ADMIN_LANG = "en"


def _t(key: str, **kw) -> str:
    from app.locales import t

    return t(key, ADMIN_LANG, **kw)


def _owner_label(shop: Shop) -> str:
    o = shop.owner
    if o is None:
        return "?"
    return f"@{o.username}" if o.username else (o.first_name or str(o.id))


def _status(shop: Shop) -> str:
    return "paused" if not sub.is_shop_open(shop) else shop.status


# --- /admin command ----------------------------------------------------------------

async def admin_command(update: Update, tg: ContextTypes.DEFAULT_TYPE) -> None:
    with db_session() as db:
        ctx = build_ctx(update, tg, db)
        if not ctx.is_admin:
            await ctx.send(_t("adm.denied"))
            return
        args = list(tg.args or [])
        cmd = args[0].lower() if args else "help"
        rest = args[1:]
        try:
            if cmd == "shops":
                await list_shops(ctx, int(rest[0]) if rest else 0)
            elif cmd == "shop":
                await shop_card(ctx, int(rest[0]))
            elif cmd == "approve":
                await do_approve(ctx, int(rest[0]), int(rest[1]))
            elif cmd == "extend":
                await do_extend(ctx, int(rest[0]), int(rest[1]))
            elif cmd == "pause":
                await do_pause(ctx, int(rest[0]), " ".join(rest[1:]) or None)
            elif cmd == "resume":
                await do_resume(ctx, int(rest[0]))
            elif cmd == "stats":
                await stats(ctx)
            elif cmd == "broadcast":
                await broadcast_preview(ctx, " ".join(rest))
            else:
                await ctx.send(_t("adm.help"), kb([[Btn("📊 Stats", callback_data="adm:stats"), Btn("🏪 Shops", callback_data="adm:shops:0")]]))
        except (IndexError, ValueError):
            await ctx.send(_t("adm.usage", usage="/admin " + cmd + " <id> [value]") + "\n\n" + _t("adm.help"))


# --- views -------------------------------------------------------------------------

async def list_shops(ctx: Ctx, page: int) -> None:
    shops = shops_repo.list_all(ctx.db, page * PAGE, PAGE)
    rows = [[Btn(_t("adm.shop_row", id=s.id, name=s.name, status=_status(s), days=sub.days_left(s))[:60], callback_data=f"adm:shop:{s.id}")] for s in shops]
    nav = []
    if page > 0:
        nav.append(Btn("◀️", callback_data=f"adm:shops:{page - 1}"))
    if len(shops) == PAGE:
        nav.append(Btn("▶️", callback_data=f"adm:shops:{page + 1}"))
    rows.append(nav)
    rows.append([Btn("📊 Stats", callback_data="adm:stats")])
    await ctx.render(_t("adm.shops_title", page=page + 1) + ("" if shops else "\n\n—"), kb(rows))


def card_text(ctx: Ctx, shop: Shop) -> str:
    return _t(
        "adm.shop_card",
        id=shop.id, name=_md(shop.name), slug=shop.slug, owner=_md(_owner_label(shop)), owner_id=shop.owner_id,
        status=_status(shop), trial=sub.fmt_date(shop.trial_ends_at), paid=sub.fmt_date(shop.paid_until),
        until=sub.fmt_date(sub.access_until(shop)), days=sub.days_left(shop),
        products=products_repo.count(ctx.db, shop.id), orders=orders_repo.count_by_status(ctx.db, shop.id, "pending"),
        ai=ai_usage.calls_today(ctx.db, shop.id), created=sub.fmt_date(shop.created_at),
    )


def card_kb(shop: Shop):
    rows = [[Btn(_t("adm.approve_1"), callback_data=f"adm:approve:{shop.id}:1"), Btn(_t("adm.approve_3"), callback_data=f"adm:approve:{shop.id}:3")]]
    if shop.status == "paused":
        rows.append([Btn(_t("adm.resume"), callback_data=f"adm:resume:{shop.id}")])
    else:
        rows.append([Btn(_t("adm.pause"), callback_data=f"adm:pause:{shop.id}")])
    rows.append([Btn("◀️ Shops", callback_data="adm:shops:0")])
    return kb(rows)


async def shop_card(ctx: Ctx, shop_id: int) -> None:
    shop = shops_repo.get(ctx.db, shop_id)
    if shop is None:
        await ctx.render(_t("adm.not_found"), kb([[Btn("◀️ Shops", callback_data="adm:shops:0")]]))
        return
    await ctx.render(card_text(ctx, shop), card_kb(shop))


async def stats(ctx: Ctx) -> None:
    by = shops_repo.count_by_status(ctx.db)
    now = utcnow()
    week = ctx.db.scalar(select(func.count()).where(Order.created_at >= now - timedelta(days=7))) or 0
    text = _t(
        "adm.stats",
        total=sum(by.values()), trial=by.get("trial", 0), active=by.get("active", 0), paused=by.get("paused", 0),
        orders_today=orders_repo.stats_today(ctx.db)["orders_today"], orders_week=week,
        ai_today=ai_usage.calls_today(ctx.db), open_q=fq_repo.count_open(ctx.db),
    )
    await ctx.render(text, kb([[Btn("🏪 Shops", callback_data="adm:shops:0")]]))


# --- actions -------------------------------------------------------------------------

async def _done(ctx: Ctx, shop: Shop) -> None:
    msg = _t("adm.done", id=shop.id, status=_status(shop), until=sub.fmt_date(sub.access_until(shop)))
    if ctx.update.callback_query and ctx.update.callback_query.message and ctx.update.callback_query.message.photo:
        await ctx.answer(msg, alert=True)  # payment-claim photo card: leave it, just confirm
        try:
            await ctx.update.callback_query.edit_message_reply_markup(None)
        except TelegramError:
            pass
        return
    await ctx.render(msg + "\n\n" + card_text(ctx, shop), card_kb(shop))


async def do_approve(ctx: Ctx, shop_id: int, months: int) -> None:
    shop = shops_repo.get(ctx.db, shop_id)
    if shop is None or months < 1:
        await ctx.send(_t("adm.not_found"))
        return
    sub.approve(ctx.db, shop, months, ctx.user.id)
    ctx.db.commit()
    await notify_owner(ctx.tg.bot, shop, "subs.approved", until=sub.fmt_date(sub.access_until(shop)))
    await _done(ctx, shop)


async def do_extend(ctx: Ctx, shop_id: int, days: int) -> None:
    shop = shops_repo.get(ctx.db, shop_id)
    if shop is None or days < 1:
        await ctx.send(_t("adm.not_found"))
        return
    sub.extend_days(ctx.db, shop, days, ctx.user.id)
    ctx.db.commit()
    await notify_owner(ctx.tg.bot, shop, "subs.extended", until=sub.fmt_date(sub.access_until(shop)))
    await _done(ctx, shop)


async def do_pause(ctx: Ctx, shop_id: int, reason: Optional[str]) -> None:
    shop = shops_repo.get(ctx.db, shop_id)
    if shop is None:
        await ctx.send(_t("adm.not_found"))
        return
    s = get_settings()
    sub.pause(ctx.db, shop, ctx.user.id, reason)
    ctx.db.commit()
    await notify_owner(ctx.tg.bot, shop, "subs.paused", reason=f"\n💬 {_md(reason)}" if reason else "", price=s.SUBSCRIPTION_PRICE_ETB, account=_md(s.PAYMENT_ACCOUNT))
    await _done(ctx, shop)


async def do_resume(ctx: Ctx, shop_id: int) -> None:
    shop = shops_repo.get(ctx.db, shop_id)
    if shop is None:
        await ctx.send(_t("adm.not_found"))
        return
    sub.resume(ctx.db, shop, ctx.user.id)
    if not sub.is_shop_open(shop):  # access date already passed: give a week so resume means something
        sub.extend_days(ctx.db, shop, 7, ctx.user.id)
    ctx.db.commit()
    await notify_owner(ctx.tg.bot, shop, "subs.resumed")
    await _done(ctx, shop)


async def do_reject(ctx: Ctx, shop_id: int) -> None:
    shop = shops_repo.get(ctx.db, shop_id)
    if shop is None:
        await ctx.answer(_t("adm.not_found"), alert=True)
        return
    await notify_owner(ctx.tg.bot, shop, "subs.rejected")
    await ctx.answer(_t("adm.rejected"), alert=True)
    try:
        await ctx.update.callback_query.edit_message_reply_markup(None)
    except TelegramError:
        pass


# --- broadcast --------------------------------------------------------------------------

async def broadcast_preview(ctx: Ctx, text: str) -> None:
    if not text.strip():
        await ctx.send(_t("adm.usage", usage="/admin broadcast <text>"))
        return
    n = sum(shops_repo.count_by_status(ctx.db).values())
    ctx.set_state(S.ADMIN_BROADCAST, {"text": text.strip()[:3000]})
    await ctx.send(_t("adm.broadcast_preview", n=n, text=text.strip()[:3000]),
                   kb([[Btn(_t("adm.broadcast_send"), callback_data="adm:bsend"), Btn("❌", callback_data="cancel")]]))


async def broadcast_send(ctx: Ctx) -> None:
    text = ctx.data.get("text")
    ctx.reset()
    if not text:
        return
    owner_ids = [s for (s,) in ctx.db.execute(select(Shop.owner_id)).all()]
    sent = failed = 0
    for oid in owner_ids:
        try:
            await ctx.tg.bot.send_message(oid, text)
            sent += 1
        except TelegramError:
            failed += 1
        await asyncio.sleep(0.05)  # stay under Telegram's ~30 msg/s
    await ctx.render(_t("adm.broadcast_done", sent=sent, failed=failed))


@on_state(S.ADMIN_BROADCAST)
async def broadcast_text_input(ctx: Ctx) -> None:
    if ctx.is_admin:
        await broadcast_preview(ctx, ctx.text)


# --- callbacks ---------------------------------------------------------------------------

@on_callback("adm")
async def admin_cb(ctx: Ctx) -> None:
    if not ctx.is_admin:
        await ctx.answer(_t("adm.denied"), alert=True)
        return
    action = arg(ctx, 1)
    sid = int(arg(ctx, 2, "0") or 0)
    if action == "shops":
        await ctx.answer()
        await list_shops(ctx, sid)
    elif action == "shop":
        await ctx.answer()
        await shop_card(ctx, sid)
    elif action == "stats":
        await ctx.answer()
        await stats(ctx)
    elif action == "approve":
        await do_approve(ctx, sid, int(arg(ctx, 3, "1")))
        await ctx.answer()
    elif action == "pause":
        await do_pause(ctx, sid, None)
        await ctx.answer()
    elif action == "resume":
        await do_resume(ctx, sid)
        await ctx.answer()
    elif action == "reject":
        await do_reject(ctx, sid)
    elif action == "bsend":
        await ctx.answer()
        await broadcast_send(ctx)
    else:
        await ctx.answer()


async def notify_admin_new_shop(bot, shop: Shop) -> None:
    s = get_settings()
    try:
        await bot.send_message(
            s.ADMIN_TELEGRAM_ID,
            _t("adm.new_shop", id=shop.id, name=_md(shop.name), owner=_md(_owner_label(shop)), owner_id=shop.owner_id, trial=sub.fmt_date(shop.trial_ends_at)),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb([[Btn("🏪 Open", callback_data=f"adm:shop:{shop.id}")]]),
        )
    except TelegramError:
        pass
