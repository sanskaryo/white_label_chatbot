import { useState, useEffect, useCallback } from 'react';
import { apiFetch } from '../../utils/api';

const styles = {
  table: { width: '100%', borderCollapse: 'collapse', fontSize: '13px' },
  th: {
    textAlign: 'left', padding: '10px 12px', fontSize: '11px', fontWeight: 700,
    textTransform: 'uppercase', letterSpacing: '0.06em', opacity: 0.6,
    borderBottom: '1px solid var(--line)',
  },
  td: { padding: '12px 12px', borderBottom: '1px solid rgba(0,0,0,0.05)', verticalAlign: 'middle' },
  btn: (variant = 'default') => ({
    padding: '5px 14px', borderRadius: '6px', border: 'none', cursor: 'pointer',
    fontSize: '12px', fontWeight: 600,
    background: variant === 'danger' ? '#ef4444' : variant === 'primary' ? 'var(--moss)' : 'var(--paper-muted)',
    color: variant === 'danger' || variant === 'primary' ? '#fff' : 'inherit',
  }),
  badge: (active) => ({
    display: 'inline-block', padding: '2px 10px', borderRadius: '12px',
    fontSize: '11px', fontWeight: 700, letterSpacing: '0.04em',
    background: active ? 'rgba(16,185,129,0.12)' : 'rgba(239,68,68,0.12)',
    color: active ? '#10b981' : '#ef4444',
    border: `1px solid ${active ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'}`,
  }),
  modal: {
    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
    display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
  },
  modalBox: {
    background: 'var(--paper)', borderRadius: '12px', padding: '24px',
    width: '440px', maxWidth: '95vw', boxShadow: '0 20px 60px rgba(0,0,0,0.25)',
  },
  input: {
    width: '100%', padding: '9px 12px', borderRadius: '8px',
    border: '1px solid var(--line)', background: '#fff', fontSize: '14px',
    boxSizing: 'border-box',
  },
  label: { fontSize: '13px', fontWeight: 600, display: 'block', marginBottom: '6px' },
};

export default function DepartmentsTab({ userEmail }) {
  const [institutes, setInstitutes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [modal, setModal] = useState(false);
  const [form, setForm] = useState({ institute_name: '', department_name: '' });
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');

  const headers = { 'X-User-Email': userEmail };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch('/api/admin/rbac/departments?active_only=false', { headers });
      setInstitutes(data.institutes || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [userEmail]);

  useEffect(() => { load(); }, [load]);

  const toggle = async (dept, active) => {
    try {
      await apiFetch('/api/admin/rbac/departments/' + dept.id + '/toggle?active=' + active, {
        method: 'PUT', headers,
      });
      await load();
    } catch (e) {
      alert('Error: ' + e.message);
    }
  };

  const create = async () => {
    setSaving(true);
    setMsg('');
    try {
      await apiFetch('/api/admin/rbac/departments', {
        method: 'POST',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({ institute_name: form.institute_name, department_name: form.department_name }),
      });
      setMsg('Department created!');
      await load();
      setModal(false);
    } catch (e) {
      setMsg('Error: ' + e.message);
    } finally {
      setSaving(false);
    }
  };

  // Flatten all departments for the table
  const allDepts = [];
  institutes.forEach(inst =>
    (inst.departments || []).forEach(d => allDepts.push({ ...d, institute_name: inst.institute_name }))
  );

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <h3 style={{ margin: 0 }}>Departments</h3>
        <button onClick={() => { setModal(true); setForm({ institute_name: '', department_name: '' }); setMsg(''); }}
          style={styles.btn('primary')}>+ Add Department</button>
      </div>

      {error && <p style={{ color: '#ef4444' }}>{error}</p>}

      {loading ? <p>Loading...</p> : (
        <table style={styles.table}>
          <thead>
            <tr>
              {['Department', 'Institute', 'Slug', 'Status', 'Actions'].map(h => (
                <th key={h} style={styles.th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {allDepts.length === 0 && (
              <tr><td colSpan={5} style={{ ...styles.td, textAlign: 'center', opacity: 0.5 }}>No departments</td></tr>
            )}
            {allDepts.map(d => (
              <tr key={d.id}>
                <td style={styles.td}><strong>{d.department_name}</strong></td>
                <td style={styles.td} title={d.institute_name}>{d.institute_name}</td>
                <td style={styles.td}><code style={{ fontSize: '11px', opacity: 0.7 }}>{d.department_slug}</code></td>
                <td style={styles.td}><span style={styles.badge(d.is_active)}>{d.is_active ? 'Active' : 'Inactive'}</span></td>
                <td style={styles.td}>
                  <button
                    onClick={() => toggle(d, !d.is_active)}
                    style={styles.btn(d.is_active ? 'danger' : 'primary')}
                  >
                    {d.is_active ? 'Deactivate' : 'Reactivate'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {modal && (
        <div style={styles.modal} onClick={() => setModal(false)}>
          <div style={styles.modalBox} onClick={e => e.stopPropagation()}>
            <h3 style={{ marginTop: 0 }}>Add Department</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={styles.label}>Institute Name *</label>
                <input style={styles.input} value={form.institute_name}
                  onChange={e => setForm(f => ({ ...f, institute_name: e.target.value }))}
                  placeholder="e.g. Institute of Engineering" />
              </div>
              <div>
                <label style={styles.label}>Department Name *</label>
                <input style={styles.input} value={form.department_name}
                  onChange={e => setForm(f => ({ ...f, department_name: e.target.value }))}
                  placeholder="e.g. Computer Science & Engineering" />
              </div>
            </div>
            {msg && <p style={{ color: msg.startsWith('Error') ? '#ef4444' : '#10b981', margin: '12px 0 0' }}>{msg}</p>}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '20px' }}>
              <button onClick={() => setModal(false)} style={styles.btn()}>Cancel</button>
              <button onClick={create} disabled={saving} style={styles.btn('primary')}>
                {saving ? 'Creating...' : 'Create Department'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
