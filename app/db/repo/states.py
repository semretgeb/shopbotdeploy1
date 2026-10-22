"""DB-backed conversation state for bot handlers."""
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.db.models import ChatState


def get_state(db: Session, tg_user_id: int) -> ChatState:
    st = db.get(ChatState, tg_user_id)
    if st is None:
        st = ChatState(tg_user_id=tg_user_id, state="idle", data={})
        db.add(st)
        db.flush()
    return st


def set_state(
    db: Session,
    tg_user_id: int,
    state: str,
    data: Optional[dict[str, Any]] = None,
    shop_id: Optional[int] = ...,  # type: ignore[assignment]  # Ellipsis = leave unchanged
) -> ChatState:
    st = get_state(db, tg_user_id)
    st.state = state
    if data is not None:
        st.data = data
    if shop_id is not ...:
        st.shop_id = shop_id
    db.flush()
    return st


def update_data(db: Session, tg_user_id: int, **fields: Any) -> ChatState:
    st = get_state(db, tg_user_id)
    merged = dict(st.data or {})
    merged.update(fields)
    st.data = merged  # reassign so SQLAlchemy sees the JSON change
    db.flush()
    return st


def reset(db: Session, tg_user_id: int, keep_shop: bool = True) -> ChatState:
    st = get_state(db, tg_user_id)
    st.state = "idle"
    st.data = {}
    if not keep_shop:
        st.shop_id = None
    db.flush()
    return st
