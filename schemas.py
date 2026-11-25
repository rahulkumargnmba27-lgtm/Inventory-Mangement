from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, Field


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class UserLogin(BaseModel):
    email: str
    password: str


class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str
    phone: str | None = None
    password: str = Field(min_length=6)
    role: Literal["owner", "manager", "staff"] = "staff"


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    phone: str | None = None
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class CategoryOut(BaseModel):
    id: int
    name: str
    description: str | None = None
    icon: str
    display_order: int

    model_config = {"from_attributes": True}


class SupplierBase(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    contact_person: str | None = None
    phone: str = Field(min_length=6, max_length=30)
    email: str | None = None
    address: str | None = None
    gstin: str | None = None
    notes: str | None = None


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(BaseModel):
    name: str | None = None
    contact_person: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    gstin: str | None = None
    notes: str | None = None


class SupplierOut(SupplierBase):
    id: int
    created_at: datetime
    product_count: int = 0
    total_purchase_qty: float = 0.0

    model_config = {"from_attributes": True}


class ProductBase(BaseModel):
    sku: str = Field(min_length=2, max_length=40)
    name: str = Field(min_length=2, max_length=200)
    category_name: str = "Staples"
    supplier_id: int | None = None
    unit: str = "pack"
    purchase_price: float = Field(ge=0)
    selling_price: float = Field(ge=0)
    mrp: float | None = Field(default=None, ge=0)
    stock_qty: float = 0.0
    reorder_level: float = Field(default=10.0, ge=0)
    barcode: str | None = None
    expiry_date: date | None = None
    image_url: str | None = None


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: str | None = None
    category_name: str | None = None
    supplier_id: int | None = None
    unit: str | None = None
    purchase_price: float | None = Field(default=None, ge=0)
    selling_price: float | None = Field(default=None, ge=0)
    mrp: float | None = Field(default=None, ge=0)
    stock_qty: float | None = None
    reorder_level: float | None = Field(default=None, ge=0)
    barcode: str | None = None
    expiry_date: date | None = None
    image_url: str | None = None
    reason: str | None = None


class ProductOut(BaseModel):
    id: int
    sku: str
    name: str
    category_id: int
    category_name: str
    supplier_id: int | None = None
    supplier_name: str | None = None
    unit: str
    purchase_price: float
    selling_price: float
    mrp: float | None = None
    stock_qty: float
    reorder_level: float
    barcode: str | None = None
    expiry_date: date | None = None
    image_url: str | None = None
    status: str
    stock_value: float
    is_active: bool
    created_at: datetime
    updated_at: datetime


class StockMovementCreate(BaseModel):
    product_id: int
    movement_type: Literal["PURCHASE", "SALE", "RETURN", "DAMAGED", "EXPIRED", "ADJUSTMENT"]
    quantity: float = Field(gt=0)
    direction: Literal["IN", "OUT"] | None = None
    reason: str = Field(min_length=2, max_length=500)
    reference_id: str | None = None
    idempotency_key: str | None = None


class StockTransactionOut(BaseModel):
    id: int
    transaction_id: str
    product_id: int
    sku: str
    product_name: str
    movement_type: str
    quantity: float
    previous_stock: float
    updated_stock: float
    reason: str | None = None
    reference_id: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class OrderItemInput(BaseModel):
    product_id: int
    quantity: float = Field(gt=0)
    unit_price: float | None = Field(default=None, ge=0)


class OrderCreate(BaseModel):
    customer_name: str = "Walk-in Customer"
    customer_phone: str | None = None
    customer_email: str | None = None
    payment_method: Literal["CASH", "UPI", "CARD", "OTHER"] = "CASH"
    discount: float = Field(default=0.0, ge=0)
    status: Literal["DRAFT", "CONFIRMED"] = "CONFIRMED"
    notes: str | None = None
    items: list[OrderItemInput] = Field(min_length=1)


class OrderItemOut(BaseModel):
    id: int
    product_id: int
    sku: str
    product_name: str
    quantity: float
    unit_price: float
    line_total: float

    model_config = {"from_attributes": True}


class OrderOut(BaseModel):
    id: int
    order_number: str
    customer_name: str
    customer_phone: str | None = None
    customer_email: str | None = None
    status: str
    payment_method: str
    subtotal: float
    discount: float
    total: float
    is_sample: bool
    stock_deducted: bool
    notes: str | None = None
    created_at: datetime
    confirmed_at: datetime | None = None
    items: list[OrderItemOut] = []

    model_config = {"from_attributes": True}


class AlertOut(BaseModel):
    id: int
    product_id: int
    sku: str
    product_name: str
    alert_type: str
    current_stock: float
    reorder_level: float
    shortage_qty: float
    recommended_action: str
    channel: str
    status: str
    message_payload: str | None = None
    external_message_id: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None

    model_config = {"from_attributes": True}


class AIChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    confirm_action: bool = False
    pending_action: dict | None = None


class AIChatResponse(BaseModel):
    reply: str
    mode: str
    requires_confirmation: bool = False
    pending_action: dict | None = None
    tool_calls: list[dict] = []
