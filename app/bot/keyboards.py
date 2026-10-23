"""Inline keyboard builders. Callback data format: "ns:action[:arg[:arg]]" (max 64 bytes)."""
from typing import Iterable, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, WebAppInfo

from app.locales import t

Btn = InlineKeyboardButton


def cb(*parts) -> str:
    return ":".join(str(p) for p in parts)


def nav_row(lang: str, back: Optional[str] = None, home: bool = True) -> list[Btn]:
    row = []
    if back:
        row.append(Btn(t("btn.back", lang), callback_data=back))
    if home:
        row.append(Btn(t("btn.home", lang), callback_data="home"))
    return row


def kb(rows: Iterable[Iterable[Btn]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([list(r) for r in rows if r])


def lang_picker() -> InlineKeyboardMarkup:
    return kb([[Btn(t("lang.am", "am"), callback_data="lang:am"), Btn(t("lang.en", "en"), callback_data="lang:en")]])


def cancel_only(lang: str) -> InlineKeyboardMarkup:
    return kb([[Btn(t("btn.cancel", lang), callback_data="cancel")]])


def skip_cancel(lang: str) -> InlineKeyboardMarkup:
    return kb([[Btn(t("btn.skip", lang), callback_data="skip"), Btn(t("btn.cancel", lang), callback_data="cancel")]])


def phone_request(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(t("onb.phone_share", lang), request_contact=True)]], resize_keyboard=True, one_time_keyboard=True
    )


REMOVE = ReplyKeyboardRemove()


def web_app_button(text: str, url: str) -> Btn:
    return Btn(text, web_app=WebAppInfo(url=url))


def paginator(lang: str, ns: str, page: int, total: int, page_size: int, extra: str = "") -> list[Btn]:
    """◀ 1/3 ▶ row. ns gets "ns:page:N[:extra]"."""
    pages = max(1, (total + page_size - 1) // page_size)
    if pages <= 1:
        return []
    row = []
    if page > 0:
        row.append(Btn(t("btn.prev", lang), callback_data=cb(ns, "page", page - 1, extra) if extra else cb(ns, "page", page - 1)))
    row.append(Btn(f"{page + 1}/{pages}", callback_data="noop"))
    if page < pages - 1:
        row.append(Btn(t("btn.next", lang), callback_data=cb(ns, "page", page + 1, extra) if extra else cb(ns, "page", page + 1)))
    return row
