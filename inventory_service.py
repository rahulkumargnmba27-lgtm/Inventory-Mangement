from datetime import datetime, timezone
import uuid
import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import (
    AlertHistory,
    AuditLog,
    Order,
    Product,
    StockTransaction,
    User,
    classify_stock,
)

settings = get_settings()

OUTBOUND_MOVEMENT_TYPES = {"SALE", "DAMAGED", "EXPIRED"}
INBOUND_MOVEMENT_TYPES = {"PURCHASE", "RETURN", "INITIAL"}


def generate_transaction_id() -> str:
    now_str = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    suffix = uuid.uuid4().hex[:6].upper()
    return f"TXN-{now_str}-{suffix}"


def record_audit_log(
    db: Session,
    user: User | None,
    action: str,
    entity_type: str,
    entity_id: str | int | None = None,
    details: str | None = None,
) -> None:
    log = AuditLog(
        user_id=user.id if user else None,
        user_email=user.email if user else "system",
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        details=details,
    )
    db.add(log)


def send_whatsapp_message_sync(message_text: str, recipient: str | None = None) -> tuple[bool, str]:
    target = recipient or settings.whatsapp_recipient_phone
    if not settings.whatsapp_access_token or not settings.whatsapp_phone_number_id:
        return False, "SIMULATED_NO_CREDENTIALS"

    url = f"https://graph.facebook.com/{settings.whatsapp_api_version}/{settings.whatsapp_phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {settings.whatsapp_access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": target,
        "type": "text",
        "text": {"preview_url": False, "body": message_text},
    }
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            if resp.status_code in (200, 201):
                data = resp.json()
                msg_id = data.get("messages", [{}])[0].get("id", "SENT")
                return True, msg_id
            return False, f"HTTP_{resp.status_code}: {resp.text[:160]}"
    except Exception as exc:
        return False, f"ERROR: {str(exc)[:160]}"


def evaluate_product_alert(db: Session, product: Product, dispatch_whatsapp: bool = True) -> AlertHistory | None:
    """
    Evaluates stock status for a product and creates a deduplicated alert if needed.
    Resolves existing active alerts if stock becomes HEALTHY.
    """
    new_status = classify_stock(product.stock_qty, product.reorder_level)
    product.status = new_status

    active_alerts = (
        db.query(AlertHistory)
        .filter(AlertHistory.product_id == product.id, AlertHistory.status.in_(["ACTIVE", "ACKNOWLEDGED"]))
        .all()
    )

    if new_status == "HEALTHY":
        now = datetime.now(timezone.utc)
        for alert in active_alerts:
            alert.status = "RESOLVED"
            alert.resolved_at = now
        return None

    # Check deduplication: if an unresolved alert of the exact same alert_type already exists, do not send duplicate
    for alert in active_alerts:
        if alert.alert_type == new_status:
            return None
        else:
            # Escalating from LOW_STOCK -> STOCKOUT or vice versa: resolve old type
            alert.status = "RESOLVED"
            alert.resolved_at = datetime.now(timezone.utc)

    shortage = max(0.0, round(product.reorder_level - product.stock_qty, 2))
    recommended_order = max(shortage + product.reorder_level, product.reorder_level * 2)
    action_text = (
        f"URGENT: Restock {recommended_order:g} {product.unit} immediately (0 stock left)."
        if new_status == "STOCKOUT"
        else f"Reorder at least {recommended_order:g} {product.unit} from supplier."
    )

    msg = (
        f"🚨 *Kirana Quick {new_status.replace('_', ' ')} Alert*\n"
        f"Store: {settings.store_name}\n"
        f"Product: {product.name}\n"
        f"SKU: {product.sku}\n"
        f"Current Stock: {product.stock_qty:g} {product.unit}\n"
        f"Reorder Level: {product.reorder_level:g} {product.unit}\n"
        f"Shortage Qty: {shortage:g} {product.unit}\n"
        f"Action: {action_text}"
    )

    ext_id = "IN_APP_ONLY"
    if dispatch_whatsapp:
        _, ext_id = send_whatsapp_message_sync(msg)
        # Also mirror deduplicated alert to Telegram if configured
        from .telegram_service import is_telegram_configured, send_telegram_message
        if is_telegram_configured():
            send_telegram_message(msg.replace("*", ""))

    new_alert = AlertHistory(
        product_id=product.id,
        sku=product.sku,
        product_name=product.name,
        alert_type=new_status,
        current_stock=product.stock_qty,
        reorder_level=product.reorder_level,
        shortage_qty=shortage,
        recommended_action=action_text,
        channel="WHATSAPP",
        status="ACTIVE",
        message_payload=msg,
        external_message_id=ext_id,
    )
    db.add(new_alert)
    return new_alert


def apply_stock_movement(
    db: Session,
    product: Product,
    movement_type: str,
    quantity: float,
    reason: str,
    user: User | None = None,
    direction: str | None = None,
    reference_id: str | None = None,
    idempotency_key: str | None = None,
    allow_negative: bool = False,
) -> StockTransaction:
    """
    Atomically updates product stock, records an immutable StockTransaction,
    re-classifies product status, and evaluates alerts.
    Prevents duplicate deductions via idempotency_key.
    """
    if idempotency_key:
        existing = (
            db.query(StockTransaction)
            .filter(StockTransaction.idempotency_key == idempotency_key)
            .first()
        )
        if existing:
            return existing

    if quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be greater than zero")

    if movement_type in OUTBOUND_MOVEMENT_TYPES:
        delta = -abs(quantity)
    elif movement_type in INBOUND_MOVEMENT_TYPES:
        delta = abs(quantity)
    elif movement_type == "ADJUSTMENT":
        if direction == "OUT":
            delta = -abs(quantity)
        else:
            delta = abs(quantity)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported movement type: {movement_type}")

    prev_stock = float(product.stock_qty)
    updated_stock = round(prev_stock + delta, 2)

    if updated_stock < 0 and not allow_negative:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient stock for {product.name} ({product.sku}). Available: {prev_stock:g} {product.unit}, requested deduction: {abs(delta):g} {product.unit}",
        )

    product.stock_qty = updated_stock
    product.status = classify_stock(updated_stock, product.reorder_level)

    txn = StockTransaction(
        transaction_id=generate_transaction_id(),
        product_id=product.id,
        sku=product.sku,
        product_name=product.name,
        movement_type=movement_type,
        quantity=abs(quantity),
        previous_stock=prev_stock,
        updated_stock=updated_stock,
        reason=reason,
        reference_id=reference_id,
        idempotency_key=idempotency_key,
        created_by=user.id if user else None,
    )
    db.add(txn)
    evaluate_product_alert(db, product, dispatch_whatsapp=True)
    return txn


def confirm_order_stock_deduction(db: Session, order: Order, user: User | None = None) -> None:
    """
    Deducts stock for a CONFIRMED order exactly once.
    Never deducts for DRAFT, CANCELLED, or SAMPLE orders.
    """
    if order.is_sample or order.status in ("DRAFT", "CANCELLED", "SAMPLE"):
        return
    if order.stock_deducted:
        return

    for item in order.items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product ID {item.product_id} not found")
        apply_stock_movement(
            db=db,
            product=product,
            movement_type="SALE",
            quantity=item.quantity,
            reason=f"Order {order.order_number} confirmed ({order.payment_method})",
            user=user,
            reference_id=order.order_number,
            idempotency_key=f"ORDER_CONFIRM:{order.id}:{item.product_id}",
            allow_negative=False,
        )

    order.stock_deducted = True
    order.confirmed_at = datetime.now(timezone.utc)
