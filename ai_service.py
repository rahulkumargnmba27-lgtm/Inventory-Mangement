import json
import re
from typing import Any
from google import genai
from google.genai import types
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Order, Product, StockTransaction, User
from .inventory_service import apply_stock_movement, record_audit_log

settings = get_settings()


def _db_inventory_summary(db: Session) -> dict[str, Any]:
    products = db.query(Product).filter(Product.is_active == True).all()
    total_products = len(products)
    total_units = sum(p.stock_qty for p in products)
    total_selling_value = round(sum(p.stock_qty * p.selling_price for p in products), 2)
    total_cost_value = round(sum(p.stock_qty * p.purchase_price for p in products), 2)
    healthy = [p for p in products if p.status == "HEALTHY"]
    low_stock = [p for p in products if p.status == "LOW_STOCK"]
    stockouts = [p for p in products if p.status == "STOCKOUT"]
    return {
        "total_products": total_products,
        "total_units": round(total_units, 2),
        "total_inventory_value_inr": total_selling_value,
        "total_cost_value_inr": total_cost_value,
        "healthy_count": len(healthy),
        "low_stock_count": len(low_stock),
        "stockout_count": len(stockouts),
    }


def _db_search_products(db: Session, query: str) -> list[dict[str, Any]]:
    q = f"%{query.strip()}%"
    matches = (
        db.query(Product)
        .filter(
            Product.is_active == True,
            (Product.name.ilike(q)) | (Product.sku.ilike(q)),
        )
        .order_by(Product.sku)
        .all()
    )
    return [
        {
            "id": p.id,
            "sku": p.sku,
            "name": p.name,
            "category": p.category.name if p.category else "",
            "unit": p.unit,
            "stock_qty": p.stock_qty,
            "reorder_level": p.reorder_level,
            "selling_price": p.selling_price,
            "status": p.status,
            "stock_value_inr": round(p.stock_qty * p.selling_price, 2),
        }
        for p in matches
    ]


def _db_get_alerts_products(db: Session, status_filter: str | None = None) -> list[dict[str, Any]]:
    query = db.query(Product).filter(Product.is_active == True)
    if status_filter in ("LOW_STOCK", "STOCKOUT"):
        query = query.filter(Product.status == status_filter)
    else:
        query = query.filter(Product.status.in_(["LOW_STOCK", "STOCKOUT"]))
    items = query.order_by(Product.stock_qty.asc()).all()
    results = []
    for p in items:
        shortage = max(0.0, round(p.reorder_level - p.stock_qty, 2))
        recommended_reorder = max(shortage + p.reorder_level, p.reorder_level * 2)
        results.append({
            "sku": p.sku,
            "name": p.name,
            "unit": p.unit,
            "stock_qty": p.stock_qty,
            "reorder_level": p.reorder_level,
            "shortage_qty": shortage,
            "recommended_reorder_qty": round(recommended_reorder, 2),
            "status": p.status,
            "supplier": p.supplier.name if p.supplier else "Unassigned",
        })
    return results


def _db_get_recent_transactions(db: Session, limit: int = 10) -> list[dict[str, Any]]:
    txns = db.query(StockTransaction).order_by(StockTransaction.created_at.desc()).limit(limit).all()
    return [
        {
            "transaction_id": t.transaction_id,
            "sku": t.sku,
            "product_name": t.product_name,
            "movement_type": t.movement_type,
            "quantity": t.quantity,
            "previous_stock": t.previous_stock,
            "updated_stock": t.updated_stock,
            "reason": t.reason,
            "date": t.created_at.strftime("%d/%m/%Y %I:%M %p"),
        }
        for t in txns
    ]


def _db_get_orders_summary(db: Session) -> dict[str, Any]:
    real_orders = db.query(Order).filter(Order.is_sample == False).all()
    confirmed = [o for o in real_orders if o.status in ("CONFIRMED", "DELIVERED")]
    drafts = [o for o in real_orders if o.status == "DRAFT"]
    cancelled = [o for o in real_orders if o.status == "CANCELLED"]
    total_revenue = round(sum(o.total for o in confirmed), 2)
    return {
        "total_real_orders": len(real_orders),
        "confirmed_orders": len(confirmed),
        "draft_orders": len(drafts),
        "cancelled_orders": len(cancelled),
        "total_sales_inr": total_revenue,
        "sample_orders_excluded": db.query(func.count(Order.id)).filter(Order.is_sample == True).scalar() or 0,
    }


def execute_confirmed_stock_action(
    db: Session,
    pending_action: dict[str, Any],
    user: User | None,
) -> dict[str, Any]:
    sku = str(pending_action.get("sku", "")).strip()
    qty = float(pending_action.get("quantity", 0))
    movement_type = str(pending_action.get("movement_type", "ADJUSTMENT")).upper()
    direction = pending_action.get("direction")
    reason = str(pending_action.get("reason", "AI Assistant authorized stock update"))

    product = db.query(Product).filter(Product.sku == sku, Product.is_active == True).first()
    if not product:
        raise ValueError(f"SKU '{sku}' not found in database.")

    txn = apply_stock_movement(
        db=db,
        product=product,
        movement_type=movement_type,
        quantity=qty,
        direction=direction,
        reason=reason,
        user=user,
    )
    record_audit_log(
        db=db,
        user=user,
        action="AI_STOCK_UPDATE",
        entity_type="product",
        entity_id=product.sku,
        details=f"{movement_type} {qty} {product.unit} -> {txn.updated_stock} ({txn.transaction_id})",
    )
    db.commit()
    db.refresh(product)

    return {
        "verified": True,
        "sku": product.sku,
        "product_name": product.name,
        "movement_type": txn.movement_type,
        "quantity": txn.quantity,
        "unit": product.unit,
        "previous_stock": txn.previous_stock,
        "updated_stock": product.stock_qty,
        "new_status": product.status,
        "transaction_id": txn.transaction_id,
    }


def _find_best_product_match(db: Session, phrase: str) -> list[Product]:
    clean = re.sub(r"\b(to|from|of|inventory|stock|the|my|please|kg|packets?|packs?|bottles?|jars?|tubes?|pieces?|units?)\b", " ", phrase.lower())
    tokens = [t.strip() for t in clean.split() if len(t.strip()) >= 2]
    all_products = db.query(Product).filter(Product.is_active == True).all()
    scored: list[tuple[int, Product]] = []
    for p in all_products:
        hay = f"{p.sku} {p.name}".lower()
        score = sum(1 for tok in tokens if tok in hay)
        if score > 0:
            scored.append((score, p))
    scored.sort(key=lambda x: (-x[0], x[1].sku))
    if not scored:
        return []
    top_score = scored[0][0]
    return [p for s, p in scored if s == top_score]


def run_ai_assistant(
    db: Session,
    message: str,
    user: User | None,
    confirm_action: bool = False,
    pending_action: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tool_calls_log: list[dict[str, Any]] = []

    # 1. Handle explicit user confirmation of a pending stock mutation
    if confirm_action and pending_action:
        try:
            result = execute_confirmed_stock_action(db, pending_action, user)
            tool_calls_log.append({"tool": "execute_stock_update", "result": result})
            reply = (
                f"Confirmed and verified in database:\n"
                f"- **Product:** {result['product_name']} (`{result['sku']}`)\n"
                f"- **Transaction ID:** `{result['transaction_id']}`\n"
                f"- **Stock Updated:** {result['previous_stock']:g} -> **{result['updated_stock']:g} {result['unit']}**\n"
                f"- **New Status:** `{result['new_status']}`"
            )
            return {
                "reply": reply,
                "mode": "gemini" if settings.gemini_api_key else "local_verified",
                "requires_confirmation": False,
                "pending_action": None,
                "tool_calls": tool_calls_log,
            }
        except Exception as exc:
            db.rollback()
            return {
                "reply": f"Could not complete the stock update: {exc}",
                "mode": "local_verified",
                "requires_confirmation": False,
                "pending_action": None,
                "tool_calls": tool_calls_log,
            }

    # 2. Check if message is a stock modification request (always require confirmation before mutating!)
    lower_msg = message.lower().strip()
    mod_match = re.search(
        r"\b(add|restock|increase|purchase|deduct|remove|subtract|reduce|sell)\s+(\d+(?:\.\d+)?)\s*(?:kg|g|l|ml|packets?|packs?|bottles?|jars?|tubes?|pieces?|pcs|units?)?\s*(?:of\s+)?(.+)",
        lower_msg,
    )
    if mod_match:
        verb = mod_match.group(1)
        qty = float(mod_match.group(2))
        target_phrase = mod_match.group(3)
        matches = _find_best_product_match(db, target_phrase)
        if not matches:
            return {
                "reply": f"I could not find any active product matching **'{target_phrase.strip()}'** in the database. Please specify the exact product name or SKU (e.g., `KIR002` or `KIR006`).",
                "mode": "local_verified",
                "requires_confirmation": False,
                "pending_action": None,
                "tool_calls": [{"tool": "search_products", "query": target_phrase, "matches": 0}],
            }
        if len(matches) > 1:
            options = "\n".join(f"- `{p.sku}`: {p.name} (Current: {p.stock_qty:g} {p.unit})" for p in matches[:5])
            return {
                "reply": f"Multiple products matched your request. Please clarify which SKU you want to update:\n{options}",
                "mode": "local_verified",
                "requires_confirmation": False,
                "pending_action": None,
                "tool_calls": [{"tool": "search_products", "query": target_phrase, "matches": len(matches)}],
            }

        product = matches[0]
        is_outbound = verb in ("deduct", "remove", "subtract", "reduce", "sell")
        movement_type = "SALE" if verb == "sell" else ("ADJUSTMENT" if is_outbound else "PURCHASE")
        direction = "OUT" if is_outbound else "IN"
        projected = round(product.stock_qty - qty if is_outbound else product.stock_qty + qty, 2)

        if projected < 0:
            return {
                "reply": f"Cannot deduct {qty:g} {product.unit} from **{product.name}** (`{product.sku}`). Current available stock is only **{product.stock_qty:g} {product.unit}**.",
                "mode": "local_verified",
                "requires_confirmation": False,
                "pending_action": None,
                "tool_calls": [{"tool": "validate_stock", "sku": product.sku, "available": product.stock_qty, "requested": qty}],
            }

        action_payload = {
            "sku": product.sku,
            "product_name": product.name,
            "unit": product.unit,
            "quantity": qty,
            "movement_type": movement_type,
            "direction": direction,
            "current_stock": product.stock_qty,
            "projected_stock": projected,
            "reason": f"AI Assistant request: {message}",
        }
        verb_label = "Deduct" if is_outbound else "Add"
        return {
            "reply": (
                f"Please confirm this inventory update:\n"
                f"- **Action:** {verb_label} **{qty:g} {product.unit}**\n"
                f"- **Product:** {product.name} (`{product.sku}`)\n"
                f"- **Current Stock:** {product.stock_qty:g} {product.unit}\n"
                f"- **New Stock After Update:** {projected:g} {product.unit}\n\n"
                f"Click **Confirm Update** below to execute and record the transaction."
            ),
            "mode": "gemini" if settings.gemini_api_key else "local_verified",
            "requires_confirmation": True,
            "pending_action": action_payload,
            "tool_calls": [{"tool": "verify_sku_and_preview", "sku": product.sku, "current_stock": product.stock_qty}],
        }

    # 3. If GEMINI_API_KEY is configured, use Google Gemini API with live DB tools
    if settings.gemini_api_key and not settings.gemini_api_key.startswith("your-"):
        try:
            client = genai.Client(api_key=settings.gemini_api_key)

            def get_inventory_summary() -> dict:
                """Get overall store inventory summary including total products, total value in INR, and stock status counts."""
                res = _db_inventory_summary(db)
                tool_calls_log.append({"tool": "get_inventory_summary", "result": res})
                return res

            def search_products(query: str) -> list[dict]:
                """Search products by name or SKU in the live inventory database."""
                res = _db_search_products(db, query)
                tool_calls_log.append({"tool": "search_products", "query": query, "count": len(res)})
                return res

            def get_low_stock_and_stockouts(status_filter: str = "") -> list[dict]:
                """Get all LOW_STOCK and STOCKOUT products with shortage and recommended reorder quantities."""
                res = _db_get_alerts_products(db, status_filter or None)
                tool_calls_log.append({"tool": "get_low_stock_and_stockouts", "count": len(res)})
                return res

            def get_recent_transactions(limit: int = 10) -> list[dict]:
                """Retrieve recent stock movement transactions from the ledger."""
                res = _db_get_recent_transactions(db, limit)
                tool_calls_log.append({"tool": "get_recent_transactions", "count": len(res)})
                return res

            def get_orders_summary() -> dict:
                """Retrieve live order counts and sales totals (excluding sample orders)."""
                res = _db_get_orders_summary(db)
                tool_calls_log.append({"tool": "get_orders_summary", "result": res})
                return res

            response = client.models.generate_content(
                model=settings.gemini_model,
                contents=message,
                config=types.GenerateContentConfig(
                    system_instruction=(
                        "You are the AI Inventory Assistant for Gupta Brothers Kirana Store (India). "
                        "Always use the provided database tools to inspect live inventory, orders, and transactions. "
                        "Never fabricate quantities, SKUs, or prices. Format currency in INR (₹) and use metric units."
                    ),
                    tools=[
                        get_inventory_summary,
                        search_products,
                        get_low_stock_and_stockouts,
                        get_recent_transactions,
                        get_orders_summary,
                    ],
                ),
            )
            if response.text:
                return {
                    "reply": response.text,
                    "mode": "gemini",
                    "requires_confirmation": False,
                    "pending_action": None,
                    "tool_calls": tool_calls_log,
                }
        except Exception as exc:
            tool_calls_log.append({"tool": "gemini_fallback", "error": str(exc)[:120]})

    # 4. Deterministic live-DB fallback when GEMINI_API_KEY is not configured or unavailable
    if "stockout" in lower_msg or "out of stock" in lower_msg:
        items = _db_get_alerts_products(db, "STOCKOUT")
        tool_calls_log.append({"tool": "get_low_stock_and_stockouts", "filter": "STOCKOUT"})
        if not items:
            reply = "Great news! There are currently **0 stockouts** in your inventory."
        else:
            lines = "\n".join(
                f"- **{i['name']}** (`{i['sku']}`): **0 {i['unit']}** left (Reorder level: {i['reorder_level']:g}, Recommended reorder: **{i['recommended_reorder_qty']:g} {i['unit']}**)"
                for i in items
            )
            reply = f"Here are the current **STOCKOUT** items ({len(items)}):\n{lines}"
    elif "low" in lower_msg or "shortage" in lower_msg or "running low" in lower_msg:
        items = _db_get_alerts_products(db)
        tool_calls_log.append({"tool": "get_low_stock_and_stockouts", "filter": "ALL_ALERTS"})
        if not items:
            reply = "All products are currently above their reorder levels (**HEALTHY**)."
        else:
            lines = "\n".join(
                f"- **{i['name']}** (`{i['sku']}`) [{i['status']}]: **{i['stock_qty']:g} {i['unit']}** left (Reorder level: {i['reorder_level']:g}, Recommended reorder: **{i['recommended_reorder_qty']:g} {i['unit']}**)"
                for i in items
            )
            reply = f"Products needing attention ({len(items)}):\n{lines}"
    elif "value" in lower_msg or "worth" in lower_msg or "valuation" in lower_msg:
        summary = _db_inventory_summary(db)
        tool_calls_log.append({"tool": "get_inventory_summary"})
        reply = (
            f"**Live Inventory Valuation ({summary['total_products']} active SKUs):**\n"
            f"- **Total Retail Value:** ₹{summary['total_inventory_value_inr']:,.2f}\n"
            f"- **Total Cost Value:** ₹{summary['total_cost_value_inr']:,.2f}\n"
            f"- **Stock Breakdown:** {summary['healthy_count']} Healthy, {summary['low_stock_count']} Low Stock, {summary['stockout_count']} Stockout"
        )
    elif "order" in lower_msg or "sales" in lower_msg:
        orders = _db_get_orders_summary(db)
        tool_calls_log.append({"tool": "get_orders_summary"})
        reply = (
            f"**Live Orders Summary** (excluding {orders['sample_orders_excluded']} sample record):\n"
            f"- **Confirmed Orders:** {orders['confirmed_orders']}\n"
            f"- **Draft Orders:** {orders['draft_orders']}\n"
            f"- **Cancelled Orders:** {orders['cancelled_orders']}\n"
            f"- **Total Verified Sales:** ₹{orders['total_sales_inr']:,.2f}"
        )
    elif "transaction" in lower_msg or "history" in lower_msg or "movement" in lower_msg:
        txns = _db_get_recent_transactions(db, 8)
        tool_calls_log.append({"tool": "get_recent_transactions"})
        if not txns:
            reply = "No stock transactions recorded yet."
        else:
            lines = "\n".join(
                f"- `{t['transaction_id']}` | **{t['product_name']}** ({t['movement_type']} {t['quantity']:g}): {t['previous_stock']:g} -> {t['updated_stock']:g}"
                for t in txns
            )
            reply = f"**Recent Stock Movements:**\n{lines}"
    elif "reorder" in lower_msg:
        matches = _find_best_product_match(db, lower_msg.replace("wheat flour", "atta"))
        if not matches and "flour" in lower_msg:
            matches = _find_best_product_match(db, "atta")
        tool_calls_log.append({"tool": "calculate_reorder"})
        if matches:
            p = matches[0]
            target_stock = p.reorder_level * 2
            suggested = max(0.0, round(target_stock - p.stock_qty, 2))
            if p.stock_qty > p.reorder_level:
                reply = f"**{p.name}** (`{p.sku}`) is currently **HEALTHY** with **{p.stock_qty:g} {p.unit}** (Reorder level: {p.reorder_level:g} {p.unit}). Immediate reorder is not required."
            else:
                reply = f"**{p.name}** (`{p.sku}`) has **{p.stock_qty:g} {p.unit}** (Reorder level: {p.reorder_level:g} {p.unit}). Recommended reorder quantity: **{suggested:g} {p.unit}** to reach optimal buffer ({target_stock:g} {p.unit})."
        else:
            alerts = _db_get_alerts_products(db)
            if not alerts:
                reply = "All products are currently healthy; no immediate reorders required."
            else:
                lines = "\n".join(f"- **{a['name']}** (`{a['sku']}`): Reorder **{a['recommended_reorder_qty']:g} {a['unit']}**" for a in alerts)
                reply = f"**Recommended Reorders:**\n{lines}"
    else:
        # General product lookup (e.g. "How much rice is available?")
        matches = _find_best_product_match(db, lower_msg)
        tool_calls_log.append({"tool": "search_products", "matches": len(matches)})
        if matches:
            lines = "\n".join(
                f"- **{p.name}** (`{p.sku}`): **{p.stock_qty:g} {p.unit}** available | Status: `{p.status}` | Price: ₹{p.selling_price:g}"
                for p in matches[:5]
            )
            reply = f"**Live Inventory Lookup:**\n{lines}"
        else:
            summary = _db_inventory_summary(db)
            reply = (
                f"Store currently has **{summary['total_products']} active products** worth **₹{summary['total_inventory_value_inr']:,.2f}** "
                f"({summary['low_stock_count']} low stock, {summary['stockout_count']} stockout). "
                f"Ask me about any product (e.g., *'How much rice is available?'*, *'Show all stockouts'*, or *'Add 50 kg rice to inventory'*)."
            )

    return {
        "reply": reply,
        "mode": "local_verified",
        "requires_confirmation": False,
        "pending_action": None,
        "tool_calls": tool_calls_log,
    }
