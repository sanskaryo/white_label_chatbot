import { useState, useEffect, useCallback } from 'react';
import { apiFetch } from '../../utils/api';

const styles = {
  badge: (role) => ({
    display: 'inline-block',
    padding: '2px 10px',
    borderRadius: '12px',
    fontSize: '11px',
    fontWeight: 700,
    letterSpacing: '0.04em',
    textTransform: 'uppercase',
    background: role === 'super_admin' ? 'rgba(99,102,241,0.15)' : 'rgba(16,185,129,0.15)',
    color: role === 'super_admin' ? '#6366f1' : '#10b981',
    border: `1px solid ${role === 'super_admin' ? 'rgba(99,102,241,0.3)' : 'rgba(16,185,129,0.3)'}`,
  }),
  table: {
    width: '100%', borderCollapse: 'collapse', fontSize: '13px',
  },
  th: {
    textAlign: 'left', padding: '10px 12px', fontSize: '11px', fontWeight: 700,
    textTransform: 'uppercase', letterSpacing: '0.06em', opacity: 0.6,
    borderBottom: '1px solid var(--line)',
  },
  td: {
    padding: '12px 12px', borderBottom: '1px solid rgba(0,0,0,0.05)', verticalAlign: 'middle',
  },
  btn: (variant = 'default') => ({
    padding: '5px 14px', borderRadius: '6px', border: 'none', cursor: 'pointer',
    fontSize: '12px', fontWeight: 600,
    background: variant === 'danger' ? '#ef4444' : variant === 'primary' ? 'var(--moss)' : 'var(--paper-muted)',
    color: variant === 'danger' || variant === 'primary' ? '#fff' : 'inherit',
  }),
  modal: {
    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
    display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
  },
  modalBox: {
    background: 'var(--paper)', borderRadius: '12px', padding: '24px',
    width: '480px', maxWidth: '95vw', boxShadow: '0 20px 60px rgba(0,0,0,0.25)',
  },
  input: {
    width: '100%', padding: '9px 12px', borderRadius: '8px',
    border: '1px solid var(--line)', background: '#fff', fontSize: '14px',
    boxSizing: 'border-box',
  },
  label: { fontSize: '13px', fontWeight: 600, display: 'block', marginBottom: '6px' },
};

const EMPTY_FORM = { email: '', password: '', role: 'dept_admin', department_id: '', full_name: '' };

const formatDateToIST = (dateStr) => {
  if (!dateStr) return '';
  try {
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return dateStr;
    const formatter = new Intl.DateTimeFormat('en-US', {
      timeZone: 'Asia/Kolkata',
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
      hour12: true
    });
    const parts = formatter.formatToParts(date);
    const p = {};
    parts.forEach(part => {
      p[part.type] = part.value;
    });
    const ampmPart = parts.find(part => ['dayperiod', 'ampm'].includes(part.type.toLowerCase()));
    const ampm = ampmPart ? ampmPart.value : '';
    return `${p.year}-${p.month}-${p.day} ${p.hour}:${p.minute}:${p.second} ${ampm}`.trim();
  } catch (e) {
    return dateStr;
  }
};

export default function UsersTab({ userEmail }) {
  const [users, setUsers] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [modal, setModal] = useState(null); // null | 'create' | {user}
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');

  const headers = { 'X-User-Email': userEmail };

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [ud, dd] = await Promise.all([
        apiFetch('/api/admin/rbac/users?active_only=false', { headers }),
        apiFetch('/api/admin/rbac/departments', { headers }),
      ]);
      setUsers(ud.items || []);
      const deptList = [];
      (dd.institutes || []).forEach(inst =>
        (inst.departments || []).forEach(d => deptList.push(d))
      );
      setDepartments(deptList);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [userEmail]);

  useEffect(() => { load(); }, [load]);

  
  const exportCSV = () => {
    const csvRows = [];
    csvRows.push(['ID', 'Name', 'Email', 'Role', 'Department', 'Status', 'Created At'].join(','));
    users.filter(u => u.role !== 'super_admin').forEach(u => {
      const row = [
        u.id,
        `"${(u.full_name || '').replace(/"/g, '""')}"`,
        `"${u.email}"`,
        u.role,
        `"${(u.department_name || '').replace(/"/g, '""')}"`,
        u.is_active ? 'Active' : 'Inactive',
        u.created_at ? formatDateToIST(u.created_at) : ''
      ];
      csvRows.push(row.join(','));
    });
    const blob = new Blob([csvRows.join('\n')], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'users_export.csv';
    a.click();
    window.URL.revokeObjectURL(url);
  };

  const openCreate = () => { setForm(EMPTY_FORM); setModal('create'); setMsg(''); };

  const openEdit = (u) => {
    setForm({ email: u.email, role: u.role, department_id: u.department_id || '', full_name: u.full_name || '' });
    setModal(u);
    setMsg('');
  };

  const save = async () => {
    setSaving(true);
    setMsg('');
    try {
      if (modal === 'create') {
        await apiFetch('/api/admin/rbac/users', {
          method: 'POST',
          headers: { ...headers, 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: form.email, role: form.role,
            department_id: form.department_id ? parseInt(form.department_id) : null,
            full_name: form.full_name || null,
            password: form.password || undefined,
          }),
        });
        setMsg('User created successfully.');
      } else {
        await apiFetch('/api/admin/rbac/users/' + modal.id, {
          method: 'PUT',
          headers: { ...headers, 'Content-Type': 'application/json' },
          body: JSON.stringify({
            role: form.role,
            department_id: form.department_id ? parseInt(form.department_id) : null,
            full_name: form.full_name || null,
            password: form.password || undefined,
          }),
        });
        setMsg('User updated.');
      }
      await load();
      setModal(null);
    } catch (e) {
      setMsg('Error: ' + e.message);
    } finally {
      setSaving(false);
    }
  };

  
  const hardDelete = async (userId) => {
    if (!confirm('Permanently delete this user? This action cannot be undone.')) return;
    try {
      await apiFetch('/api/admin/rbac/users/' + userId + '/hard', { method: 'DELETE', headers });
      await load();
    } catch (e) {
      alert('Error: ' + e.message);
    }
  };

  const deactivate = async (userId) => {
    if (!confirm('Deactivate this user?')) return;
    try {
      await apiFetch('/api/admin/rbac/users/' + userId, { method: 'DELETE', headers });
      await load();
    } catch (e) {
      alert('Error: ' + e.message);
    }
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <h3 style={{ margin: 0 }}>Admin Users</h3>
        <div style={{ display: 'flex', gap: '10px' }}><button onClick={exportCSV} style={styles.btn()}>Export CSV</button><button onClick={openCreate} style={styles.btn('primary')}>+ Add User</button></div>
      </div>

      {error && <p style={{ color: '#ef4444' }}>{error}</p>}

      {loading ? <p>Loading...</p> : (
        <table style={styles.table}>
          <thead>
            <tr>
              {['Name / Email', 'Role', 'Department', 'Created', 'Actions'].map(h => (
                <th key={h} style={styles.th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {users.filter(u => u.role !== 'super_admin').length === 0 && (
              <tr><td colSpan={5} style={{ ...styles.td, textAlign: 'center', opacity: 0.5 }}>No users yet</td></tr>
            )}
            {users.filter(u => u.role !== 'super_admin').map(u => (
              <tr key={u.id}>
                <td style={styles.td}>
                  <div style={{ fontWeight: 600 }}>{u.full_name || '—'}</div>
                  <div style={{ fontSize: '12px', opacity: 0.6 }}>{u.email}</div>
                </td>
                <td style={styles.td}><span style={styles.badge(u.role)}>{u.role === 'super_admin' ? 'Super Admin' : 'Dept Admin'}</span>{!u.is_active && <span style={{ ...styles.badge(''), marginLeft: '8px', background: '#fee2e2', color: '#ef4444', borderColor: '#fca5a5' }}>Inactive</span>}</td>
                <td style={styles.td}>{u.department_name || <span style={{ opacity: 0.4 }}>—</span>}</td>
                <td style={styles.td} title={u.created_at}>{u.created_at ? new Date(u.created_at).toLocaleDateString() : '—'}</td>
                <td style={styles.td}>
                  <div style={{ display: 'flex', gap: '6px' }}>
                    <button onClick={() => openEdit(u)} style={styles.btn()}>Edit</button>
                    <button onClick={() => deactivate(u.id)} style={styles.btn('danger')}>Deactivate</button><button onClick={() => hardDelete(u.id)} style={{ ...styles.btn('danger'), background: '#991b1b' }}>Delete</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {modal && (
        <div style={styles.modal} onClick={() => setModal(null)}>
          <div style={styles.modalBox} onClick={e => e.stopPropagation()}>
            <h3 style={{ marginTop: 0 }}>{modal === 'create' ? 'Add Admin User' : 'Edit User'}</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {modal === 'create' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                  <div>
                    <label style={styles.label}>Email *</label>
                    <input style={styles.input} type="email" value={form.email}
                      onChange={e => setForm(f => ({ ...f, email: e.target.value }))} placeholder="user@example.com" />
                  </div>
                  <div>
                    <label style={styles.label}>Password * <span style={{fontWeight: 'normal', opacity: 0.6}}>(Supabase Auth)</span></label>
                    <input style={styles.input} type="text" value={form.password}
                      onChange={e => setForm(f => ({ ...f, password: e.target.value }))} placeholder="Secret Password" />
                  </div>
                </div>
              )}
              <div>
                <label style={styles.label}>Full Name</label>
                <input style={styles.input} value={form.full_name}
                  onChange={e => setForm(f => ({ ...f, full_name: e.target.value }))} placeholder="Dr. Jane Doe" />
              </div>
              <div>
                <label style={styles.label}>Role *</label>
                <select style={{ ...styles.input }} value={form.role}
                  onChange={e => setForm(f => ({ ...f, role: e.target.value }))}>
                  <option value="dept_admin">Department Admin</option>
                </select>
              </div>
              {form.role === 'dept_admin' && (
                <div>
                  <label style={styles.label}>Department *</label>
                  <select style={{ ...styles.input }} value={form.department_id}
                    onChange={e => setForm(f => ({ ...f, department_id: e.target.value }))}>
                    <option value="">— Select Department —</option>
                    {departments.map(d => (
                      <option key={d.id} value={d.id}>{d.department_name} ({d.institute_name})</option>
                    ))}
                  </select>
                </div>
              )}
            </div>
            {msg && <p style={{ color: msg.startsWith('Error') ? '#ef4444' : '#10b981', margin: '12px 0 0' }}>{msg}</p>}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '20px' }}>
              <button onClick={() => setModal(null)} style={styles.btn()}>Cancel</button>
              <button onClick={save} disabled={saving} style={styles.btn('primary')}>
                {saving ? 'Saving...' : modal === 'create' ? 'Create User' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
