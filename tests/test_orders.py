"""Order lifecycle (repo), owner card rendering, and that the bot handlers register their routes."""
from app.db.repo import customers as customers_repo
from app.db.repo import orders as repo
from app.db.repo import products as products_repo
from app.db.repo import users as users_repo
from app.services import notifications as notif


def _order(db, shop, user_id=7, qty=2, pm="cod"):
    users_repo.upsert_tg_user(db, user_id, "hana", "Hana")
    cust = customers_repo.get_or_create(db, shop.id, user_id)
    p = products_repo.create(db, shop.id, "Shoe", 120000, 5, None, None)
    o = repo.create(db, shop.id, cust.id, [(p.id, qty)], "Hana", "0911223344", "Bole", pm, "chat")
    db.commit()
    return o, p


def test_status_transitions_and_restock(two_shops, db):
    a, b = two_shops
    o, p = _order(db, a)
    assert p.stock == 3
    assert repo.set_status(db, b.id, o.id, "confirmed") is None  # other shop cannot touch it
    repo.set_status(db, a.id, o.id, "confirmed")
    repo.set_status(db, a.id, o.id, "rejected")
    assert p.stock == 5  # restocked once
    repo.set_status(db, a.id, o.id, "cancelled")
    assert p.stock == 5  # not restocked twice
    assert repo.set_status(db, a.id, o.id, "bogus") is None


def test_owner_lists_by_tab(two_shops, db):
    a, _ = two_shops
    o1, _ = _order(db, a, user_id=7)
    o2, _ = _order(db, a, user_id=8)
    repo.set_status(db, a.id, o2.id, "delivered")
    assert [o.id for o in repo.list_for_owner(db, a.id, "pending", 0, 10)[0]] == [o1.id]
    assert [o.id for o in repo.list_for_owner(db, a.id, "history", 0, 10)[0]] == [o2.id]
    assert repo.count_by_status(db, a.id, "pending") == 1


def test_owner_card_and_customer_text(two_shops, db):
    a, _ = two_shops
    o, _ = _order(db, a, pm="transfer")
    a.payment_info = "Telebirr 0911 (Abebe)"
    text = notif.owner_card_text(o, "en")
    assert o.code in text and "Shoe × 2" in text and "waiting for screenshot" in text
    kb = notif.owner_card_kb(o, "en").inline_keyboard
    assert [b.callback_data for b in kb[0]] == [f"ord:status:{o.id}:confirmed", f"ord:status:{o.id}:rejected"]
    repo.set_status(db, a.id, o.id, "confirmed")
    assert notif.owner_card_kb(o, "en").inline_keyboard[0][0].callback_data == f"ord:status:{o.id}:on_the_way"
    cust_text = notif.customer_status_text(o, a, "am")
    assert "Telebirr 0911 (Abebe)" in cust_text and "ብር" in cust_text
    o.payment_proof_file_id = "fid"
    assert "Telebirr" not in notif.customer_status_text(o, a, "am")  # instructions disappear once proof is in
    # Markdown-breaking user input is neutralised
    o.full_name = "Ha*na_"
    assert "*" not in notif.owner_card_text(o, "en").split("👤")[1].split("·")[0]


def test_handlers_register_routes():
    import app.bot.application  # noqa: F401  (imports every handler module)
    from app.bot import states as S
    from app.bot.router import _callback_handlers, _state_handlers

    for ns in ("start", "lang", "home", "cancel", "onb", "prod", "prodw", "share", "settings", "ord", "ordp", "cust", "custp", "custw", "skip"):
        assert ns in _callback_handlers, ns
    for st in (S.ONB_NAME, S.PROD_PHOTO, S.PROD_EDIT_FIELD, S.CUST_NAME, S.CUST_PROOF, S.ORD_REJECT_REASON, S.SETTINGS_EDIT):
        assert st in _state_handlers, st
