import { useState } from 'react';
import { apiFetch, apiDownload } from '../../utils/api';
import { parseAnswer } from '../../utils/formatters';
import { Edit3, Download } from 'lucide-react';

export function CorrectionsTab({ corrections, refetch }) {
  return (
    <div className="fade-in tab-content-inner dashboard-main-grid" style={{ gridTemplateColumns: '1fr 2fr' }}>
      <div className="panel compact-panel">
        <div className="panel-header" style={{ padding: '12px' }}>
          <h3 style={{ fontSize: '14px' }}><Edit3 size={14} style={{ marginRight: 6, verticalAlign: 'middle' }} /> Quick Overwrite</h3>
        </div>
        <QuickOverwriteForm onSaved={refetch} />
      </div>
      
      <div className="panel compact-panel">
        <div className="panel-header" style={{ padding: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ fontSize: '14px', margin: 0 }}>Active Approved Corrections</h3>
          <button
            onClick={() => apiDownload('/api/admin/corrections/export', `corrections_${new Date().toISOString().split('T')[0]}.csv`)}
            className="btn-dash"
            style={{
              fontSize: '12px',
              padding: '4px 8px',
              background: 'transparent',
              border: '1px solid var(--line-strong)',
              color: 'var(--ink)',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              cursor: 'pointer'
            }}
          >
            <Download size={12} />
            Export CSV
          </button>
        </div>
        <div className="stack-list compact-stack" style={{ padding: '12px' }}>
          {corrections.map((item) => (
            <CorrectionCard key={item.id} item={item} onUpdated={refetch} />
          ))}
          {!corrections.length && <div className="empty-state">No approved corrections active yet.</div>}
        </div>
      </div>
    </div>
  );
}

function QuickOverwriteForm({ onSaved }) {
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');

  const submit = async () => {
    if (!question.trim() || !answer.trim()) return;
    setSaving(true);
    setMsg('');
    try {
      const data = await apiFetch('/api/admin/corrections/direct', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Admin-User': 'dashboard-admin' },
        body: JSON.stringify({ question, corrected_answer: answer, admin_note: 'Quick overwrite from ops center' }),
      });
      setMsg(`\u2705 ${data.result?.mode === 'updated' ? 'Updated' : 'Created'} correction.`);
      setQuestion('');
      setAnswer('');
      if (onSaved) onSaved();
    } catch (err) {
      setMsg(`\u274c ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ padding: '12px', background: 'rgba(197, 122, 31, 0.04)', borderTop: '1px solid var(--line)' }}>
      <p className="muted" style={{ fontSize: '12px', marginBottom: '8px', lineHeight: '1.4' }}>
        Force the chatbot to return this exact answer for this specific question.
      </p>
      <div style={{ display: 'grid', gap: '8px' }}>
        <input
          type="text"
          placeholder="Exact Question..."
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          className="admin-input"
          style={{ padding: '8px', fontSize: '13px' }}
        />
        <textarea
          placeholder="Desired Answer (Markdown supported)..."
          rows={5}
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          className="admin-input"
          style={{ padding: '8px', fontSize: '13px', resize: 'vertical' }}
        />
        <button type="button" onClick={submit} disabled={saving} className="btn-dash" style={{ background: 'var(--accent)', color: '#fff', padding: '8px', width: '100%' }}>
          {saving ? 'Saving...' : 'Save Overwrite'}
        </button>
      </div>
      {msg && <div style={{ marginTop: '8px', fontSize: '12px', color: msg.includes('\u274c') ? 'var(--danger)' : 'var(--moss)' }}>{msg}</div>}
    </div>
  );
}

function CorrectionCard({ item, onUpdated }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(item.corrected_answer || '');
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      await apiFetch(`/api/admin/corrections/${item.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'X-Admin-User': 'dashboard-admin' },
        body: JSON.stringify({ corrected_answer: text }),
      });
      setEditing(false);
      if (onUpdated) onUpdated();
    } catch (err) {
      alert(`Error saving: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const del = async () => {
    if (!window.confirm('Delete this correction? It will no longer be applied.')) return;
    try {
      await apiFetch(`/api/admin/corrections/${item.id}`, {
        method: 'DELETE',
        headers: { 'X-Admin-User': 'dashboard-admin' },
      });
      if (onUpdated) onUpdated();
    } catch (err) {
      alert(`Error deleting: ${err.message}`);
    }
  };

  return (
    <article className="record-card compact-record" style={{ padding: '12px', background: 'var(--paper)', border: '1px solid var(--line)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
        <p style={{ fontSize: '13px', fontWeight: 600, color: 'var(--ink)' }}>{item.question}</p>
        <span className="muted" style={{ fontSize: '11px', whiteSpace: 'nowrap', marginLeft: '12px' }}>
          {new Date(item.created_at).toLocaleDateString()}
        </span>
      </div>
      {editing ? (
        <div style={{ marginTop: '8px' }}>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={4}
            className="admin-input"
            style={{ width: '100%', fontSize: '13px', padding: '8px', marginBottom: '8px' }}
          />
          <div style={{ display: 'flex', gap: '8px' }}>
            <button className="text-btn success" onClick={save} disabled={saving}>{saving ? '...' : 'Save'}</button>
            <button className="text-btn muted" onClick={() => setEditing(false)}>Cancel</button>
          </div>
        </div>
      ) : (
        <>
          <div style={{ fontSize: '13px', color: 'var(--ink)', lineHeight: '1.5', background: 'rgba(0,0,0,0.02)', padding: '8px', borderRadius: '4px', marginTop: '4px' }} dangerouslySetInnerHTML={{ __html: parseAnswer(item.corrected_answer).bodyHtml }} />
          <div style={{ display: 'flex', gap: '12px', marginTop: '8px' }}>
            <button className="text-btn" style={{ fontSize: '11px', color: 'var(--moss)' }} onClick={() => setEditing(true)}>Edit</button>
            <button className="text-btn" style={{ fontSize: '11px', color: 'var(--danger)' }} onClick={del}>Remove</button>
          </div>
        </>
      )}
    </article>
  );
}
