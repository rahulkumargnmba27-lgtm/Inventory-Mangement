import { useEffect, useState } from 'react';
import { apiRequest } from '../api';
import { formatIndianDate, statusBadgeStyle } from '../utils/format';

export default function AlertsView({ alerts, onReload }) {
  const [checking, setChecking] = useState(false);
  const [statusMsg, setStatusMsg] = useState('');
  const [tgStatus, setTgStatus] = useState(null);
  const [tgMsg, setTgMsg] = useState('');
  const [tgBusy, setTgBusy] = useState(false);

  useEffect(() => {
    apiRequest('/telegram/status')
      .then(setTgStatus)
      .catch(() => setTgStatus({ configured: false }));
  }, []);

  async function runCheckNow() {
    setChecking(true);
    setStatusMsg('');
    try {
      const res = await apiRequest('/automation/check-alerts', { method: 'POST' });
      setStatusMsg(
        `Checked ${res.checked_products} products. Created ${res.new_alerts_created} new deduplicated alert(s).`
      );
      await onReload();
    } catch (e) {
      setStatusMsg(`Error: ${e.message}`);
    } finally {
      setChecking(false);
    }
  }

  async function sendTelegramSummary() {
    setTgBusy(true);
    setTgMsg('');
    try {
      const res = await apiRequest('/telegram/send-test', { method: 'POST' });
      setTgMsg(
        res.sent
          ? `Sent live inventory summary to Telegram (Message ID: ${res.external_message_id})`
          : `Telegram credentials not set (${res.external_message_id}). Preview generated:\n${res.preview}`
      );
    } catch (e) {
      setTgMsg(`Error: ${e.message}`);
    } finally {
      setTgBusy(false);
    }
  }

  async function pollTelegramNow() {
    setTgBusy(true);
    setTgMsg('');
    try {
      const res = await apiRequest('/telegram/poll-once', { method: 'POST' });
      if (!res.configured) {
        setTgMsg('Set TELEGRAM_BOT_TOKEN in backend/.env to poll live Telegram commands.');
      } else {
        setTgMsg(`Polled Telegram HTTP API: processed ${res.processed} update(s).`);
        if (res.processed > 0) await onReload();
      }
    } catch (e) {
      setTgMsg(`Error: ${e.message}`);
    } finally {
      setTgBusy(false);
    }
  }

  async function acknowledge(id) {
    await apiRequest(`/alerts/${id}/acknowledge`, { method: 'POST' });
    await onReload();
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-on-surface">Low-Stock Alerts, WhatsApp &amp; Telegram</h1>
          <p className="text-xs text-on-surface-variant">
            Deduplicated WhatsApp &amp; Telegram alerts • Automated 15-minute n8n monitoring
          </p>
        </div>
        <button
          onClick={runCheckNow}
          disabled={checking}
          className="h-10 px-4 rounded-xl bg-primary text-on-primary text-xs font-bold flex items-center gap-1.5"
        >
          <span className="material-symbols-outlined text-[18px]">sync</span>
          {checking ? 'Checking...' : 'Run 15-Min Check Now'}
        </button>
      </div>

      {statusMsg && (
        <div className="p-3 rounded-xl bg-primary-fixed/40 text-on-primary-fixed-variant text-xs font-bold">
          {statusMsg}
        </div>
      )}

      {/* Telegram Bot HTTP API Integration Card */}
      <section className="rounded-2xl bg-surface-container-lowest p-4 border border-surface-container-high shadow-sm space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2.5">
            <div className="w-10 h-10 rounded-xl bg-primary-fixed/40 text-on-primary-fixed-variant flex items-center justify-center">
              <span className="material-symbols-outlined text-[22px]">send</span>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-on-surface">Telegram Bot HTTP API</h2>
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${tgStatus?.configured ? 'bg-primary-fixed/50 text-on-primary-fixed-variant' : 'bg-secondary-fixed text-on-secondary-fixed-variant'}`}>
                  {tgStatus?.configured ? `Connected (@${tgStatus.username || 'bot'})` : 'Needs Token in .env'}
                </span>
              </div>
              <p className="text-xs text-on-surface-variant">
                Check &amp; update inventory directly from Telegram using <code className="font-mono">/stock</code>, <code className="font-mono">/lowstock</code>, <code className="font-mono">/value</code>, <code className="font-mono">/add</code>, <code className="font-mono">/deduct</code>
              </p>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              onClick={pollTelegramNow}
              disabled={tgBusy}
              className="h-9 px-3 rounded-xl bg-surface-container-high hover:bg-surface-variant text-xs font-bold text-on-surface"
            >
              Poll Updates
            </button>
            <button
              onClick={sendTelegramSummary}
              disabled={tgBusy}
              className="h-9 px-3.5 rounded-xl bg-primary text-on-primary text-xs font-bold"
            >
              Send Live Summary
            </button>
          </div>
        </div>

        {tgMsg && (
          <div className="p-3 rounded-xl bg-surface-container-low border border-surface-container-high text-xs whitespace-pre-line text-on-surface">
            {tgMsg}
          </div>
        )}
      </section>

      <div className="space-y-3">
        {alerts.length === 0 ? (
          <div className="rounded-2xl bg-surface-container-lowest p-10 text-center text-sm text-on-surface-variant border border-surface-container-high">
            No alerts in history.
          </div>
        ) : (
          alerts.map((a) => (
            <article key={a.id} className="rounded-2xl bg-surface-container-lowest p-4 border border-surface-container-high shadow-sm space-y-2">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-bold text-on-surface-variant">{a.sku}</span>
                    <span className="text-sm font-bold text-on-surface">{a.product_name}</span>
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${statusBadgeStyle(a.alert_type)}`}>
                      {a.alert_type.replace('_', ' ')}
                    </span>
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${statusBadgeStyle(a.status)}`}>
                      {a.status}
                    </span>
                  </div>
                  <div className="text-xs text-on-surface-variant mt-0.5">
                    Current: <strong>{a.current_stock}</strong> • Reorder Level: <strong>{a.reorder_level}</strong> • Shortage: <strong className="text-tertiary">{a.shortage_qty}</strong>
                  </div>
                </div>
                <div className="text-right text-[11px] text-on-surface-variant shrink-0">
                  <div>{formatIndianDate(a.created_at)}</div>
                  <div className="font-mono text-[10px]">{a.external_message_id}</div>
                </div>
              </div>
              <div className="p-2.5 rounded-xl bg-surface-container-low text-xs text-on-surface">
                <strong>Recommended Action:</strong> {a.recommended_action}
              </div>
              {a.status === 'ACTIVE' && (
                <div className="flex justify-end">
                  <button
                    onClick={() => acknowledge(a.id)}
                    className="h-8 px-3 rounded-lg bg-surface-container-high text-xs font-bold text-on-surface"
                  >
                    Acknowledge
                  </button>
                </div>
              )}
            </article>
          ))
        )}
      </div>
    </div>
  );
}
