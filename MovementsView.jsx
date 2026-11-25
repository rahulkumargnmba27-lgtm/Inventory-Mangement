import { useState } from 'react';
import { apiRequest } from '../api';
import { formatIndianDate } from '../utils/format';

export default function MovementsView({ movements, products, onReload }) {
  const [filterType, setFilterType] = useState('ALL');
  const [productId, setProductId] = useState(products[0]?.id ? String(products[0].id) : '');
  const [movementType, setMovementType] = useState('PURCHASE');
  const [direction, setDirection] = useState('IN');
  const [quantity, setQuantity] = useState('10');
  const [reason, setReason] = useState('');
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');

  const filtered = movements.filter((m) => filterType === 'ALL' || m.movement_type === filterType);

  async function handleSubmit(e) {
    e.preventDefault();
    setSaving(true);
    setErr('');
    setMsg('');
    try {
      const txn = await apiRequest('/movements', {
        method: 'POST',
        body: JSON.stringify({
          product_id: Number(productId),
          movement_type: movementType,
          quantity: Number(quantity),
          direction: movementType === 'ADJUSTMENT' ? direction : null,
          reason: reason.trim() || `${movementType} entry`,
        }),
      });
      setMsg(`Recorded ${txn.transaction_id}: ${txn.previous_stock} → ${txn.updated_stock}`);
      setReason('');
      await onReload();
    } catch (e) {
      setErr(e.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-5">
      <section className="rounded-2xl bg-surface-container-lowest p-5 shadow-sm border border-surface-container-high">
        <h2 className="text-lg font-bold text-on-surface mb-3">Record Stock Movement</h2>
        {err && <div className="mb-3 p-2.5 rounded-xl bg-error-container text-on-error-container text-xs font-bold">{err}</div>}
        {msg && <div className="mb-3 p-2.5 rounded-xl bg-primary-fixed/40 text-on-primary-fixed-variant text-xs font-bold">{msg}</div>}
        <form onSubmit={handleSubmit} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 items-end">
          <div className="lg:col-span-2">
            <label className="block text-[11px] font-bold uppercase text-on-surface-variant mb-1">Product</label>
            <select
              value={productId}
              onChange={(e) => setProductId(e.target.value)}
              className="w-full h-10 px-3 rounded-xl bg-surface-container-low border border-surface-container-high text-sm"
            >
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.sku} — {p.name} ({p.stock_qty} {p.unit})
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-[11px] font-bold uppercase text-on-surface-variant mb-1">Movement Type</label>
            <select
              value={movementType}
              onChange={(e) => setMovementType(e.target.value)}
              className="w-full h-10 px-3 rounded-xl bg-surface-container-low border border-surface-container-high text-sm"
            >
              <option value="PURCHASE">Purchase (Inward +)</option>
              <option value="RETURN">Customer Return (+)</option>
              <option value="SALE">Manual Sale (−)</option>
              <option value="DAMAGED">Damaged Goods (−)</option>
              <option value="EXPIRED">Expired Goods (−)</option>
              <option value="ADJUSTMENT">Manual Correction</option>
            </select>
          </div>
          {movementType === 'ADJUSTMENT' && (
            <div>
              <label className="block text-[11px] font-bold uppercase text-on-surface-variant mb-1">Direction</label>
              <select
                value={direction}
                onChange={(e) => setDirection(e.target.value)}
                className="w-full h-10 px-3 rounded-xl bg-surface-container-low border border-surface-container-high text-sm"
              >
                <option value="IN">Add (+)</option>
                <option value="OUT">Deduct (−)</option>
              </select>
            </div>
          )}
          <div>
            <label className="block text-[11px] font-bold uppercase text-on-surface-variant mb-1">Quantity</label>
            <input
              type="number"
              step="0.01"
              min="0.01"
              required
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              className="w-full h-10 px-3 rounded-xl bg-surface-container-low border border-surface-container-high text-sm"
            />
          </div>
          <div className="sm:col-span-2 lg:col-span-4">
            <label className="block text-[11px] font-bold uppercase text-on-surface-variant mb-1">Reason / Note *</label>
            <input
              required
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g., Received mandi stock from Mahalaxmi Traders"
              className="w-full h-10 px-3 rounded-xl bg-surface-container-low border border-surface-container-high text-sm"
            />
          </div>
          <button
            type="submit"
            disabled={saving}
            className="h-10 px-4 rounded-xl bg-primary hover:bg-primary-container text-on-primary text-xs font-bold"
          >
            {saving ? 'Recording...' : 'Record Movement'}
          </button>
        </form>
      </section>

      <section className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-bold text-on-surface">Transaction History ({filtered.length})</h2>
          <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar">
            {['ALL', 'PURCHASE', 'SALE', 'RETURN', 'DAMAGED', 'EXPIRED', 'ADJUSTMENT', 'INITIAL'].map((t) => (
              <button
                key={t}
                onClick={() => setFilterType(t)}
                className={`px-3 py-1 rounded-full text-xs font-bold whitespace-nowrap ${
                  filterType === t
                    ? 'bg-primary text-on-primary'
                    : 'bg-surface-container-lowest border border-surface-container-high text-on-surface-variant'
                }`}
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        <div className="overflow-x-auto rounded-2xl bg-surface-container-lowest border border-surface-container-high shadow-sm">
          <table className="w-full text-left text-xs">
            <thead className="bg-surface-container-low text-on-surface-variant uppercase text-[10px] font-bold">
              <tr>
                <th className="p-3">Transaction ID</th>
                <th className="p-3">Date (IST)</th>
                <th className="p-3">SKU</th>
                <th className="p-3">Product</th>
                <th className="p-3">Type</th>
                <th className="p-3">Qty</th>
                <th className="p-3">Prev → New</th>
                <th className="p-3">Reason</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-container">
              {filtered.map((t) => (
                <tr key={t.id} className="hover:bg-surface-container-low/50">
                  <td className="p-3 font-mono font-bold text-on-surface">{t.transaction_id}</td>
                  <td className="p-3 text-on-surface-variant whitespace-nowrap">{formatIndianDate(t.created_at)}</td>
                  <td className="p-3 font-bold">{t.sku}</td>
                  <td className="p-3 font-semibold text-on-surface">{t.product_name}</td>
                  <td className="p-3">
                    <span className="px-2 py-0.5 rounded-full bg-surface-container-high font-bold text-[10px]">
                      {t.movement_type}
                    </span>
                  </td>
                  <td className="p-3 font-bold">{t.quantity}</td>
                  <td className="p-3 font-bold whitespace-nowrap">
                    {t.previous_stock} → <span className="text-primary">{t.updated_stock}</span>
                  </td>
                  <td className="p-3 text-on-surface-variant">{t.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
