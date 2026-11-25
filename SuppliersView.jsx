import { useState } from 'react';
import { apiRequest } from '../api';

export default function SuppliersView({ suppliers, user, onReload }) {
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({
    name: '',
    contact_person: '',
    phone: '',
    email: '',
    address: '',
    gstin: '',
    notes: '',
  });
  const [err, setErr] = useState('');

  function openAdd() {
    setEditing(null);
    setForm({ name: '', contact_person: '', phone: '', email: '', address: '', gstin: '', notes: '' });
    setErr('');
    setModalOpen(true);
  }

  function openEdit(s) {
    setEditing(s);
    setForm({
      name: s.name,
      contact_person: s.contact_person || '',
      phone: s.phone,
      email: s.email || '',
      address: s.address || '',
      gstin: s.gstin || '',
      notes: s.notes || '',
    });
    setErr('');
    setModalOpen(true);
  }

  async function handleSave(e) {
    e.preventDefault();
    setErr('');
    try {
      if (editing) {
        await apiRequest(`/suppliers/${editing.id}`, { method: 'PUT', body: JSON.stringify(form) });
      } else {
        await apiRequest('/suppliers', { method: 'POST', body: JSON.stringify(form) });
      }
      setModalOpen(false);
      await onReload();
    } catch (e) {
      setErr(e.message);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-on-surface">Suppliers &amp; Mandi Partners</h1>
          <p className="text-xs text-on-surface-variant">Manage wholesale suppliers, GSTIN, and supplied SKUs</p>
        </div>
        {['owner', 'manager'].includes(user?.role) && (
          <button
            onClick={openAdd}
            className="h-10 px-4 rounded-xl bg-primary text-on-primary text-xs font-bold flex items-center gap-1.5"
          >
            <span className="material-symbols-outlined text-[18px]">add</span>
            Add Supplier
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {suppliers.map((s) => (
          <article key={s.id} className="rounded-2xl bg-surface-container-lowest p-4 shadow-sm border border-surface-container-high space-y-3">
            <div className="flex items-start justify-between gap-2">
              <div>
                <h3 className="text-base font-bold text-on-surface">{s.name}</h3>
                <p className="text-xs text-on-surface-variant">{s.contact_person || 'Primary Contact'} • {s.phone}</p>
              </div>
              <span className="px-2.5 py-0.5 rounded-full bg-primary-fixed/40 text-on-primary-fixed-variant text-[10px] font-bold">
                {s.product_count} SKUs
              </span>
            </div>
            <div className="p-2.5 rounded-xl bg-surface-container-low text-xs space-y-1 text-on-surface-variant">
              {s.email && <div>Email: <span className="text-on-surface font-medium">{s.email}</span></div>}
              {s.gstin && <div>GSTIN: <span className="text-on-surface font-mono font-bold">{s.gstin}</span></div>}
              {s.address && <div>Address: <span className="text-on-surface">{s.address}</span></div>}
              <div>Purchased Units: <span className="text-primary font-bold">{s.total_purchase_qty}</span></div>
            </div>
            {s.notes && <p className="text-xs text-on-surface-variant italic">{s.notes}</p>}
            {['owner', 'manager'].includes(user?.role) && (
              <div className="flex justify-end">
                <button
                  onClick={() => openEdit(s)}
                  className="h-8 px-3 rounded-lg bg-surface-container-high text-xs font-bold text-on-surface"
                >
                  Edit Details
                </button>
              </div>
            )}
          </article>
        ))}
      </div>

      {modalOpen && (
        <div className="fixed inset-0 z-50 bg-on-surface/45 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md rounded-2xl bg-surface-container-lowest p-6 shadow-xl">
            <h2 className="text-lg font-bold mb-3">{editing ? 'Edit Supplier' : 'Add Supplier'}</h2>
            {err && <div className="mb-3 p-2 rounded-xl bg-error-container text-on-error-container text-xs font-bold">{err}</div>}
            <form onSubmit={handleSave} className="space-y-3">
              <input required placeholder="Supplier Name *" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="w-full h-10 px-3 rounded-xl bg-surface-container-low border border-surface-container-high text-sm" />
              <input placeholder="Contact Person" value={form.contact_person} onChange={(e) => setForm({ ...form, contact_person: e.target.value })} className="w-full h-10 px-3 rounded-xl bg-surface-container-low border border-surface-container-high text-sm" />
              <input required placeholder="Phone *" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} className="w-full h-10 px-3 rounded-xl bg-surface-container-low border border-surface-container-high text-sm" />
              <input placeholder="Email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="w-full h-10 px-3 rounded-xl bg-surface-container-low border border-surface-container-high text-sm" />
              <input placeholder="GSTIN" value={form.gstin} onChange={(e) => setForm({ ...form, gstin: e.target.value })} className="w-full h-10 px-3 rounded-xl bg-surface-container-low border border-surface-container-high text-sm" />
              <input placeholder="Address" value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} className="w-full h-10 px-3 rounded-xl bg-surface-container-low border border-surface-container-high text-sm" />
              <textarea placeholder="Notes" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="w-full p-3 rounded-xl bg-surface-container-low border border-surface-container-high text-sm" rows={2} />
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setModalOpen(false)} className="h-9 px-4 rounded-xl bg-surface-container-high text-xs font-bold">Cancel</button>
                <button type="submit" className="h-9 px-4 rounded-xl bg-primary text-on-primary text-xs font-bold">Save Supplier</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
