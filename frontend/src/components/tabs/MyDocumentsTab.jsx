import { useState, useEffect, useCallback, useRef } from 'react';
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
    padding: '6px 14px', borderRadius: '6px', border: 'none', cursor: 'pointer',
    fontSize: '12px', fontWeight: 600,
    background: variant === 'primary' ? 'var(--moss)' : 'var(--paper-muted)',
    color: variant === 'primary' ? '#fff' : 'inherit',
    opacity: variant === 'disabled' ? 0.5 : 1,
  }),
  badge: (status) => {
    const colors = {
      pending: { bg: 'rgba(245,158,11,0.15)', text: '#f59e0b', border: 'rgba(245,158,11,0.3)' },
      approved: { bg: 'rgba(16,185,129,0.15)', text: '#10b981', border: 'rgba(16,185,129,0.3)' },
      rejected: { bg: 'rgba(239,68,68,0.15)', text: '#ef4444', border: 'rgba(239,68,68,0.3)' },
      processed: { bg: 'rgba(16,185,129,0.15)', text: '#10b981', border: 'rgba(16,185,129,0.3)' },
      not_required: { bg: 'rgba(16,185,129,0.15)', text: '#10b981', border: 'rgba(16,185,129,0.3)' },
    };
    const c = colors[status] || colors.pending;
    return {
      display: 'inline-block', padding: '3px 10px', borderRadius: '12px',
      fontSize: '11px', fontWeight: 700, letterSpacing: '0.04em', textTransform: 'uppercase',
      background: c.bg, color: c.text, border: `1px solid ${c.border}`,
    };
  },
  uploadBox: {
    border: '2px dashed var(--line)', borderRadius: '12px', padding: '30px',
    textAlign: 'center', marginBottom: '24px', background: 'var(--paper)',
    transition: 'all 0.2s', cursor: 'pointer',
  },
};

export default function MyDocumentsTab({ userEmail }) {
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef(null);

  const headers = { 'X-User-Email': userEmail };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch('/api/upload/my-documents', { headers });
      setDocs(data.items || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [userEmail]);

  useEffect(() => { load(); }, [load]);

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', file.name);
    formData.append('source_type', 'file');

    try {
      const res = await fetch((import.meta.env.VITE_API_BASE_URL || '') + '/api/upload/submit', {
        method: 'POST',
        headers: { 'X-User-Email': userEmail },
        body: formData,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Upload failed');
      alert(data.message || 'Upload successful');
      await load();
    } catch (err) {
      alert(err.message);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleWithdraw = async (id) => {
    if (!window.confirm('Are you sure you want to withdraw this document?')) return;
    try {
      const res = await fetch((import.meta.env.VITE_API_BASE_URL || '') + `/api/upload/my-documents/${id}/withdraw`, {
        method: 'POST',
        headers: { 'X-User-Email': userEmail },
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Withdrawal failed');
      alert('Document withdrawn successfully');
      await load();
    } catch (err) {
      alert(err.message);
    }
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <h3 style={{ margin: 0 }}>My Uploaded Documents</h3>
      </div>

      <div
        style={{ ...styles.uploadBox, opacity: uploading ? 0.5 : 1 }}
        onClick={() => !uploading && fileInputRef.current?.click()}
      >
        <div style={{ fontSize: '24px', marginBottom: '8px' }}>📄</div>
        <div style={{ fontWeight: 600, fontSize: '15px' }}>Click to Upload Document</div>
        <div style={{ fontSize: '12px', opacity: 0.6, marginTop: '4px' }}>PDF, DOCX, TXT • Max 50MB</div>
        <input
          type="file"
          ref={fileInputRef}
          style={{ display: 'none' }}
          accept=".pdf,.docx,.doc,.txt,.csv,.json,.md"
          onChange={handleFileChange}
          disabled={uploading}
        />
        {uploading && <div style={{ marginTop: '12px', color: 'var(--moss)', fontWeight: 600, fontSize: '13px' }}>Uploading & processing...</div>}
      </div>

      {loading ? <p>Loading documents...</p> : (
        <table style={styles.table}>
          <thead>
            <tr>
              {['Document', 'Department', 'Size', 'Approval Status', 'Ingestion Status', 'Date', 'Actions'].map(h => (
                <th key={h} style={styles.th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {docs.length === 0 && (
              <tr><td colSpan={7} style={{ ...styles.td, textAlign: 'center', opacity: 0.5 }}>You haven't uploaded any documents yet.</td></tr>
            )}
            {docs.map(d => (
              <tr key={d.id}>
                <td style={styles.td}>
                  <div style={{ fontWeight: 600 }}>{d.display_title || d.filename}</div>
                  <div style={{ fontSize: '11px', opacity: 0.6, marginTop: '2px' }}>{d.filename}</div>
                </td>
                <td style={styles.td}>{d.department_name || '—'}</td>
                <td style={styles.td}>{Math.round(d.file_size_bytes / 1024)} KB</td>
                <td style={styles.td}>
                  <span style={styles.badge(d.approval_status)}>
                    {d.approval_status === 'not_required' ? 'Auto-Approved' : d.approval_status}
                  </span>
                  {d.approval_status === 'rejected' && d.rejection_reason && (
                    <div style={{ fontSize: '11px', color: '#ef4444', marginTop: '4px', maxWidth: '200px' }}>
                      Reason: {d.rejection_reason}
                    </div>
                  )}
                </td>
                <td style={styles.td}>
                  {d.status === 'processed' ? (
                    <span style={{ color: '#10b981', fontWeight: 600, fontSize: '12px' }}>✓ Ingested ({d.total_chunks} chunks)</span>
                  ) : d.status === 'pending' ? (
                    <span style={{ opacity: 0.6, fontSize: '12px' }}>Waiting...</span>
                  ) : d.status === 'rejected' ? (
                    <span style={{ color: '#ef4444', fontSize: '12px' }}>Cancelled</span>
                  ) : (
                    <span style={{ fontSize: '12px' }}>{d.status}</span>
                  )}
                </td>
                <td style={styles.td} title={d.created_at}>{d.created_at ? new Date(d.created_at).toLocaleDateString() : '—'}</td>
                <td style={styles.td}>
                  {d.approval_status === 'pending' && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleWithdraw(d.id);
                      }}
                      style={{
                        padding: '4px 8px',
                        backgroundColor: '#fee2e2',
                        color: '#991b1b',
                        border: '1px solid #fca5a5',
                        borderRadius: '4px',
                        cursor: 'pointer',
                        fontSize: '11px',
                        fontWeight: '600',
                      }}
                    >
                      Withdraw
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
