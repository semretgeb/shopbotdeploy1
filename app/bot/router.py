"""Dispatch: DB-backed state for messages, "ns:" prefix for callback queries.

Handler modules register with @on_state("...") and @on_callback("ns"). Each handler gets a Ctx
with an open session that is committed when the handler returns (rolled back on error).
"""
import logging
from typing import Awaitable, Callable, Optional

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.context import Ctx, build_ctx
from app.db.base import db_session

log = logging.getLogger(__name__)

Handler = Callable[[Ctx], Awaitable[None]]
_state_handlers: dict[str, Handler] = {}
_callback_handlers: dict[str, Handler] = {}
_fallback: Optional[Handler] = None  # free text when state is idle


def on_state(*states: str):
    def deco(fn: Handler) -> Handler:
        for s in states:
            _state_handlers[s] = fn
        return fn
    return deco


def on_callback(*namespaces: str):
    def deco(fn: Handler) -> Handler:
        for ns in namespaces:
            _callback_handlers[ns] = fn
        return fn
    return deco


def set_fallback(fn: Handler) -> Handler:
    global _fallback
    _fallback = fn
    return fn


async def handle_message(update: Update, tg: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    with db_session() as db:
        ctx = build_ctx(update, tg, db)
        handler = _state_handlers.get(ctx.state.state)
        if handler is None:
            handler = _fallback
        if handler is None:
            return
        try:
            await handler(ctx)
        except Exception:
            log.exception("message handler failed (state=%s)", ctx.state.state)
            await ctx.send(ctx.t("err.generic"))


async def handle_callback(update: Update, tg: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if not q or not q.data:
        return
    ns = q.data.split(":", 1)[0]
    with db_session() as db:
        ctx = build_ctx(update, tg, db)
        ctx.extra["parts"] = q.data.split(":")
        handler = _callback_handlers.get(ns)
        if handler is None:
            await ctx.answer()
            return
        try:
            await handler(ctx)
        except Exception:
            log.exception("callback handler failed (data=%s)", q.data)
            await ctx.answer(ctx.t("err.generic"), alert=True)


def parts(ctx: Ctx) -> list[str]:
    return ctx.extra.get("parts", [])


def arg(ctx: Ctx, i: int, default: Optional[str] = None) -> Optional[str]:
    p = parts(ctx)
    return p[i] if len(p) > i else default
