import React, { useState, useEffect } from 'react';
import { apiFetch } from '../utils/api';

// ── helpers ───────────────────────────────────────────────────────────────

function toIST(isoStr) {
  if (!isoStr) return '—';
  try {
    return new Date(isoStr).toLocaleString('en-IN', {
      timeZone: 'Asia/Kolkata',
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return isoStr;
  }
}

// color config for intent labels
const INTENT_CONFIG = {
  high_intent:  { label: 'High Intent',  bg: 'rgba(220,38,38,0.1)',  color: '#b91c1c',  dot: '#dc2626' },
  interested:   { label: 'Interested',   bg: 'rgba(234,88,12,0.1)',  color: '#c2410c',  dot: '#ea580c' },
  evaluating:   { label: 'Evaluating',   bg: 'rgba(217,119,6,0.1)', color: '#b45309',  dot: '#d97706' },
  browsing:     { label: 'Browsing',     bg: 'rgba(75,85,99,0.1)',  color: '#374151',  dot: '#6b7280' },
};

function IntentBadge({ label }) {
  const cfg = INTENT_CONFIG[label] || INTENT_CONFIG.browsing;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '5px',
      padding: '3px 10px', borderRadius: '99px',
      background: cfg.bg, color: cfg.color,
      fontSize: '11px', fontWeight: 700,
    }}>
      <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: cfg.dot, flexShrink: 0 }} />
      {cfg.label}
    </span>
  );
}

// route badge color (matches OverviewTab)
const ROUTE_COLORS = {
  rag:              { bg: 'rgba(15,107,58,0.1)',  color: '#0f6b3a' },
  redis_cache:      { bg: 'rgba(59,130,246,0.1)', color: '#2563eb' },
  file_cache:       { bg: 'rgba(59,130,246,0.1)', color: '#2563eb' },
  static:           { bg: 'rgba(107,114,128,0.1)',color: '#4b5563' },
  greeting:         { bg: 'rgba(107,114,128,0.1)',color: '#4b5563' },
  structured_fee_single:      { bg: 'rgba(234,88,12,0.1)',  color: '#c2410c' },
  structured_fee_comparison:  { bg: 'rgba(234,88,12,0.1)',  color: '#c2410c' },
  approved_correction:        { bg: 'rgba(139,92,246,0.1)', color: '#7c3aed' },
};

function RouteBadge({ route }) {
  const cfg = ROUTE_COLORS[route] || { bg: 'rgba(107,114,128,0.1)', color: '#4b5563' };
  return (
    <span style={{
      padding: '2px 8px', borderRadius: '99px', fontSize: '10px', fontWeight: 600,
      background: cfg.bg, color: cfg.color, whiteSpace: 'nowrap',
    }}>
      {route || 'unknown'}
    </span>
  );
}

// ── component ─────────────────────────────────────────────────────────────

export default function SessionChatHistory({ sessionToken, sessionMeta, onClose }) {
  const [chats, setChats] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!sessionToken) return;
    setLoading(true);
    apiFetch(`/api/admin/sessions/${sessionToken}/chats`, {
      headers: { 'X-Admin-User': 'dashboard-admin' },
    })
      .then(d => {
        setChats(d.chats || []);
        setError(null);
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  }, [sessionToken]);

  // close on backdrop click
  const handleBackdrop = (e) => {
    if (e.target === e.currentTarget) onClose();
  };

  const intentLabel = sessionMeta?.intent_label || 'browsing';
  const intentScore = sessionMeta?.intent_score || 0;

  return (
    <div
      onClick={handleBackdrop}
      style={{
        position: 'fixed', inset: 0, zIndex: 9999,
        background: 'rgba(0,0,0,0.45)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '20px',
      }}
    >
      <div style={{
        background: 'var(--paper)',
        borderRadius: '12px',
        width: '100%',
        maxWidth: '720px',
        maxHeight: '85vh',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
        overflow: 'hidden',
      }}>

        {/* header */}
        <div style={{
          padding: '16px 20px',
          borderBottom: '1px solid var(--line)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          flexShrink: 0,
        }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span style={{ fontWeight: 700, fontSize: '15px' }}>Session Chat History</span>
              <IntentBadge label={intentLabel} />
              {intentScore > 0 && (
                <span style={{ fontSize: '11px', opacity: 0.55 }}>Score: {intentScore}</span>
              )}
            </div>
            <code style={{ fontSize: '11px', fontFamily: 'monospace', opacity: 0.5 }}>
              {sessionToken?.slice(0, 28)}...
            </code>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              fontSize: '20px', opacity: 0.5, padding: '4px 8px', lineHeight: 1,
            }}
          >
            x
          </button>
        </div>

        {/* session meta row */}
        {sessionMeta && (
          <div style={{
            padding: '10px 20px',
            borderBottom: '1px solid var(--line)',
            display: 'flex', gap: '20px', flexWrap: 'wrap',
            background: 'rgba(15,107,58,0.03)',
            flexShrink: 0,
          }}>
            {[
              ['Started', toIST(sessionMeta.started_at)],
              ['Messages', sessionMeta.total_messages ?? chats.length],
              ['Duration', sessionMeta.duration_label || '—'],
              ['IP', sessionMeta.ip_address || '—'],
              ['Browser', sessionMeta.browser || '—'],
            ].map(([k, v]) => (
              <div key={k} style={{ display: 'flex', flexDirection: 'column', gap: '1px' }}>
                <span style={{ fontSize: '10px', textTransform: 'uppercase', opacity: 0.45, fontWeight: 600 }}>{k}</span>
                <span style={{ fontSize: '12px', fontWeight: 500 }}>{v}</span>
              </div>
            ))}
          </div>
        )}

        {/* chat thread */}
        <div style={{ overflowY: 'auto', padding: '16px 20px', flex: 1 }}>
          {loading && (
            <div style={{ fontSize: '13px', opacity: 0.6, textAlign: 'center', paddingTop: '30px' }}>
              Loading chat thread...
            </div>
          )}
          {error && (
            <div style={{ fontSize: '13px', color: 'var(--danger)', paddingTop: '20px' }}>
              Error: {error}
            </div>
          )}
          {!loading && !error && chats.length === 0 && (
            <div style={{ fontSize: '13px', opacity: 0.5, textAlign: 'center', paddingTop: '30px', fontStyle: 'italic' }}>
              No messages found for this session.
            </div>
          )}
          {!loading && !error && chats.map((msg, i) => (
            <div key={msg.id || i} style={{ marginBottom: '20px' }}>

              {/* user question bubble */}
              <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '6px' }}>
                <div style={{
                  maxWidth: '72%',
                  background: 'rgba(15,107,58,0.1)',
                  borderRadius: '12px 12px 2px 12px',
                  padding: '9px 13px',
                  fontSize: '13px',
                  color: 'var(--ink)',
                  lineHeight: 1.5,
                }}>
                  {msg.question}
                </div>
              </div>

              {/* bot answer bubble */}
              <div style={{ display: 'flex', justifyContent: 'flex-start', gap: '8px', alignItems: 'flex-start' }}>
                <div style={{
                  width: '26px', height: '26px', borderRadius: '50%',
                  background: 'rgba(15,107,58,0.12)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  flexShrink: 0, marginTop: '2px',
                }}>
                  <span style={{ fontSize: '12px' }}>A</span>
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{
                    background: 'var(--paper-light, #f9fafb)',
                    border: '1px solid var(--line)',
                    borderRadius: '2px 12px 12px 12px',
                    padding: '9px 13px',
                    fontSize: '12.5px',
                    color: 'var(--ink)',
                    lineHeight: 1.6,
                    whiteSpace: 'pre-wrap',
                    maxWidth: '100%',
                  }}>
                    {msg.answer}
                  </div>
                  {/* message meta */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '5px', paddingLeft: '2px' }}>
                    <RouteBadge route={msg.route} />
                    {msg.cached && (
                      <span style={{ fontSize: '10px', opacity: 0.5 }}>cached</span>
                    )}
                    <span style={{ fontSize: '10px', opacity: 0.4, marginLeft: 'auto' }}>
                      {toIST(msg.asked_at)}
                    </span>
                  </div>
                </div>
              </div>

            </div>
          ))}
        </div>

        {/* footer */}
        <div style={{
          padding: '12px 20px',
          borderTop: '1px solid var(--line)',
          display: 'flex', justifyContent: 'flex-end',
          flexShrink: 0,
        }}>
          <button
            onClick={onClose}
            style={{
              padding: '7px 18px', borderRadius: '6px',
              background: 'var(--moss)', color: '#fff',
              border: 'none', cursor: 'pointer', fontSize: '13px', fontWeight: 600,
            }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
