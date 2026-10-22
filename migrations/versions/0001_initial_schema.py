"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TgId = sa.BigInteger().with_variant(sa.Integer, "sqlite")


def upgrade() -> None:
    op.create_table(
        "tg_users",
        sa.Column("id", TgId, primary_key=True, autoincrement=False),
        sa.Column("username", sa.String(64)),
        sa.Column("first_name", sa.String(128)),
        sa.Column("lang", sa.String(2), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("last_seen_at", sa.DateTime, nullable=False),
    )
    op.create_table(
        "shops",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("slug", sa.String(48), nullable=False, unique=True),
        sa.Column("owner_id", TgId, sa.ForeignKey("tg_users.id"), nullable=False, unique=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("phone", sa.String(32)),
        sa.Column("delivery_info", sa.Text),
        sa.Column("payment_info", sa.Text),
        sa.Column("logo_file_id", sa.String(256)),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("trial_ends_at", sa.DateTime, nullable=False),
        sa.Column("paid_until", sa.DateTime),
        sa.Column("onboarding_done", sa.Boolean, nullable=False),
        sa.Column("ai_enabled", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("shop_id", sa.Integer, sa.ForeignKey("shops.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(48), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.UniqueConstraint("shop_id", "name", name="uq_category_shop_name"),
    )
    op.create_table(
        "products",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("shop_id", sa.Integer, sa.ForeignKey("shops.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category_id", sa.Integer, sa.ForeignKey("categories.id", ondelete="SET NULL")),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("price_santim", sa.Integer, nullable=False),
        sa.Column("stock", sa.Integer),
        sa.Column("photo_file_id", sa.String(256)),
        sa.Column("photo_unique_id", sa.String(64)),
        sa.Column("is_active", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_products_shop", "products", ["shop_id", "is_active", "category_id"])
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("shop_id", sa.Integer, sa.ForeignKey("shops.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tg_user_id", TgId, sa.ForeignKey("tg_users.id"), nullable=False),
        sa.Column("full_name", sa.String(80)),
        sa.Column("phone", sa.String(32)),
        sa.Column("address", sa.Text),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("shop_id", "tg_user_id", name="uq_customer_shop_user"),
    )
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("shop_id", sa.Integer, sa.ForeignKey("shops.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", sa.Integer, sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("code", sa.String(8), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("source", sa.String(8), nullable=False),
        sa.Column("payment_method", sa.String(16), nullable=False),
        sa.Column("payment_proof_file_id", sa.String(256)),
        sa.Column("full_name", sa.String(80), nullable=False),
        sa.Column("phone", sa.String(32), nullable=False),
        sa.Column("address", sa.Text, nullable=False),
        sa.Column("note", sa.Text),
        sa.Column("total_santim", sa.Integer, nullable=False),
        sa.Column("owner_msg_id", sa.Integer),
        sa.Column("customer_msg_id", sa.Integer),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("shop_id", "code", name="uq_order_shop_code"),
    )
    op.create_index("ix_orders_shop_status", "orders", ["shop_id", "status", "created_at"])
    op.create_table(
        "order_items",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.Integer, sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.Integer, sa.ForeignKey("products.id", ondelete="SET NULL")),
        sa.Column("name_snapshot", sa.String(80), nullable=False),
        sa.Column("price_santim", sa.Integer, nullable=False),
        sa.Column("qty", sa.Integer, nullable=False),
    )
    op.create_table(
        "chat_states",
        sa.Column("tg_user_id", TgId, sa.ForeignKey("tg_users.id"), primary_key=True),
        sa.Column("shop_id", sa.Integer),
        sa.Column("state", sa.String(48), nullable=False),
        sa.Column("data", sa.JSON),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_table(
        "forwarded_questions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("shop_id", sa.Integer, sa.ForeignKey("shops.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", sa.Integer, sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("answer", sa.Text),
        sa.Column("owner_msg_id", sa.Integer),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("answered_at", sa.DateTime),
    )
    op.create_table(
        "ai_usage",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("shop_id", sa.Integer, sa.ForeignKey("shops.id", ondelete="CASCADE")),
        sa.Column("tg_user_id", TgId),
        sa.Column("window_start", sa.DateTime, nullable=False),
        sa.Column("count", sa.Integer, nullable=False),
        sa.UniqueConstraint("shop_id", "tg_user_id", "window_start", name="uq_ai_usage_window"),
    )
    op.create_table(
        "subscription_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("shop_id", sa.Integer, sa.ForeignKey("shops.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("months", sa.Integer),
        sa.Column("note", sa.Text),
        sa.Column("created_by", TgId, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )


def downgrade() -> None:
    for t in (
        "subscription_events", "ai_usage", "forwarded_questions", "chat_states", "order_items",
        "orders", "customers", "products", "categories", "shops", "tg_users",
    ):
        op.drop_table(t)
