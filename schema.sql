-- Kirana Quick Inventory Management System
-- Supabase PostgreSQL Schema

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. Users & Role-Based Access Control
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    email VARCHAR(160) NOT NULL UNIQUE,
    phone VARCHAR(20),
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'staff' CHECK (role IN ('owner', 'manager', 'staff')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Categories
CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(80) NOT NULL UNIQUE,
    description VARCHAR(255),
    icon VARCHAR(50) DEFAULT 'inventory_2',
    display_order INTEGER NOT NULL DEFAULT 0
);

-- 3. Suppliers
CREATE TABLE IF NOT EXISTS suppliers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(160) NOT NULL UNIQUE,
    contact_person VARCHAR(120),
    phone VARCHAR(30) NOT NULL,
    email VARCHAR(160),
    address TEXT,
    gstin VARCHAR(30),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. Products
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    sku VARCHAR(40) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,
    supplier_id INTEGER REFERENCES suppliers(id) ON DELETE SET NULL,
    unit VARCHAR(30) NOT NULL DEFAULT 'pack',
    purchase_price NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (purchase_price >= 0),
    selling_price NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (selling_price >= 0),
    mrp NUMERIC(12, 2),
    stock_qty NUMERIC(12, 2) NOT NULL DEFAULT 0,
    reorder_level NUMERIC(12, 2) NOT NULL DEFAULT 10 CHECK (reorder_level >= 0),
    barcode VARCHAR(80),
    expiry_date DATE,
    image_url VARCHAR(500),
    status VARCHAR(20) NOT NULL DEFAULT 'HEALTHY' CHECK (status IN ('HEALTHY', 'LOW_STOCK', 'STOCKOUT')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku);
CREATE INDEX IF NOT EXISTS idx_products_status ON products(status);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);

-- 5. Orders
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    order_number VARCHAR(60) NOT NULL UNIQUE,
    customer_name VARCHAR(160) NOT NULL DEFAULT 'Walk-in Customer',
    customer_phone VARCHAR(30),
    customer_email VARCHAR(160),
    status VARCHAR(20) NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'CONFIRMED', 'DELIVERED', 'CANCELLED', 'SAMPLE')),
    payment_method VARCHAR(20) NOT NULL DEFAULT 'CASH' CHECK (payment_method IN ('CASH', 'UPI', 'CARD', 'OTHER')),
    subtotal NUMERIC(12, 2) NOT NULL DEFAULT 0,
    discount NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (discount >= 0),
    total NUMERIC(12, 2) NOT NULL DEFAULT 0,
    is_sample BOOLEAN NOT NULL DEFAULT FALSE,
    stock_deducted BOOLEAN NOT NULL DEFAULT FALSE,
    notes TEXT,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    confirmed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_is_sample ON orders(is_sample);

-- 6. Order Items
CREATE TABLE IF NOT EXISTS order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    sku VARCHAR(40) NOT NULL,
    product_name VARCHAR(200) NOT NULL,
    quantity NUMERIC(12, 2) NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(12, 2) NOT NULL CHECK (unit_price >= 0),
    line_total NUMERIC(12, 2) NOT NULL CHECK (line_total >= 0)
);

CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);

-- 7. Stock Transactions (Immutable Movement Ledger)
CREATE TABLE IF NOT EXISTS stock_transactions (
    id SERIAL PRIMARY KEY,
    transaction_id VARCHAR(60) NOT NULL UNIQUE,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    sku VARCHAR(40) NOT NULL,
    product_name VARCHAR(200) NOT NULL,
    movement_type VARCHAR(20) NOT NULL CHECK (movement_type IN ('PURCHASE', 'SALE', 'RETURN', 'DAMAGED', 'EXPIRED', 'ADJUSTMENT', 'INITIAL')),
    quantity NUMERIC(12, 2) NOT NULL,
    previous_stock NUMERIC(12, 2) NOT NULL,
    updated_stock NUMERIC(12, 2) NOT NULL,
    reason TEXT,
    reference_id VARCHAR(80),
    idempotency_key VARCHAR(120) UNIQUE,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stock_txns_product ON stock_transactions(product_id);
CREATE INDEX IF NOT EXISTS idx_stock_txns_created_at ON stock_transactions(created_at DESC);

-- 8. Alert History (Deduplicated Low-Stock & Stockout Notifications)
CREATE TABLE IF NOT EXISTS alert_history (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    sku VARCHAR(40) NOT NULL,
    product_name VARCHAR(200) NOT NULL,
    alert_type VARCHAR(20) NOT NULL CHECK (alert_type IN ('LOW_STOCK', 'STOCKOUT')),
    current_stock NUMERIC(12, 2) NOT NULL,
    reorder_level NUMERIC(12, 2) NOT NULL,
    shortage_qty NUMERIC(12, 2) NOT NULL,
    recommended_action TEXT NOT NULL,
    channel VARCHAR(20) NOT NULL DEFAULT 'WHATSAPP' CHECK (channel IN ('WHATSAPP', 'IN_APP')),
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'ACKNOWLEDGED', 'RESOLVED')),
    message_payload TEXT,
    external_message_id VARCHAR(120),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_alerts_product_status ON alert_history(product_id, status);

-- 9. Audit Logs
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    user_email VARCHAR(160),
    action VARCHAR(80) NOT NULL,
    entity_type VARCHAR(60) NOT NULL,
    entity_id VARCHAR(80),
    details TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at DESC);
