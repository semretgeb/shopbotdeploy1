"""All SQLAlchemy models. Every shop-owned table carries shop_id (tenant isolation)."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Telegram ids exceed 32 bits; BigInteger on Postgres, plain INTEGER on SQLite.
TgId = BigInteger().with_variant(Integer, "sqlite")


class TgUser(Base):
    __tablename__ = "tg_users"

    id: Mapped[int] = mapped_column(TgId, primary_key=True, autoincrement=False)
    username: Mapped[Optional[str]] = mapped_column(String(64))
    first_name: Mapped[Optional[str]] = mapped_column(String(128))
    lang: Mapped[str] = mapped_column(String(2), default="am", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class Shop(Base):
    __tablename__ = "shops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(48), unique=True, nullable=False)
    owner_id: Mapped[int] = mapped_column(TgId, ForeignKey("tg_users.id"), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    phone: Mapped[Optional[str]] = mapped_column(String(32))
    delivery_info: Mapped[Optional[str]] = mapped_column(Text)
    payment_info: Mapped[Optional[str]] = mapped_column(Text)
    logo_file_id: Mapped[Optional[str]] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(16), default="trial", nullable=False)  # trial|active|paused
    trial_ends_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    paid_until: Mapped[Optional[datetime]] = mapped_column(DateTime)
    onboarding_done: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    owner: Mapped[TgUser] = relationship()


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("shop_id", "name", name="uq_category_shop_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(48), nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (Index("ix_products_shop", "shop_id", "is_active", "category_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id", ondelete="CASCADE"), nullable=False)
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    price_santim: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 birr = 100 santim
    stock: Mapped[Optional[int]] = mapped_column(Integer)  # NULL = unlimited
    photo_file_id: Mapped[Optional[str]] = mapped_column(String(256))
    photo_unique_id: Mapped[Optional[str]] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    category: Mapped[Optional[Category]] = relationship()


class Customer(Base):
    """A Telegram user as a customer of ONE shop. Saved checkout details are per shop."""

    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("shop_id", "tg_user_id", name="uq_customer_shop_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id", ondelete="CASCADE"), nullable=False)
    tg_user_id: Mapped[int] = mapped_column(TgId, ForeignKey("tg_users.id"), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(80))
    phone: Mapped[Optional[str]] = mapped_column(String(32))
    address: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    tg_user: Mapped[TgUser] = relationship()


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("shop_id", "code", name="uq_order_shop_code"),
        Index("ix_orders_shop_status", "shop_id", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id", ondelete="CASCADE"), nullable=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    source: Mapped[str] = mapped_column(String(8), nullable=False)  # miniapp|chat
    payment_method: Mapped[str] = mapped_column(String(16), nullable=False)  # cod|transfer
    payment_proof_file_id: Mapped[Optional[str]] = mapped_column(String(256))
    full_name: Mapped[str] = mapped_column(String(80), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text)
    total_santim: Mapped[int] = mapped_column(Integer, nullable=False)
    owner_msg_id: Mapped[Optional[int]] = mapped_column(Integer)
    customer_msg_id: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    customer: Mapped[Customer] = relationship()
    items: Mapped[list["OrderItem"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[Optional[int]] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"))
    name_snapshot: Mapped[str] = mapped_column(String(80), nullable=False)
    price_santim: Mapped[int] = mapped_column(Integer, nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)


class ChatState(Base):
    """DB-backed conversation state so webhook redeploys never lose a wizard in progress."""

    __tablename__ = "chat_states"

    tg_user_id: Mapped[int] = mapped_column(TgId, ForeignKey("tg_users.id"), primary_key=True)
    shop_id: Mapped[Optional[int]] = mapped_column(Integer)  # shop the customer is currently "in"
    state: Mapped[str] = mapped_column(String(48), default="idle", nullable=False)
    data: Mapped[Optional[dict]] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class ForwardedQuestion(Base):
    __tablename__ = "forwarded_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id", ondelete="CASCADE"), nullable=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[Optional[str]] = mapped_column(Text)
    owner_msg_id: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    answered_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class AiUsage(Base):
    """Fixed-window counters. shop_id NULL + tg_user_id NULL = global daily counter."""

    __tablename__ = "ai_usage"
    __table_args__ = (UniqueConstraint("shop_id", "tg_user_id", "window_start", name="uq_ai_usage_window"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shop_id: Mapped[Optional[int]] = mapped_column(ForeignKey("shops.id", ondelete="CASCADE"))
    tg_user_id: Mapped[Optional[int]] = mapped_column(TgId)
    window_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class SubscriptionEvent(Base):
    __tablename__ = "subscription_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id", ondelete="CASCADE"), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)  # approve|extend|pause|resume|trial
    months: Mapped[Optional[int]] = mapped_column(Integer)
    note: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[int] = mapped_column(TgId, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
