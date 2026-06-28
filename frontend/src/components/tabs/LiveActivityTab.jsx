import { useState, useMemo } from 'react';
import { parseAnswer } from '../../utils/formatters';
import { apiFetch } from '../../utils/api';

export function LiveActivityTab({ sessions, chats, loading, error, refetch }) {
  const [search, setSearch] = useState('');

  const q = search.trim().toLowerCase();

  const filteredSessions = useMemo(() => {
    if (!q) return sessions;
    return sessions.filter(s =>
      (s.session_token || '').toLowerCase().includes(q) ||
      (s.ip_address || '').includes(q) ||
      (s.visitor_id || '').toLowerCase().includes(q) ||
      (s.user_agent || '').toLowerCase().includes(q)
    );
  }, [sessions, q]);

  const filteredChats = useMemo(() => {
    if (!q) return chats;
    return chats.filter(c =>
      (c.question || '').toLowerCase().includes(q) ||
      (c.answer || '').toLowerCase().includes(q) ||
      (c.session_token || '').toLowerCase().includes(q) ||
      (c.id || '').toString().toLowerCase().includes(q)
    );
  }, [chats, q]);

  if (loading) {
    return (
      <div className="fade-in tab-content-inner empty-state">
        Loading live activity feed...
      </div>
    );
  }

  if (error) {
    return (
      <div className="fade-in tab-content-inner empty-state" style={{ color: 'var(--danger)' }}>
        Error loading live activity: {error}
      </div>
    );
  }

  return (
    <div className="fade-in tab-content-inner">

      {/* ── Search + Refresh bar ─────────────────────────────────────────── */}
      <div style={{
        display: 'flex', gap: '10px', alignItems: 'center',
        marginBottom: '16px', flexWrap: 'wrap',
      }}>
        <div style={{ flex: 1, minWidth: '260px', position: 'relative' }}>
          <span style={{
            position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)',
            fontSize: '14px', opacity: 0.4, pointerEvents: 'none',
          }}>🔍</span>
          <input
            type="text"
            placeholder="Search by session ID, IP, question, answer, chat ID…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{
              width: '100%', padding: '8px 36px 8px 32px', fontSize: '13px',
              border: '1px solid var(--line-strong)', borderRadius: '6px',
              background: 'var(--paper)', color: 'var(--ink)',
              boxSizing: 'border-box',
            }}
          />
          {search && (
            <button
              onClick={() => setSearch('')}
              style={{
                position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)',
                background: 'none', border: 'none', cursor: 'pointer', opacity: 0.5, fontSize: '12px',
              }}
            >✕</button>
          )}
        </div>

        {/* Match count pill */}
        {search && (
          <span style={{
            fontSize: '12px', padding: '4px 10px', borderRadius: '99px',
            background: 'rgba(15,107,58,0.1)', color: 'var(--moss)', fontWeight: 600,
            whiteSpace: 'nowrap',
          }}>
            {filteredSessions.length} session{filteredSessions.length !== 1 ? 's' : ''} &middot; {filteredChats.length} chat{filteredChats.length !== 1 ? 's' : ''}
          </span>
        )}

        {/* Refresh */}
        {refetch && (
          <button
            onClick={refetch}
            style={{
              padding: '7px 14px', fontSize: '12px', borderRadius: '6px',
              border: '1px solid var(--line-strong)', background: 'transparent',
              color: 'var(--ink)', cursor: 'pointer', whiteSpace: 'nowrap',
            }}
          >
            ↻ Refresh
          </button>
        )}
      </div>

      {/* ── Two-panel grid ───────────────────────────────────────────────── */}
      <div className="dashboard-main-grid" style={{ gridTemplateColumns: '1fr 2fr' }}>
        <div className="panel compact-panel">
          <div className="panel-header" style={{ padding: '12px' }}>
            <h3 style={{ fontSize: '14px' }}>
              Active Sessions
              {search && <span style={{ marginLeft: '6px', fontSize: '11px', opacity: 0.6 }}>({filteredSessions.length}/{sessions.length})</span>}
            </h3>
          </div>
          <div className="stack-list compact-stack" style={{ padding: '12px' }}>
            {filteredSessions.map((s) => (
              <SessionCard key={s.id} session={s} highlight={q} />
            ))}
            {!filteredSessions.length && (
              <div className="empty-state">
                {search ? 'No sessions match your search.' : 'No active sessions right now.'}
              </div>
            )}
          </div>
        </div>

        <div className="panel compact-panel">
          <div className="panel-header" style={{ padding: '12px' }}>
            <h3 style={{ fontSize: '14px' }}>
              Realtime Chat Feed
              {search && <span style={{ marginLeft: '6px', fontSize: '11px', opacity: 0.6 }}>({filteredChats.length}/{chats.length})</span>}
            </h3>
          </div>
          <div className="stack-list compact-stack" style={{ padding: '12px' }}>
            {filteredChats.map((c) => (
              <ChatTraceCard key={c.id} c={c} highlight={q} />
            ))}
            {!filteredChats.length && (
              <div className="empty-state">
                {search ? 'No chats match your search.' : 'No live chats right now.'}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function SessionCard({ session, highlight }) {
  const [expanded, setExpanded] = useState(false);
  const token = session.session_token || '';

  return (
    <article className="record-card compact-record" style={{ background: 'var(--paper)', border: '1px solid var(--line)', padding: '10px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '3px' }}>
            <span style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', opacity: 0.4, letterSpacing: '0.04em' }}>Session</span>
            <code 
              style={{
                fontSize: '11px', fontFamily: 'monospace',
                background: highlight && token.toLowerCase().includes(highlight) ? 'rgba(255,200,0,0.3)' : 'rgba(0,0,0,0.05)',
                padding: '2px 5px', borderRadius: '3px',
                wordBreak: 'break-all',
                userSelect: 'all',
                cursor: 'pointer'
              }}
              title="Double-click to select full Session ID"
            >
              {token}
            </code>
          </div>
          <p style={{ fontSize: '11px', color: 'var(--ink)', opacity: 0.6, margin: 0 }}>
            IP: {session.ip_address || 'Unknown'} &middot; {new Date(session.started_at).toLocaleTimeString()}
          </p>
          {session.visitor_id && (
            <p style={{ fontSize: '10px', opacity: 0.45, margin: '2px 0 0', fontFamily: 'monospace' }}>
              Visitor: {session.visitor_id.slice(0, 16)}
            </p>
          )}
        </div>
        <div style={{ textAlign: 'right', flexShrink: 0, marginLeft: '8px' }}>
          <span className="severity-badge medium">{session.total_messages ?? 0} msgs</span>
          <button className="text-btn" style={{ display: 'block', fontSize: '11px', marginTop: '4px', textAlign: 'right', width: '100%' }} onClick={() => setExpanded(!expanded)}>
            [{expanded ? 'Collapse' : 'Expand'}]
          </button>
        </div>
      </div>

      {expanded && (
        <div style={{ marginTop: '8px', paddingTop: '8px', borderTop: '1px solid var(--line)', fontSize: '12px', color: 'var(--ink)', display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <p><strong>Full Session ID:</strong> <code style={{ fontSize: '10px', wordBreak: 'break-all' }}>{token}</code></p>
          <p><strong>Last Active:</strong> {session.last_active_at ? new Date(session.last_active_at).toLocaleTimeString() : 'N/A'}</p>
          <p><strong>Platform:</strong> {session.user_agent ? session.user_agent.substring(0, 80) + (session.user_agent.length > 80 ? '...' : '') : 'Unknown'}</p>
        </div>
      )}
    </article>
  );
}

function ChatTraceCard({ c, highlight }) {
  const [expanded, setExpanded] = useState(false);
  const [isRewriting, setIsRewriting] = useState(false);
  const [rewriteText, setRewriteText] = useState('');
  const [savingRewrite, setSavingRewrite] = useState(false);

  const parsed = parseAnswer(c.answer || '').bodyHtml;
  const preview = parsed.split('<p>').slice(0, 2).join('<p>') + (parsed.includes('<p>') ? '...' : '');
  const sessionToken = c.session_token || '';

  const handleSaveRewrite = async () => {
    if (!rewriteText.trim()) return;
    setSavingRewrite(true);
    try {
      await apiFetch('/api/admin/corrections/direct', {
        method: 'POST',
        body: JSON.stringify({
          question: c.question,
          corrected_answer: rewriteText,
          admin_note: 'Rewritten directly from Live Activity log'
        }),
      });
      setIsRewriting(false);
      setRewriteText('');
      alert('Rewrite saved as a permanent correction!');
    } catch (err) {
      alert('Error saving rewrite: ' + err.message);
    } finally {
      setSavingRewrite(false);
    }
  };

  return (
    <article className="record-card compact-record" style={{ background: 'var(--paper)', border: '1px solid var(--line)', padding: '10px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px', gap: '8px', alignItems: 'flex-start' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
          <span style={{ fontSize: '11px', color: 'var(--ink)', opacity: 0.6 }}>{new Date(c.asked_at).toLocaleTimeString()}</span>
          {/* Session token badge */}
          {sessionToken && (
            <code 
              style={{
                fontSize: '10px', fontFamily: 'monospace', opacity: 0.8,
                background: highlight && sessionToken.toLowerCase().includes(highlight) ? 'rgba(255,200,0,0.3)' : 'rgba(0,0,0,0.05)',
                padding: '2px 5px', borderRadius: '3px', display: 'inline-block',
                wordBreak: 'break-all',
                userSelect: 'all',
                cursor: 'pointer'
              }}
              title="Double-click to select full Session ID"
            >
              {sessionToken}
            </code>
          )}
        </div>
        <div style={{ display: 'flex', gap: '8px', flexShrink: 0 }}>
          <button className="text-btn" style={{ fontSize: '11px', color: 'var(--accent)' }} onClick={() => { setIsRewriting(!isRewriting); setRewriteText(c.answer || ''); }}>
            [Rewrite]
          </button>
          <button className="text-btn muted" style={{ fontSize: '11px' }} onClick={() => setExpanded(!expanded)}>
            [{expanded ? 'Collapse' : 'Expand'}]
          </button>
        </div>
      </div>
      <p style={{ fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>{c.question}</p>
      
      {!isRewriting ? (
        <div style={{ fontSize: '12px', color: 'var(--ink)', background: 'var(--paper-muted)', padding: '8px', borderRadius: '4px', lineHeight: '1.4' }} dangerouslySetInnerHTML={{ __html: expanded ? parsed : preview }} />
      ) : (
        <div style={{ marginTop: '8px', padding: '10px', background: 'var(--paper)', border: '1px solid var(--accent)', borderRadius: '6px' }}>
          <p style={{ fontSize: '12px', fontWeight: 600, color: 'var(--accent)', marginBottom: '8px' }}>Rewrite Answer (Saves to Corrections Database)</p>
          <textarea
            value={rewriteText}
            onChange={(e) => setRewriteText(e.target.value)}
            rows={4}
            className="admin-input"
            style={{ width: '100%', fontSize: '13px', padding: '8px', marginBottom: '8px', fontFamily: 'inherit' }}
            placeholder="Enter the correct markdown answer here..."
          />
          <div style={{ display: 'flex', gap: '8px' }}>
            <button className="text-btn success" onClick={handleSaveRewrite} disabled={savingRewrite}>
              {savingRewrite ? 'Saving...' : 'Save Correction'}
            </button>
            <button className="text-btn muted" onClick={() => setIsRewriting(false)}>Cancel</button>
          </div>
        </div>
      )}
    </article>
  );
}
