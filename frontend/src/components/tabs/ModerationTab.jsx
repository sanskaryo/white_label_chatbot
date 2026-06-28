import { useState, useMemo } from 'react';
import { parseAnswer } from '../../utils/formatters';
import { apiFetch, apiDownload } from '../../utils/api';
import { Download } from 'lucide-react';

export function ModerationTab({ flagged, negativeFeedback, approveFlagged, rejectFlagged, deleteNegativeFeedback }) {
  const [filter, setFilter] = useState('All');
  const [expandedRow, setExpandedRow] = useState(null);
  const [rewritingRow, setRewritingRow] = useState(null);
  const [rewriteText, setRewriteText] = useState('');
  const [savingRewrite, setSavingRewrite] = useState(false);

  const handleSaveRewrite = async (item) => {
    if (!rewriteText.trim()) return;
    setSavingRewrite(true);
    try {
      await apiFetch('/api/admin/corrections/direct', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Admin-User': 'dashboard-admin' },
        body: JSON.stringify({ question: item.question, corrected_answer: rewriteText, admin_note: 'Rewritten from Moderation Queue' }),
      });
      // For both human-flagged and AI batch items, reject the original after rewriting
      if (item._type === 'flagged' || item._type === 'ai_batch') {
        await rejectFlagged(item.id);
      }
      setRewritingRow(null);
      setRewriteText('');
      alert('Rewrite saved as a correction!');
    } catch (err) {
      alert('Error saving rewrite: ' + err.message);
    } finally {
      setSavingRewrite(false);
    }
  };

  const items = useMemo(() => {
    let combined = [
      // AI batch entries (tester_verdict === 'ai_review') — LOW severity, distinct type
      ...flagged
        .filter(f => f.tester_verdict === 'ai_review')
        .map(f => ({ ...f, _type: 'ai_batch', _severity: 'LOW', _date: f.created_at || new Date().toISOString() })),
      // Human-flagged entries — MEDIUM severity
      ...flagged
        .filter(f => f.tester_verdict !== 'ai_review')
        .map(f => ({ ...f, _type: 'flagged', _severity: 'MEDIUM', _date: f.created_at || new Date().toISOString() })),
      // Negative feedback from real users — HIGH severity
      ...negativeFeedback.map(n => ({
        id: n.id,
        chat_id: n.chat_id,
        session_token: n.session_token,
        question: n.chats?.question,
        chatbot_answer: n.chats?.answer,
        tester_note: n.comment,
        _type: 'negative',
        _severity: 'HIGH',
        _date: n.submitted_at,
      })),
    ];

    if (filter === 'Flagged') combined = combined.filter(i => i._type === 'flagged');
    if (filter === 'Negative Feedback') combined = combined.filter(i => i._type === 'negative');

    combined.sort((a, b) => {
      if (a._severity === 'HIGH' && b._severity !== 'HIGH') return -1;
      if (b._severity === 'HIGH' && a._severity !== 'HIGH') return 1;
      return new Date(b._date).getTime() - new Date(a._date).getTime();
    });

    return combined;
  }, [flagged, negativeFeedback, filter]);

  // Border color per severity
  const borderColor = (item) => {
    if (item._severity === 'HIGH') return 'var(--danger)';
    if (item._severity === 'MEDIUM') return 'var(--orange)';
    return 'var(--moss)'; // LOW — ai_batch
  };

  return (
    <div className="fade-in tab-content-inner">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {['All', 'Flagged', 'Negative Feedback'].map(f => (
            <button
              key={f}
              className={`filter-chip ${filter === f ? 'active' : ''}`}
              onClick={() => setFilter(f)}
            >
              {f}
            </button>
          ))}
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            onClick={() => apiDownload('/api/admin/flagged-responses/export', `moderation_history_${new Date().toISOString().split('T')[0]}.csv`)}
            className="btn-dash"
            style={{
              fontSize: '12px',
              padding: '6px 12px',
              background: 'transparent',
              border: '1px solid var(--line-strong)',
              color: 'var(--ink)',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              cursor: 'pointer',
              borderRadius: '4px'
            }}
          >
            <Download size={12} />
            Export Moderation Logs
          </button>
          <button
            onClick={() => apiDownload('/api/admin/flagged-responses/export?reviewed_by=tester', `tester_moderation_history_${new Date().toISOString().split('T')[0]}.csv`)}
            className="btn-dash"
            style={{
              fontSize: '12px',
              padding: '6px 12px',
              background: 'transparent',
              border: '1px solid var(--line-strong)',
              color: 'var(--ink)',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              cursor: 'pointer',
              borderRadius: '4px'
            }}
          >
            <Download size={12} />
            Export Tester Logs
          </button>
        </div>
      </div>

      <div className="stack-list compact-stack">
        {items.map((item) => {
          const isExpanded = expandedRow === item.id;
          const rawAnswer = item.chatbot_answer || '';
          // Truncate on raw markdown (250 chars) so it works regardless of
          // whether the parsed HTML uses <p>, <ul>, <h3>, or any other tags.
          const PREVIEW_LIMIT = 250;
          const isLong = rawAnswer.length > PREVIEW_LIMIT;
          const parsedAnswer = parseAnswer(rawAnswer).bodyHtml;
          const parsedPreview = isLong
            ? parseAnswer(rawAnswer.slice(0, PREVIEW_LIMIT) + '...').bodyHtml
            : parsedAnswer;

          return (
            <article key={item.id} className="record-card compact-record" style={{ borderLeft: `4px solid ${borderColor(item)}` }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <span className={`severity-badge ${item._severity.toLowerCase()}`}>
                    {item._type === 'ai_batch' ? 'AI' : item._severity}
                  </span>
                  <span className="muted" style={{ fontSize: '11px' }}>{new Date(item._date).toLocaleString()}</span>
                </div>

                {/* Human-flagged: Approve / Rewrite / Reject */}
                {item._type === 'flagged' && (
                  <div className="action-links" style={{ display: 'flex', gap: '8px', fontSize: '12px' }}>
                    <button className="text-btn success" onClick={() => approveFlagged(item.id)}>Approve</button>
                    <button className="text-btn" style={{ color: 'var(--accent)' }} onClick={() => { setRewritingRow(item.id); setRewriteText(item.tester_answer_improved || item.tester_answer_raw || ''); }}>Rewrite</button>
                    <button className="text-btn danger" onClick={() => rejectFlagged(item.id)}>Reject</button>
                  </div>
                )}

                {/* AI batch: same actions — admin decides if the answer is good, needs rewriting, or is useless */}
                {item._type === 'ai_batch' && (
                  <div className="action-links" style={{ display: 'flex', gap: '8px', fontSize: '12px' }}>
                    <button className="text-btn success" onClick={() => approveFlagged(item.id)}>Approve</button>
                    <button className="text-btn" style={{ color: 'var(--accent)' }} onClick={() => { setRewritingRow(item.id); setRewriteText(''); }}>Rewrite</button>
                    <button className="text-btn danger" onClick={() => rejectFlagged(item.id)}>Reject</button>
                  </div>
                )}

                {/* Negative feedback: Rewrite + Delete (to dismiss spam/joke feedback) */}
                {item._type === 'negative' && (
                  <div className="action-links" style={{ display: 'flex', gap: '8px', fontSize: '12px' }}>
                    <button className="text-btn" style={{ color: 'var(--accent)' }} onClick={() => { setRewritingRow(item.id); setRewriteText(''); }}>Rewrite</button>
                    <button className="text-btn danger" onClick={() => deleteNegativeFeedback && deleteNegativeFeedback(item.id)}>Delete</button>
                  </div>
                )}
              </div>

              <p style={{ fontSize: '14px', fontWeight: 600, marginBottom: '6px' }}>{item.question}</p>

              <div style={{ background: 'rgba(0,0,0,0.02)', padding: '8px', borderRadius: '4px', fontSize: '13px', color: 'var(--ink)' }}>
                <strong style={{ color: 'var(--moss)', fontSize: '11px', textTransform: 'uppercase' }}>Bot Response</strong>
                <div
                  className="preview-html"
                  dangerouslySetInnerHTML={{ __html: isExpanded ? parsedAnswer : parsedPreview }}
                  style={{ marginTop: '4px', lineHeight: '1.4' }}
                />
                {isLong && (
                  <button
                    className="text-btn muted"
                    style={{ marginTop: '4px', fontSize: '11px' }}
                    onClick={() => setExpandedRow(isExpanded ? null : item.id)}
                  >
                    [{isExpanded ? 'Collapse' : 'Expand'}]
                  </button>
                )}
              </div>

              {/* Human-flagged corrections (only shown when expanded) */}
              {item._type === 'flagged' && isExpanded && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '6px' }}>
                  {item.tester_answer_raw && (
                    <div style={{ background: 'rgba(0,0,0,0.03)', padding: '8px', borderRadius: '4px', fontSize: '13px' }}>
                      <strong style={{ color: 'var(--accent)', fontSize: '11px', textTransform: 'uppercase' }}>Suggested Correction (Raw)</strong>
                      <div style={{ marginTop: '4px', whiteSpace: 'pre-wrap' }}>{item.tester_answer_raw}</div>
                    </div>
                  )}
                  {item.tester_answer_improved && (
                    <div style={{ background: 'rgba(197, 122, 31, 0.05)', padding: '8px', borderRadius: '4px', fontSize: '13px' }}>
                      <strong style={{ color: 'var(--accent)', fontSize: '11px', textTransform: 'uppercase' }}>Suggested Correction (AI Improved)</strong>
                      <div dangerouslySetInnerHTML={{ __html: parseAnswer(item.tester_answer_improved).bodyHtml }} style={{ marginTop: '4px' }} />
                    </div>
                  )}
                </div>
              )}

              {/* Rewrite inline editor */}
              {rewritingRow === item.id && (
                <div style={{ marginTop: '12px', padding: '12px', background: 'var(--paper)', border: '1px solid var(--accent)', borderRadius: '6px' }}>
                  <p style={{ fontSize: '12px', fontWeight: 600, color: 'var(--accent)', marginBottom: '8px' }}>Rewrite Answer (Saves as Correction)</p>
                  <textarea
                    value={rewriteText}
                    onChange={(e) => setRewriteText(e.target.value)}
                    rows={4}
                    className="admin-input"
                    style={{ width: '100%', fontSize: '13px', padding: '8px', marginBottom: '8px', fontFamily: 'inherit' }}
                    placeholder="Enter the correct markdown answer here..."
                  />
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button className="text-btn success" onClick={() => handleSaveRewrite(item)} disabled={savingRewrite}>{savingRewrite ? 'Saving...' : 'Save & Resolve'}</button>
                    <button className="text-btn muted" onClick={() => setRewritingRow(null)}>Cancel</button>
                  </div>
                </div>
              )}

              {(item.chat_id || item.session_token) && (
                <div style={{ 
                  marginTop: '8px', 
                  padding: '6px 10px', 
                  background: 'rgba(0,0,0,0.02)', 
                  border: '1px solid rgba(0,0,0,0.05)', 
                  borderRadius: '4px', 
                  fontSize: '11px', 
                  display: 'flex', 
                  flexDirection: 'column', 
                  gap: '4px',
                  fontFamily: 'monospace',
                  color: '#666' 
                }}>
                  {item.chat_id && (
                    <div>
                      <strong style={{ color: 'var(--ink)' }}>Chat ID:</strong>{' '}
                      <span style={{ userSelect: 'all', cursor: 'pointer' }} title="Click/Double-click to select all">{item.chat_id}</span>
                    </div>
                  )}
                  {item.session_token && (
                    <div>
                      <strong style={{ color: 'var(--ink)' }}>Session ID:</strong>{' '}
                      <span style={{ userSelect: 'all', cursor: 'pointer' }} title="Click/Double-click to select all">{item.session_token}</span>
                    </div>
                  )}
                </div>
              )}

              {item.tester_note && (
                <p style={{ marginTop: '6px', fontSize: '12px', color: 'var(--ink)' }}><strong>Note:</strong> {item.tester_note}</p>
              )}
            </article>
          );
        })}
        {!items.length && <div className="empty-state">No items in the moderation queue.</div>}
      </div>
    </div>
  );
}
