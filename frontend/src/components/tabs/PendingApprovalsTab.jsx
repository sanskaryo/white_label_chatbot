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
    padding: '6px 14px', borderRadius: '6px', border: 'none', cursor: 'pointer',
    fontSize: '12px', fontWeight: 600,
    background: variant === 'danger' ? '#ef4444' : variant === 'primary' ? 'var(--moss)' : 'var(--paper-muted)',
    color: variant === 'danger' || variant === 'primary' ? '#fff' : 'inherit',
    opacity: variant === 'disabled' ? 0.5 : 1,
  }),
  badge: (status) => {
    const colors = {
      pending: { bg: 'rgba(245,158,11,0.15)', text: '#f59e0b', border: 'rgba(245,158,11,0.3)' },
      approved: { bg: 'rgba(16,185,129,0.15)', text: '#10b981', border: 'rgba(16,185,129,0.3)' },
      rejected: { bg: 'rgba(239,68,68,0.15)', text: '#ef4444', border: 'rgba(239,68,68,0.3)' },
    };
    const c = colors[status] || colors.pending;
    return {
      display: 'inline-block', padding: '3px 10px', borderRadius: '12px',
      fontSize: '11px', fontWeight: 700, letterSpacing: '0.04em', textTransform: 'uppercase',
      background: c.bg, color: c.text, border: `1px solid ${c.border}`,
    };
  },
  modal: {
    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
    display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
  },
  modalBox: {
    background: 'var(--paper)', borderRadius: '12px', padding: '24px',
    width: '500px', maxWidth: '95vw', boxShadow: '0 20px 60px rgba(0,0,0,0.25)',
  },
  textarea: {
    width: '100%', padding: '10px 12px', borderRadius: '8px', minHeight: '100px',
    border: '1px solid var(--line)', background: '#fff', fontSize: '14px',
    boxSizing: 'border-box', resize: 'vertical', fontFamily: 'inherit',
  },
};

export default function PendingApprovalsTab({ userEmail }) {
  const [docs, setDocs] = useState([]);
  const [counts, setCounts] = useState({ pending: 0, approved: 0, rejected: 0 });
  const [statusFilter, setStatusFilter] = useState('pending');
  const [loading, setLoading] = useState(true);
  const [actioning, setActioning] = useState(null); // id of doc being processed

  const [rejectModal, setRejectModal] = useState(null); // doc object
  const [rejectReason, setRejectReason] = useState('');
  
  const [viewModal, setViewModal] = useState(null);
  const [viewContent, setViewContent] = useState('');
  const [viewLoading, setViewLoading] = useState(false);


  const headers = { 'X-User-Email': userEmail };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch(`/api/upload/pending?status=${statusFilter}`, { headers });
      setDocs(data.items || []);
      if (data.counts) setCounts(data.counts);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, userEmail]);

  useEffect(() => { load(); }, [load]);

  const viewDocument = async (doc) => {
    setViewModal(doc);
    setViewLoading(true);
    setViewContent('');
    try {
      const data = await apiFetch(`/api/upload/pending/${doc.id}/content`, { headers });
      setViewContent(data.content || 'No readable text content.');
    } catch (e) {
      setViewContent('Error loading content: ' + e.message);
    } finally {
      setViewLoading(false);
    }
  };

  const approve = async (doc) => {
    if (!confirm(`Approve "${doc.filename}" for ingestion?`)) return;
    setActioning(doc.id);
    try {
      await apiFetch(`/api/upload/pending/${doc.id}/approve`, { method: 'POST', headers });
      await load();
    } catch (e) {
      alert('Error approving document: ' + e.message);
    } finally {
      setActioning(null);
    }
  };

  const submitReject = async () => {
    setActioning(rejectModal.id);
    try {
      await apiFetch(`/api/upload/pending/${rejectModal.id}/reject`, {
        method: 'POST', headers,
        body: JSON.stringify({ reason: rejectReason }),
      });
      setRejectModal(null);
      await load();
    } catch (e) {
      alert('Error rejecting document: ' + e.message);
    } finally {
      setActioning(null);
    }
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <h3 style={{ margin: 0 }}>Document Approvals</h3>
        <div style={{ display: 'flex', gap: '8px', background: 'var(--paper-muted)', padding: '4px', borderRadius: '8px' }}>
          {['pending', 'approved', 'rejected'].map(s => (
            <button key={s} onClick={() => setStatusFilter(s)}
              style={{
                padding: '6px 14px', borderRadius: '6px', border: 'none', cursor: 'pointer',
                fontSize: '12px', fontWeight: 600, textTransform: 'capitalize',
                background: statusFilter === s ? 'var(--paper)' : 'transparent',
                boxShadow: statusFilter === s ? '0 2px 8px rgba(0,0,0,0.05)' : 'none',
                color: statusFilter === s ? 'var(--text)' : 'var(--text-muted)',
              }}>
              {s} ({counts[s] || 0})
            </button>
          ))}
        </div>
      </div>

      {loading ? <p>Loading documents...</p> : (
        <table style={styles.table}>
          <thead>
            <tr>
              {['Document', 'Department', 'Uploader', 'Size', 'Status', 'Actions'].map(h => (
                <th key={h} style={styles.th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {docs.length === 0 && (
              <tr><td colSpan={6} style={{ ...styles.td, textAlign: 'center', opacity: 0.5 }}>No {statusFilter} documents found.</td></tr>
            )}
            {docs.map(d => (
              <tr key={d.id}>
                <td style={styles.td}>
                  <div style={{ fontWeight: 600 }}>{d.display_title || d.filename}</div>
                  <div style={{ fontSize: '11px', opacity: 0.6, marginTop: '2px' }}>{d.filename}</div>
                </td>
                <td style={styles.td}>{d.department_name || 'General'}</td>
                <td style={styles.td}>
                  <div style={{ fontSize: '13px' }}>{d.submitted_by_name || d.submitted_by_email}</div>
                  {d.submitted_by_name && <div style={{ fontSize: '11px', opacity: 0.6 }}>{d.submitted_by_email}</div>}
                </td>
                <td style={styles.td}>{Math.round(d.file_size_bytes / 1024)} KB</td>
                <td style={styles.td}><span style={styles.badge(d.status)}>{d.status}</span></td>
                <td style={styles.td}>
                  {d.status === 'pending' ? (

                    <div style={{ display: 'flex', gap: '8px' }}>
                      <button onClick={() => viewDocument(d)} style={styles.btn()}>
                        View
                      </button>
                      <button onClick={() => approve(d)} disabled={actioning === d.id} style={styles.btn(actioning === d.id ? 'disabled' : 'primary')}>
                        {actioning === d.id ? 'Processing...' : 'Approve'}
                      </button>
                      <button onClick={() => { setRejectModal(d); setRejectReason(''); }} disabled={actioning === d.id} style={styles.btn('danger')}>
                        Reject
                      </button>
                    </div>

                  ) : (
                    <span style={{ fontSize: '12px', opacity: 0.6 }}>
                      {d.status === 'approved' ? 'Ingested' : d.rejection_reason ? `Reason: ${d.rejection_reason}` : 'Rejected'}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}


      {viewModal && (
        <div style={styles.modal} onClick={() => setViewModal(null)}>
          <div style={{ ...styles.modalBox, width: '700px', maxWidth: '90vw', maxHeight: '90vh', display: 'flex', flexDirection: 'column' }} onClick={e => e.stopPropagation()}>
            <h3 style={{ marginTop: 0 }}>Viewing: {viewModal.filename}</h3>
            <div style={{ flex: 1, overflowY: 'auto', background: 'var(--paper-muted)', padding: '16px', borderRadius: '8px', fontSize: '14px', whiteSpace: 'pre-wrap', border: '1px solid var(--line)', marginBottom: '20px', minHeight: '200px' }}>
              {viewLoading ? 'Loading document text...' : viewContent}
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button onClick={() => setViewModal(null)} style={styles.btn()}>Close</button>
              {viewModal.status === 'pending' && (
                <button onClick={() => { setViewModal(null); approve(viewModal); }} style={styles.btn('primary')}>
                  Approve
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {rejectModal && (

        <div style={styles.modal} onClick={() => setRejectModal(null)}>
          <div style={styles.modalBox} onClick={e => e.stopPropagation()}>
            <h3 style={{ marginTop: 0, color: '#ef4444' }}>Reject Document</h3>
            <p style={{ fontSize: '14px', marginBottom: '16px' }}>
              Are you sure you want to reject <strong>{rejectModal.filename}</strong>?
            </p>
            <label style={{ fontSize: '13px', fontWeight: 600, display: 'block', marginBottom: '6px' }}>Reason (optional)</label>
            <textarea
              style={styles.textarea}
              placeholder="Explain why this document is being rejected..."
              value={rejectReason}
              onChange={e => setRejectReason(e.target.value)}
            />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '20px' }}>
              <button onClick={() => setRejectModal(null)} style={styles.btn()}>Cancel</button>
              <button onClick={submitReject} disabled={actioning === rejectModal.id} style={styles.btn('danger')}>
                {actioning === rejectModal.id ? 'Rejecting...' : 'Confirm Rejection'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
