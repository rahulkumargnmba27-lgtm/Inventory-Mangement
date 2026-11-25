import { formatINR, formatIndianDate, statusBadgeStyle } from '../utils/format';

export default function DashboardView({ data, loading, onNavigate, onRefresh }) {
  if (loading && !data) {
    return (
      <div className="space-y-4 animate-pulse">
        <div className="h-44 rounded-2xl bg-surface-container-high" />
        <div className="h-16 rounded-xl bg-surface-container-high" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="h-64 rounded-xl bg-surface-container-high" />
          <div className="h-64 rounded-xl bg-surface-container-high" />
        </div>
      </div>
    );
  }

  const kpis = data?.kpis || {};
  const lowItems = data?.low_stock_items || [];
  const stockoutItems = data?.stockout_items || [];
  const categories = data?.category_analytics || [];
  const recentOrders = data?.recent_orders || [];
  const recentMovements = data?.recent_movements || [];

  return (
    <div className="space-y-5">
      {/* Hero Vyapar Inventory Summary Card matching dukandar_khata_store_management */}
      <section className="rounded-2xl bg-surface-container-lowest p-5 shadow-[0_2px_8px_-1px_rgba(28,25,23,0.06)] border border-surface-container-high relative overflow-hidden">
        <div className="absolute -right-8 -bottom-8 w-40 h-40 rounded-full bg-primary/5 pointer-events-none" />
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-secondary animate-ping" />
            <span className="text-[11px] font-bold text-secondary uppercase tracking-wider">
              Vyapar Live Inventory Ledger
            </span>
          </div>
          <button
            onClick={onRefresh}
            className="inline-flex items-center gap-1 text-[11px] font-bold text-on-surface-variant bg-surface-container px-2.5 py-1 rounded-full hover:bg-surface-container-high"
          >
            <span className="material-symbols-outlined text-[14px]">refresh</span>
            Refresh
          </button>
        </div>

        <div className="mt-2 flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
          <div>
            <span className="text-xs font-medium text-on-surface-variant">Total Inventory Valuation</span>
            <div className="flex items-baseline gap-2.5 mt-0.5">
              <span className="text-3xl sm:text-4xl font-extrabold text-primary tracking-tight">
                {formatINR(kpis.total_inventory_value)}
              </span>
              <span className="text-xs font-semibold text-on-surface-variant">
                across {kpis.total_products || 0} SKUs
              </span>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <span className="px-2.5 py-1 rounded-full bg-primary-fixed/40 text-on-primary-fixed-variant text-xs font-bold">
              {kpis.healthy_count || 0} Healthy
            </span>
            <span className="px-2.5 py-1 rounded-full bg-secondary-fixed text-on-secondary-fixed-variant text-xs font-bold">
              {kpis.low_stock_count || 0} Low Stock
            </span>
            <span className="px-2.5 py-1 rounded-full bg-tertiary-fixed text-tertiary text-xs font-bold">
              {kpis.stockout_count || 0} Stockout
            </span>
          </div>
        </div>

        {/* Sub-Metrics Grid */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mt-4 bg-surface-container-low p-3.5 rounded-xl">
          <div>
            <div className="flex items-center gap-1 text-primary text-[11px] font-bold uppercase">
              <span className="material-symbols-outlined text-[15px]">inventory_2</span>
              Available Units
            </div>
            <div className="text-lg font-bold text-on-surface mt-0.5">
              {Number(kpis.total_available_stock || 0).toLocaleString('en-IN')}
            </div>
          </div>
          <div>
            <div className="flex items-center gap-1 text-secondary text-[11px] font-bold uppercase">
              <span className="material-symbols-outlined text-[15px]">payments</span>
              Verified Sales
            </div>
            <div className="text-lg font-bold text-on-surface mt-0.5">{formatINR(kpis.total_sales)}</div>
          </div>
          <div>
            <div className="flex items-center gap-1 text-primary text-[11px] font-bold uppercase">
              <span className="material-symbols-outlined text-[15px]">receipt_long</span>
              Confirmed Orders
            </div>
            <div className="text-lg font-bold text-on-surface mt-0.5">{kpis.confirmed_orders_count || 0}</div>
          </div>
          <div>
            <div className="flex items-center gap-1 text-tertiary text-[11px] font-bold uppercase">
              <span className="material-symbols-outlined text-[15px]">notifications_active</span>
              Active Alerts
            </div>
            <div className="text-lg font-bold text-tertiary mt-0.5">{kpis.active_alerts_count || 0}</div>
          </div>
        </div>

        {/* Quick Action Buttons */}
        <div className="flex flex-wrap items-center gap-2.5 mt-4">
          <button
            onClick={() => onNavigate('orders')}
            className="flex-1 min-w-[150px] h-11 px-4 rounded-xl bg-primary hover:bg-primary-container text-on-primary font-bold text-sm flex items-center justify-center gap-2 shadow-[0_2px_6px_rgba(0,105,72,0.25)] active:scale-[0.98] transition-all"
          >
            <span className="material-symbols-outlined text-[20px]">add_shopping_cart</span>
            New Order / Bill
          </button>
          <button
            onClick={() => onNavigate('inventory')}
            className="h-11 px-4 rounded-xl bg-surface-container-high hover:bg-surface-variant text-on-surface font-bold text-sm flex items-center justify-center gap-1.5 transition-all"
          >
            <span className="material-symbols-outlined text-primary text-[20px]">add_box</span>
            Manage Stock
          </button>
          <button
            onClick={() => onNavigate('ai')}
            className="h-11 px-4 rounded-xl bg-secondary-fixed hover:opacity-90 text-on-secondary-fixed-variant font-bold text-sm flex items-center justify-center gap-1.5 transition-all"
          >
            <span className="material-symbols-outlined text-[20px]">smart_toy</span>
            Ask AI Assistant
          </button>
        </div>
      </section>

      {/* Alert Banner matching Soundbox / Notification Strip */}
      {(stockoutItems.length > 0 || lowItems.length > 0) && (
        <section className="rounded-xl bg-primary-fixed/25 border border-primary-fixed p-3.5 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-10 h-10 rounded-xl bg-tertiary flex items-center justify-center shrink-0 text-on-tertiary">
              <span className="material-symbols-outlined text-[20px]">warning</span>
            </div>
            <div className="min-w-0">
              <div className="text-[11px] font-bold uppercase text-tertiary tracking-wide">
                Attention Needed • WhatsApp Monitor Active
              </div>
              <p className="text-sm text-on-surface truncate">
                <span className="font-bold text-tertiary">{stockoutItems.length} stockout</span> and{' '}
                <span className="font-bold text-secondary">{lowItems.length} low-stock</span> items need reorder:{' '}
                {[...stockoutItems, ...lowItems].slice(0, 3).map((i) => i.name).join(', ')}
              </p>
            </div>
          </div>
          <button
            onClick={() => onNavigate('alerts')}
            className="shrink-0 px-3 py-1.5 rounded-full bg-surface-container-lowest text-xs font-bold text-primary shadow-sm hover:bg-surface-container"
          >
            View Alerts →
          </button>
        </section>
      )}

      {/* Category Analytics & Critical Stock Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Category Breakdown */}
        <section className="rounded-2xl bg-surface-container-lowest p-4 shadow-sm border border-surface-container-high">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-base font-bold text-on-surface">Category-Wise Valuation</h2>
            <button
              onClick={() => onNavigate('analytics')}
              className="text-xs font-bold text-primary hover:underline"
            >
              Full Report →
            </button>
          </div>
          <div className="space-y-2.5">
            {categories.map((cat) => {
              const pct = kpis.total_inventory_value
                ? Math.min(100, Math.round((cat.total_value / kpis.total_inventory_value) * 100))
                : 0;
              return (
                <div key={cat.category} className="p-2.5 rounded-xl bg-surface-container-low">
                  <div className="flex items-center justify-between text-xs font-bold mb-1">
                    <span className="text-on-surface">
                      {cat.category}{' '}
                      <span className="font-normal text-on-surface-variant">({cat.product_count} SKUs)</span>
                    </span>
                    <span className="text-primary">{formatINR(cat.total_value)}</span>
                  </div>
                  <div className="w-full h-2 rounded-full bg-surface-container-high overflow-hidden">
                    <div className="h-full bg-primary rounded-full" style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* Critical Low Stock & Stockout Items */}
        <section className="rounded-2xl bg-surface-container-lowest p-4 shadow-sm border border-surface-container-high">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-base font-bold text-on-surface">Low Stock &amp; Stockouts</h2>
            <button
              onClick={() => onNavigate('inventory')}
              className="text-xs font-bold text-primary hover:underline"
            >
              Restock →
            </button>
          </div>
          {[...stockoutItems, ...lowItems].length === 0 ? (
            <div className="py-10 text-center text-sm text-on-surface-variant">
              All products are well-stocked!
            </div>
          ) : (
            <div className="space-y-2.5">
              {[...stockoutItems, ...lowItems].map((item) => (
                <div
                  key={item.id}
                  className="p-3 rounded-xl bg-surface-container-low flex items-center justify-between gap-2"
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <img
                      src={item.image_url || `/images/skus/${item.sku}.svg`}
                      onError={(e) => { e.currentTarget.src = '/images/skus/DEFAULT.svg'; }}
                      alt={item.name}
                      className="w-10 h-10 rounded-lg bg-surface-container-lowest border border-surface-container-high object-cover shrink-0"
                    />
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-on-surface-variant">{item.sku}</span>
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${statusBadgeStyle(item.status)}`}>
                          {item.status.replace('_', ' ')}
                        </span>
                      </div>
                      <div className="text-sm font-bold text-on-surface truncate mt-0.5">{item.name}</div>
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <div className={`text-sm font-extrabold ${item.stock_qty <= 0 ? 'text-tertiary' : 'text-secondary'}`}>
                      {item.stock_qty} {item.unit}
                    </div>
                    <div className="text-[11px] text-on-surface-variant">Min: {item.reorder_level}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      {/* Recent Orders & Stock Movements */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <section className="rounded-2xl bg-surface-container-lowest p-4 shadow-sm border border-surface-container-high">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-base font-bold text-on-surface">Recent Orders</h2>
            <button onClick={() => onNavigate('orders')} className="text-xs font-bold text-primary hover:underline">
              All Orders →
            </button>
          </div>
          {recentOrders.length === 0 ? (
            <div className="py-8 text-center text-sm text-on-surface-variant">No orders yet.</div>
          ) : (
            <div className="space-y-2">
              {recentOrders.map((ord) => (
                <div key={ord.id} className="p-3 rounded-xl bg-surface-container-low flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-on-surface">{ord.order_number}</span>
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${statusBadgeStyle(ord.status)}`}>
                        {ord.status}
                      </span>
                      {ord.is_sample && (
                        <span className="text-[10px] text-outline font-semibold">(Excluded from sales)</span>
                      )}
                    </div>
                    <div className="text-xs text-on-surface-variant truncate mt-0.5">
                      {ord.customer_name} • {ord.payment_method}
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <div className="text-sm font-bold text-on-surface">{formatINR(ord.total)}</div>
                    <div className="text-[10px] text-on-surface-variant">{formatIndianDate(ord.created_at)}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="rounded-2xl bg-surface-container-lowest p-4 shadow-sm border border-surface-container-high">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-base font-bold text-on-surface">Recent Stock Movements</h2>
            <button onClick={() => onNavigate('movements')} className="text-xs font-bold text-primary hover:underline">
              Full Ledger →
            </button>
          </div>
          {recentMovements.length === 0 ? (
            <div className="py-8 text-center text-sm text-on-surface-variant">No movements recorded.</div>
          ) : (
            <div className="space-y-2">
              {recentMovements.map((t) => (
                <div key={t.id} className="p-3 rounded-xl bg-surface-container-low flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-surface-container-high text-on-surface">
                        {t.movement_type}
                      </span>
                      <span className="text-xs font-bold text-on-surface truncate">{t.product_name}</span>
                    </div>
                    <div className="text-[11px] text-on-surface-variant truncate mt-0.5">{t.reason}</div>
                  </div>
                  <div className="text-right shrink-0">
                    <div className="text-xs font-bold text-on-surface">
                      {t.previous_stock} → <span className="text-primary">{t.updated_stock}</span>
                    </div>
                    <div className="text-[10px] text-on-surface-variant">{formatIndianDate(t.created_at)}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
