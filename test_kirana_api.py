import uuid
from fastapi.testclient import TestClient
from app.main import app


def get_owner_headers(client: TestClient) -> dict[str, str]:
    res = client.post("/api/auth/login", json={"email": "owner@kiranaquick.in", "password": "Kirana@123"})
    assert res.status_code == 200
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_seeded_inventory_and_classification():
    with TestClient(app) as client:
        headers = get_owner_headers(client)
        res = client.get("/api/products", headers=headers)
        assert res.status_code == 200
        products = res.json()
        assert len(products) >= 24

        by_sku = {p["sku"]: p for p in products}
        assert by_sku["KIR020"]["stock_qty"] == 0
        assert by_sku["KIR020"]["status"] == "STOCKOUT"
        assert by_sku["KIR022"]["stock_qty"] == 5
        assert by_sku["KIR022"]["status"] == "LOW_STOCK"
        assert by_sku["KIR001"]["status"] == "HEALTHY"


def test_sample_order_excluded_from_sales():
    with TestClient(app) as client:
        headers = get_owner_headers(client)
        dash = client.get("/api/dashboard", headers=headers).json()
        # SAMPLE-001 (₹28) must be excluded from total_sales
        orders = client.get("/api/orders", headers=headers).json()
        sample_orders = [o for o in orders if o["order_number"] == "SAMPLE-001"]
        assert len(sample_orders) == 1
        assert sample_orders[0]["is_sample"] is True
        assert sample_orders[0]["stock_deducted"] is False
        assert dash["kpis"]["total_sales"] >= 0


def test_product_crud_and_stock_movements():
    with TestClient(app) as client:
        headers = get_owner_headers(client)
        # Create
        create_res = client.post(
            "/api/products",
            headers=headers,
            json={
                "sku": f"KIR-{uuid.uuid4().hex[:6].upper()}",
                "name": "Test Ghee 500ml",
                "category_name": "Dairy",
                "unit": "jar",
                "purchase_price": 250,
                "selling_price": 300,
                "stock_qty": 15,
                "reorder_level": 5,
            },
        )
        assert create_res.status_code == 200
        prod = create_res.json()
        assert prod["status"] == "HEALTHY"

        # Stock inward
        in_res = client.post(
            "/api/movements",
            headers=headers,
            json={
                "product_id": prod["id"],
                "movement_type": "PURCHASE",
                "quantity": 10,
                "reason": "Test inward purchase",
            },
        )
        assert in_res.status_code == 200
        assert in_res.json()["updated_stock"] == 25

        # Stock outward -> LOW_STOCK
        out_res = client.post(
            "/api/movements",
            headers=headers,
            json={
                "product_id": prod["id"],
                "movement_type": "DAMAGED",
                "quantity": 21,
                "reason": "Test damaged goods",
            },
        )
        assert out_res.status_code == 200
        assert out_res.json()["updated_stock"] == 4

        # Delete
        del_res = client.delete(f"/api/products/{prod['id']}", headers=headers)
        assert del_res.status_code == 200


def test_order_confirmation_and_duplicate_deduction_prevention():
    with TestClient(app) as client:
        headers = get_owner_headers(client)
        products = {p["sku"]: p for p in client.get("/api/products", headers=headers).json()}
        salt = products["KIR006"]
        initial_stock = salt["stock_qty"]

        # Draft order must NOT deduct stock
        draft_res = client.post(
            "/api/orders",
            headers=headers,
            json={
                "customer_name": "Sharma Ji",
                "payment_method": "UPI",
                "status": "DRAFT",
                "items": [{"product_id": salt["id"], "quantity": 2}],
            },
        )
        assert draft_res.status_code == 200
        draft = draft_res.json()
        assert draft["stock_deducted"] is False

        # Confirm order -> deducts 2
        c1 = client.post(f"/api/orders/{draft['id']}/confirm", headers=headers)
        assert c1.status_code == 200
        assert c1.json()["stock_deducted"] is True

        # Confirming again must NOT deduct twice
        c2 = client.post(f"/api/orders/{draft['id']}/confirm", headers=headers)
        assert c2.status_code == 200

        after = {p["sku"]: p for p in client.get("/api/products", headers=headers).json()}["KIR006"]
        assert after["stock_qty"] == initial_stock - 2

        # Cancel order -> restores stock
        cancel_res = client.post(f"/api/orders/{draft['id']}/cancel", headers=headers)
        assert cancel_res.status_code == 200
        restored = {p["sku"]: p for p in client.get("/api/products", headers=headers).json()}["KIR006"]
        assert restored["stock_qty"] == initial_stock


def test_ai_retrieval_and_confirmed_stock_update():
    with TestClient(app) as client:
        headers = get_owner_headers(client)
        # Retrieval
        r1 = client.post("/api/ai/chat", headers=headers, json={"message": "Show all stockouts"})
        assert r1.status_code == 200
        assert "KIR020" in r1.json()["reply"]

        # Modification requires confirmation first
        r2 = client.post("/api/ai/chat", headers=headers, json={"message": "Add 5 kg rice to inventory"})
        assert r2.status_code == 200
        data2 = r2.json()
        assert data2["requires_confirmation"] is True
        assert data2["pending_action"]["sku"] == "KIR002"

        # Execute confirmed
        r3 = client.post(
            "/api/ai/chat",
            headers=headers,
            json={"message": "confirm", "confirm_action": True, "pending_action": data2["pending_action"]},
        )
        assert r3.status_code == 200
        assert "Confirmed and verified" in r3.json()["reply"]

        # Alert deduplication check
        a1 = client.post("/api/automation/check-alerts")
        assert a1.status_code == 200
        a2 = client.post("/api/automation/check-alerts")
        assert a2.status_code == 200
        assert a2.json()["new_alerts_created"] == 0


def test_telegram_webhook_check_and_update():
    with TestClient(app) as client:
        headers = get_owner_headers(client)
        # 1. Check stock via /stock command
        r1 = client.post(
            "/api/telegram/webhook",
            json={"update_id": 101, "message": {"chat": {"id": 99999}, "text": "/stock rice"}},
        )
        assert r1.status_code == 200
        assert "KIR002" in r1.json()["reply"]

        # 2. Request stock update via /add -> returns inline confirmation buttons
        r2 = client.post(
            "/api/telegram/webhook",
            json={"update_id": 102, "message": {"chat": {"id": 99999}, "text": "/add 5 KIR002"}},
        )
        assert r2.status_code == 200
        assert r2.json()["has_confirmation_buttons"] is True

        # 3. Confirm via Telegram callback_query -> executes & verifies DB update
        before = {p["sku"]: p for p in client.get("/api/products", headers=headers).json()}["KIR002"]["stock_qty"]
        r3 = client.post(
            "/api/telegram/webhook",
            json={
                "update_id": 103,
                "callback_query": {
                    "id": "cb-1",
                    "message": {"chat": {"id": 99999}},
                    "data": "CONFIRM_STOCK:KIR002:IN:5.0:PURCHASE",
                },
            },
        )
        assert r3.status_code == 200
        assert r3.json()["action"] == "confirmed"
        after = {p["sku"]: p for p in client.get("/api/products", headers=headers).json()}["KIR002"]["stock_qty"]
        assert after == before + 5

