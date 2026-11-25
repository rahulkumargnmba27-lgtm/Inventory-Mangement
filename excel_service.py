from datetime import datetime, timezone
import csv
import io
from openpyxl import Workbook, load_workbook
from sqlalchemy.orm import Session

from ..models import (
    Category,
    Order,
    OrderItem,
    Product,
    StockTransaction,
    Supplier,
    User,
    classify_stock,
)
from .inventory_service import generate_transaction_id, evaluate_product_alert, record_audit_log


def import_excel_bytes(
    db: Session,
    file_bytes: bytes,
    user: User | None = None,
) -> dict:
    """
    Imports Inventory and Orders worksheets from an Excel (.xlsx) workbook.
    Preserves existing SKUs, product names, stock quantities, and reorder levels.
    Prevents duplicate records and marks SAMPLE orders as is_sample=True.
    """
    wb = load_workbook(filename=io.BytesIO(file_bytes), data_only=True)
    summary = {
        "products_imported": 0,
        "products_skipped_duplicate": 0,
        "orders_imported": 0,
        "orders_skipped_duplicate": 0,
        "sample_orders_marked": 0,
        "errors": [],
    }

    default_supplier = db.query(Supplier).first()

    # 1. Import Inventory Worksheet
    if "Inventory" in wb.sheetnames:
        ws = wb["Inventory"]
        rows = list(ws.iter_rows(values_only=True))
        if rows:
            headers = [str(h).strip() if h is not None else "" for h in rows[0]]
            col_idx = {name: idx for idx, name in enumerate(headers)}

            for row_num, row in enumerate(rows[1:], start=2):
                if not row or all(cell is None or str(cell).strip() == "" for cell in row):
                    continue
                try:
                    sku = str(row[col_idx["SKU"]]).strip()
                    name = str(row[col_idx["Product"]]).strip()
                    category_name = str(row[col_idx["Category"]]).strip()
                    unit = str(row[col_idx["Unit"]]).strip()
                    price = float(row[col_idx["Price"]])
                    stock = float(row[col_idx["Stock"]])
                    reorder = float(row[col_idx["ReorderLevel"]])
                except Exception as exc:
                    summary["errors"].append(f"Inventory row {row_num}: invalid data ({exc})")
                    continue

                if not sku or not name:
                    summary["errors"].append(f"Inventory row {row_num}: missing SKU or Product")
                    continue

                existing = db.query(Product).filter(Product.sku == sku).first()
                if existing:
                    summary["products_skipped_duplicate"] += 1
                    continue

                category = db.query(Category).filter(Category.name == category_name).first()
                if not category:
                    category = Category(name=category_name, description=f"{category_name} items")
                    db.add(category)
                    db.flush()

                purchase_price = round(price * 0.85, 2)
                product = Product(
                    sku=sku,
                    name=name,
                    category_id=category.id,
                    supplier_id=default_supplier.id if default_supplier else None,
                    unit=unit,
                    purchase_price=purchase_price,
                    selling_price=price,
                    mrp=round(price * 1.05, 2),
                    stock_qty=stock,
                    reorder_level=reorder,
                    status=classify_stock(stock, reorder),
                    is_active=True,
                )
                db.add(product)
                db.flush()

                txn = StockTransaction(
                    transaction_id=generate_transaction_id(),
                    product_id=product.id,
                    sku=product.sku,
                    product_name=product.name,
                    movement_type="INITIAL",
                    quantity=stock,
                    previous_stock=0.0,
                    updated_stock=stock,
                    reason="Imported from Excel Inventory worksheet",
                    reference_id="EXCEL_IMPORT",
                    idempotency_key=f"EXCEL_INIT:{product.sku}",
                    created_by=user.id if user else None,
                )
                db.add(txn)
                evaluate_product_alert(db, product, dispatch_whatsapp=False)
                summary["products_imported"] += 1

    # 2. Import Orders Worksheet
    if "Orders" in wb.sheetnames:
        ws_orders = wb["Orders"]
        rows = list(ws_orders.iter_rows(values_only=True))
        if rows:
            headers = [str(h).strip() if h is not None else "" for h in rows[0]]
            col_idx = {name: idx for idx, name in enumerate(headers)}

            for row_num, row in enumerate(rows[1:], start=2):
                if not row or all(cell is None or str(cell).strip() == "" for cell in row):
                    continue
                try:
                    order_id = str(row[col_idx["OrderID"]]).strip()
                    raw_date = row[col_idx["Date"]]
                    phone = str(row[col_idx["Phone"]]).strip() if row[col_idx["Phone"]] else None
                    customer_name = str(row[col_idx["CustomerName"]]).strip() if row[col_idx["CustomerName"]] else "Walk-in Customer"
                    customer_email = str(row[col_idx["CustomerEmail"]]).strip() if row[col_idx["CustomerEmail"]] else None
                    items_str = str(row[col_idx["Items"]]).strip() if row[col_idx["Items"]] else ""
                    total = float(row[col_idx["Total"]] or 0)
                    raw_status = str(row[col_idx["Status"]]).strip() if row[col_idx["Status"]] else "CONFIRMED"
                except Exception as exc:
                    summary["errors"].append(f"Orders row {row_num}: invalid data ({exc})")
                    continue

                if not order_id:
                    continue

                existing_order = db.query(Order).filter(Order.order_number == order_id).first()
                if existing_order:
                    summary["orders_skipped_duplicate"] += 1
                    continue

                is_sample = (
                    raw_status.lower() == "sample"
                    or order_id.upper().startswith("SAMPLE")
                    or "sample" in customer_name.lower()
                )
                mapped_status = "SAMPLE" if is_sample else raw_status.upper()
                if mapped_status not in ("DRAFT", "CONFIRMED", "DELIVERED", "CANCELLED", "SAMPLE"):
                    mapped_status = "CONFIRMED"

                parsed_dt = datetime.now(timezone.utc)
                if isinstance(raw_date, datetime):
                    parsed_dt = raw_date.replace(tzinfo=timezone.utc)
                elif raw_date:
                    try:
                        parsed_dt = datetime.fromisoformat(str(raw_date)).replace(tzinfo=timezone.utc)
                    except ValueError:
                        pass

                order = Order(
                    order_number=order_id,
                    customer_name=customer_name,
                    customer_phone=phone,
                    customer_email=customer_email,
                    status=mapped_status,
                    payment_method="CASH",
                    subtotal=total,
                    discount=0.0,
                    total=total,
                    is_sample=is_sample,
                    stock_deducted=False,
                    notes=f"Imported from Excel Orders sheet ({items_str})",
                    created_by=user.id if user else None,
                    created_at=parsed_dt,
                )
                db.add(order)
                db.flush()

                # Try linking item if format is "1x Product Name"
                if items_str:
                    for part in items_str.split(","):
                        part = part.strip()
                        qty = 1.0
                        prod_name = part
                        if "x " in part:
                            qty_part, prod_name = part.split("x ", 1)
                            try:
                                qty = float(qty_part.strip())
                            except ValueError:
                                qty = 1.0
                        prod = db.query(Product).filter(Product.name.ilike(f"%{prod_name.strip()}%")).first()
                        if prod:
                            db.add(
                                OrderItem(
                                    order_id=order.id,
                                    product_id=prod.id,
                                    sku=prod.sku,
                                    product_name=prod.name,
                                    quantity=qty,
                                    unit_price=prod.selling_price,
                                    line_total=round(qty * prod.selling_price, 2),
                                )
                            )

                if is_sample:
                    summary["sample_orders_marked"] += 1
                summary["orders_imported"] += 1

    record_audit_log(
        db=db,
        user=user,
        action="EXCEL_IMPORT",
        entity_type="workbook",
        details=f"Imported {summary['products_imported']} products and {summary['orders_imported']} orders",
    )
    db.commit()
    return summary


def export_inventory_excel(db: Session) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Inventory"
    ws.append([
        "SKU", "Product", "Category", "Unit", "PurchasePrice",
        "SellingPrice", "Stock", "ReorderLevel", "Status", "InventoryValue",
        "Supplier", "Barcode", "ExpiryDate"
    ])
    products = db.query(Product).filter(Product.is_active == True).order_by(Product.sku).all()
    for p in products:
        ws.append([
            p.sku,
            p.name,
            p.category.name if p.category else "",
            p.unit,
            p.purchase_price,
            p.selling_price,
            p.stock_qty,
            p.reorder_level,
            p.status,
            round(p.stock_qty * p.selling_price, 2),
            p.supplier.name if p.supplier else "",
            p.barcode or "",
            p.expiry_date.isoformat() if p.expiry_date else "",
        ])

    ws_orders = wb.create_sheet("Orders")
    ws_orders.append(["OrderID", "Date", "CustomerName", "Phone", "PaymentMethod", "Subtotal", "Discount", "Total", "Status", "IsSample"])
    orders = db.query(Order).order_by(Order.created_at.desc()).all()
    for o in orders:
        ws_orders.append([
            o.order_number,
            o.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            o.customer_name,
            o.customer_phone or "",
            o.payment_method,
            o.subtotal,
            o.discount,
            o.total,
            o.status,
            "Yes" if o.is_sample else "No",
        ])

    ws_txns = wb.create_sheet("StockMovements")
    ws_txns.append(["TransactionID", "Date", "SKU", "Product", "Type", "Quantity", "PreviousStock", "UpdatedStock", "Reason"])
    txns = db.query(StockTransaction).order_by(StockTransaction.created_at.desc()).all()
    for t in txns:
        ws_txns.append([
            t.transaction_id,
            t.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            t.sku,
            t.product_name,
            t.movement_type,
            t.quantity,
            t.previous_stock,
            t.updated_stock,
            t.reason or "",
        ])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def export_inventory_csv(db: Session) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["SKU", "Product", "Category", "Unit", "PurchasePrice", "SellingPrice", "Stock", "ReorderLevel", "Status", "StockValue"])
    products = db.query(Product).filter(Product.is_active == True).order_by(Product.sku).all()
    for p in products:
        writer.writerow([
            p.sku,
            p.name,
            p.category.name if p.category else "",
            p.unit,
            p.purchase_price,
            p.selling_price,
            p.stock_qty,
            p.reorder_level,
            p.status,
            round(p.stock_qty * p.selling_price, 2),
        ])
    return buf.getvalue()
