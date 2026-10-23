"""Telegram messages triggered by orders: the owner's order card and the customer's status message.

Both the API (Mini App orders) and the chat fallback call these. Message ids are stored on the
order so later status changes edit the same messages in place instead of spamming new ones.
"""
import logging
from typing import Optional

from sqlalchemy.orm import Session
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.constants import ParseMode
from telegram.error import TelegramError

from app.db.models import Customer, Order, Shop, TgUser
from app.locales import norm_lang, t
from app.services.money import fmt_price

log = logging.getLogger(__name__)

STATUS_KEYS = {
    "pending": "order.status_pending",
    "confirmed": "order.status_confirmed",
    "on_the_way": "order.status_on_the_way",
    "delivered": "order.status_delivered",
    "rejected": "order.status_rejected",
    "cancelled": "order.status_cancelled",
}


def _items_text(order: Order, lang: str) -> str:
    return "\n".join(f"• {it.name_snapshot} × {it.qty} — {fmt_price(it.price_santim * it.qty, lang)}" for it in order.items)


def _md(s: Optional[str]) -> str:
    """Escape the few Markdown-v1 characters that break parsing in user-supplied text."""
    return (s or "").replace("*", "＊").replace("_", "＿").replace("`", "'").replace("[", "［")


def owner_card_text(order: Order, lang: str) -> str:
    pay = t("order.pay_cod" if order.payment_method == "cod" else "order.pay_transfer", lang)
    if order.payment_method == "transfer":
        pay += " · " + t("order.proof_attached" if order.payment_proof_file_id else "order.proof_missing", lang)
    note = t("order.note", lang, note=_md(order.note)) if order.note else ""
    return t(
        "order.card_owner",
        lang,
        code=order.code,
        total=fmt_price(order.total_santim, lang),
        pay=pay,
        name=_md(order.full_name),
        phone=_md(order.phone),
        address=_md(order.address),
        note=note,
        items=_items_text(order, lang),
        status=t(STATUS_KEYS[order.status], lang),
    ).replace("\n\n\n", "\n\n")


def owner_card_kb(order: Order, lang: str) -> Optional[InlineKeyboardMarkup]:
    o = f"ord:{order.id}"
    phone = order.phone.replace(" ", "")
    call = InlineKeyboardButton(t("order.btn_call", lang), callback_data=f"ord:call:{order.id}")
    if order.status == "pending":
        rows = [
            [InlineKeyboardButton(t("order.btn_confirm", lang), callback_data=f"ord:status:{order.id}:confirmed"),
             InlineKeyboardButton(t("order.btn_reject", lang), callback_data=f"ord:status:{order.id}:rejected")],
            [call],
        ]
    elif order.status == "confirmed":
        rows = [[InlineKeyboardButton(t("order.btn_on_the_way", lang), callback_data=f"ord:status:{order.id}:on_the_way")], [call]]
    elif order.status == "on_the_way":
        rows = [[InlineKeyboardButton(t("order.btn_delivered", lang), callback_data=f"ord:status:{order.id}:delivered")], [call]]
    else:
        rows = [[call]]
    return InlineKeyboardMarkup(rows)


def customer_status_text(order: Order, shop: Shop, lang: str) -> str:
    status = t(STATUS_KEYS[order.status], lang)
    extra = ""
    if order.payment_method == "transfer" and order.status in ("pending", "confirmed") and not order.payment_proof_file_id:
        extra = "\n\n" + t("order.transfer_instructions", lang, total=fmt_price(order.total_santim, lang), payment=_md(shop.payment_info) or t("not_set", lang))
    return t(
        "order.status_customer",
        lang,
        code=order.code,
        shop=_md(shop.name),
        items=_items_text(order, lang),
        total=fmt_price(order.total_santim, lang),
        status=status,
    ) + extra


# --- sending -------------------------------------------------------------------

async def notify_new_order(bot: Optional[Bot], db: Session, shop: Shop, order: Order, customer: Customer) -> None:
    """Owner card + customer status message. Best-effort: never fails the order."""
    if bot is None:
        log.warning("No bot available; skipping notifications for order %s", order.code)
        return
    owner: Optional[TgUser] = shop.owner
    owner_lang = norm_lang(owner.lang if owner else "am")
    try:
        if order.payment_proof_file_id:
            m = await bot.send_photo(
                shop.owner_id, order.payment_proof_file_id,
                caption=owner_card_text(order, owner_lang), parse_mode=ParseMode.MARKDOWN, reply_markup=owner_card_kb(order, owner_lang),
            )
        else:
            m = await bot.send_message(
                shop.owner_id, owner_card_text(order, owner_lang), parse_mode=ParseMode.MARKDOWN, reply_markup=owner_card_kb(order, owner_lang),
            )
        order.owner_msg_id = m.message_id
    except TelegramError:
        log.exception("Could not send order card to owner %s", shop.owner_id)

    cust_user: Optional[TgUser] = customer.tg_user
    cust_lang = norm_lang(cust_user.lang if cust_user else "am")
    try:
        m = await bot.send_message(customer.tg_user_id, customer_status_text(order, shop, cust_lang), parse_mode=ParseMode.MARKDOWN)
        order.customer_msg_id = m.message_id
    except TelegramError:
        log.exception("Could not send status to customer %s", customer.tg_user_id)
    db.flush()


async def notify_status_change(bot: Optional[Bot], db: Session, shop: Shop, order: Order, reason: Optional[str] = None) -> None:
    """Edit the customer's status message in place (or send a new one if editing fails)."""
    if bot is None:
        return
    customer = order.customer
    cust_user: Optional[TgUser] = customer.tg_user if customer else None
    lang = norm_lang(cust_user.lang if cust_user else "am")
    text = customer_status_text(order, shop, lang)
    if reason:
        text += "\n" + t("order.reason", lang, reason=_md(reason))
    try:
        if order.customer_msg_id:
            await bot.edit_message_text(text, chat_id=customer.tg_user_id, message_id=order.customer_msg_id, parse_mode=ParseMode.MARKDOWN)
            # A silent edit is easy to miss; also ping with a short line.
            await bot.send_message(customer.tg_user_id, f"#{order.code}: {t(STATUS_KEYS[order.status], lang)}")
        else:
            m = await bot.send_message(customer.tg_user_id, text, parse_mode=ParseMode.MARKDOWN)
            order.customer_msg_id = m.message_id
    except TelegramError:
        try:
            m = await bot.send_message(customer.tg_user_id, text, parse_mode=ParseMode.MARKDOWN)
            order.customer_msg_id = m.message_id
        except TelegramError:
            log.exception("Could not notify customer %s", customer.tg_user_id)
    db.flush()


async def refresh_owner_card(bot: Optional[Bot], shop: Shop, order: Order) -> None:
    """Re-render the owner's card after a status change or proof upload."""
    if bot is None or not order.owner_msg_id:
        return
    owner = shop.owner
    lang = norm_lang(owner.lang if owner else "am")
    try:
        if order.payment_proof_file_id:
            await bot.edit_message_caption(
                chat_id=shop.owner_id, message_id=order.owner_msg_id, caption=owner_card_text(order, lang),
                parse_mode=ParseMode.MARKDOWN, reply_markup=owner_card_kb(order, lang),
            )
        else:
            await bot.edit_message_text(
                owner_card_text(order, lang), chat_id=shop.owner_id, message_id=order.owner_msg_id,
                parse_mode=ParseMode.MARKDOWN, reply_markup=owner_card_kb(order, lang),
            )
    except TelegramError as e:
        if "not modified" not in str(e).lower():
            log.warning("Could not refresh owner card for %s: %s", order.code, e)


async def send_proof_to_owner(bot: Optional[Bot], db: Session, shop: Shop, order: Order, image: bytes, filename: str) -> Optional[str]:
    """Uploads the screenshot to the owner's chat; the returned file_id becomes our stored proof."""
    if bot is None:
        return None
    owner = shop.owner
    lang = norm_lang(owner.lang if owner else "am")
    try:
        m = await bot.send_photo(
            shop.owner_id, InputFile(image, filename=filename),
            caption=t("order.new_proof", lang, code=order.code), reply_to_message_id=order.owner_msg_id, allow_sending_without_reply=True,
        )
        file_id = m.photo[-1].file_id
        order.payment_proof_file_id = file_id
        db.flush()
        await refresh_owner_card(bot, shop, order)
        return file_id
    except TelegramError:
        log.exception("Could not forward payment proof for %s", order.code)
        return None
