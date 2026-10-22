from typing import Optional

from sqlalchemy.orm import Session

from app.db.models import TgUser, utcnow


def upsert_tg_user(
    db: Session,
    tg_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    lang: Optional[str] = None,
) -> TgUser:
    user = db.get(TgUser, tg_id)
    if user is None:
        user = TgUser(id=tg_id, username=username, first_name=first_name, lang=lang or "am")
        db.add(user)
    else:
        user.username = username or user.username
        user.first_name = first_name or user.first_name
        user.last_seen_at = utcnow()
    db.flush()
    return user


def set_lang(db: Session, tg_id: int, lang: str) -> None:
    user = db.get(TgUser, tg_id)
    if user:
        user.lang = lang
        db.flush()
