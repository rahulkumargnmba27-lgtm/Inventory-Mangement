import { useState } from 'react';
import { apiRequest } from '../api';

const QUICK_PROMPTS = [
  'How much rice is available?',
  'Which products are running low?',
  'Show all stockouts',
  'What is my inventory value?',
  'How much wheat flour should I reorder?',
  'Add 50 kg rice to inventory',
  'Deduct 5 packets of salt',
];

function renderFormattedText(text) {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} className="font-bold">{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return <code key={i} className="px-1 py-0.5 rounded bg-surface-container-high font-mono text-[12px]">{part.slice(1, -1)}</code>;
    }
    return part;
  });
}

export default function AIChatView({ onReload }) {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      text: 'Namaste! I am your **Kirana Quick AI Inventory Assistant** powered by Gemini + Live Database Tools.\n\nAsk me about stock levels, reorder recommendations, inventory valuation, or request stock updates (I will always ask for your confirmation before modifying stock).',
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  async function sendMessage(textToSend, confirmAction = false, pendingAction = null) {
    const clean = (textToSend || '').trim();
    if (!clean && !confirmAction) return;

    if (!confirmAction) {
      setMessages((prev) => [...prev, { role: 'user', text: clean }]);
      setInput('');
    }
    setLoading(true);
    try {
      const res = await apiRequest('/ai/chat', {
        method: 'POST',
        body: JSON.stringify({
          message: clean || 'confirm',
          confirm_action: confirmAction,
          pending_action: pendingAction,
        }),
      });
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: res.reply,
          mode: res.mode,
          requires_confirmation: res.requires_confirmation,
          pending_action: res.pending_action,
          tool_calls: res.tool_calls,
        },
      ]);
      if (confirmAction) {
        await onReload();
      }
    } catch (err) {
      setMessages((prev) => [...prev, { role: 'assistant', text: `Error: ${err.message}` }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="w-full max-w-full flex flex-col h-[calc(100vh-11.5rem)] md:h-[calc(100vh-8rem)] rounded-2xl bg-surface-container-lowest border border-surface-container-high shadow-sm overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-surface-container flex items-center justify-between bg-surface-container-low">
        <div className="flex items-center gap-2.5">
          <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center text-on-primary">
            <span className="material-symbols-outlined text-[22px]">smart_toy</span>
          </div>
          <div>
            <h2 className="text-base font-bold text-on-surface">Kirana AI Assistant</h2>
            <p className="text-[11px] text-on-surface-variant">Gemini API • Verified Live Database Queries &amp; Stock Control</p>
          </div>
        </div>
        <span className="px-2.5 py-1 rounded-full bg-primary-fixed/40 text-on-primary-fixed-variant text-[10px] font-bold">
          Live DB Connected
        </span>
      </div>

      {/* Quick Prompts */}
      <div className="px-4 py-2.5 border-b border-surface-container flex flex-wrap items-center gap-2 bg-surface">
        {QUICK_PROMPTS.map((q) => (
          <button
            key={q}
            onClick={() => sendMessage(q)}
            className="px-3 py-1.5 rounded-full bg-surface-container-lowest border border-surface-container-high text-xs font-semibold text-on-surface hover:bg-primary-fixed/30 hover:border-primary whitespace-nowrap transition-colors"
          >
            {q}
          </button>
        ))}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.map((m, idx) => (
          <div key={idx} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[85%] sm:max-w-[75%] rounded-2xl p-3.5 text-sm whitespace-pre-line ${
                m.role === 'user'
                  ? 'bg-primary text-on-primary rounded-br-sm'
                  : 'bg-surface-container-low text-on-surface border border-surface-container-high rounded-bl-sm'
              }`}
            >
              <div>{renderFormattedText(m.text)}</div>

              {m.requires_confirmation && m.pending_action && (
                <div className="mt-3 p-3 rounded-xl bg-surface-container-lowest border border-secondary/40 flex flex-wrap items-center justify-between gap-2">
                  <span className="text-xs font-bold text-secondary">
                    Confirm {m.pending_action.sku} ({m.pending_action.current_stock} → {m.pending_action.projected_stock} {m.pending_action.unit})?
                  </span>
                  <div className="flex gap-2">
                    <button
                      disabled={loading}
                      onClick={() => sendMessage('confirm', true, m.pending_action)}
                      className="px-3 py-1.5 rounded-lg bg-primary text-on-primary text-xs font-bold"
                    >
                      Confirm Update
                    </button>
                  </div>
                </div>
              )}

              {m.tool_calls && m.tool_calls.length > 0 && (
                <div className="mt-2 pt-2 border-t border-surface-container-high text-[10px] text-on-surface-variant">
                  Verified via: {m.tool_calls.map((t) => t.tool).join(', ')}
                </div>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="rounded-2xl bg-surface-container-low px-4 py-2.5 text-xs font-semibold text-on-surface-variant animate-pulse">
              Querying live Kirana inventory...
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          sendMessage(input);
        }}
        className="p-3 border-t border-surface-container bg-surface-container-low flex gap-2"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about stock, reorder qty, or say 'Add 50 kg rice to inventory'..."
          className="flex-1 h-11 px-4 rounded-xl bg-surface-container-lowest border border-surface-container-high text-sm focus:outline-none focus:border-primary"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="h-11 px-5 rounded-xl bg-primary hover:bg-primary-container text-on-primary text-sm font-bold disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </div>
  );
}
