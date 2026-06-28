import { formatCount } from '../../utils/formatters';
import { apiDownload } from '../../utils/api';
import { Download } from 'lucide-react';

export function KnowledgeBaseTab({ summary }) {
  const byDept = summary?.uploads?.by_department || [];
  const activeChunks = summary?.uploads?.active_chunks || 0;

  return (
    <div className="fade-in tab-content-inner dashboard-main-grid" style={{ gridTemplateColumns: '1fr 2.5fr' }}>
      <div className="panel compact-panel">
        <div className="panel-header" style={{ padding: '12px' }}>
          <h3 style={{ fontSize: '14px' }}>System Status</h3>
        </div>
        <div style={{ padding: '12px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ padding: '12px', background: 'var(--paper-muted)', borderRadius: '6px' }}>
            <p className="muted" style={{ fontSize: '11px', textTransform: 'uppercase', marginBottom: '4px' }}>Total Active Chunks</p>
            <strong style={{ fontSize: '20px', color: 'var(--ink)' }}>{formatCount(activeChunks)}</strong>
          </div>
          <div style={{ padding: '12px', background: 'rgba(239, 68, 68, 0.05)', borderRadius: '6px', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
            <p className="muted" style={{ fontSize: '11px', textTransform: 'uppercase', marginBottom: '4px', color: 'var(--danger)' }}>Failed Uploads</p>
            <strong style={{ fontSize: '16px', color: 'var(--danger)' }}>0</strong>
            <p style={{ fontSize: '11px', color: 'var(--danger)', marginTop: '4px', opacity: 0.8 }}>No failures reported.</p>
          </div>
          <button className="btn-dash" style={{ width: '100%', justifyContent: 'center', background: 'transparent', color: 'var(--ink)', borderColor: 'var(--line)', opacity: 0.5, cursor: 'not-allowed' }} disabled>
            Reindex All Chunks
          </button>
          <button
            className="btn-dash"
            onClick={() => apiDownload('/api/admin/upload-documents/export', `upload_history_${new Date().toISOString().split('T')[0]}.csv`)}
            style={{ width: '100%', justifyContent: 'center', background: 'transparent', color: 'var(--ink)', borderColor: 'var(--line)', display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}
          >
            <Download size={14} />
            Export Upload Logs (CSV)
          </button>
        </div>
      </div>

      <div className="panel compact-panel">
        <div className="panel-header" style={{ padding: '12px' }}>
          <h3 style={{ fontSize: '14px' }}>Department-wise Uploads</h3>
        </div>
        {byDept.some((item) => Number(item.total_uploads || 0) > 0) ? (
          <div className="stack-list compact-stack" style={{ padding: '12px', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
            {byDept
              .filter((item) => Number(item.total_uploads || 0) > 0)
              .map((item) => (
                <article key={item.department_slug} className="metric-card" style={{ padding: '12px', background: 'var(--paper)', border: '1px solid var(--line)' }}>
                  <p style={{ margin: '0 0 4px', fontSize: '13px', fontWeight: 600, color: 'var(--moss)' }}>{item.department_name}</p>
                  <p style={{ margin: '0 0 12px', fontSize: '11px', color: 'var(--ink)', opacity: 0.7 }}>{item.institute_name}</p>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', background: 'var(--paper-muted)', padding: '6px', borderRadius: '4px' }}>
                    <span>Total: <strong>{formatCount(item.total_uploads)}</strong></span>
                    <span>Processed: <strong>{formatCount(item.processed_uploads)}</strong></span>
                  </div>
                </article>
              ))}
          </div>
        ) : (
          <div className="empty-state">No department uploads found.</div>
        )}
      </div>
    </div>
  );
}
