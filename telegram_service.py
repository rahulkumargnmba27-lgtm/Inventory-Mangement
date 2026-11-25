import re
from typing import Any
import httpx
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Product, User
from .ai_service import (
    _db_get_alerts_products,
    _db_inventory_summary,
    _db_get_orders_summary,
    _find_best_product_match,
    execute_confirmed_stock_action,
    run_ai_assistant,
)

settings = get_settings()


def is_telegram_configured() -> bool:
    return bool(
        settings.telegram_bot_token
        and not settings.telegram_bot_token.startswith("your-")
    )


def telegram_api_url(method: str) -> str:
    return f"https://api.telegram.org/bot{settings.telegram_bot_token}/{method}"


def send_telegram_message(
    text: str,
    chat_id: str | int | None = None,
    reply_markup: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    target_chat = str(chat_id or settings.telegram_chat_id or "").strip()
    if not is_telegram_configured() or not target_chat or target_chat.startswith("your-"):
        return False, "SIMULATED_NO_TELEGRAM_CREDENTIALS"

    payload: dict[str, Any] = {
        "chat_id": target_chat,
        "text": text,
        "parse_mode": "Markdown",
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(telegram_api_url("sendMessage"), json=payload)
            if resp.status_code == 200:
                data = resp.json()
                msg_id = str(data.get("result", {}).get("message_id", "SENT"))
                return True, msg_id
            return False, f"HTTP_{resp.status_code}: {resp.text[:160]}"
    except Exception as exc:
        return False, f"ERROR: {str(exc)[:160]}"


def answer_telegram_callback(callback_query_id: str, text: str = "Done") -> None:
    if not is_telegram_configured():
        return
    try:
        with httpx.Client(timeout=5.0) as client:
            client.post(
                telegram_api_url("answerCallbackQuery"),
                json={"callback_query_id": callback_query_id, "text": text},
            )
    except Exception:
        pass


def get_telegram_bot_info() -> dict[str, Any]:
    if not is_telegram_configured():
        return {"configured": False, "chat_id_configured": bool(settings.telegram_chat_id and not settings.telegram_chat_id.startswith("your-"))}
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(telegram_api_url("getMe"))
            if resp.status_code == 200 and resp.json().get("ok"):
                bot = resp.json()["result"]
                return {
                    "configured": True,
                    "chat_id_configured": bool(settings.telegram_chat_id and not settings.telegram_chat_id.startswith("your-")),
                    "username": bot.get("username"),
                    "first_name": bot.get("first_name"),
                }
            return {"configured": True, "error": f"HTTP_{resp.status_code}"}
    except Exception as exc:
        return {"configured": True, "error": str(exc)[:120]}


def _format_help_message() -> str:
    return (
        f"🏪 *{settings.store_name} — Telegram Inventory Bot*\n\n"
        "Use these commands or type any natural-language question:\n"
        "• `/stock <name or SKU>` — Check available stock\n"
        "• `/lowstock` — List all low-stock & stockout items\n"
        "• `/stockouts` — List out-of-stock items\n"
        "• `/value` — Total inventory valuation (₹)\n"
        "• `/orders` — Verified sales & orders summary\n"
        "• `/add <qty> <SKU or name>` — Add stock (asks confirmation)\n"
        "• `/deduct <qty> <SKU or name>` — Deduct stock (asks confirmation)\n"
    )


def handle_telegram_update(db: Session, update: dict[str, Any], dispatch: bool = True) -> dict[str, Any]:
    """
    Processes an incoming Telegram Update (message or callback_query).
    Returns the structured response and optionally dispatches via Telegram HTTP API.
    """
    owner = db.query(User).filter(User.role == "owner").first()

    # 1. Handle Inline Keyboard Confirmation Callback
    if "callback_query" in update:
        cb = update["callback_query"]
        cb_id = cb.get("id", "")
        chat_id = cb.get("message", {}).get("chat", {}).get("id")
        data = str(cb.get("data", ""))

        if data == "CANCEL_STOCK":
            answer_telegram_callback(cb_id, "Cancelled")
            reply_text = "❌ Stock update cancelled. No changes were made."
            if dispatch and chat_id:
                send_telegram_message(reply_text, chat_id=chat_id)
            return {"handled": True, "action": "cancelled", "reply": reply_text}

        if data.startswith("CONFIRM_STOCK:"):
            parts = data.split(":")
            if len(parts) == 5:
                _, sku, direction, qty_str, mtype = parts
                try:
                    qty = float(qty_str)
                    result = execute_confirmed_stock_action(
                        db=db,
                        pending_action={
                            "sku": sku,
                            "quantity": qty,
                            "movement_type": mtype,
                            "direction": direction,
                            "reason": f"Confirmed via Telegram Bot (chat {chat_id})",
                        },
                        user=owner,
                    )
                    answer_telegram_callback(cb_id, "Stock updated!")
                    reply_text = (
                        f"✅ *Stock Updated & Verified*\n"
                        f"• Product: *{result['product_name']}* (`{result['sku']}`)\n"
                        f"• Txn ID: `{result['transaction_id']}`\n"
                        f"• Stock: {result['previous_stock']:g} → *{result['updated_stock']:g} {result['unit']}*\n"
                        f"• Status: `{result['new_status']}`"
                    )
                except Exception as exc:
                    db.rollback()
                    answer_telegram_callback(cb_id, "Failed")
                    reply_text = f"⚠️ Could not update stock: {exc}"
            else:
                reply_text = "⚠️ Invalid confirmation payload."

            if dispatch and chat_id:
                send_telegram_message(reply_text, chat_id=chat_id)
            return {"handled": True, "action": "confirmed", "reply": reply_text}

    # 2. Handle Text / Command Messages
    msg = update.get("message") or update.get("edited_message")
    if not msg or not msg.get("text"):
        return {"handled": False, "reason": "No text message in update"}

    chat_id = msg.get("chat", {}).get("id")
    raw_text = msg["text"].strip()
    lower = raw_text.lower()
    reply_markup: dict[str, Any] | None = None

    if lower in ("/start", "/help", "help"):
        reply_text = _format_help_message()
    elif lower.startswith("/value"):
        s = _db_inventory_summary(db)
        reply_text = (
            f"💰 *Live Inventory Valuation*\n"
            f"• Active SKUs: *{s['total_products']}*\n"
            f"• Retail Value: *₹{s['total_inventory_value_inr']:,.2f}*\n"
            f"• Cost Value: *₹{s['total_cost_value_inr']:,.2f}*\n"
            f"• Healthy: {s['healthy_count']} | Low: {s['low_stock_count']} | Stockout: {s['stockout_count']}"
        )
    elif lower.startswith("/orders"):
        o = _db_get_orders_summary(db)
        reply_text = (
            f"🧾 *Orders & Sales Summary*\n"
            f"• Confirmed Orders: *{o['confirmed_orders']}*\n"
            f"• Draft Orders: {o['draft_orders']}\n"
            f"• Verified Sales: *₹{o['total_sales_inr']:,.2f}*\n"
            f"_(Excluded {o['sample_orders_excluded']} sample record)_"
        )
    elif lower.startswith("/stockouts"):
        items = _db_get_alerts_products(db, "STOCKOUT")
        if not items:
            reply_text = "✅ *0 Stockouts*! All items have stock available."
        else:
            lines = "\n".join(
                f"• *{i['name']}* (`{i['sku']}`): 0 {i['unit']} (Reorder: *{i['recommended_reorder_qty']:g} {i['unit']}*)"
                for i in items
            )
            reply_text = f"🚨 *Stockout Items ({len(items)}):*\n{lines}"
    elif lower.startswith("/lowstock"):
        items = _db_get_alerts_products(db)
        if not items:
            reply_text = "✅ All products are *HEALTHY*!"
        else:
            lines = "\n".join(
                f"• *{i['name']}* (`{i['sku']}`) [{i['status']}]: *{i['stock_qty']:g} {i['unit']}* left (Min: {i['reorder_level']:g})"
                for i in items
            )
            reply_text = f"⚠️ *Low Stock & Stockouts ({len(items)}):*\n{lines}"
    elif lower.startswith("/stock "):
        query = raw_text[7:].strip()
        matches = _find_best_product_match(db, query)
        if not matches:
            reply_text = f"No active product found matching `{query}`."
        else:
            lines = "\n".join(
                f"• *{p.name}* (`{p.sku}`): *{p.stock_qty:g} {p.unit}* | `{p.status}` | ₹{p.selling_price:g}"
                for p in matches[:5]
            )
            reply_text = f"📦 *Stock Lookup:*\n{lines}"
    elif re.match(r"^/(add|deduct)\s+", lower):
        # Convert "/add 10 KIR002" or "/deduct 5 salt" to natural language for unified validation & confirmation
        clean_cmd = raw_text[1:]
        ai_res = run_ai_assistant(db=db, message=clean_cmd, user=owner)
        reply_text = ai_res["reply"].replace("**", "*")
        if ai_res.get("requires_confirmation") and ai_res.get("pending_action"):
            pa = ai_res["pending_action"]
            cb_data = f"CONFIRM_STOCK:{pa['sku']}:{pa['direction']}:{pa['quantity']}:{pa['movement_type']}"
            reply_markup = {
                "inline_keyboard": [[
                    {"text": "✅ Confirm Update", "callback_data": cb_data},
                    {"text": "❌ Cancel", "callback_data": "CANCEL_STOCK"},
                ]]
            }
    else:
        ai_res = run_ai_assistant(db=db, message=raw_text, user=owner)
        reply_text = ai_res["reply"].replace("**", "*")
        if ai_res.get("requires_confirmation") and ai_res.get("pending_action"):
            pa = ai_res["pending_action"]
            cb_data = f"CONFIRM_STOCK:{pa['sku']}:{pa['direction']}:{pa['quantity']}:{pa['movement_type']}"
            reply_markup = {
                "inline_keyboard": [[
                    {"text": "✅ Confirm Update", "callback_data": cb_data},
                    {"text": "❌ Cancel", "callback_data": "CANCEL_STOCK"},
                ]]
            }

    sent_status = "SKIPPED"
    if dispatch and chat_id:
        _, sent_status = send_telegram_message(reply_text, chat_id=chat_id, reply_markup=reply_markup)

    return {
        "handled": True,
        "chat_id": chat_id,
        "reply": reply_text,
        "has_confirmation_buttons": reply_markup is not None,
        "telegram_dispatch": sent_status,
    }


def poll_telegram_updates_once(db: Session, offset: int = 0) -> dict[str, Any]:
    if not is_telegram_configured():
        return {"configured": False, "processed": 0, "next_offset": offset}
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                telegram_api_url("getUpdates"),
                params={"offset": offset, "timeout": 1, "allowed_updates": '["message","callback_query"]'},
            )
            if resp.status_code != 200:
                return {"configured": True, "error": f"HTTP_{resp.status_code}", "processed": 0, "next_offset": offset}
            updates = resp.json().get("result", [])
            next_offset = offset
            results = []
            for upd in updates:
                next_offset = max(next_offset, upd["update_id"] + 1)
                results.append(handle_telegram_update(db, upd, dispatch=True))
            return {"configured": True, "processed": len(results), "next_offset": next_offset, "results": results}
    except Exception as exc:
        return {"configured": True, "error": str(exc)[:120], "processed": 0, "next_offset": offset}
