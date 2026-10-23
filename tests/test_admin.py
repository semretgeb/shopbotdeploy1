"""Subscription expiry cycle (idempotent), admin actions via the service layer, route registration."""
import asyncio
from datetime import timedelta
from types import SimpleNamespace

from app.db.models import utcnow
from app.db.repo import shops as shops_repo
from app.services import subscription as sub


class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, **kw):
        self.sent.append((chat_id, text))
        return SimpleNamespace(message_id=1)


def test_find_due_expire_and_warn(two_shops, db):
    a, b = two_shops
    now = utcnow()
    a.trial_ends_at = now - timedelta(hours=1)  # expired
    b.trial_ends_at = now + timedelta(days=2)  # ending soon
    db.commit()
    to_expire, to_warn = sub.find_due(db, now)
    assert [s.id for s in to_expire] == [a.id] and [s.id for s in to_warn] == [b.id]
    sub.expire(db, a)
    sub.mark_warned(db, b)
    db.commit()
    assert a.status == "paused" and not sub.is_shop_open(a)
    # second pass is a no-op: a is paused, b already warned for this period
    assert sub.find_due(db, now) == ([], [])
    # approving b pushes access out and allows a fresh warning later
    sub.approve(db, b, 1, admin_id=999)
    db.commit()
    assert sub.find_due(db, now) == ([], [])
    assert sub.find_due(db, sub.access_until(b) - timedelta(days=1)) == ([], [b])


def test_run_expiry_cycle_notifies_owners(two_shops, db):
    a, b = two_shops
    a.trial_ends_at = utcnow() - timedelta(minutes=1)
    db.commit()
    bot = FakeBot()
    counts = asyncio.run(sub.run_expiry_cycle(bot))
    assert counts == {"expired": 1, "warned": 0}
    assert bot.sent and bot.sent[0][0] == a.owner_id
    assert "ETB" in bot.sent[0][1] or "ብር" in bot.sent[0][1]
    db.expire_all()
    assert shops_repo.get(db, a.id).status == "paused"
    assert asyncio.run(sub.run_expiry_cycle(bot)) == {"expired": 0, "warned": 0}


def test_resume_after_expiry_gives_grace(two_shops, db):
    a, _ = two_shops
    a.trial_ends_at = utcnow() - timedelta(days=5)
    sub.expire(db, a)
    sub.resume(db, a, admin_id=999)
    assert not sub.is_shop_open(a)  # resume alone cannot reopen an expired shop ...
    sub.extend_days(db, a, 7, admin_id=999)
    assert sub.is_shop_open(a) and 6 <= sub.days_left(a) <= 7  # ... the admin handler adds 7 days


def test_shop_stats_and_listing(two_shops, db):
    a, b = two_shops
    sub.pause(db, a, admin_id=999)
    db.commit()
    assert shops_repo.count_by_status(db) == {"paused": 1, "trial": 1}
    assert [s.id for s in shops_repo.list_all(db, 0, 10)] == [b.id, a.id]


def test_admin_routes_registered():
    import app.bot.application  # noqa: F401
    from app.bot import states as S
    from app.bot.router import _callback_handlers, _state_handlers

    assert "adm" in _callback_handlers and "subs" in _callback_handlers and "fq" in _callback_handlers
    assert S.SUBS_PROOF in _state_handlers and S.ADMIN_BROADCAST in _state_handlers and S.FQ_REPLY in _state_handlers
