"""Questions the assistant could not answer, forwarded to the owner."""
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import ForwardedQuestion, utcnow


def create(db: Session, shop_id: int, customer_id: int, question: str) -> ForwardedQuestion:
    fq = ForwardedQuestion(shop_id=shop_id, customer_id=customer_id, question=question.strip()[:1000])
    db.add(fq)
    db.flush()
    return fq


def get(db: Session, shop_id: int, fq_id: int) -> Optional[ForwardedQuestion]:
    return db.scalar(select(ForwardedQuestion).where(ForwardedQuestion.shop_id == shop_id, ForwardedQuestion.id == fq_id))


def answer(db: Session, shop_id: int, fq_id: int, text: str) -> Optional[ForwardedQuestion]:
    fq = get(db, shop_id, fq_id)
    if fq is None:
        return None
    fq.answer = text.strip()[:2000]
    fq.answered_at = utcnow()
    db.flush()
    return fq


def count_open(db: Session, shop_id: Optional[int] = None) -> int:
    q = select(func.count()).where(ForwardedQuestion.answered_at.is_(None))
    if shop_id is not None:
        q = q.where(ForwardedQuestion.shop_id == shop_id)
    return db.scalar(q) or 0
