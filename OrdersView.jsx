import { useState } from 'react';
import { apiRequest } from '../api';
import { formatINR, formatIndianDate, statusBadgeStyle } from '../utils/format';

export default function OrdersView({ orders, products, onReload }) {
  const [customerName, setCustomerName] = useState('Walk-in Customer');
  const [customerPhone, setCustomerPhone] = useState('');
  const [paymentMethod, setPaymentMethod] = useState('UPI');
  const [discount, setDiscount] = useState('0');
  const [selectedProdId, setSelectedProdId] = useState(products[0]?.id ? String(products[0].id) : '');
  const [qtyInput, setQtyInput] = useState('1');
  const [cart, setCart] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');

  function addToCart() {
    const prod = products.find((p) => String(p.id) === String(selectedProdId));
    if (!prod) return;
    const qty = Number(qtyInput || 1);
    if (qty <= 0) return;

    setCart((prev) => {
      const existing = prev.find((i) => i.product_id === prod.id);
      if (existing) {
        return prev.map((i) =>
          i.product_id === prod.id ? { ...i, quantity: i.quantity + qty } : i
        );
      }
      return [
        ...prev,
        {
          product_id: prod.id,
          sku: prod.sku,
          name: prod.name,
          unit: prod.unit,
          unit_price: prod.selling_price,
          quantity: qty,
        },
      ];
    });
  }

  function removeFromCart(productId) {
    setCart((prev) => prev.filter((i) => i.product_id !== productId));
  }

  const subtotal = cart.reduce((sum, i) => sum + i.unit_price * i.quantity, 0);
  const discountNum = Math.min(Number(discount || 0), subtotal);
  const grandTotal = Math.max(0, subtotal - discountNum);

  async function submitOrder(status) {
    if (cart.length === 0) {
      setErr('Add at least one product to the basket.');
      return;
    }
    setSubmitting(true);
    setErr('');
    setMsg('');
    try {
      const order = await apiRequest('/orders', {
        method: 'POST',
        body: JSON.stringify({
          customer_name: customerName,
          customer_phone: customerPhone || null,
          payment_method: paymentMethod,
          discount: discountNum,
          status,
          items: cart.map((i) => ({ product_id: i.product_id, quantity: i.quantity })),
        }),
      });
      setCart([]);
      setDiscount('0');
      setMsg(
        status === 'CONFIRMED'
          ? `Order ${order.order_number} confirmed! Stock automatically deducted.`
          : `Draft order ${order.order_number} saved (stock NOT deducted).`
      );
      await onReload();
    } catch (e) {
      setErr(e.message);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleConfirmOrder(orderId) {
    setErr('');
    setMsg('');
    try {
      const res = await apiRequest(`/orders/${orderId}/confirm`, { method: 'POST' });
      setMsg(`Order ${res.order_number} confirmed and stock deducted.`);
      await onReload();
    } catch (e) {
      setErr(e.message);
    }
  }

  async function handleCancelOrder(orderId) {
    setErr('');
    setMsg('');
    try {
      const res = await apiRequest(`/orders/${orderId}/cancel`, { method: 'POST' });
      setMsg(`Order ${res.order_number} cancelled.`);
      await onReload();
    } catch (e) {
      setErr(e.message);
    }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
      {/* Left: Smart Checkout / Billing Panel matching cart_smart_checkout_khata */}
      <section className="lg:col-span-5 rounded-2xl bg-surface-container-lowest p-5 shadow-sm border border-surface-container-high space-y-4 h-fit">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-on-surface">New Store Order / Bill</h2>
          <span className="px-2.5 py-0.5 rounded-full bg-primary-fixed/40 text-on-primary-fixed-variant text-xs font-bold">
            {cart.length} Items
          </span>
        </div>

        {err && <div className="p-2.5 rounded-xl bg-error-container text-on-error-container text-xs font-bold">{err}</div>}
        {msg && <div className="p-2.5 rounded-xl bg-primary-fixed/40 text-on-primary-fixed-variant text-xs font-bold">{msg}</div>}

        <div className="grid grid-cols-2 gap-2.5">
          <div>
            <label className="block text-[11px] font-bold uppercase text-on-surface-variant mb-1">Customer Name</label>
            <input
              value={customerName}
              onChange={(e) => setCustomerName(e.target.value)}
              className="w-full h-10 px-3 rounded-xl bg-surface-container-low border border-surface-container-high text-sm"
            />
          </div>
          <div>
            <label className="block text-[11px] font-bold uppercase text-on-surface-variant mb-1">Phone (Optional)</label>
            <input
              value={customerPhone}
              onChange={(e) => setCustomerPhone(e.target.value)}
              placeholder="+91 98..."
              className="w-full h-10 px-3 rounded-xl bg-surface-container-low border border-surface-container-high text-sm"
            />
          </div>
        </div>

        {/* Product Picker */}
        <div className="p-3 rounded-xl bg-surface-container-low space-y-2.5">
          <label className="block text-[11px] font-bold uppercase text-on-surface-variant">Select Product</label>
          <div className="flex gap-2">
            <select
              value={selectedProdId}
              onChange={(e) => setSelectedProdId(e.target.value)}
              className="flex-1 h-10 px-3 rounded-xl bg-surface-container-lowest border border-surface-container-high text-sm"
            >
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.stock_qty} {p.unit} • ₹{p.selling_price})
                </option>
              ))}
            </select>
            <input
              type="number"
              min="0.5"
              step="0.5"
              value={qtyInput}
              onChange={(e) => setQtyInput(e.target.value)}
              className="w-20 h-10 px-2.5 rounded-xl bg-surface-container-lowest border border-surface-container-high text-sm text-center"
            />
            <button
              type="button"
              onClick={addToCart}
              className="h-10 px-3.5 rounded-xl bg-primary text-on-primary text-xs font-bold"
            >
              Add
            </button>
          </div>
        </div>

        {/* Cart Items */}
        {cart.length > 0 && (
          <div className="space-y-2 max-h-48 overflow-y-auto">
            {cart.map((item) => (
              <div key={item.product_id} className="p-2.5 rounded-xl bg-surface-container-low flex items-center justify-between text-xs gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <img
                    src={`/images/skus/${item.sku}.svg`}
                    onError={(e) => { e.currentTarget.src = '/images/skus/DEFAULT.svg'; }}
                    alt={item.name}
                    className="w-9 h-9 rounded-lg bg-surface-container-lowest border border-surface-container-high object-cover shrink-0"
                  />
                  <div className="min-w-0">
                    <div className="font-bold text-on-surface truncate">{item.name}</div>
                    <div className="text-on-surface-variant">
                      {item.quantity} {item.unit} × {formatINR(item.unit_price)}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2.5 shrink-0">
                  <span className="font-extrabold text-on-surface">{formatINR(item.quantity * item.unit_price)}</span>
                  <button onClick={() => removeFromCart(item.product_id)} className="text-tertiary font-bold">✕</button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Payment Method & Discount */}
        <div className="grid grid-cols-2 gap-2.5">
          <div>
            <label className="block text-[11px] font-bold uppercase text-on-surface-variant mb-1">Payment Method</label>
            <select
              value={paymentMethod}
              onChange={(e) => setPaymentMethod(e.target.value)}
              className="w-full h-10 px-3 rounded-xl bg-surface-container-low border border-surface-container-high text-sm font-bold"
            >
              <option value="UPI">UPI (GPay / PhonePe)</option>
              <option value="CASH">Cash</option>
              <option value="CARD">Card</option>
              <option value="OTHER">Other / Khata</option>
            </select>
          </div>
          <div>
            <label className="block text-[11px] font-bold uppercase text-on-surface-variant mb-1">Discount (₹)</label>
            <input
              type="number"
              min="0"
              value={discount}
              onChange={(e) => setDiscount(e.target.value)}
              className="w-full h-10 px-3 rounded-xl bg-surface-container-low border border-surface-container-high text-sm"
            />
          </div>
        </div>

        {/* Bill Summary */}
        <div className="p-3.5 rounded-xl bg-surface-container-low space-y-1.5 text-xs">
          <div className="flex justify-between text-on-surface-variant">
            <span>Subtotal</span>
            <span className="font-bold text-on-surface">{formatINR(subtotal)}</span>
          </div>
          <div className="flex justify-between text-primary">
            <span>Discount</span>
            <span className="font-bold">− {formatINR(discountNum)}</span>
          </div>
          <div className="flex justify-between text-base font-extrabold text-on-surface pt-1.5 border-t border-surface-container-high">
            <span>Grand Total</span>
            <span>{formatINR(grandTotal)}</span>
          </div>
        </div>

        <div className="flex gap-2.5">
          <button
            type="button"
            disabled={submitting}
            onClick={() => submitOrder('DRAFT')}
            className="h-11 px-4 rounded-xl bg-surface-container-high hover:bg-surface-variant text-on-surface text-xs font-bold"
          >
            Save Draft
          </button>
          <button
            type="button"
            disabled={submitting}
            onClick={() => submitOrder('CONFIRMED')}
            className="flex-1 h-11 px-4 rounded-xl bg-primary hover:bg-primary-container text-on-primary text-sm font-bold shadow-sm"
          >
            {submitting ? 'Processing...' : `Confirm & Deduct Stock (${formatINR(grandTotal)})`}
          </button>
        </div>
      </section>

      {/* Right: Order History */}
      <section className="lg:col-span-7 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-on-surface">Order History ({orders.length})</h2>
        </div>

        {orders.length === 0 ? (
          <div className="rounded-2xl bg-surface-container-lowest p-10 text-center text-sm text-on-surface-variant border border-surface-container-high">
            No orders found.
          </div>
        ) : (
          <div className="space-y-3">
            {orders.map((ord) => (
              <article key={ord.id} className="rounded-2xl bg-surface-container-lowest p-4 shadow-sm border border-surface-container-high space-y-2.5">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-extrabold text-on-surface">{ord.order_number}</span>
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${statusBadgeStyle(ord.status)}`}>
                        {ord.status}
                      </span>
                      <span className="px-2 py-0.5 rounded-full bg-surface-container text-[10px] font-bold text-on-surface-variant">
                        {ord.payment_method}
                      </span>
                      {ord.stock_deducted && (
                        <span className="text-[10px] font-bold text-primary">✓ Stock Deducted</span>
                      )}
                    </div>
                    <div className="text-xs text-on-surface-variant mt-0.5">
                      {ord.customer_name} • {formatIndianDate(ord.created_at)}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-base font-extrabold text-on-surface">{formatINR(ord.total)}</div>
                    {ord.discount > 0 && (
                      <div className="text-[10px] text-primary">Saved {formatINR(ord.discount)}</div>
                    )}
                  </div>
                </div>

                {ord.items?.length > 0 && (
                  <div className="p-2.5 rounded-xl bg-surface-container-low text-xs text-on-surface-variant">
                    {ord.items.map((it) => `${it.quantity}× ${it.product_name} (${formatINR(it.line_total)})`).join(', ')}
                  </div>
                )}

                {!ord.is_sample && ord.status !== 'CANCELLED' && (
                  <div className="flex justify-end gap-2">
                    {ord.status === 'DRAFT' && (
                      <button
                        onClick={() => handleConfirmOrder(ord.id)}
                        className="h-8 px-3 rounded-lg bg-primary text-on-primary text-xs font-bold"
                      >
                        Confirm Order
                      </button>
                    )}
                    <button
                      onClick={() => handleCancelOrder(ord.id)}
                      className="h-8 px-3 rounded-lg bg-error-container text-on-error-container text-xs font-bold"
                    >
                      Cancel Order
                    </button>
                  </div>
                )}
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
