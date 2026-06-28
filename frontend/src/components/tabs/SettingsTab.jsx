import { useState, useEffect, useCallback } from 'react';
import { apiFetch } from '../../utils/api';

const styles = {
  card: {
    background: 'var(--paper)', borderRadius: '12px', padding: '24px',
    boxShadow: '0 4px 20px rgba(0,0,0,0.05)', marginBottom: '24px',
  },
  title: { margin: '0 0 16px 0', fontSize: '18px', fontWeight: 600 },
  row: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' },
  desc: { fontSize: '13px', opacity: 0.7, maxWidth: '600px', lineHeight: 1.5, marginTop: '4px' },
  btn: (variant = 'primary') => ({
    padding: '8px 16px', borderRadius: '6px', border: 'none', cursor: 'pointer',
    fontSize: '13px', fontWeight: 600,
    background: variant === 'primary' ? 'var(--moss)' : 'var(--paper-muted)',
    color: variant === 'primary' ? '#fff' : 'inherit',
    transition: 'opacity 0.2s', opacity: 1,
  }),
  textarea: {
    width: '100%', padding: '12px', borderRadius: '8px', minHeight: '180px',
    border: '1px solid var(--line)', background: '#fff', fontSize: '13px',
    boxSizing: 'border-box', resize: 'vertical', fontFamily: 'monospace',
    lineHeight: 1.5,
  },
  toggleTrack: (on) => ({
    width: '44px', height: '24px', borderRadius: '12px',
    background: on ? '#10b981' : '#e5e7eb',
    position: 'relative', cursor: 'pointer', transition: 'background 0.3s',
  }),
  toggleThumb: (on) => ({
    width: '20px', height: '20px', borderRadius: '50%', background: '#fff',
    position: 'absolute', top: '2px', left: on ? '22px' : '2px',
    transition: 'left 0.3s', boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
  })
};

export default function SettingsTab({ userEmail }) {
  const [settings, setSettings] = useState({ require_document_approval: true, system_prompt: '' });
  const [loading, setLoading] = useState(true);
  const [savingPrompt, setSavingPrompt] = useState(false);
  const [msg, setMsg] = useState({ type: '', text: '' });

  const headers = { 'X-User-Email': userEmail };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch('/api/admin/rbac/settings', { headers });
      setSettings(data);
    } catch (e) {
      console.error(e);
      setMsg({ type: 'error', text: 'Failed to load settings.' });
    } finally {
      setLoading(false);
    }
  }, [userEmail]);

  useEffect(() => { load(); }, [load]);

  const toggleApproval = async () => {
    const newVal = !settings.require_document_approval;
    // Optimistic update
    setSettings(s => ({ ...s, require_document_approval: newVal }));
    try {
      await apiFetch('/api/admin/rbac/settings/require_document_approval', {
        method: 'PUT', headers,
        body: JSON.stringify({ value: newVal ? 'true' : 'false' }),
      });
    } catch (e) {
      alert('Failed to update setting: ' + e.message);
      setSettings(s => ({ ...s, require_document_approval: !newVal })); // revert
    }
  };

  const savePrompt = async () => {
    setSavingPrompt(true);
    setMsg({ type: '', text: '' });
    try {
      await apiFetch('/api/admin/rbac/settings/system_prompt', {
        method: 'PUT', headers,
        body: JSON.stringify({ value: settings.system_prompt }),
      });
      setMsg({ type: 'success', text: 'System prompt updated successfully. Cache invalidated.' });
    } catch (e) {
      setMsg({ type: 'error', text: 'Failed to update prompt: ' + e.message });
    } finally {
      setSavingPrompt(false);
    }
  };

  if (loading) return <p>Loading settings...</p>;

  return (
    <div>
      <div style={styles.card}>
        <div style={styles.row}>
          <div>
            <div style={{ fontWeight: 600, fontSize: '15px' }}>Require Document Approval</div>
            <div style={styles.desc}>
              When enabled, documents uploaded by Department Admins will be held in a pending state until a Super Admin approves them. 
              If disabled, uploads will immediately be ingested into the vector database.
            </div>
          </div>
          <div style={styles.toggleTrack(settings.require_document_approval)} onClick={toggleApproval}>
            <div style={styles.toggleThumb(settings.require_document_approval)} />
          </div>
        </div>
      </div>

      <div style={styles.card}>
        <h3 style={styles.title}>System Prompt</h3>
        <div style={{ ...styles.desc, marginBottom: '16px' }}>
          This is the core instruction set given to the AI. Be careful when modifying this, as it deeply affects how the chatbot answers questions and formats its responses.
        </div>
        <textarea
          style={styles.textarea}
          value={settings.system_prompt}
          onChange={(e) => setSettings(s => ({ ...s, system_prompt: e.target.value }))}
        />
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '16px' }}>
          <div style={{ fontSize: '13px', color: msg.type === 'error' ? '#ef4444' : '#10b981', fontWeight: 600 }}>
            {msg.text}
          </div>
          <button style={styles.btn()} onClick={savePrompt} disabled={savingPrompt}>
            {savingPrompt ? 'Saving...' : 'Save System Prompt'}
          </button>
        </div>
      </div>
    </div>
  );
}
