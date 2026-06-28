import React, { useState, useEffect, useMemo } from 'react';
import { apiFetch, apiDownload } from '../../utils/api';
import { Download } from 'lucide-react';

export function AuditLogsTab() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [actionFilter, setActionFilter] = useState('');

  const adminHeaders = useMemo(() => ({
    'Content-Type': 'application/json',
    'X-Admin-User': 'dashboard-admin'
  }), []);

  useEffect(() => {
    setLoading(true);
    apiFetch('/api/admin/audit-logs', { headers: adminHeaders })
      .then(data => {
        setLogs(data.logs || []);
        setError(null);
      })
      .catch(err => {
        setError(err.message);
      })
      .finally(() => setLoading(false));
  }, [adminHeaders]);

  const uniqueActions = useMemo(() => {
    const actions = new Set(logs.map(log => log.action).filter(Boolean));
    return Array.from(actions).sort();
  }, [logs]);

  const filteredLogs = useMemo(() => {
    return logs.filter(log => {
      const matchesSearch = !searchTerm.trim() ||
        (log.details || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
        (log.admin_id || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
        (log.action || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
        (log.session_token || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
        (log.chat_id || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
        (log.id || '').toString().toLowerCase().includes(searchTerm.toLowerCase());

      const matchesAction = !actionFilter || log.action === actionFilter;

      return matchesSearch && matchesAction;
    });
  }, [logs, searchTerm, actionFilter]);


  if (loading) return <div className="empty-state">Loading audit logs...</div>;
  if (error) return <div className="empty-state error">Error loading logs: {error}</div>;
  if (!logs.length) return <div className="empty-state">No audit logs found.</div>;

  return (
    <div className="fade-in tab-content-inner">
      <div className="panel compact-panel">
        <div className="panel-header" style={{ marginBottom: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
          <h3 style={{ margin: 0 }}>Recent Administrative Actions</h3>
          <button
            onClick={() => apiDownload('/api/admin/audit-logs/export', `audit_logs_${new Date().toISOString().split('T')[0]}.csv`)}
            className="btn-dash"
            style={{
              background: 'transparent',
              border: '1px solid var(--line-strong)',
              color: 'var(--ink)',
              fontSize: '12.5px',
              padding: '6px 12px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              cursor: 'pointer'
            }}
          >
            <Download size={14} />
            Export Audit Logs (CSV)
          </button>
        </div>


        {/* Filters and Search Bar */}
        <div style={{
          display: 'flex',
          gap: '12px',
          padding: '0 16px 16px 16px',
          borderBottom: '1px solid var(--line)',
          marginBottom: '16px',
          flexWrap: 'wrap',
          alignItems: 'center'
        }}>
          <div style={{ flex: '1', minWidth: '240px', position: 'relative' }}>
            <input
              type="text"
              placeholder="Search by session ID, chat ID, admin, action, or details…"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 12px',
                fontSize: '13px',
                border: '1px solid var(--line-strong)',
                borderRadius: '4px',
                background: 'var(--paper)',
                color: 'var(--ink)'
              }}
            />
            {searchTerm && (
              <button 
                onClick={() => setSearchTerm('')} 
                style={{
                  position: 'absolute',
                  right: '10px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  color: 'var(--ink)',
                  opacity: 0.5,
                  fontSize: '12px'
                }}
              >
                ✕
              </button>
            )}
          </div>
          
          <div style={{ minWidth: '180px' }}>
            <select
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 12px',
                fontSize: '13px',
                border: '1px solid var(--line-strong)',
                borderRadius: '4px',
                background: 'var(--paper)',
                color: 'var(--ink)',
                cursor: 'pointer'
              }}
            >
              <option value="">All Actions</option>
              {uniqueActions.map(action => (
                <option key={action} value={action}>{action}</option>
              ))}
            </select>
          </div>
          
          {(searchTerm || actionFilter) && (
            <button
              onClick={() => { setSearchTerm(''); setActionFilter(''); }}
              className="btn-dash"
              style={{
                background: 'transparent',
                border: '1px solid var(--line-strong)',
                color: 'var(--ink)',
                fontSize: '12.5px',
                padding: '6px 12px',
                cursor: 'pointer'
              }}
            >
              Reset Filters
            </button>
          )}
          
          <div style={{ fontSize: '12px', opacity: 0.7, marginLeft: 'auto' }}>
            Showing {filteredLogs.length} of {logs.length} entries
          </div>
        </div>

        <div className="data-table-container" style={{ padding: '0 16px 16px 16px', overflowX: 'auto' }}>
          {filteredLogs.length > 0 ? (
            <table className="data-table" style={{ tableLayout: 'fixed', width: '100%' }}>
              <colgroup>
                <col style={{ width: '180px' }} />
                <col style={{ width: '150px' }} />
                <col style={{ width: '200px' }} />
                <col />
              </colgroup>
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Admin ID</th>
                  <th>Action</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {filteredLogs.map(log => (
                  <tr key={log.id}>
                    <td className="muted" style={{ whiteSpace: 'nowrap' }}>{new Date(log.created_at).toLocaleString()}</td>
                    <td style={{ whiteSpace: 'nowrap' }}><strong>{log.admin_id}</strong></td>
                    <td style={{ whiteSpace: 'nowrap' }}><span className="badge badge-static">{log.action}</span></td>
                    <td style={{ whiteSpace: 'normal', wordBreak: 'break-word', lineHeight: '1.5' }}>{log.details}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="empty-state" style={{ padding: '40px 0' }}>
              No audit logs match your search criteria.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
