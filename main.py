from contextlib import asynccontextmanager
from datetime import datetime, timezone
import io
import os
from pathlib import Path
import uuid
from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from .auth import (
    create_access_token,
    get_current_user,
    hash_password,
    require_roles,
    verify_password,
)
from .config import get_settings
from .database import Base, SessionLocal, engine, get_db
from .models import (
    AlertHistory,
    AuditLog,
    Category,
    Order,
    OrderItem,
    Product,
    StockTransaction,
    Supplier,
    User,
    classify_stock,
)
from .schemas import (
    AIChatRequest,
    AIChatResponse,
    AlertOut,
    CategoryOut,
    OrderCreate,
    OrderOut,
    ProductCreate,
    ProductOut,
    ProductUpdate,
    StockMovementCreate,
    StockTransactionOut,
    SupplierCreate,
    SupplierOut,
    SupplierUpdate,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserOut,
)
from .seed import seed_database
from .services.ai_service import run_ai_assistant
from .services.excel_service import (
    export_inventory_csv,
    export_inventory_excel,
    import_excel_bytes,
)
from .services.inventory_service import (
    apply_stock_movement,
    confirm_order_stock_deduction,
    evaluate_product_alert,
    generate_transaction_id,
    record_audit_log,
    send_whatsapp_message_sync,
)
from .services.telegram_service import (
    get_telegram_bot_info,
    handle_telegram_update,
    poll_telegram_updates_once,
    send_telegram_message,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    # Ensure image_url column exists on existing SQLite/Postgres databases
    with engine.begin() as conn:
        if settings.database_url.startswith("sqlite"):
            cols = [row[1] for row in conn.execute(text("PRAGMA table_info(products)")).fetchall()]
            if "image_url" not in cols:
                conn.execute(text("ALTER TABLE products ADD COLUMN image_url VARCHAR(500)"))
        else:
            conn.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS image_url VARCHAR(500)"))
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="Kirana Quick AI Inventory API",
    version="1.0.0",
    lifespan=lifespan,
)

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _to_product_out(p: Product) -> ProductOut:
    return ProductOut(
        id=p.id,
        sku=p.sku,
        name=p.name,
        category_id=p.category_id,
        category_name=p.category.name if p.category else "General",
        supplier_id=p.supplier_id,
        supplier_name=p.supplier.name if p.supplier else None,
        unit=p.unit,
        purchase_price=p.purchase_price,
        selling_price=p.selling_price,
        mrp=p.mrp,
        stock_qty=p.stock_qty,
        reorder_level=p.reorder_level,
        barcode=p.barcode,
        expiry_date=p.expiry_date,
        image_url=p.image_url or f"/images/skus/{p.sku}.svg",
        status=p.status,
        stock_value=round(p.stock_qty * p.selling_price, 2),
        is_active=p.is_active,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "store_name": settings.store_name,
        "gemini_configured": bool(settings.gemini_api_key and not settings.gemini_api_key.startswith("your-")),
        "whatsapp_configured": bool(settings.whatsapp_access_token and not settings.whatsapp_access_token.startswith("your-")),
    }


# ---------------- AUTH ----------------
@app.post("/api/auth/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.strip().lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is disabled")
    token = create_access_token({"sub": str(user.id), "role": user.role})
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@app.post("/api/auth/register", response_model=UserOut)
def register_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("owner")),
):
    if db.query(User).filter(User.email == payload.email.strip().lower()).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        name=payload.name,
        email=payload.email.strip().lower(),
        phone=payload.phone,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    record_audit_log(db, current_user, "USER_CREATE", "user", payload.email)
    db.commit()
    db.refresh(user)
    return user


@app.get("/api/auth/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


# ---------------- DASHBOARD & ANALYTICS ----------------
@app.get("/api/dashboard")
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    products = db.query(Product).filter(Product.is_active == True).all()
    total_products = len(products)
    total_inventory_value = round(sum(p.stock_qty * p.selling_price for p in products), 2)
    total_available_stock = round(sum(p.stock_qty for p in products), 2)
    healthy_count = sum(1 for p in products if p.status == "HEALTHY")
    low_stock_items = [p for p in products if p.status == "LOW_STOCK"]
    stockout_items = [p for p in products if p.status == "STOCKOUT"]

    # Exclude sample orders from sales calculations
    real_orders = (
        db.query(Order)
        .filter(Order.is_sample == False)
        .order_by(Order.created_at.desc())
        .all()
    )
    confirmed_orders = [o for o in real_orders if o.status in ("CONFIRMED", "DELIVERED")]
    total_sales = round(sum(o.total for o in confirmed_orders), 2)

    today_utc = datetime.now(timezone.utc).date()
    todays_sales = round(
        sum(o.total for o in confirmed_orders if o.created_at.date() == today_utc), 2
    )

    recent_orders = (
        db.query(Order)
        .order_by(Order.created_at.desc())
        .limit(6)
        .all()
    )
    recent_movements = (
        db.query(StockTransaction)
        .order_by(StockTransaction.created_at.desc())
        .limit(8)
        .all()
    )

    # Category-wise breakdown
    cat_map: dict[str, dict] = {}
    for p in products:
        cname = p.category.name if p.category else "General"
        if cname not in cat_map:
            cat_map[cname] = {"category": cname, "product_count": 0, "total_units": 0.0, "total_value": 0.0, "low_or_out": 0}
        cat_map[cname]["product_count"] += 1
        cat_map[cname]["total_units"] = round(cat_map[cname]["total_units"] + p.stock_qty, 2)
        cat_map[cname]["total_value"] = round(cat_map[cname]["total_value"] + p.stock_qty * p.selling_price, 2)
        if p.status in ("LOW_STOCK", "STOCKOUT"):
            cat_map[cname]["low_or_out"] += 1

    active_alerts_count = (
        db.query(func.count(AlertHistory.id))
        .filter(AlertHistory.status == "ACTIVE")
        .scalar()
        or 0
    )

    return {
        "kpis": {
            "total_products": total_products,
            "total_inventory_value": total_inventory_value,
            "total_available_stock": total_available_stock,
            "healthy_count": healthy_count,
            "low_stock_count": len(low_stock_items),
            "stockout_count": len(stockout_items),
            "total_sales": total_sales,
            "todays_sales": todays_sales,
            "confirmed_orders_count": len(confirmed_orders),
            "active_alerts_count": active_alerts_count,
        },
        "low_stock_items": [_to_product_out(p) for p in low_stock_items],
        "stockout_items": [_to_product_out(p) for p in stockout_items],
        "recent_orders": [OrderOut.model_validate(o) for o in recent_orders],
        "recent_movements": [StockTransactionOut.model_validate(t) for t in recent_movements],
        "category_analytics": sorted(cat_map.values(), key=lambda x: -x["total_value"]),
    }


@app.get("/api/analytics")
def get_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    products = db.query(Product).filter(Product.is_active == True).all()
    txns = db.query(StockTransaction).all()
    real_orders = db.query(Order).filter(Order.is_sample == False, Order.status.in_(["CONFIRMED", "DELIVERED"])).all()

    purchase_total_qty = round(sum(t.quantity for t in txns if t.movement_type == "PURCHASE"), 2)
    sale_total_qty = round(sum(t.quantity for t in txns if t.movement_type == "SALE"), 2)

    # Fast-moving vs slow-moving products based on SALE transaction quantities
    sales_by_sku: dict[str, float] = {}
    for t in txns:
        if t.movement_type == "SALE":
            sales_by_sku[t.sku] = sales_by_sku.get(t.sku, 0.0) + t.quantity

    movement_summary: dict[str, int] = {}
    for t in txns:
        movement_summary[t.movement_type] = movement_summary.get(t.movement_type, 0) + 1

    product_velocity = [
        {
            "sku": p.sku,
            "name": p.name,
            "category": p.category.name if p.category else "General",
            "units_sold": round(sales_by_sku.get(p.sku, 0.0), 2),
            "current_stock": p.stock_qty,
            "stock_value": round(p.stock_qty * p.selling_price, 2),
        }
        for p in products
    ]
    fast_moving = sorted([x for x in product_velocity if x["units_sold"] > 0], key=lambda x: -x["units_sold"])[:5]
    slow_moving = sorted(product_velocity, key=lambda x: (x["units_sold"], -x["stock_value"]))[:5]

    return {
        "valuation": {
            "total_selling_value": round(sum(p.stock_qty * p.selling_price for p in products), 2),
            "total_cost_value": round(sum(p.stock_qty * p.purchase_price for p in products), 2),
            "potential_margin": round(sum(p.stock_qty * (p.selling_price - p.purchase_price) for p in products), 2),
        },
        "purchase_vs_sales": {
            "purchase_units": purchase_total_qty,
            "sale_units": sale_total_qty,
            "confirmed_revenue": round(sum(o.total for o in real_orders), 2),
            "confirmed_orders_count": len(real_orders),
        },
        "movement_counts": movement_summary,
        "fast_moving": fast_moving,
        "slow_moving": slow_moving,
    }


# ---------------- CATEGORIES ----------------
@app.get("/api/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Category).order_by(Category.display_order, Category.name).all()


# ---------------- PRODUCTS ----------------
@app.get("/api/products", response_model=list[ProductOut])
def list_products(
    search: str | None = None,
    category: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Product).filter(Product.is_active == True)
    if search:
        s = f"%{search.strip()}%"
        query = query.filter((Product.name.ilike(s)) | (Product.sku.ilike(s)) | (Product.barcode.ilike(s)))
    if category and category != "ALL":
        query = query.join(Category).filter(Category.name == category)
    if status and status != "ALL":
        query = query.filter(Product.status == status)
    products = query.order_by(Product.sku).all()
    return [_to_product_out(p) for p in products]


@app.post("/api/products", response_model=ProductOut)
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "manager", "staff")),
):
    sku = payload.sku.strip().upper()
    if db.query(Product).filter(Product.sku == sku).first():
        raise HTTPException(status_code=400, detail=f"Product with SKU '{sku}' already exists")

    cat = db.query(Category).filter(Category.name == payload.category_name).first()
    if not cat:
        cat = Category(name=payload.category_name, description=f"{payload.category_name} items")
        db.add(cat)
        db.flush()

    product = Product(
        sku=sku,
        name=payload.name.strip(),
        category_id=cat.id,
        supplier_id=payload.supplier_id,
        unit=payload.unit.strip(),
        purchase_price=payload.purchase_price,
        selling_price=payload.selling_price,
        mrp=payload.mrp or payload.selling_price,
        stock_qty=payload.stock_qty,
        reorder_level=payload.reorder_level,
        barcode=payload.barcode,
        expiry_date=payload.expiry_date,
        image_url=payload.image_url or f"/images/skus/{sku}.svg",
        status=classify_stock(payload.stock_qty, payload.reorder_level),
    )
    db.add(product)
    db.flush()

    if payload.stock_qty > 0:
        db.add(
            StockTransaction(
                transaction_id=generate_transaction_id(),
                product_id=product.id,
                sku=product.sku,
                product_name=product.name,
                movement_type="INITIAL",
                quantity=payload.stock_qty,
                previous_stock=0.0,
                updated_stock=payload.stock_qty,
                reason="Initial stock on product creation",
                created_by=current_user.id,
            )
        )
    evaluate_product_alert(db, product, dispatch_whatsapp=True)
    record_audit_log(db, current_user, "PRODUCT_CREATE", "product", product.sku, f"Created {product.name}")
    db.commit()
    db.refresh(product)
    return _to_product_out(product)


@app.put("/api/products/{product_id}", response_model=ProductOut)
def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "manager", "staff")),
):
    product = db.query(Product).filter(Product.id == product_id, Product.is_active == True).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    if payload.category_name is not None:
        cat = db.query(Category).filter(Category.name == payload.category_name).first()
        if not cat:
            cat = Category(name=payload.category_name)
            db.add(cat)
            db.flush()
        product.category_id = cat.id

    for field in ("name", "supplier_id", "unit", "purchase_price", "selling_price", "mrp", "reorder_level", "barcode", "expiry_date", "image_url"):
        val = getattr(payload, field)
        if val is not None:
            setattr(product, field, val)

    if payload.stock_qty is not None and payload.stock_qty != product.stock_qty:
        prev = product.stock_qty
        diff = round(payload.stock_qty - prev, 2)
        product.stock_qty = payload.stock_qty
        db.add(
            StockTransaction(
                transaction_id=generate_transaction_id(),
                product_id=product.id,
                sku=product.sku,
                product_name=product.name,
                movement_type="ADJUSTMENT",
                quantity=abs(diff),
                previous_stock=prev,
                updated_stock=payload.stock_qty,
                reason=payload.reason or "Manual stock adjustment via product edit",
                created_by=current_user.id,
            )
        )

    evaluate_product_alert(db, product, dispatch_whatsapp=True)
    record_audit_log(db, current_user, "PRODUCT_UPDATE", "product", product.sku)
    db.commit()
    db.refresh(product)
    return _to_product_out(product)


@app.delete("/api/products/{product_id}")
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "manager")),
):
    product = db.query(Product).filter(Product.id == product_id, Product.is_active == True).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    product.is_active = False
    record_audit_log(db, current_user, "PRODUCT_DELETE", "product", product.sku, f"Soft-deleted {product.name}")
    db.commit()
    return {"deleted": True, "sku": product.sku}


# ---------------- STOCK MOVEMENTS ----------------
@app.get("/api/movements", response_model=list[StockTransactionOut])
def list_movements(
    product_id: int | None = None,
    movement_type: str | None = None,
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(StockTransaction)
    if product_id:
        query = query.filter(StockTransaction.product_id == product_id)
    if movement_type and movement_type != "ALL":
        query = query.filter(StockTransaction.movement_type == movement_type)
    return query.order_by(StockTransaction.created_at.desc()).limit(limit).all()


@app.post("/api/movements", response_model=StockTransactionOut)
def create_movement(
    payload: StockMovementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "manager", "staff")),
):
    product = db.query(Product).filter(Product.id == payload.product_id, Product.is_active == True).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    txn = apply_stock_movement(
        db=db,
        product=product,
        movement_type=payload.movement_type,
        quantity=payload.quantity,
        direction=payload.direction,
        reason=payload.reason,
        reference_id=payload.reference_id,
        idempotency_key=payload.idempotency_key,
        user=current_user,
    )
    record_audit_log(
        db, current_user, "STOCK_MOVEMENT", "stock_transaction", txn.transaction_id,
        f"{payload.movement_type} {payload.quantity} {product.unit} on {product.sku}",
    )
    db.commit()
    db.refresh(txn)
    return txn


# ---------------- ORDERS ----------------
@app.get("/api/orders", response_model=list[OrderOut])
def list_orders(
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Order)
    if status and status != "ALL":
        query = query.filter(Order.status == status)
    return query.order_by(Order.created_at.desc()).all()


@app.post("/api/orders", response_model=OrderOut)
def create_order(
    payload: OrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "manager", "staff")),
):
    order_number = f"ORD-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:5].upper()}"
    subtotal = 0.0
    order_items: list[OrderItem] = []

    for item in payload.items:
        product = db.query(Product).filter(Product.id == item.product_id, Product.is_active == True).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product ID {item.product_id} not found")
        unit_price = item.unit_price if item.unit_price is not None else product.selling_price
        line_total = round(unit_price * item.quantity, 2)
        subtotal += line_total
        order_items.append(
            OrderItem(
                product_id=product.id,
                sku=product.sku,
                product_name=product.name,
                quantity=item.quantity,
                unit_price=unit_price,
                line_total=line_total,
            )
        )

    subtotal = round(subtotal, 2)
    discount = min(payload.discount, subtotal)
    total = round(subtotal - discount, 2)

    order = Order(
        order_number=order_number,
        customer_name=payload.customer_name.strip() or "Walk-in Customer",
        customer_phone=payload.customer_phone,
        customer_email=payload.customer_email,
        status=payload.status,
        payment_method=payload.payment_method,
        subtotal=subtotal,
        discount=discount,
        total=total,
        is_sample=False,
        stock_deducted=False,
        notes=payload.notes,
        created_by=current_user.id,
        items=order_items,
    )
    db.add(order)
    db.flush()

    if payload.status == "CONFIRMED":
        confirm_order_stock_deduction(db, order, user=current_user)

    record_audit_log(db, current_user, "ORDER_CREATE", "order", order.order_number, f"Status: {order.status}, Total: ₹{order.total}")
    db.commit()
    db.refresh(order)
    return order


@app.post("/api/orders/{order_id}/confirm", response_model=OrderOut)
def confirm_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "manager", "staff")),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status == "CANCELLED":
        raise HTTPException(status_code=400, detail="Cannot confirm a cancelled order")
    if order.is_sample:
        raise HTTPException(status_code=400, detail="Sample orders cannot be confirmed")

    order.status = "CONFIRMED"
    confirm_order_stock_deduction(db, order, user=current_user)
    record_audit_log(db, current_user, "ORDER_CONFIRM", "order", order.order_number)
    db.commit()
    db.refresh(order)
    return order


@app.post("/api/orders/{order_id}/cancel", response_model=OrderOut)
def cancel_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "manager", "staff")),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status == "CANCELLED":
        return order

    if order.stock_deducted:
        for item in order.items:
            product = db.query(Product).filter(Product.id == item.product_id).first()
            if product:
                apply_stock_movement(
                    db=db,
                    product=product,
                    movement_type="RETURN",
                    quantity=item.quantity,
                    reason=f"Stock restored on cancellation of order {order.order_number}",
                    reference_id=order.order_number,
                    idempotency_key=f"ORDER_CANCEL:{order.id}:{item.product_id}",
                    user=current_user,
                )
        order.stock_deducted = False

    order.status = "CANCELLED"
    record_audit_log(db, current_user, "ORDER_CANCEL", "order", order.order_number)
    db.commit()
    db.refresh(order)
    return order


# ---------------- SUPPLIERS ----------------
@app.get("/api/suppliers", response_model=list[SupplierOut])
def list_suppliers(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    suppliers = db.query(Supplier).order_by(Supplier.name).all()
    results = []
    for s in suppliers:
        active_products = [p for p in s.products if p.is_active]
        prod_ids = [p.id for p in active_products]
        purchase_qty = 0.0
        if prod_ids:
            purchase_qty = (
                db.query(func.coalesce(func.sum(StockTransaction.quantity), 0.0))
                .filter(StockTransaction.product_id.in_(prod_ids), StockTransaction.movement_type == "PURCHASE")
                .scalar()
                or 0.0
            )
        results.append(
            SupplierOut(
                id=s.id,
                name=s.name,
                contact_person=s.contact_person,
                phone=s.phone,
                email=s.email,
                address=s.address,
                gstin=s.gstin,
                notes=s.notes,
                created_at=s.created_at,
                product_count=len(active_products),
                total_purchase_qty=round(float(purchase_qty), 2),
            )
        )
    return results


@app.post("/api/suppliers", response_model=SupplierOut)
def create_supplier(
    payload: SupplierCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "manager")),
):
    if db.query(Supplier).filter(Supplier.name == payload.name.strip()).first():
        raise HTTPException(status_code=400, detail="Supplier with this name already exists")
    supplier = Supplier(**payload.model_dump())
    db.add(supplier)
    record_audit_log(db, current_user, "SUPPLIER_CREATE", "supplier", payload.name)
    db.commit()
    db.refresh(supplier)
    return SupplierOut(
        **{k: getattr(supplier, k) for k in SupplierBase.model_fields},
        id=supplier.id,
        created_at=supplier.created_at,
        product_count=0,
        total_purchase_qty=0.0,
    )


@app.put("/api/suppliers/{supplier_id}", response_model=SupplierOut)
def update_supplier(
    supplier_id: int,
    payload: SupplierUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "manager")),
):
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(supplier, k, v)
    record_audit_log(db, current_user, "SUPPLIER_UPDATE", "supplier", supplier.name)
    db.commit()
    db.refresh(supplier)
    return SupplierOut(
        id=supplier.id,
        name=supplier.name,
        contact_person=supplier.contact_person,
        phone=supplier.phone,
        email=supplier.email,
        address=supplier.address,
        gstin=supplier.gstin,
        notes=supplier.notes,
        created_at=supplier.created_at,
        product_count=len([p for p in supplier.products if p.is_active]),
        total_purchase_qty=0.0,
    )


@app.delete("/api/suppliers/{supplier_id}")
def delete_supplier(
    supplier_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("owner")),
):
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    db.delete(supplier)
    record_audit_log(db, current_user, "SUPPLIER_DELETE", "supplier", supplier.name)
    db.commit()
    return {"deleted": True}


# ---------------- ALERTS & N8N AUTOMATION ----------------
@app.get("/api/alerts", response_model=list[AlertOut])
def list_alerts(
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(AlertHistory)
    if status and status != "ALL":
        query = query.filter(AlertHistory.status == status)
    return query.order_by(AlertHistory.created_at.desc()).all()


@app.post("/api/alerts/{alert_id}/acknowledge", response_model=AlertOut)
def acknowledge_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alert = db.query(AlertHistory).filter(AlertHistory.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.status = "ACKNOWLEDGED"
    db.commit()
    db.refresh(alert)
    return alert


@app.post("/api/automation/check-alerts")
def run_inventory_alert_check(
    x_n8n_secret: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """
    Endpoint called every 15 minutes by n8n (or manually from the UI).
    Evaluates all active products, deduplicates unresolved alerts,
    and dispatches WhatsApp Cloud API messages for newly detected issues.
    """
    products = db.query(Product).filter(Product.is_active == True).all()
    newly_created: list[AlertOut] = []
    for product in products:
        alert = evaluate_product_alert(db, product, dispatch_whatsapp=True)
        if alert:
            db.flush()
            newly_created.append(AlertOut.model_validate(alert))
    db.commit()
    return {
        "checked_products": len(products),
        "new_alerts_created": len(newly_created),
        "new_alerts": newly_created,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/automation/daily-summary")
def send_daily_summary(
    x_n8n_secret: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    products = db.query(Product).filter(Product.is_active == True).all()
    total_val = round(sum(p.stock_qty * p.selling_price for p in products), 2)
    low_count = sum(1 for p in products if p.status == "LOW_STOCK")
    out_count = sum(1 for p in products if p.status == "STOCKOUT")
    today_utc = datetime.now(timezone.utc).date()
    real_orders = db.query(Order).filter(Order.is_sample == False, Order.status.in_(["CONFIRMED", "DELIVERED"])).all()
    todays_sales = round(sum(o.total for o in real_orders if o.created_at.date() == today_utc), 2)

    summary_msg = (
        f"📊 *{settings.store_name} — Daily Inventory Summary*\n"
        f"Total SKUs: {len(products)}\n"
        f"Inventory Value: ₹{total_val:,.2f}\n"
        f"Today's Sales: ₹{todays_sales:,.2f}\n"
        f"Low Stock Items: {low_count}\n"
        f"Stockout Items: {out_count}"
    )
    sent, ext_id = send_whatsapp_message_sync(summary_msg)
    return {"sent": sent, "external_message_id": ext_id, "message": summary_msg}


# ---------------- EXCEL IMPORT & EXPORT ----------------
@app.post("/api/import/excel")
async def import_excel_endpoint(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "manager")),
):
    if not file.filename or not file.filename.endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="Please upload a valid .xlsx Excel workbook")
    content = await file.read()
    return import_excel_bytes(db, content, user=current_user)


@app.get("/api/export/excel")
def export_excel_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = export_inventory_excel(db)
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=kirana_inventory_report.xlsx"},
    )


@app.get("/api/export/csv")
def export_csv_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    csv_text = export_inventory_csv(db)
    return StreamingResponse(
        io.BytesIO(csv_text.encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=kirana_inventory.csv"},
    )


# ---------------- AI INVENTORY ASSISTANT ----------------
@app.post("/api/ai/chat", response_model=AIChatResponse)
def ai_chat(
    payload: AIChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = run_ai_assistant(
        db=db,
        message=payload.message,
        user=current_user,
        confirm_action=payload.confirm_action,
        pending_action=payload.pending_action,
    )
    return AIChatResponse(**result)


# ---------------- AUDIT LOGS ----------------
@app.get("/api/audit-logs")
def list_audit_logs(
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "manager")),
):
    return db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()


# ---------------- TELEGRAM BOT HTTP API ----------------
@app.get("/api/telegram/status")
def telegram_status(current_user: User = Depends(get_current_user)):
    return get_telegram_bot_info()


@app.post("/api/telegram/webhook")
async def telegram_webhook(
    update: dict,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    if (
        settings.telegram_webhook_secret
        and x_telegram_bot_api_secret_token is not None
        and x_telegram_bot_api_secret_token != settings.telegram_webhook_secret
    ):
        raise HTTPException(status_code=403, detail="Invalid Telegram webhook secret")
    return handle_telegram_update(db, update, dispatch=True)


@app.post("/api/telegram/send-test")
def telegram_send_test(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "manager")),
):
    products = db.query(Product).filter(Product.is_active == True).all()
    total_val = round(sum(p.stock_qty * p.selling_price for p in products), 2)
    low_count = sum(1 for p in products if p.status == "LOW_STOCK")
    out_count = sum(1 for p in products if p.status == "STOCKOUT")
    msg = (
        f"🏪 *{settings.store_name} — Live Inventory Check*\n"
        f"• Active SKUs: {len(products)}\n"
        f"• Inventory Value: ₹{total_val:,.2f}\n"
        f"• Low Stock: {low_count} | Stockout: {out_count}"
    )
    sent, msg_id = send_telegram_message(msg)
    return {"sent": sent, "external_message_id": msg_id, "preview": msg}


@app.post("/api/telegram/poll-once")
def telegram_poll_once(
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "manager")),
):
    return poll_telegram_updates_once(db, offset=offset)


# ---------------- PRODUCTION STATIC FRONTEND ----------------
_static_dist = Path(
    os.environ.get(
        "STATIC_DIST_DIR",
        str(Path(__file__).resolve().parents[2] / "frontend" / "dist"),
    )
)
if _static_dist.exists():
    _assets_dir = _static_dist / "assets"
    _images_dir = _static_dist / "images"
    if _assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="assets")
    if _images_dir.exists():
        app.mount("/images", StaticFiles(directory=str(_images_dir)), name="images")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API endpoint not found")
        target = _static_dist / full_path
        if target.is_file():
            return FileResponse(str(target))
        return FileResponse(str(_static_dist / "index.html"))
