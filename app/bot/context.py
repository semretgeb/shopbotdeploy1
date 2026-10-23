"""Per-update context: one DB session, the user, their language, state and role.

Handlers receive a `Ctx` instead of digging through Update/CallbackContext each time.
"""
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy.orm import Session
from telegram import InlineKeyboardMarkup, InputMediaPhoto, Message, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from app.config import get_settings
from app.db.models import ChatState, Shop, TgUser
from app.db.repo import shops as shops_repo
from app.db.repo import states as states_repo
from app.db.repo import users as users_repo
from app.locales import norm_lang, t

log = logging.getLogger(__name__)


@dataclass
class Ctx:
    update: Update
    tg: ContextTypes.DEFAULT_TYPE
    db: Session
    user: TgUser
    state: ChatState
    owner_shop: Optional[Shop] = None  # shop this user OWNS (if any)
    extra: dict[str, Any] = field(default_factory=dict)

    # --- convenience -------------------------------------------------------
    @property
    def lang(self) -> str:
        return norm_lang(self.user.lang)

    @property
    def is_admin(self) -> bool:
        return self.user.id == get_settings().ADMIN_TELEGRAM_ID

    @property
    def is_owner(self) -> bool:
        return self.owner_shop is not None

    @property
    def chat_id(self) -> int:
        return self.update.effective_chat.id

    @property
    def msg(self) -> Optional[Message]:
        return self.update.effective_message

    @property
    def text(self) -> str:
        return (self.msg.text or self.msg.caption or "").strip() if self.msg else ""

    @property
    def data(self) -> dict[str, Any]:
        return dict(self.state.data or {})

    def t(self, key: str, **kw) -> str:
        return t(key, self.lang, **kw)

    # --- state -------------------------------------------------------------
    def set_state(self, state: str, data: Optional[dict] = None, shop_id=...) -> None:
        self.state = states_repo.set_state(self.db, self.user.id, state, data, shop_id)

    def update_data(self, **fields) -> None:
        self.state = states_repo.update_data(self.db, self.user.id, **fields)

    def reset(self) -> None:
        self.state = states_repo.reset(self.db, self.user.id)

    # --- output ------------------------------------------------------------
    async def send(self, text: str, kb: Optional[InlineKeyboardMarkup] = None, **kw) -> Message:
        kw.setdefault("parse_mode", ParseMode.MARKDOWN)
        kw.setdefault("disable_web_page_preview", True)
        return await self.tg.bot.send_message(self.chat_id, text, reply_markup=kb, **kw)

    async def render(self, text: str, kb: Optional[InlineKeyboardMarkup] = None, parse_mode=ParseMode.MARKDOWN) -> Optional[Message]:
        """Edit the message the button lives on when possible (UX rule: edit in place), else send."""
        q = self.update.callback_query
        if q and q.message and not q.message.photo:
            try:
                return await q.edit_message_text(
                    text, reply_markup=kb, parse_mode=parse_mode, disable_web_page_preview=True
                )
            except BadRequest as e:
                if "not modified" in str(e).lower():
                    return q.message
                log.debug("edit failed (%s); sending new message", e)
        elif q and q.message and q.message.photo:
            # Can't turn a photo message into a text message: remove the card and send fresh.
            try:
                await q.message.delete()
            except BadRequest:
                pass
        return await self.send(text, kb, parse_mode=parse_mode)

    async def send_photo(self, file_id: str, caption: str, kb: Optional[InlineKeyboardMarkup] = None) -> Message:
        return await self.tg.bot.send_photo(self.chat_id, file_id, caption=caption, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

    async def edit_photo_card(self, file_id: str, caption: str, kb: Optional[InlineKeyboardMarkup] = None) -> None:
        q = self.update.callback_query
        if q and q.message and q.message.photo:
            try:
                await q.edit_message_media(InputMediaPhoto(file_id, caption=caption, parse_mode=ParseMode.MARKDOWN), reply_markup=kb)
                return
            except BadRequest as e:
                if "not modified" in str(e).lower():
                    return
            try:
                await q.message.delete()
            except BadRequest:
                pass
        elif q and q.message:
            try:
                await q.message.delete()
            except BadRequest:
                pass
        await self.send_photo(file_id, caption, kb)

    async def answer(self, text: Optional[str] = None, alert: bool = False) -> None:
        q = self.update.callback_query
        if q:
            try:
                await q.answer(text=text, show_alert=alert)
            except BadRequest:
                pass


def build_ctx(update: Update, tg: ContextTypes.DEFAULT_TYPE, db: Session) -> Ctx:
    u = update.effective_user
    is_new = db.get(TgUser, u.id) is None
    user = users_repo.upsert_tg_user(db, u.id, u.username, u.first_name, lang=u.language_code if u.language_code in ("am", "en") else None)
    state = states_repo.get_state(db, u.id)
    if is_new:
        # First contact ever: ask for the language before anything else.
        state = states_repo.update_data(db, u.id, lang_pending=True)
    owner_shop = shops_repo.get_by_owner(db, u.id)
    return Ctx(update=update, tg=tg, db=db, user=user, state=state, owner_shop=owner_shop)
