import { useCallback, useEffect, useState } from 'react';
import { apiRequest, getToken, setToken } from './api';
import { formatINR } from './utils/format';
import LoginView from './components/LoginView';
import DashboardView from './components/DashboardView';
import InventoryView from './components/InventoryView';
import OrdersView from './components/OrdersView';
import MovementsView from './components/MovementsView';
import SuppliersView from './components/SuppliersView';
import AIChatView from './components/AIChatView';
import AnalyticsView from './components/AnalyticsView';
import AlertsView from './components/AlertsView';

const NAV_ITEMS = [
  { id: 'dashboard', label: 'Dashboard', icon: 'home' },
  { id: 'inventory', label: 'Inventory', icon: 'inventory_2' },
  { id: 'orders', label: 'Orders', icon: 'receipt_long' },
  { id: 'movements', label: 'Movements', icon: 'swap_vert' },
  { id: 'suppliers', label: 'Suppliers', icon: 'local_shipping' },
  { id: 'ai', label: 'AI Assistant', icon: 'smart_toy' },
  { id: 'analytics', label: 'Analytics', icon: 'bar_chart' },
  { id: 'alerts', label: 'Alerts', icon: 'notifications_active' },
];

export default function App() {
  const [user, setUser] = useState(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [loading, setLoading] = useState(false);

  const [dashboard, setDashboard] = useState(null);
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [orders, setOrders] = useState([]);
  const [movements, setMovements] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [analytics, setAnalytics] = useState(null);

  const loadAllData = useCallback(async () => {
    setLoading(true);
    try {
      const [dash, prods, cats, sups, ords, movs, alts, anly] = await Promise.all([
        apiRequest('/dashboard'),
        apiRequest('/products'),
        apiRequest('/categories'),
        apiRequest('/suppliers'),
        apiRequest('/orders'),
        apiRequest('/movements'),
        apiRequest('/alerts'),
        apiRequest('/analytics'),
      ]);
      setDashboard(dash);
      setProducts(prods);
      setCategories(cats);
      setSuppliers(sups);
      setOrders(ords);
      setMovements(movs);
      setAlerts(alts);
      setAnalytics(anly);
    } catch (err) {
      console.error('Data load error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const handleUnauth = () => {
      setUser(null);
      setAuthChecked(true);
    };
    window.addEventListener('kirana:unauthorized', handleUnauth);

    const token = getToken();
    if (!token) {
      setAuthChecked(true);
    } else {
      apiRequest('/auth/me')
        .then((u) => {
          setUser(u);
          setAuthChecked(true);
        })
        .catch(() => {
          setToken(null);
          setAuthChecked(true);
        });
    }
    return () => window.removeEventListener('kirana:unauthorized', handleUnauth);
  }, []);

  useEffect(() => {
    if (user) {
      loadAllData();
    }
  }, [user, loadAllData]);

  function handleLogout() {
    setToken(null);
    setUser(null);
  }

  if (!authChecked) {
    return (
      <div className="min-h-screen bg-surface flex items-center justify-center text-sm font-bold text-on-surface-variant">
        Loading Gupta Brothers Kirana...
      </div>
    );
  }

  if (!user) {
    return <LoginView onLogin={(u) => setUser(u)} />;
  }

  const activeAlertCount = alerts.filter((a) => a.status === 'ACTIVE').length;
  const todaysSales = dashboard?.kpis?.todays_sales || 0;

  return (
    <div className="min-h-screen bg-surface text-on-surface flex flex-col md:flex-row">
      {/* Desktop Sidebar */}
      <aside className="hidden md:flex md:w-64 md:flex-col md:fixed md:inset-y-0 bg-surface-container-lowest border-r border-surface-container-high z-40">
        <div className="p-4 border-b border-surface-container flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center shrink-0 shadow-sm">
            <span className="material-symbols-outlined text-on-primary text-[22px]">storefront</span>
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-1">
              <span className="font-bold text-sm text-on-surface truncate">Gupta Brothers Kirana</span>
              <span className="material-symbols-outlined text-primary text-[15px]">verified</span>
            </div>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-primary-fixed/40 text-[10px] font-bold text-on-primary-fixed-variant">
                <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
                ONLINE
              </span>
              <span className="text-[10px] font-bold text-secondary">{formatINR(todaysSales)} Today</span>
            </div>
          </div>
        </div>

        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          {NAV_ITEMS.map((item) => {
            const active = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm font-bold transition-colors ${
                  active
                    ? 'bg-primary text-on-primary shadow-sm'
                    : 'text-on-surface-variant hover:bg-surface-container-low hover:text-on-surface'
                }`}
              >
                <span className="flex items-center gap-2.5">
                  <span className="material-symbols-outlined text-[20px]">{item.icon}</span>
                  {item.label}
                </span>
                {item.id === 'alerts' && activeAlertCount > 0 && (
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-extrabold ${active ? 'bg-on-primary text-primary' : 'bg-tertiary text-on-tertiary'}`}>
                    {activeAlertCount}
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        <div className="p-3 border-t border-surface-container flex items-center justify-between gap-2">
          <div className="min-w-0">
            <div className="text-xs font-bold text-on-surface truncate">{user.name}</div>
            <div className="text-[10px] uppercase font-bold text-primary">{user.role}</div>
          </div>
          <button
            onClick={handleLogout}
            className="px-2.5 py-1.5 rounded-lg bg-surface-container-high text-xs font-bold text-on-surface hover:bg-error-container hover:text-on-error-container"
          >
            Logout
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 md:pl-64 flex flex-col min-h-screen min-w-0">
        {/* Top Bar (Mobile & Desktop) */}
        <header className="sticky top-0 z-30 bg-surface/90 backdrop-blur-xl border-b border-surface-container-high px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2.5 md:hidden min-w-0">
            <div className="w-9 h-9 rounded-xl bg-primary flex items-center justify-center shrink-0">
              <span className="material-symbols-outlined text-on-primary text-[20px]">storefront</span>
            </div>
            <div className="min-w-0">
              <div className="text-sm font-bold truncate">Gupta Brothers Kirana</div>
              <div className="text-[10px] font-bold text-secondary">{formatINR(todaysSales)} Today</div>
            </div>
          </div>
          <div className="hidden md:block text-sm font-bold text-on-surface-variant capitalize">
            {NAV_ITEMS.find((n) => n.id === activeTab)?.label}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setActiveTab('ai')}
              className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-primary-fixed/40 text-on-primary-fixed-variant text-xs font-bold hover:bg-primary-fixed/60"
            >
              <span className="material-symbols-outlined text-[16px]">smart_toy</span>
              Ask AI
            </button>
            <button
              onClick={() => setActiveTab('alerts')}
              aria-label="Alerts"
              className="w-10 h-10 rounded-full flex items-center justify-center hover:bg-surface-container relative"
            >
              <span className="material-symbols-outlined text-[22px] text-on-surface-variant">notifications</span>
              {activeAlertCount > 0 && (
                <span className="absolute top-2 right-2 w-2.5 h-2.5 rounded-full bg-tertiary ring-2 ring-surface" />
              )}
            </button>
            <button
              onClick={handleLogout}
              className="md:hidden px-2.5 py-1 rounded-lg bg-surface-container-high text-xs font-bold"
            >
              Logout
            </button>
          </div>
        </header>

        <main className="flex-1 p-4 sm:p-6 pb-24 md:pb-8 max-w-7xl w-full mx-auto">
          {activeTab === 'dashboard' && (
            <DashboardView data={dashboard} loading={loading} onNavigate={setActiveTab} onRefresh={loadAllData} />
          )}
          {activeTab === 'inventory' && (
            <InventoryView products={products} categories={categories} suppliers={suppliers} user={user} onReload={loadAllData} />
          )}
          {activeTab === 'orders' && (
            <OrdersView orders={orders} products={products} onReload={loadAllData} />
          )}
          {activeTab === 'movements' && (
            <MovementsView movements={movements} products={products} onReload={loadAllData} />
          )}
          {activeTab === 'suppliers' && (
            <SuppliersView suppliers={suppliers} user={user} onReload={loadAllData} />
          )}
          {activeTab === 'ai' && (
            <AIChatView onReload={loadAllData} />
          )}
          {activeTab === 'analytics' && (
            <AnalyticsView analytics={analytics} dashboard={dashboard} />
          )}
          {activeTab === 'alerts' && (
            <AlertsView alerts={alerts} onReload={loadAllData} />
          )}
        </main>

        {/* Mobile Sticky Bottom Navigation Bar matching screenshots */}
        <nav className="md:hidden fixed bottom-0 inset-x-0 z-40 bg-surface-container-lowest/95 backdrop-blur-lg border-t border-surface-container-high flex items-center justify-around h-16 px-1">
          {[
            { id: 'dashboard', label: 'Home', icon: 'home' },
            { id: 'inventory', label: 'Inventory', icon: 'inventory_2' },
            { id: 'orders', label: 'Orders', icon: 'receipt_long' },
            { id: 'ai', label: 'AI Chat', icon: 'smart_toy' },
            { id: 'alerts', label: 'Alerts', icon: 'notifications_active' },
          ].map((item) => {
            const active = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`flex flex-col items-center justify-center gap-0.5 px-2 py-1 rounded-xl ${
                  active ? 'text-primary font-bold' : 'text-on-surface-variant'
                }`}
              >
                <span className="material-symbols-outlined text-[22px]">{item.icon}</span>
                <span className="text-[10px]">{item.label}</span>
              </button>
            );
          })}
        </nav>
      </div>
    </div>
  );
}
