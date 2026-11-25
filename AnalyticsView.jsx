import { downloadFile } from '../api';
import { formatINR } from '../utils/format';

export default function AnalyticsView({ analytics, dashboard }) {
  const val = analytics?.valuation || {};
  const pvs = analytics?.purchase_vs_sales || {};
  const fast = analytics?.fast_moving || [];
  const slow = analytics?.slow_moving || [];
  const categories = dashboard?.category_analytics || [];

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-on-surface">Analytics &amp; Export Reports</h1>
          <p className="text-xs text-on-surface-variant">Real-time valuation, movement velocity, and Excel/CSV exports</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => downloadFile('/export/csv', 'kirana_inventory.csv')}
            className="h-10 px-4 rounded-xl bg-surface-container-lowest border border-surface-container-high text-xs font-bold flex items-center gap-1.5 hover:bg-surface-container"
          >
            <span className="material-symbols-outlined text-[18px] text-primary">csv</span>
            Export CSV
          </button>
          <button
            onClick={() => downloadFile('/export/excel', 'kirana_inventory_report.xlsx')}
            className="h-10 px-4 rounded-xl bg-primary text-on-primary text-xs font-bold flex items-center gap-1.5"
          >
            <span className="material-symbols-outlined text-[18px]">table_view</span>
            Export Excel (.xlsx)
          </button>
        </div>
      </div>

      {/* Valuation & Sales Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
        <div className="rounded-2xl bg-surface-container-lowest p-4 border border-surface-container-high">
          <div className="text-xs font-bold text-on-surface-variant uppercase">Retail Stock Value</div>
          <div className="text-2xl font-extrabold text-primary mt-1">{formatINR(val.total_selling_value)}</div>
        </div>
        <div className="rounded-2xl bg-surface-container-lowest p-4 border border-surface-container-high">
          <div className="text-xs font-bold text-on-surface-variant uppercase">Cost Stock Value</div>
          <div className="text-2xl font-extrabold text-on-surface mt-1">{formatINR(val.total_cost_value)}</div>
        </div>
        <div className="rounded-2xl bg-surface-container-lowest p-4 border border-surface-container-high">
          <div className="text-xs font-bold text-on-surface-variant uppercase">Potential Margin</div>
          <div className="text-2xl font-extrabold text-secondary mt-1">{formatINR(val.potential_margin)}</div>
        </div>
        <div className="rounded-2xl bg-surface-container-lowest p-4 border border-surface-container-high">
          <div className="text-xs font-bold text-on-surface-variant uppercase">Verified Sales Revenue</div>
          <div className="text-2xl font-extrabold text-primary mt-1">{formatINR(pvs.confirmed_revenue)}</div>
          <div className="text-[11px] text-on-surface-variant">{pvs.confirmed_orders_count || 0} confirmed orders</div>
        </div>
      </div>

      {/* Category Table */}
      <section className="rounded-2xl bg-surface-container-lowest p-4 border border-surface-container-high">
        <h2 className="text-base font-bold text-on-surface mb-3">Category-Wise Stock &amp; Valuation</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-surface-container-low text-on-surface-variant uppercase text-[10px] font-bold">
              <tr>
                <th className="p-2.5">Category</th>
                <th className="p-2.5">SKUs</th>
                <th className="p-2.5">Total Units</th>
                <th className="p-2.5">Low / Stockout</th>
                <th className="p-2.5 text-right">Stock Value</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-container">
              {categories.map((c) => (
                <tr key={c.category}>
                  <td className="p-2.5 font-bold text-on-surface">{c.category}</td>
                  <td className="p-2.5">{c.product_count}</td>
                  <td className="p-2.5">{c.total_units}</td>
                  <td className="p-2.5 font-bold text-tertiary">{c.low_or_out}</td>
                  <td className="p-2.5 text-right font-bold text-primary">{formatINR(c.total_value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Fast Moving vs Slow Moving */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <section className="rounded-2xl bg-surface-container-lowest p-4 border border-surface-container-high">
          <h2 className="text-base font-bold text-on-surface mb-3">Fast-Moving Products</h2>
          {fast.length === 0 ? (
            <p className="text-xs text-on-surface-variant py-6 text-center">
              Confirm orders to track fast-moving product velocity.
            </p>
          ) : (
            <div className="space-y-2">
              {fast.map((item) => (
                <div key={item.sku} className="p-2.5 rounded-xl bg-surface-container-low flex justify-between text-xs">
                  <span className="font-bold">{item.name} ({item.sku})</span>
                  <span className="font-extrabold text-primary">{item.units_sold} sold</span>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="rounded-2xl bg-surface-container-lowest p-4 border border-surface-container-high">
          <h2 className="text-base font-bold text-on-surface mb-3">Slow-Moving / High-Stock Items</h2>
          <div className="space-y-2">
            {slow.map((item) => (
              <div key={item.sku} className="p-2.5 rounded-xl bg-surface-container-low flex justify-between text-xs">
                <span className="font-bold">{item.name} ({item.sku})</span>
                <span className="text-on-surface-variant">
                  {item.units_sold} sold • {formatINR(item.stock_value)} tied up
                </span>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
