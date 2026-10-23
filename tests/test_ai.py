"""AI assistant: context is shop-scoped, unknowns are forwarded, rate limits hold, owner reply flow stores answers."""
import asyncio
from datetime import timedelta

import pytest

from app.db.models import utcnow
from app.db.repo import ai_usage, customers as customers_repo, forwarded as fq_repo, products as products_repo, users as users_repo
from app.services import ai


def run(coro):
    return asyncio.run(coro)


class FakeProvider:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    async def complete(self, system, messages):
        self.calls.append((system, messages))
        return self.reply


@pytest.fixture
def stocked(two_shops, db):
    a, b = two_shops
    products_repo.create(db, a.id, "Red Shoes", 120000, 3, None, None, description="Leather, sizes 40-44")
    products_repo.create(db, b.id, "Lipstick", 35000, None, None, None)
    db.commit()
    return a, b


def test_context_contains_only_this_shops_products(stocked, db):
    a, b = stocked
    ctx_a = ai.build_context(db, a, "en")
    assert "Red Shoes" in ctx_a and "ETB 1,200" in ctx_a and "3 in stock" in ctx_a and "Lipstick" not in ctx_a
    assert "Red Shoes" not in ai.build_context(db, b, "am") and "ብር" in ai.build_context(db, b, "am")
    assert "Never invent" in ai.system_prompt(ctx_a)


def test_answer_and_forward_paths(stocked, db):
    a, _ = stocked
    ai.set_provider(FakeProvider('{"answer": "Red Shoes cost ETB 1,200.", "forward": false}'))
    r = run(ai.ask(db, a, "how much are the shoes?", "en"))
    assert not r.forward and "1,200" in r.answer
    ai.set_provider(FakeProvider('{"answer": "", "forward": true, "reason": "discount not in data"}'))
    assert (run(ai.ask(db, a, "any discount?", "en"))).forward
    ai.set_provider(FakeProvider("I am not JSON"))
    assert (run(ai.ask(db, a, "x", "en"))).forward
    ai.set_provider(FakeProvider('{"answer": "", "forward": false}'))
    assert (run(ai.ask(db, a, "x", "en"))).forward  # empty answer == forward
    ai.set_provider(None)
    r = run(ai.ask(db, a, "x", "en"))
    assert r.forward and r.reason in ("no_provider", "provider_error")


def test_history_is_passed_and_capped(stocked, db):
    a, _ = stocked
    p = FakeProvider('{"answer": "ok", "forward": false}')
    ai.set_provider(p)
    hist = [{"role": "user", "content": f"q{i}"} for i in range(10)]
    run(ai.ask(db, a, "final", "en", hist))
    msgs = p.calls[0][1]
    assert len(msgs) == ai.MAX_HISTORY + 1 and msgs[-1]["content"] == "final"
    ai.set_provider(None)


def test_rate_limits_customer_shop_global(two_shops, db):
    a, b = two_shops
    now = utcnow()
    for _ in range(2):
        assert ai_usage.check_and_count(db, a.id, 1, 2, 100, 100, now) is None
    assert ai_usage.check_and_count(db, a.id, 1, 2, 100, 100, now) == "customer"
    assert ai_usage.check_and_count(db, a.id, 2, 2, 100, 100, now) is None  # another customer still fine
    assert ai_usage.check_and_count(db, a.id, 1, 2, 100, 100, now + timedelta(hours=1)) is None  # new hour window
    # shop daily: 4 calls so far for shop a
    assert ai_usage.check_and_count(db, a.id, 3, 10, 4, 100, now) == "shop"
    assert ai_usage.calls_today(db, a.id, now) == 4
    # global daily counts across shops
    assert ai_usage.check_and_count(db, b.id, 9, 10, 10, 4, now) == "global"
    assert ai_usage.calls_today(db, None, now) == 4


def test_forwarded_questions_are_shop_scoped(two_shops, db):
    a, b = two_shops
    users_repo.upsert_tg_user(db, 7, "hana", "Hana")
    cust = customers_repo.get_or_create(db, a.id, 7)
    fq = fq_repo.create(db, a.id, cust.id, "Do you deliver to Hawassa?")
    assert fq_repo.get(db, b.id, fq.id) is None
    assert fq_repo.count_open(db, a.id) == 1
    assert fq_repo.answer(db, b.id, fq.id, "no") is None
    assert fq_repo.answer(db, a.id, fq.id, "Yes, 200 birr").answered_at is not None
    assert fq_repo.count_open(db, a.id) == 0
