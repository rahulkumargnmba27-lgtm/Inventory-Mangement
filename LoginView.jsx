import { useState } from 'react';
import { apiRequest, setToken } from '../api';

export default function LoginView({ onLogin }) {
  const [email, setEmail] = useState('owner@kiranaquick.in');
  const [password, setPassword] = useState('Kirana@123');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const data = await apiRequest('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      });
      setToken(data.access_token);
      onLogin(data.user);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-surface flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-surface-container-lowest rounded-2xl p-6 sm:p-8 shadow-[0_8px_30px_rgba(28,25,23,0.08)] border border-surface-container-high">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-12 h-12 rounded-xl bg-primary flex items-center justify-center shadow-sm">
            <span className="material-symbols-outlined text-on-primary text-[26px]">storefront</span>
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <h1 className="text-xl font-bold text-on-surface tracking-tight">Gupta Brothers Kirana</h1>
              <span className="material-symbols-outlined text-primary text-[18px]">verified</span>
            </div>
            <p className="text-xs text-on-surface-variant">AI-Powered Kirana Inventory &amp; Digital Khata</p>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-xl bg-error-container text-on-error-container text-sm font-medium">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-on-surface-variant mb-1.5">
              Store Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full h-11 px-3.5 rounded-xl bg-surface-container-low border border-surface-container-high text-sm text-on-surface focus:outline-none focus:border-primary"
            />
          </div>
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-on-surface-variant mb-1.5">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full h-11 px-3.5 rounded-xl bg-surface-container-low border border-surface-container-high text-sm text-on-surface focus:outline-none focus:border-primary"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full h-11 rounded-xl bg-primary hover:bg-primary-container text-on-primary font-bold text-sm shadow-[0_2px_8px_rgba(0,105,72,0.28)] transition-all active:scale-[0.98] disabled:opacity-60"
          >
            {loading ? 'Signing in...' : 'Sign In to Store Console'}
          </button>
        </form>

        <div className="mt-6 p-3.5 rounded-xl bg-surface-container-low border border-surface-container-high text-xs text-on-surface-variant space-y-1.5">
          <div className="font-bold text-on-surface">Demo Accounts (Click to Fill):</div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => { setEmail('owner@kiranaquick.in'); setPassword('Kirana@123'); }}
              className="px-2.5 py-1 rounded-full bg-primary-fixed/40 text-on-primary-fixed-variant font-bold hover:bg-primary-fixed/70"
            >
              Owner (owner@kiranaquick.in)
            </button>
            <button
              type="button"
              onClick={() => { setEmail('staff@kiranaquick.in'); setPassword('Staff@123'); }}
              className="px-2.5 py-1 rounded-full bg-secondary-fixed text-on-secondary-fixed-variant font-bold hover:opacity-90"
            >
              Staff (staff@kiranaquick.in)
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
