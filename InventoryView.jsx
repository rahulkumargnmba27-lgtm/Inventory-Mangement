import { useRef, useState } from 'react';
import { apiRequest, downloadFile } from '../api';
import { formatINR, formatShortDate, statusBadgeStyle } from '../utils/format';

export default function InventoryView({ products, categories, suppliers, user, onReload }) {
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(null);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState('');
  const [error, setError] = useState('');
  const fileInputRef = useRef(null);

  const [form, setForm] = useState({
    sku: '',
    name: '',
    category_name: 'Staples',
    supplier_id: '',
    unit: 'pack',
    purchase_price: '',
    selling_price: '',
    mrp: '',
    stock_qty: '',
    reorder_level: '10',
    barcode: '',
    expiry_date: '',
    image_url: '',
  });

  const filtered = products.filter((p) => {
    const matchesSearch =
      !search ||
      p.name.toLowerCase().includes(search.toLowerCase()) ||
      p.sku.toLowerCase().includes(search.toLowerCase()) ||
      (p.barcode || '').toLowerCase().includes(search.toLowerCase());
    const matchesCat = categoryFilter === 'ALL' || p.category_name === categoryFilter;
    const matchesStatus = statusFilter === 'ALL' || p.status === statusFilter;
    return matchesSearch && matchesCat && matchesStatus;
  });

  function openAdd() {
    setEditing(null);
    setForm({
      sku: `KIR${String(products.length + 1).padStart(3, '0')}`,
      name: '',
      category_name: categories[0]?.name || 'Staples',
      supplier_id: suppliers[0]?.id ? String(suppliers[0].id) : '',
      unit: 'pack',
      purchase_price: '',
      selling_price: '',
      mrp: '',
      stock_qty: '0',
      reorder_level: '10',
      barcode: '',
      expiry_date: '',
      image_url: '',
    });
    setError('');
    setModalOpen(true);
  }

  function openEdit(p) {
    setEditing(p);
    setForm({
      sku: p.sku,
      name: p.name,
      category_name: p.category_name,
      supplier_id: p.supplier_id ? String(p.supplier_id) : '',
      unit: p.unit,
      purchase_price: String(p.purchase_price),
      selling_price: String(p.selling_price),
      mrp: p.mrp ? String(p.mrp) : '',
      stock_qty: String(p.stock_qty),
      reorder_level: String(p.reorder_level),
      barcode: p.barcode || '',
      expiry_date: p.expiry_date || '',
      image_url: p.image_url || '',
    });
    setError('');
    setModalOpen(true);
  }

  async function handleSave(e) {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      const payload = {
        sku: form.sku.trim(),
        name: form.name.trim(),
        category_name: form.category_name,
        supplier_id: form.supplier_id ? Number(form.supplier_id) : null,
        unit: form.unit.trim(),
        purchase_price: Number(form.purchase_price || 0),
        selling_price: Number(form.selling_price || 0),
        mrp: form.mrp ? Number(form.mrp) : null,
        stock_qty: Number(form.stock_qty || 0),
        reorder_level: Number(form.reorder_level || 0),
        barcode: form.barcode.trim() || null,
        expiry_date: form.expiry_date || null,
        image_url: form.image_url.trim() || null,
      };
      if (editing) {
        await apiRequest(`/products/${editing.id}`, {
          method: 'PUT',
          body: JSON.stringify(payload),
        });
        setToast(`Updated ${payload.name}`);
      } else {
        await apiRequest('/products', {
          method: 'POST',
          body: JSON.stringify(payload),
        });
        setToast(`Added ${payload.name} (${payload.sku})`);
      }
      setModalOpen(false);
      await onReload();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleQuickAdjust(p, delta) {
    try {
      await apiRequest('/movements', {
        method: 'POST',
        body: JSON.stringify({
          product_id: p.id,
          movement_type: 'ADJUSTMENT',
          quantity: Math.abs(delta),
          direction: delta > 0 ? 'IN' : 'OUT',
          reason: `Quick ${delta > 0 ? '+' : ''}${delta} adjustment from Inventory`,
        }),
      });
      setToast(`${p.name} stock updated`);
      await onReload();
    } catch (err) {
      setToast(`Error: ${err.message}`);
    }
  }

  async function handleDelete(p) {
    try {
      await apiRequest(`/products/${p.id}`, { method: 'DELETE' });
      setConfirmDelete(null);
      setToast(`Deleted ${p.name}`);
      await onReload();
    } catch (err) {
      setToast(`Error: ${err.message}`);
    }
  }

  async function handleExcelUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append('file', file);
    try {
      const res = await apiRequest('/import/excel', { method: 'POST', body: fd });
      setToast(`Imported ${res.products_imported} products, ${res.orders_imported} orders (skipped ${res.products_skipped_duplicate} duplicates)`);
      await onReload();
    } catch (err) {
      setToast(`Import failed: ${err.message}`);
    } finally {
      e.target.value = '';
    }
  }

  return (
    <div className="space-y-4">
      {toast && (
        <div className="p-3 rounded-xl bg-primary-fixed/40 text-on-primary-fixed-variant text-xs font-bold flex items-center justify-between">
          <span>{toast}</span>
          <button onClick={() => setToast('')} className="underline ml-3">Dismiss</button>
        </div>
      )}

      {/* Header Actions */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-on-surface">Inventory Catalog</h1>
          <p className="text-xs text-on-surface-variant">{products.length} total SKUs • Auto-classified by Reorder Level</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input ref={fileInputRef} type="file" accept=".xlsx,.xlsm" onChange={handleExcelUpload} className="hidden" />
          <button
            onClick={() => fileInputRef.current?.click()}
            className="h-10 px-3.5 rounded-xl bg-surface-container-lowest border border-surface-container-high text-xs font-bold text-on-surface hover:bg-surface-container flex items-center gap-1.5"
          >
            <span className="material-symbols-outlined text-[18px] text-primary">upload_file</span>
            Import Excel
          </button>
          <button
            onClick={() => downloadFile('/export/excel', 'kirana_inventory_report.xlsx')}
            className="h-10 px-3.5 rounded-xl bg-surface-container-lowest border border-surface-container-high text-xs font-bold text-on-surface hover:bg-surface-container flex items-center gap-1.5"
          >
            <span className="material-symbols-outlined text-[18px] text-secondary">download</span>
            Export Excel
          </button>
          <button
            onClick={openAdd}
            className="h-10 px-4 rounded-xl bg-primary hover:bg-primary-container text-on-primary text-xs font-bold flex items-center gap-1.5 shadow-sm"
          >
            <span className="material-symbols-outlined text-[18px]">add</span>
            Add Product
          </button>
        </div>
      </div>

      {/* Search & Filter Bar matching designs */}
      <div className="space-y-2.5">
        <div className="relative">
          <span className="material-symbols-outlined absolute left-3.5 top-1/2 -translate-y-1/2 text-outline text-[20px]">search</span>
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by product name, SKU (e.g. KIR001), or barcode..."
            className="w-full h-11 pl-10 pr-4 rounded-xl bg-surface-container-lowest border border-surface-container-high text-sm text-on-surface placeholder:text-outline focus:outline-none focus:border-primary"
          />
        </div>

        <div className="flex items-center gap-2 overflow-x-auto no-scrollbar pb-1">
          {[
            { id: 'ALL', label: `All (${products.length})` },
            { id: 'HEALTHY', label: `Healthy (${products.filter((p) => p.status === 'HEALTHY').length})` },
            { id: 'LOW_STOCK', label: `Low Stock (${products.filter((p) => p.status === 'LOW_STOCK').length})` },
            { id: 'STOCKOUT', label: `Stockout (${products.filter((p) => p.status === 'STOCKOUT').length})` },
          ].map((pill) => (
            <button
              key={pill.id}
              onClick={() => setStatusFilter(pill.id)}
              className={`px-3 py-1.5 rounded-full text-xs font-bold whitespace-nowrap transition-colors ${
                statusFilter === pill.id
                  ? 'bg-primary text-on-primary shadow-sm'
                  : 'bg-surface-container-lowest text-on-surface-variant border border-surface-container-high hover:bg-surface-container'
              }`}
            >
              {pill.label}
            </button>
          ))}
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="h-8 px-3 rounded-full bg-surface-container-lowest border border-surface-container-high text-xs font-bold text-on-surface focus:outline-none"
          >
            <option value="ALL">All Categories</option>
            {categories.map((c) => (
              <option key={c.id} value={c.name}>{c.name}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Product Cards Grid */}
      {filtered.length === 0 ? (
        <div className="rounded-2xl bg-surface-container-lowest p-10 text-center border border-surface-container-high">
          <span className="material-symbols-outlined text-[40px] text-outline">inventory_2</span>
          <p className="mt-2 text-sm font-bold text-on-surface">No products match your filters</p>
          <p className="text-xs text-on-surface-variant">Try clearing your search or adding a new SKU.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3.5">
          {filtered.map((p) => (
            <article
              key={p.id}
              className="rounded-2xl bg-surface-container-lowest p-4 shadow-[0_2px_8px_-1px_rgba(28,25,23,0.06)] border border-surface-container-high flex flex-col justify-between gap-3"
            >
              {/* Large visible 1:1 / banner product image matching Kirana Quick card design */}
              <div className="relative w-full h-40 rounded-xl bg-surface-container-low border border-surface-container overflow-hidden flex items-center justify-center p-2">
                <img
                  src={p.image_url || `/images/skus/${p.sku}.svg`}
                  onError={(e) => { e.currentTarget.src = '/images/skus/DEFAULT.svg'; }}
                  alt={p.name}
                  className="w-full h-full object-contain"
                />
                <span className="absolute top-2 left-2 text-[10px] font-bold px-2 py-0.5 rounded-full bg-surface-container-lowest/95 text-on-surface shadow-sm border border-surface-container-high">
                  {p.sku}
                </span>
                <span className={`absolute top-2 right-2 px-2.5 py-0.5 rounded-full text-[10px] font-bold shadow-sm ${statusBadgeStyle(p.status)}`}>
                  {p.status.replace('_', ' ')}
                </span>
              </div>

              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <h3 className="text-sm font-bold text-on-surface truncate">{p.name}</h3>
                  <div className="flex items-center gap-1.5 mt-0.5 text-[11px] text-on-surface-variant">
                    <span>{p.category_name}</span>
                    <span>•</span>
                    <span>{p.unit}</span>
                  </div>
                </div>
                <div className="text-right shrink-0">
                  <div className="text-base font-extrabold text-on-surface">{formatINR(p.selling_price)}</div>
                  <div className="text-[10px] text-on-surface-variant">Cost {formatINR(p.purchase_price)}</div>
                </div>
              </div>

              <div className="p-2.5 rounded-xl bg-surface-container-low flex items-center justify-between text-xs">
                <div>
                  <span className="text-on-surface-variant">Available: </span>
                  <span className={`font-extrabold ${p.stock_qty <= 0 ? 'text-tertiary' : p.stock_qty <= p.reorder_level ? 'text-secondary' : 'text-primary'}`}>
                    {p.stock_qty} {p.unit}
                  </span>
                </div>
                <div className="text-on-surface-variant">
                  Reorder: <span className="font-bold text-on-surface">{p.reorder_level}</span>
                </div>
                <div className="text-on-surface-variant">
                  Val: <span className="font-bold text-on-surface">{formatINR(p.stock_value)}</span>
                </div>
              </div>

              {(p.supplier_name || p.expiry_date) && (
                <div className="text-[11px] text-on-surface-variant flex items-center justify-between gap-2">
                  <span className="truncate">{p.supplier_name || 'No supplier'}</span>
                  {p.expiry_date && <span>Exp: {formatShortDate(p.expiry_date)}</span>}
                </div>
              )}

              <div className="flex items-center justify-between gap-2 pt-1 border-t border-surface-container">
                <div className="flex items-center rounded-lg border border-primary/40 overflow-hidden">
                  <button
                    onClick={() => handleQuickAdjust(p, -1)}
                    disabled={p.stock_qty <= 0}
                    className="w-8 h-8 flex items-center justify-center text-primary hover:bg-primary-fixed/30 disabled:opacity-40 font-bold"
                    title="Deduct 1"
                  >
                    −
                  </button>
                  <span className="px-2 text-xs font-bold text-on-surface">{p.stock_qty}</span>
                  <button
                    onClick={() => handleQuickAdjust(p, 1)}
                    className="w-8 h-8 flex items-center justify-center text-primary hover:bg-primary-fixed/30 font-bold"
                    title="Add 1"
                  >
                    +
                  </button>
                </div>

                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => openEdit(p)}
                    className="h-8 px-3 rounded-lg bg-surface-container-high hover:bg-surface-variant text-xs font-bold text-on-surface"
                  >
                    Edit
                  </button>
                  {['owner', 'manager'].includes(user?.role) && (
                    <button
                      onClick={() => setConfirmDelete(p)}
                      className="h-8 px-2.5 rounded-lg bg-error-container text-on-error-container text-xs font-bold hover:opacity-90"
                    >
                      Delete
                    </button>
                  )}
                </div>
              </div>
            </article>
          ))}
        </div>
      )}

      {/* Add/Edit Product Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 bg-on-surface/45 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-lg rounded-2xl bg-surface-container-lowest p-6 shadow-xl max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-on-surface">{editing ? `Edit ${editing.sku}` : 'Add New Product'}</h2>
              <button onClick={() => setModalOpen(false)} className="text-outline hover:text-on-surface">
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>
            {error && <div className="mb-3 p-2.5 rounded-xl bg-error-container text-on-error-container text-xs font-bold">{error}</div>}
            <form onSubmit={handleSave} className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] font-bold uppercase text-on-surface-variant mb-1">SKU *</label>
                <input
                  required
                  disabled={!!editing}
                  value={form.sku}
                  onChange={(e) => setForm({ ...form, sku: e.target.value })}
                  className="w-full h-10 px-3 rounded-xl bg-surface-container-low border border-surface-container-high text-sm disabled:opacity-60"
                />
              </div>
              <div>
                <label className="block text-[11px] font-bold uppercase text-on-surface-variant mb-1">Category *</label>
                <select
                  value={form.category_name}
                  onChange={(e) => setForm({ ...form, category_name: e.target.value })}
                  className="w-full h-10 px-3 rounded-xl bg-surface-container-low border border-surface-container-high text-sm"
                >
                  {categories.map((c) => <option key={c.id} value={c.name}>{c.name}</option>)}
                </select>
              </div>
              <div className="sm:col-span-2">
                <label className="block text-[11px] font-bold uppercase text-on-surface-variant mb-1">Product Name *</label>
                <input
                  required
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="w-full h-10 px-3 rounded-xl bg-surface-container-low border border-surface-container-high text-sm"
                />
              </div>
              <div>
                <label className="block text-[11px] font-bold uppercase text-on-surface-variant mb-1">Unit *</label>
                <input
                  required
                  value={form.unit}
                  onChange={(e) => setForm({ ...form, unit: e.target.value })}
                  placeholder="kg, pack, bottle, jar"
                  className="w-full h-10 px-3 rounded-xl bg-surface-container-low border border-surface-container-high text-sm"
                />
              </div>
              <div>
                <label className="block text-[11px] font-bold uppercase text-on-surface-variant mb-1">Supplier</label>
                <select
                  value={form.supplier_id}
                  onChange={(e) => setForm({ ...form, supplier_id: e.target.value })}
                  className="w-full h-10 px-3 rounded-xl bg-surface-container-low border border-surface-container-high text-sm"
                >
                  <option value="">None</option>
                  {suppliers.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-[11px] font-bold uppercase text-on-surface-variant mb-1">Purchase Price (₹) *</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  required
                  value={form.purchase_price}
                  onChange={(e) => setForm({ ...form, purchase_price: e.target.value })}
                  className="w-full h-10 px-3 rounded-xl bg-surface-container-low border border-surface-container-high text-sm"
                />
              </div>
              <div>
                <label className="block text-[11px] font-bold uppercase text-on-surface-variant mb-1">Selling Price (₹) *</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  required
                  value={form.selling_price}
                  onChange={(e) => setForm({ ...form, selling_price: e.target.value })}
                  className="w-full h-10 px-3 rounded-xl bg-surface-container-low border border-surface-container-high text-sm"
                />
              </div>
              <div>
                <label className="block text-[11px] font-bold uppercase text-on-surface-variant mb-1">Available Stock *</label>
                <input
                  type="number"
                  step="0.01"
                  required
                  value={form.stock_qty}
                  onChange={(e) => setForm({ ...form, stock_qty: e.target.value })}
                  className="w-full h-10 px-3 rounded-xl bg-surface-container-low border border-surface-container-high text-sm"
                />
              </div>
              <div>
                <label className="block text-[11px] font-bold uppercase text-on-surface-variant mb-1">Reorder Level *</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  required
                  value={form.reorder_level}
                  onChange={(e) => setForm({ ...form, reorder_level: e.target.value })}
                  className="w-full h-10 px-3 rounded-xl bg-surface-container-low border border-surface-container-high text-sm"
                />
              </div>
              <div>
                <label className="block text-[11px] font-bold uppercase text-on-surface-variant mb-1">Barcode (Optional)</label>
                <input
                  value={form.barcode}
                  onChange={(e) => setForm({ ...form, barcode: e.target.value })}
                  className="w-full h-10 px-3 rounded-xl bg-surface-container-low border border-surface-container-high text-sm"
                />
              </div>
              <div>
                <label className="block text-[11px] font-bold uppercase text-on-surface-variant mb-1">Expiry Date (Optional)</label>
                <input
                  type="date"
                  value={form.expiry_date}
                  onChange={(e) => setForm({ ...form, expiry_date: e.target.value })}
                  className="w-full h-10 px-3 rounded-xl bg-surface-container-low border border-surface-container-high text-sm"
                />
              </div>
              <div className="sm:col-span-2">
                <label className="block text-[11px] font-bold uppercase text-on-surface-variant mb-1">Product Image URL (Optional)</label>
                <input
                  value={form.image_url}
                  onChange={(e) => setForm({ ...form, image_url: e.target.value })}
                  placeholder="/images/skus/KIR001.svg or https://..."
                  className="w-full h-10 px-3 rounded-xl bg-surface-container-low border border-surface-container-high text-sm"
                />
              </div>
              <div className="sm:col-span-2 flex justify-end gap-2 pt-3">
                <button type="button" onClick={() => setModalOpen(false)} className="h-10 px-4 rounded-xl bg-surface-container-high text-xs font-bold">
                  Cancel
                </button>
                <button type="submit" disabled={saving} className="h-10 px-5 rounded-xl bg-primary text-on-primary text-xs font-bold">
                  {saving ? 'Saving...' : editing ? 'Save Changes' : 'Create Product'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Confirm Delete Dialog */}
      {confirmDelete && (
        <div className="fixed inset-0 z-50 bg-on-surface/45 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-sm rounded-2xl bg-surface-container-lowest p-5 shadow-xl space-y-3">
            <h3 className="text-base font-bold text-on-surface">Delete Product?</h3>
            <p className="text-xs text-on-surface-variant">
              Are you sure you want to remove <strong>{confirmDelete.name}</strong> ({confirmDelete.sku}) from active inventory?
            </p>
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setConfirmDelete(null)} className="h-9 px-4 rounded-xl bg-surface-container-high text-xs font-bold">
                Cancel
              </button>
              <button onClick={() => handleDelete(confirmDelete)} className="h-9 px-4 rounded-xl bg-tertiary text-on-tertiary text-xs font-bold">
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
