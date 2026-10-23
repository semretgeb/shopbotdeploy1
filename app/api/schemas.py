"""Request/response models for the Mini App API."""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class ShopOut(BaseModel):
    id: int
    slug: str
    name: str
    description: Optional[str] = None
    phone: Optional[str] = None
    delivery_info: Optional[str] = None
    payment_info: Optional[str] = None
    logo_url: Optional[str] = None
    is_open: bool
    lang: str  # the requesting user's language


class CategoryOut(BaseModel):
    id: int
    name: str
    count: int


class ProductOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    price_santim: int
    price_text: str
    stock: Optional[int] = None
    in_stock: bool
    category_id: Optional[int] = None
    thumb_url: Optional[str] = None
    image_url: Optional[str] = None


class ProductPage(BaseModel):
    items: list[ProductOut]
    page: int
    page_size: int
    total: int
    has_more: bool


class MeOut(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    lang: str


class MeIn(BaseModel):
    full_name: Optional[str] = Field(default=None, max_length=80)
    phone: Optional[str] = Field(default=None, max_length=32)
    address: Optional[str] = Field(default=None, max_length=500)
    lang: Optional[Literal["am", "en"]] = None


class OrderItemIn(BaseModel):
    product_id: int
    qty: int = Field(ge=1, le=99)


class OrderIn(BaseModel):
    items: list[OrderItemIn] = Field(min_length=1, max_length=50)
    full_name: str = Field(min_length=2, max_length=80)
    phone: str = Field(min_length=7, max_length=32)
    address: str = Field(min_length=3, max_length=500)
    note: Optional[str] = Field(default=None, max_length=500)
    payment_method: Literal["cod", "transfer"]
    save_details: bool = True

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        digits = "".join(ch for ch in v if ch.isdigit() or ch == "+")
        if len(digits.lstrip("+")) < 7:
            raise ValueError("phone too short")
        return v.strip()


class OrderItemOut(BaseModel):
    product_id: Optional[int]
    name: str
    price_santim: int
    qty: int
    line_total_text: str


class OrderOut(BaseModel):
    id: int
    code: str
    status: str
    payment_method: str
    has_proof: bool
    total_santim: int
    total_text: str
    items: list[OrderItemOut]
    full_name: str
    phone: str
    address: str
    note: Optional[str] = None
    payment_info: Optional[str] = None  # shop's transfer details (for the proof screen)
    created_at: datetime


class ProofOut(BaseModel):
    ok: bool
    order_id: int
    has_proof: bool
