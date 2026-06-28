import { useEffect, useMemo, useRef, useState, Fragment, createContext, useContext } from 'react';
import { BrowserRouter, NavLink, Navigate, Route, Routes, useNavigate } from 'react-router-dom';
import { supabase } from './supabaseClient';
import { MessageSquare, Clock, ThumbsDown, Download, Database, FileText, Filter, Search, Edit3, RefreshCw, Users, Upload, Mic, Volume2, Square } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RTooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { Analytics } from "@vercel/analytics/react"
import { apiFetch, apiDownload } from './utils/api';
import { formatCount, formatPercent, formatNumber, formatShortDay, parseAnswer } from './utils/formatters';


import UsersTab from './components/tabs/UsersTab';
import DepartmentsTab from './components/tabs/DepartmentsTab';
import PendingApprovalsTab from './components/tabs/PendingApprovalsTab';
import MyDocumentsTab from './components/tabs/MyDocumentsTab';
import SettingsTab from './components/tabs/SettingsTab';
import { getRoleFromSession, clearRoleCache } from './utils/auth';

import { useAdminMetrics } from './hooks/useAdminMetrics';
import { useSupabaseSessions } from './hooks/useSupabaseSessions';
import { useFeedback } from './hooks/useFeedback';
import { useCorrections } from './hooks/useCorrections';
import { useUploads } from './hooks/useUploads';
import { OverviewTab } from './components/tabs/OverviewTab';
import { ModerationTab } from './components/tabs/ModerationTab';
import { CorrectionsTab } from './components/tabs/CorrectionsTab';
import { KnowledgeBaseTab } from './components/tabs/KnowledgeBaseTab';
import { LiveActivityTab } from './components/tabs/LiveActivityTab';
import { SystemPromptTab } from './components/tabs/SystemPromptTab';
import { AuditLogsTab } from './components/tabs/AuditLogsTab';
import { VisitorSessionsTab } from './components/tabs/VisitorSessionsTab';

export const RoleContext = createContext(null);

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

function Shell({ status, workflow, children }) {
  const roleData = useContext(RoleContext);
  const isSuper = roleData?.role === 'super_admin';
  const isDept = roleData?.role === 'dept_admin';
  const [isDark, setIsDark] = useState(() => localStorage.getItem('theme') === 'dark');
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    if (isDark) {
      document.documentElement.setAttribute('data-theme', 'dark');
      localStorage.setItem('theme', 'dark');
    } else {
      document.documentElement.removeAttribute('data-theme');
      localStorage.setItem('theme', 'light');
    }
  }, [isDark]);

  const navItems = useMemo(
    () => {
      if (isSuper || !roleData?.role) return [
        { to: '/dashboard', label: 'Main Dashboard', icon: <Search size={18} /> },
        { to: '/admin', label: 'Operations Center', icon: <Edit3 size={18} /> },
        { to: '/chat', label: 'Chat Console', icon: <MessageSquare size={18} /> },
        { to: '/tester', label: 'Tester Page', icon: <Clock size={18} /> },
        { to: '/upload', label: 'Documents', icon: <FileText size={18} /> },
        { to: '/blocked-terms', label: 'Blocked Terms', icon: <Filter size={18} /> },
        { to: '/logs', label: 'Logs', icon: <Download size={18} /> },
        // { to: '/rag-knowledge', label: 'Knowledge Index', icon: <Database size={18} /> },
        { to: '/access', label: 'Access Control', icon: <Users size={18} /> }
      ];
      if (isDept) return [
        { to: '/admin', label: 'Operations Center', icon: <Edit3 size={18} /> },
        { to: '/upload', label: 'Documents', icon: <FileText size={18} /> },
      ];
      return [];
    },
    [isSuper, isDept, roleData]
  );

  return (
    <div className={`chrome-shell ${sidebarOpen ? 'sidebar-open' : ''}`}>
      <div className="sidebar-overlay" onClick={() => setSidebarOpen(false)}></div>

      <aside className="left-rail">
        <div className="rail-header">
          <div className="rail-title">Admin Dashboard</div>
          <button className="mobile-close" onClick={() => setSidebarOpen(false)}>✕</button>
        </div>

        <nav className="rail-nav">
          {navItems.map((item) => (
            <NavLink key={item.to} to={item.to} onClick={() => setSidebarOpen(false)} className={({ isActive }) => `rail-link ${isActive ? 'active' : ''}`}>
              {item.icon}
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="rail-footer">
          <button onClick={() => setIsDark(!isDark)} className="rail-link action-link">
            {isDark ? '☀️ Light Mode' : '🌙 Dark Mode'}
          </button>
          <button
            onClick={() => {
              sessionStorage.removeItem('admin_chat_history');
              supabase.auth.signOut();
            }}
            className="rail-link danger-link action-link"
          >
            Log Out
          </button>
        </div>
      </aside>

      <div className="main-content-wrapper">
        <header className="headline">
          <div className="headline-left">
            <button className="mobile-menu-btn" onClick={() => setSidebarOpen(true)}>
              ☰
            </button>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '12px' }}>
              <h1 style={{ fontSize: '16px', fontWeight: '600' }}>Operations Center</h1>
            </div>
          </div>
          <div className="status-strip">
            <div className="status-pill">
              <span>Server</span>
              <strong className={status?.status === 'ok' || status?.status === 'healthy' || status?.status === 'ready' ? 'text-green' : 'text-red'}>
                {status?.status || 'unknown'}
              </strong>
            </div>
            <div className="status-pill hide-mobile">
              <span>Index Chunks</span>
              <strong>{status?.documents ?? 0}</strong>
            </div>
            <div className="status-pill">
              <span>Reviews</span>
              <strong className={(workflow?.flagged?.pending ?? 0) > 0 ? 'text-orange' : ''}>
                {workflow?.flagged?.pending ?? 0}
              </strong>
            </div>
          </div>
        </header>

        <main className="content-deck">{children}</main>
      </div>
    </div>
  );
}

function DashboardPage({ status, workflow }) {
  const [analytics, setAnalytics] = useState(null);
  const [recentChats, setRecentChats] = useState([]);
  const [expandedRow, setExpandedRow] = useState(null);
  const [loadingAnalytics, setLoadingAnalytics] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [secondsAgo, setSecondsAgo] = useState(0);

  useEffect(() => {
    setLoadingAnalytics(true);
    const adminHeaders = {};
    Promise.all([
      apiFetch('/api/admin/analytics/summary', { headers: adminHeaders }),
      apiFetch('/api/admin/flagged-responses?status=pending&limit=5', { headers: adminHeaders }),
    ])
      .then(([analyticsData, flaggedData]) => {
        setAnalytics(analyticsData);
        setRecentChats(flaggedData?.items || []);
        setLastUpdated(new Date());
      })
      .catch(() => { })
      .finally(() => setLoadingAnalytics(false));
  }, []);

  useEffect(() => {
    if (!lastUpdated) return;
    const interval = setInterval(() => {
      setSecondsAgo(Math.floor((Date.now() - lastUpdated) / 1000));
    }, 5000);
    return () => clearInterval(interval);
  }, [lastUpdated]);

  const serverOk = status?.status === 'ok' || status?.status === 'healthy' || status?.status === 'ready';
  const pendingRev = workflow?.flagged?.pending ?? 0;
  const uploadsOk = workflow?.uploads?.processed !== undefined;

  const queriesToday = analytics?.queries_today ?? null;
  const sessionsToday = analytics?.sessions_today ?? null;
  const cacheHitRate = analytics?.cache_hit_rate_today != null ? `${Math.round(analytics.cache_hit_rate_today * 100)}%` : null;
  const avgLatencyMs = analytics?.avg_latency_ms_today;
  const avgLatency = avgLatencyMs != null ? `${(avgLatencyMs / 1000).toFixed(2)}s` : null;
  const errorCount = analytics?.error_like_answers_today ?? null;
  const feedbackDown = analytics?.feedback_today?.down ?? null;
  const topQuestions = analytics?.top_questions_today || [];
  const routeBreakdown = analytics?.route_breakdown_today || [];
  const trendData = analytics?.queries_last_7_days || [];

  const health = [
    { label: 'AI API', ok: serverOk },
    { label: 'Database', ok: true },
    { label: 'Search Index', ok: true },
    { label: 'Upload Service', ok: uploadsOk },
  ];

  const Stat = ({ label, value, note, accent, loading }) => (
    <div className="metric-card" style={{ borderTop: `4px solid ${accent}` }}>
      <div className="metric-label">{label}</div>
      {loading ? (
        <div className="metric-skeleton" />
      ) : value == null ? (
        <div className="metric-value empty">No data</div>
      ) : (
        <div className="metric-value">{value}</div>
      )}
      {note && <div className="metric-note">{note}</div>}
    </div>
  );

  const [activeTab, setActiveTab] = useState('overview');

  // Route badge colours
  const routeStyle = (route) => {
    const r = (route || '').toLowerCase();
    if (r.includes('rag') || r.includes('retriev')) return { bg: 'rgba(29, 78, 216, 0.1)', color: '#1d4ed8', label: 'RAG' };
    if (r.includes('cache') || r.includes('redis') || r.includes('file')) return { bg: 'rgba(6, 95, 70, 0.1)', color: '#065f46', label: 'Cache' };
    if (r.includes('static') || r.includes('correction') || r.includes('greeting')) return { bg: 'rgba(55, 65, 81, 0.1)', color: '#374151', label: 'Static' };
    return { bg: 'rgba(154, 52, 18, 0.1)', color: '#9a3412', label: route };
  };

  return (
    <section className="dashboard-page">
      <div className="dashboard-header">
        <div>
          <h2>System Overview</h2>
          <p className="freshness">
            {lastUpdated ? `Auto-refreshed ${secondsAgo < 60 ? `${secondsAgo}s` : `${Math.floor(secondsAgo / 60)}m`} ago` : 'Loading metrics...'}
          </p>
        </div>
        <div className="dashboard-actions">
          <NavLink to="/upload" className="btn-dash">↑ Upload Knowledge</NavLink>
          <NavLink to="/admin" className="btn-dash">✓ Review Feedback</NavLink>
        </div>
      </div>

      <div className="metric-grid">
        <Stat label="Pending Reviews" value={pendingRev} note="Needs action" accent={pendingRev > 0 ? 'var(--accent)' : 'var(--moss)'} loading={false} />
        <Stat label="Error Responses" value={errorCount} note="Failed requests" accent="var(--danger)" loading={loadingAnalytics} />
        <Stat label="Active Users Now" value={analytics?.active_users_now} note="In last 5 mins" accent="var(--moss)" loading={loadingAnalytics} />
        <Stat label="Sessions Today" value={sessionsToday} note="Unique users" accent="var(--forest)" loading={loadingAnalytics} />
        <Stat label="Queries Today" value={queriesToday} note="Since midnight" accent="var(--moss)" loading={loadingAnalytics} />
        <Stat label="Avg Response" value={avgLatency} note="Last 24 hrs" accent="var(--line-strong)" loading={loadingAnalytics} />
        <Stat label="Cache Hit Rate" value={cacheHitRate} note="Cache efficiency" accent="var(--line-strong)" loading={loadingAnalytics} />
      </div>

      <div className="dashboard-tabs">
        <button className={`tab-btn ${activeTab === 'overview' ? 'active' : ''}`} onClick={() => setActiveTab('overview')}>Trends & Overview</button>
        <button className={`tab-btn ${activeTab === 'quality' ? 'active' : ''}`} onClick={() => setActiveTab('quality')}>Reviews & Quality</button>
        <button className={`tab-btn ${activeTab === 'health' ? 'active' : ''}`} onClick={() => setActiveTab('health')}>System Health</button>
        <button className={`tab-btn ${activeTab === 'prompt' ? 'active' : ''}`} onClick={() => setActiveTab('prompt')}>System Prompt</button>
      </div>

      <div className="tab-content">
        {activeTab === 'overview' && (
          <div className="dashboard-main-grid">
            <div className="panel chart-panel">
              <div className="panel-header">
                <h3>Queries — Last 7 Days</h3>
              </div>
              <div className="chart-container">
                {trendData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={trendData} margin={{ top: 10, right: 10, bottom: 0, left: -20 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" vertical={false} />
                      <XAxis dataKey="day" fontSize={11} tickLine={false} axisLine={false} stroke="var(--ink)" tickFormatter={d => d ? d.slice(5) : ''} />
                      <YAxis fontSize={11} tickLine={false} axisLine={false} stroke="var(--ink)" />
                      <RTooltip contentStyle={{ borderRadius: '8px', border: '1px solid var(--line)', background: 'var(--paper)', fontSize: '12px' }} />
                      <Line type="monotone" dataKey="queries" stroke="var(--moss)" strokeWidth={3} dot={{ r: 4, fill: 'var(--paper)', strokeWidth: 2 }} activeDot={{ r: 6 }} name="Queries" />
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="empty-state">{loadingAnalytics ? 'Loading chart...' : 'No data available'}</div>
                )}
              </div>
            </div>

            <div className="side-panels">
              {routeBreakdown.length > 0 && (
                <div className="panel">
                  <div className="panel-header">
                    <h3>Answer Routes Today</h3>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    {routeBreakdown.map((r, i) => {
                      const style = routeStyle(r.route);
                      const pct = Math.round((r.share || 0) * 100);
                      return (
                        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '12.5px' }}>
                          <span style={{ padding: '4px 10px', borderRadius: '99px', background: style.bg, color: style.color, fontWeight: 600, fontSize: '11px', minWidth: '70px', textAlign: 'center' }}>{style.label}</span>
                          <div style={{ flex: 1, background: 'var(--line)', borderRadius: '4px', height: '6px' }}>
                            <div style={{ width: `${pct}%`, background: style.color, height: '6px', borderRadius: '4px', transition: 'width 0.5s' }} />
                          </div>
                          <span style={{ color: 'var(--ink)', opacity: 0.6, minWidth: '40px', textAlign: 'right' }}>{pct}%</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'quality' && (
          <div className="dashboard-main-grid" style={{ gridTemplateColumns: '1fr 2.5fr' }}>
            <div className="side-panels">
              <div className="panel top-questions-panel">
                <div className="panel-header">
                  <h3>Top Questions</h3>
                </div>
                {topQuestions.length > 0 ? (
                  <ol className="top-questions-list">
                    {topQuestions.slice(0, 5).map((q, i) => (
                      <li key={i}>
                        <span className="q-text">{q.question}</span>
                        <span className="q-count">×{q.count}</span>
                      </li>
                    ))}
                  </ol>
                ) : (
                  <div className="empty-state small">{loadingAnalytics ? 'Loading...' : 'No data yet'}</div>
                )}
              </div>
            </div>

            <div className="panel reviews-panel">
              <div className="panel-header">
                <h3>Pending Review Queue</h3>
                <NavLink to="/admin" className="btn-secondary">View All ({pendingRev}) →</NavLink>
              </div>
              {recentChats.length > 0 ? (
                <div className="table-responsive">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Question</th>
                        <th>Route</th>
                        <th>Flagged By</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {recentChats.map((r, i) => (
                        <Fragment key={i}>
                          <tr onClick={() => setExpandedRow(expandedRow === i ? null : i)} className={expandedRow === i ? 'expanded' : 'collapsible-row'}>
                            <td className="truncate-cell">{r.question}</td>
                            <td><span className="badge tag-route">flagged</span></td>
                            <td className="muted-cell">{r.tester_id || '—'}</td>
                            <td><span className="badge pending">Pending</span></td>
                          </tr>
                          {expandedRow === i && (
                            <tr className="expanded-content">
                              <td colSpan={4}>
                                <div className="expanded-details">
                                  <strong>Chatbot Answer:</strong> {r.chatbot_answer}<br />
                                  {r.tester_answer_raw && <><strong>Tester Correction:</strong> {r.tester_answer_raw}<br /></>}
                                  {r.tester_note && <><strong>Note:</strong> {r.tester_note}</>}
                                </div>
                              </td>
                            </tr>
                          )}
                        </Fragment>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="empty-state">{loadingAnalytics ? 'Loading...' : '✓ No pending reviews in queue'}</div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'health' && (
          <div className="dashboard-main-grid" style={{ gridTemplateColumns: '1fr' }}>
            <div className="panel health-panel" style={{ maxWidth: '400px', padding: '16px' }}>
              <div className="panel-header" style={{ marginBottom: '12px' }}>
                <h3 style={{ fontSize: '14px' }}>System Health</h3>
              </div>
              <div className="health-list" style={{ gap: '8px' }}>
                {health.map(h => (
                  <div key={h.label} className="health-item" style={{ fontSize: '13px', padding: '4px 0', borderBottom: '1px solid var(--line)' }}>
                    <span style={{ minWidth: '120px' }}>{h.label}</span>
                    <div className={`status-badge ${h.ok ? 'ok' : 'error'}`} style={{ background: 'transparent', padding: '0' }}>
                      <span className="dot" />
                      {h.ok ? 'Online' : 'Offline'}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'prompt' && <SystemPromptTab />}
      </div>
    </section>
  );
}




function formatSourceUrl(url) {
  if (!url) return '#';
  const cleanBase = API_BASE.replace(/\/+$/, '');
  if (url.startsWith('file://') && url.includes('document_summary.pdf')) {
    const pageMatch = url.match(/#page=(\d+)/);
    const pageSuffix = pageMatch ? `#page=${pageMatch[1]}` : '';
    return `${cleanBase}/static/document_summary.pdf${pageSuffix}`;
  }
  if (url.startsWith('upload://')) {
    const parts = url.replace('upload://', '').split('/');
    const uploadId = parts[0];
    if (uploadId) {
      return `${cleanBase}/api/upload/documents/${uploadId}/download`;
    }
  }
  if (url.startsWith('file://')) {
    return '#';
  }
  return url;
}

function ChatMessage({ msg, onSuggestionClick }) {
  if (msg.role === 'user') {
    return (
      <article className="chat-bubble user">
        <div className="chat-role">Tester</div>
        <div className="chat-text user-text">{msg.text}</div>
      </article>
    );
  }

  const { bodyHtml, suggestions } = parseAnswer(msg.text);
  const validSources = (msg.sources || []).filter(
    (s) => s.title && s.category !== 'correction' && s.section_type !== 'exact'
  );

  return (
    <article className="chat-bubble assistant">
      <div className="chat-role assistant-role">Assistant</div>
      {/* eslint-disable-next-line react/no-danger */}
      <div className="chat-text assistant-body" dangerouslySetInnerHTML={{ __html: bodyHtml }} />

      {suggestions.length > 0 && (
        <div className="suggestion-bar">
          <span className="suggestion-label">Quick follow-ups</span>
          <div className="suggestion-chips">
            {suggestions.map((s) => (
              <button
                key={s}
                type="button"
                className="suggestion-chip"
                onClick={() => onSuggestionClick(s)}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      {validSources.length > 0 && (
        <div className="citation-bar">
          <span className="citation-label">Sources</span>
          <div className="citation-list">
            {validSources.slice(0, 4).map((src, i) => (
              <a
                key={`${src.title}-${i}`}
                href={formatSourceUrl(src.url)}
                target="_blank"
                rel="noreferrer"
                className="citation-pill"
                title={src.snippet || src.title}
              >
                <span className="citation-num">{i + 1}</span>
                <span className="citation-title">{src.title}</span>
              </a>
            ))}
          </div>
        </div>
      )}
    </article>
  );
}

function ChatPage() {
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  // Fix #7: use real refs so scroll works
  const chatEndRef = useRef(null);
  const starterPrompts = useMemo(
    () => [
      'What is the admission process?',
      'Tell me B.Tech CSE fee details.',
      'What are scholarship options?',
      'Share latest placement highlights.',
    ],
    []
  );
  const [messages, setMessages] = useState(() => {
    const saved = sessionStorage.getItem('admin_chat_history');
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch (e) { }
    }
    return [
      {
        role: 'assistant',
        text: 'Ask anything. Approved corrections and uploaded knowledge are now part of this response flow.',
        sources: [],
      },
    ];
  });

  useEffect(() => {
    sessionStorage.setItem('admin_chat_history', JSON.stringify(messages));
  }, [messages]);

  // Fix #7: auto-scroll whenever messages change
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  // Build conversation history — exclude ALL error messages, cap at 4, truncate content
  const isErrorMessage = (m) =>
    m.isError ||
    (typeof m.text === 'string' && (
      m.text.startsWith('Error:') ||
      m.text.startsWith('Sorry, something went wrong') ||
      m.text.includes('"type":"toolong"') ||
      m.text.includes('"type":"stringtoolong"')
    ));

  const buildHistory = (currentMessages) =>
    currentMessages
      .filter((m) => (m.role === 'user' || m.role === 'assistant') && !isErrorMessage(m))
      .slice(-4) // backend hard limit: max 4 items
      .map((m) => ({ role: m.role === 'assistant' ? 'assistant' : 'user', content: (m.text || '').slice(0, 799) }));

  const doSend = async (q) => {
    if (!q || loading) return;
    setQuestion('');
    setLoading(true);

    // Step 1: add user message to state synchronously
    const userMsg = { role: 'user', text: q, sources: [] };
    const nextMessages = [...messages, userMsg];
    setMessages(nextMessages);

    // Step 2: fire the API call OUTSIDE setMessages to avoid double-fire in React StrictMode
    apiFetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question: q,
        top_k: 5,
        conversation_history: buildHistory(nextMessages),
      }),
    })
      .then((data) => {
        setMessages((m) => [
          ...m,
          { role: 'assistant', text: data.answer || 'No answer.', sources: data.sources || [] },
        ]);
      })
      .catch((err) => {
        setMessages((m) => [
          ...m,
          { role: 'assistant', text: `Sorry, something went wrong: ${err.message}`, sources: [], isError: true },
        ]);
      })
      .finally(() => setLoading(false));
  };

  const send = (event) => { event.preventDefault(); doSend(question.trim()); };

  return (
    <section className="panel panel-feature">
      <div className="panel-headline">
        <p className="panel-kicker">Live QA</p>
        <h2>Chat Console</h2>
      </div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '8px' }}>
        <button type="button" className="toggle" onClick={() => setMessages([])} style={{ fontSize: '13px', padding: '4px 12px', opacity: 0.7 }}>Clear Chat</button>
      </div>

      <div className="chip-wrap">
        {starterPrompts.map((prompt) => (
          // Fix #18: prefill input so user can edit before sending
          <button key={prompt} type="button" className="chip" onClick={() => setQuestion(prompt)}>
            {prompt}
          </button>
        ))}
      </div>

      <div className="chat-stream-modern">
        {messages.map((msg, idx) => (
          <ChatMessage
            key={`${msg.role}-${idx}`}
            msg={msg}
            onSuggestionClick={(s) => {
              if (s.trim().toLowerCase() === 'apply now') {
                window.open('https://example.com', '_blank');
              } else {
                doSend(s);
              }
            }}
          />
        ))}
        {loading && (
          <article className="chat-bubble assistant">
            <div className="chat-role assistant-role">Assistant</div>
            <div className="chat-typing">
              <span /><span /><span />
            </div>
          </article>
        )}
        <div ref={chatEndRef} />
      </div>

      <form className="inline-form" onSubmit={send}>
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a question..."
          maxLength={500}
        />
        <button type="submit" disabled={loading}>{loading ? 'Thinking...' : 'Send'}</button>
      </form>
    </section>
  );
}

function TesterAiQueue({ testerId }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [actionStates, setActionStates] = useState({}); // { [id]: { status: 'loading_approve' | ..., error: string } }

  const fetchItems = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await apiFetch('/api/tester/ai-responses');
      setItems(data.items || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchItems();
  }, []);

  const handleAction = async (id, action) => {
    setActionStates(prev => ({ ...prev, [id]: { status: `loading_${action}`, error: null } }));
    try {
      const url = `/api/tester/ai-responses/${id}/${action}?tester_id=${encodeURIComponent(testerId || 'tester')}`;
      await apiFetch(url, {
        method: 'POST',
      });
      
      setActionStates(prev => ({
        ...prev,
        [id]: { status: action, error: null }
      }));

      // Smoothly remove item from list after the user sees the confirmation
      setTimeout(() => {
        setItems(prev => prev.filter(item => item.id !== id));
        setActionStates(prev => {
          const copy = { ...prev };
          delete copy[id];
          return copy;
        });
      }, 1500);
      
    } catch (err) {
      setActionStates(prev => ({
        ...prev,
        [id]: { status: 'failed', error: err.message }
      }));
    }
  };

  if (loading && items.length === 0) {
    return (
      <div style={{ padding: '20px', background: 'var(--paper)', border: '1px solid var(--line)', borderRadius: '12px', textAlign: 'center' }}>
        <p className="muted">Loading AI Q&A queue...</p>
      </div>
    );
  }

  return (
    <div style={{ background: '#fff', border: '1px solid var(--line)', borderRadius: '12px', padding: '24px', boxShadow: '0 4px 20px rgba(0,0,0,0.03)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <div>
          <h3 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--ink)', margin: 0 }}>AI-Generated Q&A Moderation Queue (Tester Review)</h3>
          <p className="muted" style={{ fontSize: '12px', margin: '4px 0 0' }}>Review and approve generated Q&As. If you are not sure about the answer, click "Send to Admin".</p>
        </div>
        <button 
          onClick={fetchItems} 
          className="btn-dash" 
          style={{ fontSize: '11px', padding: '4px 10px', display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}
        >
          ↻ Refresh List
        </button>
      </div>

      {error && <div style={{ color: 'var(--danger)', fontSize: '13px', marginBottom: '12px' }}>{error}</div>}

      <div style={{ display: 'grid', gap: '16px', maxHeight: '500px', overflowY: 'auto', paddingRight: '8px' }}>
        {items.map((item) => {
          const state = actionStates[item.id] || { status: 'idle', error: null };
          const isLoading = state.status.startsWith('loading_');
          const isDone = ['approve', 'reject', 'escalate'].includes(state.status);
          
          let cardBg = 'rgba(0,0,0,0.01)';
          let cardBorder = '1px solid var(--line)';
          if (state.status === 'approve') {
            cardBg = 'rgba(43,94,50,0.06)';
            cardBorder = '1px solid var(--moss)';
          } else if (state.status === 'reject') {
            cardBg = 'rgba(239,68,68,0.06)';
            cardBorder = '1px solid var(--danger)';
          } else if (state.status === 'escalate') {
            cardBg = 'rgba(197,122,31,0.06)';
            cardBorder = '1px solid var(--orange)';
          }

          return (
            <article 
              key={item.id} 
              style={{ 
                background: cardBg, 
                border: cardBorder, 
                borderRadius: '8px', 
                padding: '16px', 
                display: 'flex', 
                flexDirection: 'column', 
                gap: '10px',
                position: 'relative',
                transition: 'all 0.3s ease',
                opacity: isDone ? 0.85 : 1,
                transform: isDone ? 'scale(0.99)' : 'scale(1)'
              }}
            >
              {/* If completed, overlay a beautiful indicator */}
              {isDone && (
                <div style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  right: 0,
                  bottom: 0,
                  background: 'rgba(255,255,255,0.7)',
                  borderRadius: '8px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  zIndex: 2
                }}>
                  <div style={{
                    padding: '8px 16px',
                    borderRadius: '20px',
                    fontWeight: 'bold',
                    fontSize: '14px',
                    boxShadow: '0 2px 10px rgba(0,0,0,0.08)',
                    background: '#fff',
                    border: `1.5px solid ${
                      state.status === 'approve' ? 'var(--moss)' : 
                      state.status === 'reject' ? 'var(--danger)' : 
                      'var(--orange)'
                    }`,
                    color: 
                      state.status === 'approve' ? 'var(--moss)' : 
                      state.status === 'reject' ? 'var(--danger)' : 
                      'var(--orange)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px'
                  }}>
                    {state.status === 'approve' && <>Approved & Added to Knowledge Base ✓</>}
                    {state.status === 'reject' && <>Rejected ✗</>}
                    {state.status === 'escalate' && <>Sent to Admin (Escalated) ⤪</>}
                  </div>
                </div>
              )}

              <div style={{ opacity: isDone ? 0.3 : 1 }}>
                <h4 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--ink)', marginBottom: '4px' }}>Q: {item.question}</h4>
              </div>

              <div style={{ background: '#fff', border: '1px solid var(--line)', borderRadius: '6px', padding: '10px', fontSize: '13px', opacity: isDone ? 0.3 : 1 }}>
                <strong style={{ color: 'var(--moss)', fontSize: '11px', textTransform: 'uppercase', display: 'block', marginBottom: '4px' }}>Proposed Answer</strong>
                <div 
                  className="preview-html"
                  dangerouslySetInnerHTML={{ __html: parseAnswer(item.chatbot_answer || '').bodyHtml }} 
                  style={{ lineHeight: '1.5', color: 'var(--ink)' }} 
                />
              </div>

              {!isDone && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '4px' }}>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button 
                      disabled={isLoading}
                      onClick={() => handleAction(item.id, 'approve')} 
                      className="text-btn success" 
                      style={{ 
                        fontSize: '12px', 
                        border: '1px solid var(--moss)', 
                        padding: '6px 12px', 
                        borderRadius: '4px', 
                        background: state.status === 'loading_approve' ? 'rgba(43,94,50,0.15)' : 'rgba(43,94,50,0.05)', 
                        cursor: isLoading ? 'not-allowed' : 'pointer', 
                        fontWeight: 600,
                        opacity: isLoading && state.status !== 'loading_approve' ? 0.5 : 1
                      }}
                    >
                      {state.status === 'loading_approve' ? 'Approving...' : 'Approve (Add to KB)'}
                    </button>
                    <button 
                      disabled={isLoading}
                      onClick={() => handleAction(item.id, 'reject')} 
                      className="text-btn danger" 
                      style={{ 
                        fontSize: '12px', 
                        border: '1px solid var(--danger)', 
                        padding: '6px 12px', 
                        borderRadius: '4px', 
                        background: state.status === 'loading_reject' ? 'rgba(239,68,68,0.15)' : 'rgba(239,68,68,0.05)', 
                        cursor: isLoading ? 'not-allowed' : 'pointer', 
                        fontWeight: 600,
                        opacity: isLoading && state.status !== 'loading_reject' ? 0.5 : 1
                      }}
                    >
                      {state.status === 'loading_reject' ? 'Rejecting...' : 'Reject'}
                    </button>
                    <button 
                      disabled={isLoading}
                      onClick={() => handleAction(item.id, 'escalate')} 
                      style={{ 
                        fontSize: '12px', 
                        border: '1px solid var(--orange)', 
                        padding: '6px 12px', 
                        borderRadius: '4px', 
                        background: state.status === 'loading_escalate' ? 'rgba(197,122,31,0.15)' : 'rgba(197,122,31,0.05)', 
                        color: 'var(--orange)', 
                        fontWeight: 600,
                        cursor: isLoading ? 'not-allowed' : 'pointer',
                        opacity: isLoading && state.status !== 'loading_escalate' ? 0.5 : 1
                      }}
                    >
                      {state.status === 'loading_escalate' ? 'Sending...' : 'Not Sure (Send to Admin)'}
                    </button>
                  </div>
                  
                  {state.status === 'failed' && (
                    <div style={{ color: 'var(--danger)', fontSize: '12px', fontWeight: 500, marginTop: '4px' }}>
                      ⚠️ Error: {state.error}
                    </div>
                  )}
                </div>
              )}
            </article>
          );
        })}

        {items.length === 0 && (
          <div style={{ padding: '30px', textAlign: 'center', color: '#888', border: '1px dashed var(--line)', borderRadius: '8px', fontSize: '13px' }}>
            No pending AI-generated questions to review. Click "Generate Questions with AI" in the chat widget to create some!
          </div>
        )}
      </div>
    </div>
  );
}


function TesterPage() {
  const [predefined, setPredefined] = useState([]);
  const [question, setQuestion] = useState('');
  const [chatAnswer, setChatAnswer] = useState('');
  const [chatId, setChatId] = useState('');
  const [verdict, setVerdict] = useState('');
  const [testerAnswer, setTesterAnswer] = useState('');
  const [improvedAnswer, setImprovedAnswer] = useState('');
  const [testerNote, setTesterNote] = useState('');
  const [testerId, setTesterId] = useState('tester-01');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [widgetOpen, setWidgetOpen] = useState(false);

  // AI batch generation state
  const [showGeneratePanel, setShowGeneratePanel] = useState(false);
  const [generateTopic, setGenerateTopic] = useState('');
  const [generateCount, setGenerateCount] = useState(20);
  const [generating, setGenerating] = useState(false);
  const [generateResult, setGenerateResult] = useState(null); // { total_stored, topic } | null
  const [generateError, setGenerateError] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [audioBase64, setAudioBase64] = useState('');
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const currentAudioRef = useRef(null);
  const recognitionRef = useRef(null);

  useEffect(() => {
    apiFetch('/api/tester/predefined-questions')
      .then((data) => setPredefined(data.questions || []))
      .catch(() => setPredefined([]));

    return () => {
      stopAudio();
    };
  }, []);

  const generateAndTest = async () => {
    const topic = generateTopic.trim();
    if (!topic || generating) return;
    setGenerating(true);
    setGenerateResult(null);
    setGenerateError('');
    try {
      const finalCount = Math.max(1, Math.min(50, Number(generateCount) || 20));
      const data = await apiFetch('/api/tester/generate-and-test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic, num_questions: finalCount }),
      });
      setGenerateResult({ total_stored: data.total_stored, topic: data.topic });
      // Ensure the count state is reconciled to final valid number
      setGenerateCount(finalCount);
    } catch (err) {
      setGenerateError(`Generation failed: ${err.message}`);
    } finally {
      setGenerating(false);
    }
  };

  const playAudio = (b64) => {
    stopAudio();
    if (!b64) return;
    try {
      const audio = new Audio("data:audio/wav;base64," + b64);
      currentAudioRef.current = audio;
      setIsPlaying(true);
      audio.onended = () => setIsPlaying(false);
      audio.onerror = () => setIsPlaying(false);
      audio.play();
    } catch (e) {
      console.error("Playback failed", e);
      setIsPlaying(false);
    }
  };

  const stopAudio = () => {
    if (currentAudioRef.current) {
      try {
        currentAudioRef.current.pause();
        currentAudioRef.current.currentTime = 0;
      } catch (e) {}
      currentAudioRef.current = null;
    }
    setIsPlaying(false);
  };

  const startSpeechRecognition = () => {
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRec) return false;
    
    try {
      const rec = new SpeechRec();
      rec.continuous = false;
      rec.interimResults = false;
      rec.lang = 'en-IN';
      
      rec.onstart = () => {
        setIsRecording(true);
      };
      
      rec.onresult = (event) => {
        const text = event.results[0][0].transcript;
        if (text) {
          setQuestion(text);
        }
      };
      
      rec.onerror = (e) => {
        console.error("Speech recognition error:", e);
        setIsRecording(false);
      };
      
      rec.onend = () => {
        setIsRecording(false);
      };
      
      recognitionRef.current = rec;
      rec.start();
      return true;
    } catch (e) {
      console.error(e);
      return false;
    }
  };

  const startRecording = async () => {
    stopAudio();
    setAudioBase64('');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;
      audioChunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      recorder.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        const reader = new FileReader();
        reader.readAsDataURL(audioBlob);
        reader.onloadend = async () => {
          const base64Data = reader.result.split(',')[1];
          setAudioBase64(base64Data);
          await askChatbotWithAudio(base64Data);
        };
        stream.getTracks().forEach(track => track.stop());
      };

      recorder.start();
      setIsRecording(true);
    } catch (err) {
      alert("Microphone permission required for voice chat: " + err.message);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
  };

  const startVoiceInput = async () => {
    stopAudio();
    const success = startSpeechRecognition();
    if (success) return;
    await startRecording();
  };

  const askChatbotWithAudio = async (b64) => {
    setLoading(true);
    setMessage('');
    setVerdict('');
    setTesterAnswer('');
    setImprovedAnswer('');
    setTesterNote('');
    setChatAnswer('');
    try {
      const data = await apiFetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ audio_base64: b64, top_k: 5 }),
      });
      const ans = data.answer || 'No response received.';
      setChatAnswer(ans);
      setChatId(data.chat_id || '');
      if (data.transcribed_text) {
        setQuestion(data.transcribed_text);
      }
      if (data.audio_base64) {
        setAudioBase64(data.audio_base64);
        playAudio(data.audio_base64);
      }
    } catch (error) {
      setChatAnswer(`Error: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleTTS = async (textToSpeak) => {
    if (isPlaying) {
      stopAudio();
      return;
    }
    if (audioBase64) {
      playAudio(audioBase64);
      return;
    }
    setLoading(true);
    try {
      const data = await apiFetch('/api/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: textToSpeak,
          chat_id: chatId || null
        }),
      });
      if (data.audio_base64) {
        setAudioBase64(data.audio_base64);
        playAudio(data.audio_base64);
      }
    } catch (err) {
      alert("TTS failed: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  const askChatbot = async () => {
    const q = question.trim();
    if (!q || loading) return;
    stopAudio();
    setAudioBase64('');
    setLoading(true);
    setMessage('');
    setVerdict('');
    setTesterAnswer('');
    setImprovedAnswer('');
    setTesterNote('');
    try {
      const data = await apiFetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q, top_k: 5 }),
      });
      setChatAnswer(data.answer || 'No response received.');
      setChatId(data.chat_id || '');
    } catch (error) {
      setChatAnswer(`Error: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const improveAnswer = async () => {
    if (!testerAnswer.trim()) return;
    try {
      const data = await apiFetch('/api/tester/improve-answer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, draft_answer: testerAnswer }),
      });
      setImprovedAnswer(data.improved_answer || testerAnswer);
    } catch (error) {
      setMessage(`Improve failed: ${error.message}`);
    }
  };

  const submitReview = async () => {
    if (!question.trim() || !chatAnswer.trim() || !verdict) {
      setMessage('Ask a question, receive answer, then choose right/wrong.');
      return;
    }
    setSaving(true);
    setMessage('');
    try {
      const data = await apiFetch('/api/tester/flag-response', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question,
          chatbot_answer: chatAnswer,
          verdict,
          tester_answer: verdict === 'wrong' ? testerAnswer : null,
          tester_answer_improved: verdict === 'wrong' ? improvedAnswer : null,
          tester_note: testerNote || null,
          tester_id: testerId,
          chat_id: chatId || null,
        }),
      });
      setMessage(data.message || `Submitted: ${data.status}`);
    } catch (error) {
      setMessage(`Submit failed: ${error.message}`);
    } finally {
      setSaving(false);
    }
  };

  const isMessageError = /error|failed|required/i.test(message);

  return (
    <section className="tester-page">
      <div className="tester-site-shell">
        <header className="tester-top-strip">
          <div className="tester-logo-pack">
            <div className="tester-logo-badge">CHAT</div>
            <div className="tester-logo-text">
              <strong>White-label Chat</strong>
              <span>Secure conversational experience</span>
            </div>
            <div className="tester-grade">Trusted Chat Assistant</div>
          </div>
          <div className="tester-top-links">
            <span>Admission Open</span>
            <span>Student</span>
            <span>Examination</span>
            <span>IQAC</span>
            <span>Careers</span>
            <span className="tester-helpline">Admission Helpline 9027068068</span>
          </div>
        </header>

        <nav className="tester-main-nav">
          <span>About Us</span>
          <span>Academics</span>
          <span>Courses</span>
          <span>Admissions</span>
          <span>Campus Life</span>
          <span>Placements</span>
          <span>Research and Innovation</span>
        </nav>

        <section className="tester-hero">
          <div className="tester-hero-left">
            <p className="tester-hero-kicker">Powered Chat</p>
            <h2>
              Customer-ready
              <span>Experience</span>
            </h2>
            <p>
              A modern AI chat experience for your users, with secure document support and admin controls.
            </p>
          </div>
          <div className="tester-hero-right">
            <p className="tester-hero-student">Product Demo | Live Assistant</p>
            <div className="tester-company-pill">Trusted by teams</div>
            <div className="tester-package">
              <strong>24/7</strong>
              <span>AI assistant support</span>
            </div>
          </div>
        </section>

        <section className="tester-stats-section">
          <p className="tester-stats-eyebrow">Legacy</p>
          <h3>A Legacy of Educational Excellence</h3>
          <div className="tester-stats-grid">
            <article>
              <strong>86%</strong>
              <span>Overall Placement in Past 5 Years</span>
            </article>
            <article>
              <strong>46,000+</strong>
              <span>Alumni Settled across the Globe</span>
            </article>
            <article>
              <strong>850+</strong>
              <span>Faculty Members from Global Institutions</span>
            </article>
            <article>
              <strong>26,000+</strong>
              <span>Students Enrolled in Different Courses</span>
            </article>
          </div>
        </section>

        {/* Tester AI Moderation Queue */}
        <section style={{ maxWidth: '1200px', margin: '2.5rem auto', padding: '0 2rem' }}>
          <TesterAiQueue testerId={testerId} />
        </section>

        <div className="tester-left-quick-tools" aria-hidden="true">
          <span>360°</span>
          <span>Alerts</span>
        </div>
        <div className="tester-admission-ribbon" aria-hidden="true">Admission Query</div>

        <button
          type="button"
          className="tester-launcher"
          onClick={() => setWidgetOpen((prev) => !prev)}
          aria-expanded={widgetOpen}
          aria-controls="tester-chat-widget"
          aria-label={widgetOpen ? 'Close tester chatbot' : 'Open tester chatbot'}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M4 5h16a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H9l-5 4V6a1 1 0 0 1 1-1zm2 4h12v2H6V9zm0 4h8v2H6v-2z" />
          </svg>
        </button>

        {widgetOpen && (
          <aside id="tester-chat-widget" className="tester-widget" role="dialog" aria-modal="false">
            <header className="tester-widget-head">
              <div>
                <h4>Tester Chat Console</h4>
                <p>Ask, verify, and push corrections in one flow.</p>
              </div>
              <button type="button" className="tester-widget-close" onClick={() => setWidgetOpen(false)}>
                Close
              </button>
            </header>

            <div className="tester-widget-body">
              <label className="tester-field">
                <span>Tester ID</span>
                <input value={testerId} onChange={(e) => setTesterId(e.target.value)} maxLength={120} />
              </label>

              <div className="tester-chip-wrap">
                {predefined.map((item) => (
                  <button key={item.id} type="button" className="tester-chip" onClick={() => setQuestion(item.question)}>
                    {item.question}
                  </button>
                ))}
              </div>

              <div style={{ position: 'relative' }}>
                <label className="tester-field">
                  <span>Question</span>
                  <textarea
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    maxLength={500}
                    rows={4}
                    placeholder="Ask or pick a predefined question"
                    style={{ paddingRight: '45px' }}
                  />
                </label>
                <button
                  type="button"
                  onClick={isRecording ? stopRecording : startVoiceInput}
                  style={{
                    position: 'absolute',
                    right: '12px',
                    bottom: '12px',
                    background: isRecording ? '#ef4444' : 'var(--paper-muted)',
                    color: isRecording ? '#fff' : 'var(--text)',
                    border: '1px solid var(--line)',
                    borderRadius: '50%',
                    width: '36px',
                    height: '36px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    cursor: 'pointer',
                    boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
                    transition: 'all 0.2s',
                  }}
                  title={isRecording ? "Stop Recording" : "Voice Input (Mic)"}
                >
                  {isRecording ? <Square size={16} /> : <Mic size={16} />}
                </button>
              </div>

              <button type="button" className="tester-primary-btn" onClick={askChatbot} disabled={loading}>
                {loading ? 'Asking...' : 'Ask Chatbot'}
              </button>

              {/* AI batch question generator */}
              <button
                type="button"
                className="tester-secondary-btn"
                onClick={() => { setShowGeneratePanel((p) => !p); setGenerateResult(null); setGenerateError(''); }}
                style={{ marginTop: '4px' }}
              >
                {showGeneratePanel ? 'Hide Generator' : 'Generate Questions with AI'}
              </button>

              {showGeneratePanel && (
                <div style={{ marginTop: '8px', padding: '12px', background: 'rgba(0,0,0,0.03)', borderRadius: '8px', border: '1px solid rgba(28,53,77,0.14)' }}>
                  <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', marginBottom: '8px' }}>
                    <label className="tester-field" style={{ flex: '2 1 200px', margin: 0 }}>
                      <span>Topic</span>
                      <textarea
                        value={generateTopic}
                        onChange={(e) => setGenerateTopic(e.target.value)}
                        maxLength={200}
                        rows={2}
                        placeholder="e.g. placements, hostel fees, B.Tech admission, scholarships"
                        disabled={generating}
                      />
                    </label>
                    <label className="tester-field" style={{ flex: '1 1 80px', margin: 0 }}>
                      <span>Count</span>
                      <input
                        type="number"
                        min={1}
                        max={50}
                        value={generateCount}
                        onChange={(e) => {
                          const val = e.target.value;
                          if (val === '') {
                            setGenerateCount('');
                          } else {
                            const num = Number(val);
                            if (!isNaN(num)) {
                              setGenerateCount(num);
                            }
                          }
                        }}
                        onBlur={() => {
                          let num = Number(generateCount);
                          if (isNaN(num) || num <= 0) {
                            setGenerateCount(20);
                          } else {
                            setGenerateCount(Math.max(1, Math.min(50, num)));
                          }
                        }}
                        disabled={generating}
                        style={{ padding: '8px', borderRadius: '4px', border: '1px solid var(--line)', background: '#fff', fontSize: '13px', boxSizing: 'border-box', height: '48px', marginTop: '4px', width: '100%' }}
                      />
                    </label>
                  </div>
                  <button
                    type="button"
                    className="tester-primary-btn"
                    onClick={generateAndTest}
                    disabled={generating || !generateTopic.trim()}
                  >
                    {generating ? 'Generating and testing...' : 'Generate and Test'}
                  </button>
                  {generating && (
                    <p style={{ marginTop: '8px', fontSize: '12px', color: 'var(--ink)', opacity: 0.7 }}>
                      Generating questions and running them through the chatbot. This may take 10-20 seconds.
                    </p>
                  )}
                  {generateResult && (
                    <div className="tester-widget-flash success" style={{ marginTop: '10px', padding: '10px' }}>
                      Done. {generateResult.total_stored} questions tested and sent to the Moderation tab for topic "{generateResult.topic}".
                    </div>
                  )}
                  {generateError && (
                    <div className="tester-widget-flash error" style={{ marginTop: '10px', padding: '10px' }}>
                      {generateError}
                    </div>
                  )}
                </div>
              )}

              {chatAnswer && (
                <div className="tester-answer-card">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <p className="tester-answer-label" style={{ margin: 0 }}>Chatbot Answer</p>
                    <button
                      type="button"
                      onClick={() => handleTTS(chatAnswer)}
                      style={{
                        background: isPlaying ? 'var(--moss)' : 'var(--paper-muted)',
                        color: isPlaying ? '#fff' : 'var(--text)',
                        border: '1px solid var(--line)',
                        borderRadius: '6px',
                        padding: '4px 8px',
                        fontSize: '12px',
                        fontWeight: '600',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px',
                        cursor: 'pointer',
                      }}
                    >
                      <Volume2 size={14} />
                      {isPlaying ? 'Stop' : 'Listen'}
                    </button>
                  </div>
                  <div dangerouslySetInnerHTML={{ __html: parseAnswer(chatAnswer).bodyHtml }} style={{ fontSize: '14px', lineHeight: '1.6' }} />
                </div>
              )}

              {chatAnswer && (
                <div className="tester-review-card">
                  <p className="tester-answer-label">Validation Verdict</p>
                  <div className="tester-verdict-row">
                    <button
                      type="button"
                      className={`tester-verdict-btn ${verdict === 'right' ? 'selected right' : ''}`}
                      onClick={() => setVerdict('right')}
                    >
                      Response is Right
                    </button>
                    <button
                      type="button"
                      className={`tester-verdict-btn ${verdict === 'wrong' ? 'selected wrong' : ''}`}
                      onClick={() => setVerdict('wrong')}
                    >
                      Response is Wrong
                    </button>
                  </div>

                  {verdict === 'wrong' && (
                    <div className="tester-correction-stack">
                      <label className="tester-field">
                        <span>Correct Answer</span>
                        <textarea value={testerAnswer} onChange={(e) => setTesterAnswer(e.target.value)} rows={4} maxLength={8000} />
                      </label>

                      <button type="button" className="tester-secondary-btn" onClick={improveAnswer}>
                        Improve with AI
                      </button>

                      {improvedAnswer && (
                        <label className="tester-field">
                          <span>Improved Answer</span>
                          <textarea value={improvedAnswer} onChange={(e) => setImprovedAnswer(e.target.value)} rows={4} maxLength={8000} />
                        </label>
                      )}
                    </div>
                  )}

                  {verdict && (
                    <div className="tester-correction-stack" style={{ marginTop: '12px' }}>
                      <label className="tester-field">
                        <span>Notes for Admin</span>
                        <textarea value={testerNote} onChange={(e) => setTesterNote(e.target.value)} rows={2} maxLength={2000} placeholder="Add any comments here..." />
                      </label>
                    </div>
                  )}

                  <button type="button" className="tester-submit-btn" onClick={submitReview} disabled={saving} style={{ marginTop: '16px' }}>
                    {saving ? 'Submitting...' : 'Submit Review'}
                  </button>
                </div>
              )}

              {message && <div className={`tester-widget-flash ${isMessageError ? 'error' : 'success'}`}>{message}</div>}
            </div>
          </aside>
        )}
      </div>
    </section>
  );
}



function OperationsCenter() {
  const roleData = useContext(RoleContext);
  const isSuper = roleData?.role === 'super_admin';
  const isDept = roleData?.role === 'dept_admin';
  const [activeTab, setActiveTab] = useState('overview');
  const navigate = useNavigate();

  const { metrics, loading: metricsLoading, refetch: refetchMetrics } = useAdminMetrics();
  const { summary, loading: summaryLoading, refetch: refetchSummary } = useUploads();
  const { flagged, negativeFeedback, approveFlagged, rejectFlagged, refetch: refetchFeedback, deleteNegativeFeedback } = useFeedback();
  const { corrections, refetch: refetchCorrections } = useCorrections();
  const { sessions, chats, loading: liveLoading, error: liveError, refetch: refetchLive } = useSupabaseSessions();

  // Quick Action States
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [statsModalOpen, setStatsModalOpen] = useState(false);
  const [statsLoading, setStatsLoading] = useState(false);
  const [statsData, setStatsData] = useState(null);
  const [statsError, setStatsError] = useState(null);
  const [clearingCache, setClearingCache] = useState(false);
  const [actionMessage, setActionMessage] = useState(null); // { type: 'success'|'error', text: string }

  const handleRefresh = () => {
    refetchMetrics();
    refetchSummary();
    refetchFeedback();
    refetchCorrections();
  };

  const isLoading = metricsLoading || summaryLoading;

  const triggerClearCache = async () => {
    setDropdownOpen(false);
    setClearingCache(true);
    setActionMessage(null);
    try {
      await apiFetch('/api/admin/cache/clear', { method: 'POST' });
      setActionMessage({ type: 'success', text: 'Cache cleared successfully! Chat responses are now synchronized.' });
      setTimeout(() => setActionMessage(null), 6000);
      handleRefresh();
    } catch (err) {
      setActionMessage({ type: 'error', text: `Failed to clear cache: ${err.message}` });
    } finally {
      setClearingCache(false);
    }
  };

  const triggerViewStats = async () => {
    setDropdownOpen(false);
    setStatsModalOpen(true);
    setStatsLoading(true);
    setStatsError(null);
    try {
      const data = await apiFetch('/api/admin/cache/stats');
      setStatsData(data);
    } catch (err) {
      setStatsError(err.message);
    } finally {
      setStatsLoading(false);
    }
  };

  return (
    <section className="panel panel-feature" style={{ minHeight: 'calc(100vh - 40px)', padding: '20px', position: 'relative' }}>
      <div className="panel-headline" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
        <div>
          <p className="panel-kicker">Moderation + Monitoring</p>
          <h2>Operations Center</h2>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <button
            type="button"
            className="btn-dash"
            onClick={handleRefresh}
            disabled={isLoading}
            style={{
              background: 'var(--paper)',
              color: 'var(--ink)',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
            {isLoading ? 'Refreshing...' : 'Refresh'}
          </button>

          {/* Working Quick Actions Dropdown */}
          <div className="dropdown" style={{ position: 'relative' }}>
            <button
              className="btn-dash"
              onClick={() => setDropdownOpen(!dropdownOpen)}
              style={{ background: 'var(--moss)', color: '#fff', border: 'none' }}
              aria-haspopup="true"
              aria-expanded={dropdownOpen}
            >
              + Quick Actions ▾
            </button>
            {dropdownOpen && (
              <>
                <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, zIndex: 90 }} onClick={() => setDropdownOpen(false)} />
                <ul className="quick-dropdown-menu">
                  <li>
                    <button className="quick-dropdown-item" onClick={triggerClearCache} disabled={clearingCache}>
                      🧹 {clearingCache ? 'Clearing...' : 'Clear Response Cache'}
                    </button>
                  </li>
                  <li>
                    <button className="quick-dropdown-item" onClick={triggerViewStats}>
                      📊 View Cache Stats
                    </button>
                  </li>
                  <li>
                    <button className="quick-dropdown-item" onClick={() => { setDropdownOpen(false); navigate('/blocked-terms'); }}>
                      🚫 Block New Phrase
                    </button>
                  </li>
                  <li>
                    <button className="quick-dropdown-item" onClick={() => { setDropdownOpen(false); navigate('/upload'); }}>
                      📁 Ingest Document
                    </button>
                  </li>
                </ul>
              </>
            )}
          </div>
        </div>
      </div>

      {actionMessage && (
        <div style={{
          marginBottom: '16px',
          padding: '12px 16px',
          borderRadius: '4px',
          fontSize: '13px',
          background: actionMessage.type === 'error' ? 'rgba(239, 68, 68, 0.08)' : 'rgba(16, 185, 129, 0.08)',
          border: actionMessage.type === 'error' ? '1px solid rgba(239, 68, 68, 0.2)' : '1px solid rgba(16, 185, 129, 0.2)',
          color: actionMessage.type === 'error' ? 'var(--danger)' : 'var(--moss)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <span>{actionMessage.text}</span>
          <button onClick={() => setActionMessage(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'inherit', fontWeight: 'bold' }}>✕</button>
        </div>
      )}

      {summary && (
        <div className="metric-grid compact admin-metric-grid" style={{ marginBottom: '16px', gridTemplateColumns: isSuper ? 'repeat(4, 1fr)' : 'repeat(2, 1fr)' }}>
          {isSuper && (
            <>
              <article className="metric-card compact-panel" style={{ borderTop: '3px solid var(--orange)', padding: '12px' }}>
                <span className="metric-label">Pending Reviews</span>
                <strong className="metric-value" style={{ fontSize: '20px' }}>{formatCount(summary.flagged.pending)}</strong>
              </article>
              <article className="metric-card compact-panel" style={{ borderTop: '3px solid var(--accent)', padding: '12px' }}>
                <span className="metric-label">Corrections</span>
                <strong className="metric-value" style={{ fontSize: '20px' }}>{formatCount(summary.corrections.active)}</strong>
              </article>
            </>
          )}
          <article className="metric-card compact-panel" style={{ borderTop: '3px solid var(--teal)', padding: '12px' }}>
            <span className="metric-label">Upload Chunks</span>
            <strong className="metric-value" style={{ fontSize: '20px' }}>{formatCount(summary.uploads.active_chunks)}</strong>
          </article>
          <article className="metric-card compact-panel" style={{ borderTop: '3px solid var(--moss)', padding: '12px' }}>
            <span className="metric-label">System Health</span>
            <strong className="metric-value" style={{ fontSize: '20px', color: 'var(--moss)' }}>Optimal</strong>
          </article>
        </div>
      )}

      <div className="dashboard-tabs" style={{ marginBottom: '16px', overflowX: 'auto', whiteSpace: 'nowrap' }}>
        {(!roleData?.role || isSuper) && <button className={`tab-btn ${activeTab === 'overview' ? 'active' : ''}`} onClick={() => setActiveTab('overview')}>Overview</button>}
        {(!roleData?.role || isSuper) && <button className={`tab-btn ${activeTab === 'moderation' ? 'active' : ''}`} onClick={() => setActiveTab('moderation')}>Moderation</button>}
        {(!roleData?.role || isSuper) && <button className={`tab-btn ${activeTab === 'corrections' ? 'active' : ''}`} onClick={() => setActiveTab('corrections')}>Corrections</button>}
        {(!roleData?.role || isSuper) && <button className={`tab-btn ${activeTab === 'live' ? 'active' : ''}`} onClick={() => setActiveTab('live')}>Live Activity</button>}
        {(!roleData?.role || isSuper) && <button className={`tab-btn ${activeTab === 'visitor_sessions' ? 'active' : ''}`} onClick={() => setActiveTab('visitor_sessions')}>Visitor Sessions</button>}
        {(!roleData?.role || isSuper) && <button className={`tab-btn ${activeTab === 'audit_logs' ? 'active' : ''}`} onClick={() => setActiveTab('audit_logs')}>Audit Logs</button>}
      </div>

      <div className="tab-content" style={{ minHeight: '400px' }}>
        {(!roleData?.role || isSuper) && activeTab === 'overview' && <OverviewTab analytics={metrics} />}
        {(!roleData?.role || isSuper) && activeTab === 'moderation' && <ModerationTab flagged={flagged} negativeFeedback={negativeFeedback} approveFlagged={approveFlagged} rejectFlagged={rejectFlagged} deleteNegativeFeedback={deleteNegativeFeedback} />}
        {(!roleData?.role || isSuper) && activeTab === 'corrections' && <CorrectionsTab corrections={corrections} refetch={refetchCorrections} />}
        {(!roleData?.role || isSuper) && activeTab === 'live' && <LiveActivityTab sessions={sessions} chats={chats} loading={liveLoading} error={liveError} refetch={refetchLive} />}
        {(!roleData?.role || isSuper) && activeTab === 'visitor_sessions' && <VisitorSessionsTab />}
        {(!roleData?.role || isSuper) && activeTab === 'audit_logs' && <AuditLogsTab />}

        {isDept && (activeTab === 'my_docs' || activeTab === 'overview') && <MyDocumentsTab userEmail={roleData.email} />}
      </div>

      {/* Cache Stats Modal */}
      {statsModalOpen && (
        <div className="modal-overlay" onClick={() => setStatsModalOpen(false)}>
          <div className="modal-container" onClick={(e) => e.stopPropagation()} style={{ padding: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', borderBottom: '1px solid var(--line)', paddingBottom: '10px' }}>
              <h3 style={{ margin: 0, fontSize: '16px', color: 'var(--moss)', fontWeight: '600' }}>Cache System Statistics</h3>
              <button onClick={() => setStatsModalOpen(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '18px', color: 'var(--ink)' }}>✕</button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {statsLoading ? (
                <p style={{ textAlign: 'center', fontSize: '13px', margin: '20px 0' }}>Loading cache metrics...</p>
              ) : statsError ? (
                <p style={{ color: 'var(--danger)', fontSize: '13px' }}>Error: {statsError}</p>
              ) : statsData ? (
                <>
                  <div style={{ padding: '10px', background: 'var(--paper-muted)', borderRadius: '4px' }}>
                    <span style={{ fontSize: '10px', textTransform: 'uppercase', opacity: 0.6, display: 'block', fontWeight: 600 }}>Knowledge Data Version</span>
                    <strong style={{ fontSize: '13px', fontFamily: 'monospace' }}>{statsData.data_version}</strong>
                  </div>

                  <div style={{ padding: '10px', background: 'var(--paper-muted)', borderRadius: '4px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <span style={{ fontSize: '10px', textTransform: 'uppercase', opacity: 0.6, display: 'block', fontWeight: 600 }}>File Response Cache</span>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12.5px' }}>
                      <span>Total / Live / Stale:</span>
                      <strong>{statsData.file_cache?.total_entries ?? 0} / {statsData.file_cache?.live_entries ?? 0} / {statsData.file_cache?.stale_entries ?? 0}</strong>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12.5px' }}>
                      <span>Configured TTL:</span>
                      <strong>{((statsData.file_cache?.ttl_sec ?? 0) / 3600).toFixed(0)} hours</strong>
                    </div>
                  </div>

                  <div style={{ padding: '10px', background: 'var(--paper-muted)', borderRadius: '4px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <span style={{ fontSize: '10px', textTransform: 'uppercase', opacity: 0.6, display: 'block', fontWeight: 600 }}>Redis Response Cache</span>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12.5px' }}>
                      <span>Connection Status:</span>
                      <strong style={{ color: statsData.redis_cache?.enabled ? 'var(--moss)' : 'var(--danger)' }}>
                        {statsData.redis_cache?.enabled ? 'Connected' : 'Offline'}
                      </strong>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12.5px' }}>
                      <span>Cache TTL:</span>
                      <strong>{((statsData.redis_cache?.ttl_sec ?? 0) / 3600).toFixed(0)} hours</strong>
                    </div>
                  </div>

                  <div style={{ padding: '10px', background: 'var(--paper-muted)', borderRadius: '4px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <span style={{ fontSize: '10px', textTransform: 'uppercase', opacity: 0.6, display: 'block', fontWeight: 600 }}>Query Embedding LRU Cache</span>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12.5px' }}>
                      <span>Current / Capacity:</span>
                      <strong>{statsData.embed_cache?.in_memory_entries ?? 0} / {statsData.embed_cache?.max_size ?? 0}</strong>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12.5px' }}>
                      <span>In-Memory TTL:</span>
                      <strong>{((statsData.embed_cache?.ttl_sec ?? 0) / 60).toFixed(0)} minutes</strong>
                    </div>
                  </div>
                </>
              ) : (
                <p style={{ textAlign: 'center', fontSize: '13px' }}>No stats data returned.</p>
              )}
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '16px', borderTop: '1px solid var(--line)', paddingTop: '10px' }}>
              <button
                onClick={() => setStatsModalOpen(false)}
                className="btn-dash"
                style={{ background: 'var(--moss)', color: '#fff', border: 'none', padding: '6px 16px' }}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}


function UploadPage() {
  const roleData = useContext(RoleContext);
  const isSuper = roleData?.role === 'super_admin';
  const isDept = roleData?.role === 'dept_admin';
  const [activeTab, setActiveTab] = useState(isDept ? 'my_docs' : 'upload');

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '16px', height: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ fontSize: '1.4rem', margin: 0, color: '#111827', letterSpacing: '-0.02em' }}>Documents</h2>
          <p style={{ fontSize: '13px', color: '#6b7280', margin: '4px 0 0' }}>Manage knowledge base documents and approvals</p>
        </div>
      </div>
      
      <div className="dashboard-tabs" style={{ marginBottom: '16px', overflowX: 'auto', whiteSpace: 'nowrap' }}>
        {isSuper && <button className={`tab-btn ${activeTab === 'upload' ? 'active' : ''}`} onClick={() => setActiveTab('upload')}>Upload Documents</button>}
        {isSuper && <button className={`tab-btn ${activeTab === 'pending' ? 'active' : ''}`} onClick={() => setActiveTab('pending')}>Pending Approvals</button>}
        {isDept && <button className={`tab-btn ${activeTab === 'my_docs' ? 'active' : ''}`} onClick={() => setActiveTab('my_docs')}>My Documents</button>}
      </div>
      
      <div className="tab-content" style={{ flex: 1, overflowY: 'auto' }}>
        {isSuper && activeTab === 'upload' && <UploadContent />}
        {isSuper && activeTab === 'pending' && <PendingApprovalsTab userEmail={roleData?.email} />}
        {isDept && activeTab === 'my_docs' && <MyDocumentsTab userEmail={roleData?.email} />}
      </div>
    </section>
  );
}

function UploadContent() {
  const [ingestMode, setIngestMode] = useState('file'); // 'file' or 'text'
  const [file, setFile] = useState(null);
  const [rawText, setRawText] = useState('');
  const [title, setTitle] = useState('');
  const [departmentSlug, setDepartmentSlug] = useState('');
  const [departmentGroups, setDepartmentGroups] = useState([]);
  const [uploaderId, setUploaderId] = useState('uploader-01');
  const [uploaderKey, setUploaderKey] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  const [uploads, setUploads] = useState([]);
  const [viewStatus, setViewStatus] = useState('active'); // 'active' or 'deleted'

  const loadUploads = async (status = viewStatus) => {
    try {
      const data = await apiFetch(`/api/upload/documents?limit=50&status=${status}`);
      setUploads(data.items || []);
    } catch {
      setUploads([]);
    }
  };

  const loadDepartments = async () => {
    try {
      const data = await apiFetch('/api/upload/departments');
      const groups = data.institutes || [];
      setDepartmentGroups(groups);
      const firstSlug = groups?.[0]?.departments?.[0]?.department_slug || '';
      setDepartmentSlug((prev) => prev || firstSlug);
    } catch (error) {
      setDepartmentGroups([]);
      setDepartmentSlug('');
      setMessage(`Department catalog load failed: ${error.message}`);
    }
  };

  useEffect(() => {
    loadDepartments();
  }, []);

  useEffect(() => {
    loadUploads(viewStatus);
  }, [viewStatus]);

  const handleIngest = async () => {
    if (ingestMode === 'file' && !file) return setMessage('Select a file first.');
    if (ingestMode === 'text' && !rawText.trim()) return setMessage('Enter raw text first.');
    if (!departmentSlug) return setMessage('Select a department before uploading.');

    const formData = new FormData();
    if (ingestMode === 'file') {
      formData.append('file', file);
      formData.append('source_type', 'file');
    } else {
      formData.append('raw_text', rawText);
      formData.append('source_type', 'text');
    }
    formData.append('title', title);
    formData.append('department_slug', departmentSlug);
    formData.append('uploader_id', uploaderId);

    setBusy(true);
    setMessage('');
    try {
      const response = await fetch(`${API_BASE}/api/upload/ingest`, {
        method: 'POST',
        headers: uploaderKey.trim() ? { 'X-Uploader-Key': uploaderKey.trim() } : {},
        body: formData,
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload?.detail || 'Ingestion failed');

      const deptLabel = payload.department_name ? ` under ${payload.department_name}` : '';
      setMessage(`✅ Ingested: ${payload.chunks_saved} chunks for ${payload.filename}${deptLabel}`);
      setFile(null);
      setRawText('');
      setTitle('');
      if (viewStatus === 'active') loadUploads('active');
    } catch (error) {
      setMessage(`❌ Ingestion failed: ${error.message}`);
    } finally {
      setBusy(false);
    }
  };

  const toggleUploadStatus = async (uploadId, currentStatus) => {
    const isDeactivating = currentStatus !== 'deleted';
    if (isDeactivating && !window.confirm('Are you sure you want to deactivate this file and remove its chunks from the chatbot?')) return;

    setBusy(true);
    setMessage('');
    try {
      if (isDeactivating) {
        await apiFetch(`/api/upload/documents/${uploadId}`, {
          method: 'DELETE',
          headers: uploaderKey.trim() ? { 'X-Uploader-Key': uploaderKey.trim() } : {},
        });
        setMessage('✅ File deactivated and removed from RAG index.');
      } else {
        await apiFetch(`/api/upload/documents/${uploadId}/reactivate`, {
          method: 'POST',
          headers: uploaderKey.trim() ? { 'X-Uploader-Key': uploaderKey.trim() } : {},
        });
        setMessage('✅ File reactivated! Note: You may need to trigger a reindex if it requires processing.');
      }
      loadUploads();
    } catch (error) {
      setMessage(`❌ Action failed: ${error.message}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="fade-in" style={{ padding: '24px', maxWidth: '1000px', margin: '0 auto' }}>
      <div style={{ marginBottom: '24px' }}>
        <h2 style={{ fontSize: '24px', color: 'var(--moss)', marginBottom: '8px' }}>Knowledge Base Management</h2>
        <p className="muted">Upload new knowledge files or raw text, and manage past ingestions.</p>
      </div>

      <div className="dashboard-main-grid" style={{ gridTemplateColumns: '1fr 1.5fr' }}>
        {/* LEFT: INGESTION FORM */}
        <div className="panel compact-panel">
          <div className="panel-header" style={{ padding: '16px' }}>
            <h3 style={{ fontSize: '16px' }}>Ingest New Knowledge</h3>
          </div>

          <div style={{ padding: '16px', borderBottom: '1px solid var(--line)' }}>
            <div className="dashboard-tabs" style={{ marginBottom: '16px' }}>
              <button className={`tab-btn ${ingestMode === 'file' ? 'active' : ''}`} onClick={() => setIngestMode('file')}>File Upload</button>
              <button className={`tab-btn ${ingestMode === 'text' ? 'active' : ''}`} onClick={() => setIngestMode('text')}>Raw Text</button>
            </div>

            <div className="form-stack">
              {ingestMode === 'file' ? (
                <input type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} className="admin-input" />
              ) : (
                <textarea
                  value={rawText}
                  onChange={(e) => setRawText(e.target.value)}
                  placeholder="Paste raw text here to be chunked and indexed directly..."
                  rows={6}
                  className="admin-input"
                  style={{ width: '100%' }}
                />
              )}

              <input className="admin-input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Display Title (optional)" maxLength={260} />

              <select className="admin-input" value={departmentSlug} onChange={(e) => setDepartmentSlug(e.target.value)} disabled={!departmentGroups.length || busy}>
                <option value="">Select department mapping...</option>
                {departmentGroups.map((group) => (
                  <optgroup key={group.institute_name} label={group.institute_name}>
                    {(group.departments || []).map((dept) => (
                      <option key={dept.department_slug} value={dept.department_slug}>
                        {dept.department_name}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>

              <div style={{ display: 'flex', gap: '8px' }}>
                <input className="admin-input" style={{ flex: 1 }} value={uploaderId} onChange={(e) => setUploaderId(e.target.value)} placeholder="Uploader ID" maxLength={120} />
                <input className="admin-input" style={{ flex: 1 }} value={uploaderKey} onChange={(e) => setUploaderKey(e.target.value)} placeholder="Uploader Key" type="password" />
              </div>

              <button className="btn-dash" style={{ width: '100%', justifyContent: 'center', marginTop: '8px' }} onClick={handleIngest} disabled={busy}>
                {busy ? 'Processing...' : 'Ingest to Chatbot DB'}
              </button>
            </div>
            {message && <div style={{ marginTop: '12px', padding: '12px', background: 'var(--paper-muted)', borderRadius: '6px', fontSize: '13px', color: message.includes('❌') ? 'var(--danger)' : 'var(--moss)' }}>{message}</div>}
          </div>
        </div>

        {/* RIGHT: PAST UPLOADS */}
        <div className="panel compact-panel">
          <div className="panel-header" style={{ padding: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ fontSize: '16px' }}>Upload History</h3>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <button
                onClick={() => apiDownload('/api/admin/upload-documents/export', `upload_history_${new Date().toISOString().split('T')[0]}.csv`)}
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
                  marginRight: '8px',
                  cursor: 'pointer'
                }}
              >
                <Download size={12} />
                Export CSV
              </button>
              <button className={`filter-chip ${viewStatus === 'active' ? 'active' : ''}`} onClick={() => setViewStatus('active')}>Active</button>
              <button className={`filter-chip ${viewStatus === 'deleted' ? 'active' : ''}`} onClick={() => setViewStatus('deleted')}>Deactivated</button>
            </div>
          </div>


          <div className="stack-list compact-stack" style={{ padding: '16px' }}>
            {uploads.map((item) => (
              <article key={item.id} className="record-card compact-record" style={{ borderLeft: `4px solid ${viewStatus === 'active' ? 'var(--moss)' : 'var(--danger)'}` }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <p style={{ fontSize: '14px', fontWeight: 600, color: 'var(--ink)' }}>{item.display_title || item.filename}</p>
                    <p style={{ fontSize: '12px', color: 'var(--ink)', opacity: 0.7, marginTop: '4px' }}>
                      {item.department_name} • {item.total_chunks} chunks
                    </p>
                  </div>
                  <div className="action-links" style={{ display: 'flex', gap: '8px', fontSize: '12px' }}>
                    <a href={`${API_BASE}/api/upload/documents/${item.id}/download`} target="_blank" rel="noreferrer" className="text-btn success" style={{ textDecoration: 'none' }}>View File</a>
                    {viewStatus === 'active' ? (
                      <button className="text-btn danger" onClick={() => toggleUploadStatus(item.id, item.status)} disabled={busy}>Deactivate</button>
                    ) : (
                      <button className="text-btn" style={{ color: 'var(--accent)' }} onClick={() => toggleUploadStatus(item.id, item.status)} disabled={busy}>Reactivate</button>
                    )}
                  </div>
                </div>
                {item.error_message && <p style={{ fontSize: '11px', color: 'var(--danger)', marginTop: '6px' }}>Error: {item.error_message}</p>}
              </article>
            ))}
            {!uploads.length && <div className="empty-state">No {viewStatus} uploads found.</div>}
          </div>
        </div>
      </div>
    </section>
  );
}

function LogExportPage() {
  const [rangeType, setRangeType] = useState('today');
  const [customFrom, setCustomFrom] = useState('');
  const [customTo, setCustomTo] = useState('');
  const [table, setTable] = useState('chats');
  const [exporting, setExporting] = useState(false);
  const [preview, setPreview] = useState([]);
  const [totalRows, setTotalRows] = useState(0);
  const [message, setMessage] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedRow, setExpandedRow] = useState(null);

  const getDateRange = () => {
    const now = new Date();
    const todayStr = now.toISOString().split('T')[0];
    if (rangeType === 'today') return { from: todayStr + 'T00:00:00', to: todayStr + 'T23:59:59' };
    if (rangeType === 'yesterday') {
      const y = new Date(now); y.setDate(y.getDate() - 1);
      const yStr = y.toISOString().split('T')[0];
      return { from: yStr + 'T00:00:00', to: yStr + 'T23:59:59' };
    }
    if (rangeType === 'last7') {
      const d = new Date(now); d.setDate(d.getDate() - 7);
      return { from: d.toISOString(), to: now.toISOString() };
    }
    if (rangeType === 'last30') {
      const d = new Date(now); d.setDate(d.getDate() - 30);
      return { from: d.toISOString(), to: now.toISOString() };
    }
    if (rangeType === 'thisMonth') {
      return { from: todayStr.substring(0, 7) + '-01T00:00:00', to: now.toISOString() };
    }
    if (rangeType === 'custom' && customFrom && customTo) {
      return { from: customFrom + 'T00:00:00', to: customTo + 'T23:59:59' };
    }
    return { from: todayStr + 'T00:00:00', to: now.toISOString() };
  };

  const dateCol = table === 'chats' ? 'asked_at' : table === 'feedback' ? 'submitted_at' : 'started_at';

  const fetchPreview = async () => {
    const { from, to } = getDateRange();
    setMessage('');
    try {
      const { data, error, count } = await supabase
        .from(table)
        .select('*', { count: 'exact' })
        .gte(dateCol, from)
        .lte(dateCol, to)
        .order(dateCol, { ascending: false })
        .limit(20);
      if (error) throw error;
      setPreview(data || []);
      setTotalRows(count || 0);
      setExpandedRow(null);
    } catch (err) {
      setMessage(`Preview failed: ${err.message}`);
    }
  };

  useEffect(() => { 
    setSearchQuery('');
    setExpandedRow(null);
    fetchPreview(); 
  }, [rangeType, table, customFrom, customTo]);

  const escapeCsv = (val) => {
    if (val === null || val === undefined) return '';
    const str = typeof val === 'object' ? JSON.stringify(val) : String(val);
    if (str.includes(',') || str.includes('"') || str.includes('\n')) {
      return '"' + str.replace(/"/g, '""') + '"';
    }
    return str;
  };

  const exportCsv = async () => {
    const { from, to } = getDateRange();
    setExporting(true);
    setMessage('');
    try {
      let allData = [];
      let offset = 0;
      const batchSize = 1000;
      while (true) {
        const { data, error } = await supabase
          .from(table)
          .select('*')
          .gte(dateCol, from)
          .lte(dateCol, to)
          .order(dateCol, { ascending: false })
          .range(offset, offset + batchSize - 1);
        if (error) throw error;
        if (!data || data.length === 0) break;
        allData = allData.concat(data);
        if (data.length < batchSize) break;
        offset += batchSize;
      }

      if (allData.length === 0) {
        setMessage('No data found for this range.');
        return;
      }

      const headers = Object.keys(allData[0]);
      const csvRows = [headers.join(',')];
      for (const row of allData) {
        csvRows.push(headers.map(h => escapeCsv(row[h])).join(','));
      }
      const csvString = csvRows.join('\n');
      const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${table}_${rangeType}_${new Date().toISOString().split('T')[0]}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      setMessage(`Exported ${allData.length} rows successfully!`);
    } catch (err) {
      setMessage(`Export failed: ${err.message}`);
    } finally {
      setExporting(false);
    }
  };

  const filteredPreview = useMemo(() => {
    if (!searchQuery.trim()) return preview;
    const q = searchQuery.toLowerCase().trim();
    return preview.filter(row => {
      return Object.entries(row).some(([key, val]) => {
        if (val === null || val === undefined) return false;
        const str = typeof val === 'object' ? JSON.stringify(val) : String(val);
        return str.toLowerCase().includes(q);
      });
    });
  }, [preview, searchQuery]);

  const previewCols = preview.length > 0 ? Object.keys(preview[0]).slice(0, 6) : [];

  return (
    <section className="panel panel-feature">
      <div className="panel-headline">
        <p className="panel-kicker">Monitoring & Export</p>
        <h2>Log Export Center</h2>
        <p className="muted">Download chat logs, feedback, and session data as CSV for any time range.</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginTop: '1rem' }}>
        <div>
          <label style={{ fontFamily: 'Teko, sans-serif', fontSize: '20px', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'rgba(22,24,18,0.7)' }}>Data Source</label>
          <select value={table} onChange={(e) => setTable(e.target.value)}>
            <option value="chats">Chat Logs</option>
            <option value="feedback">Feedback</option>
            <option value="sessions">Sessions</option>
            <option value="tts_logs">TTS Usage</option>
          </select>
        </div>
        <div>
          <label style={{ fontFamily: 'Teko, sans-serif', fontSize: '20px', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'rgba(22,24,18,0.7)' }}>Time Range</label>
          <select value={rangeType} onChange={(e) => setRangeType(e.target.value)}>
            <option value="today">Today</option>
            <option value="yesterday">Yesterday</option>
            <option value="last7">Last 7 Days</option>
            <option value="last30">Last 30 Days</option>
            <option value="thisMonth">This Month</option>
            <option value="custom">Custom Range</option>
          </select>
        </div>
      </div>

      {rangeType === 'custom' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginTop: '0.75rem' }}>
          <div>
            <label style={{ fontFamily: 'Teko, sans-serif', fontSize: '18px', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'rgba(22,24,18,0.6)' }}>From</label>
            <input type="date" value={customFrom} onChange={(e) => setCustomFrom(e.target.value)} />
          </div>
          <div>
            <label style={{ fontFamily: 'Teko, sans-serif', fontSize: '18px', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'rgba(22,24,18,0.6)' }}>To</label>
            <input type="date" value={customTo} onChange={(e) => setCustomTo(e.target.value)} />
          </div>
        </div>
      )}

      <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', marginTop: '1rem', flexWrap: 'wrap' }}>
        <button type="button" onClick={exportCsv} disabled={exporting}>
          <Download size={16} style={{ marginRight: 6, verticalAlign: 'middle' }} />
          {exporting ? 'Exporting...' : `Export ${totalRows} rows as CSV`}
        </button>
        <button type="button" onClick={fetchPreview} className="toggle">
          Refresh Preview
        </button>
        <div style={{ flex: 1, minWidth: '200px', display: 'flex', alignItems: 'center', position: 'relative' }}>
          <Search size={16} style={{ position: 'absolute', left: '10px', color: '#888', pointerEvents: 'none' }} />
          <input
            type="text"
            placeholder="Search in preview..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ padding: '8px 10px 8px 32px', border: '1px solid #e5e7eb', borderRadius: '7px', fontSize: '13px', width: '100%', outline: 'none', boxSizing: 'border-box' }}
          />
        </div>
      </div>

      {message && <div className={`flash ${/fail|error/i.test(message) ? 'error' : ''}`} style={{ marginTop: '1rem' }}>{message}</div>}

      <h3 style={{ marginTop: '1.5rem' }}>
        <FileText size={18} style={{ marginRight: 6, verticalAlign: 'middle' }} />
        Preview ({totalRows} total rows)
      </h3>

      {filteredPreview.length > 0 ? (
        <div style={{ overflowX: 'auto', marginTop: '0.75rem' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '15px', fontFamily: 'Poppins, sans-serif' }}>
            <thead>
              <tr>
                {previewCols.map(col => (
                  <th key={col} style={{ textAlign: 'left', padding: '8px 10px', borderBottom: '2px solid var(--line)', fontFamily: 'Teko, sans-serif', fontSize: '18px', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--moss)' }}>{col}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filteredPreview.map((row, ri) => (
                <Fragment key={ri}>
                  <tr 
                    onClick={() => setExpandedRow(expandedRow === ri ? null : ri)} 
                    style={{ borderBottom: '1px solid var(--line)', cursor: 'pointer', background: expandedRow === ri ? 'rgba(0,0,0,0.02)' : 'transparent' }}
                  >
                    {previewCols.map(col => (
                      <td key={col} style={{ padding: '6px 10px', maxWidth: '250px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: '14px' }}>
                        {typeof row[col] === 'object' ? JSON.stringify(row[col]).substring(0, 60) : String(row[col] ?? '').substring(0, 80)}
                      </td>
                    ))}
                  </tr>
                  {expandedRow === ri && (
                    <tr style={{ background: '#fcfcfc', borderBottom: '1px solid var(--line)' }}>
                      <td colSpan={previewCols.length} style={{ padding: '15px' }}>
                        <div style={{ background: 'var(--paper)', border: '1px solid var(--line)', borderRadius: '8px', padding: '16px' }}>
                          <h4 style={{ margin: '0 0 12px 0', fontSize: '14px', fontWeight: 600, color: 'var(--moss)', borderBottom: '1.5px solid var(--line)', paddingBottom: '6px' }}>
                            Full Row Details
                          </h4>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                            {Object.entries(row).map(([k, v]) => (
                              <div key={k} style={{ display: 'grid', gridTemplateColumns: '150px 1fr', gap: '8px', fontSize: '13px' }}>
                                <span style={{ fontWeight: 600, color: '#555', wordBreak: 'break-all' }}>{k}</span>
                                <span style={{ 
                                  whiteSpace: 'pre-wrap', 
                                  wordBreak: 'break-all', 
                                  fontFamily: 'monospace', 
                                  background: 'rgba(0,0,0,0.02)', 
                                  padding: '4px 8px', 
                                  borderRadius: '4px',
                                  border: '1.5px solid rgba(0,0,0,0.03)',
                                  userSelect: 'all' 
                                }}>
                                  {typeof v === 'object' ? JSON.stringify(v, null, 2) : String(v ?? '—')}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="muted" style={{ marginTop: '1rem' }}>No data in this range.</p>
      )}
    </section>
  );
}

function RAGKnowledgePage() {
  const [docs, setDocs] = useState([]);
  const [categories, setCategories] = useState([]);
  const [selectedCat, setSelectedCat] = useState('');
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [expandedIdx, setExpandedIdx] = useState(null);

  const adminHeaders = useMemo(() => ({ 'Content-Type': 'application/json', 'X-Admin-User': 'dashboard-admin' }), []);

  const loadDocs = async (cat = '') => {
    setLoading(true);
    try {
      const url = `/api/admin/rag-index?limit=500${cat ? `&category=${encodeURIComponent(cat)}` : ''}`;
      const data = await apiFetch(url, { headers: adminHeaders });
      setDocs(data.items || []);
      setCategories(data.categories || []);
      setTotal(data.total || 0);
    } catch (err) {
      setDocs([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadDocs(selectedCat); }, [selectedCat]);

  const filtered = searchTerm
    ? docs.filter(d => d.title.toLowerCase().includes(searchTerm.toLowerCase()) || d.text_preview.toLowerCase().includes(searchTerm.toLowerCase()))
    : docs;

  const catCounts = {};
  for (const d of docs) { catCounts[d.category] = (catCounts[d.category] || 0) + 1; }

  return (
    <section className="panel panel-feature">
      <div className="panel-headline">
        <p className="panel-kicker">Knowledge Base</p>
        <h2>RAG Index Viewer</h2>
        <p className="muted">All {total} documents/chunks currently used by the chatbot for retrieval.</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto', gap: '0.75rem', marginTop: '1rem', alignItems: 'end' }}>
        <div>
          <label style={{ fontFamily: 'Teko, sans-serif', fontSize: '18px', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'rgba(22,24,18,0.65)' }}>
            <Filter size={14} style={{ marginRight: 4, verticalAlign: 'middle' }} /> Category Filter
          </label>
          <select value={selectedCat} onChange={(e) => setSelectedCat(e.target.value)}>
            <option value="">All Categories</option>
            {categories.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div>
          <label style={{ fontFamily: 'Teko, sans-serif', fontSize: '18px', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'rgba(22,24,18,0.65)' }}>
            <Search size={14} style={{ marginRight: 4, verticalAlign: 'middle' }} /> Search
          </label>
          <input value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} placeholder="Search by title or content..." />
        </div>
        <button type="button" onClick={() => loadDocs(selectedCat)} disabled={loading}>
          {loading ? 'Loading...' : 'Refresh'}
        </button>
      </div>

      {categories.length > 0 && (
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '1rem' }}>
          {categories.map(c => (
            <button key={c} type="button" className={`chip ${selectedCat === c ? '' : 'toggle'}`} onClick={() => setSelectedCat(selectedCat === c ? '' : c)} style={{ fontSize: '15px', padding: '4px 10px', textTransform: 'capitalize' }}>
              <Database size={12} style={{ marginRight: 4, verticalAlign: 'middle' }} />
              {c} ({catCounts[c] || '...'})
            </button>
          ))}
        </div>
      )}

      <h3 style={{ marginTop: '1.5rem' }}>
        <Database size={18} style={{ marginRight: 6, verticalAlign: 'middle' }} />
        Showing {filtered.length} of {total} chunks
      </h3>

      <div className="stack-list" style={{ marginTop: '0.75rem' }}>
        {filtered.map((doc) => (
          <article
            key={doc.index}
            className="record-card soft"
            style={{ cursor: 'pointer', transition: 'all 0.15s ease' }}
            onClick={() => setExpandedIdx(expandedIdx === doc.index ? null : doc.index)}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div style={{ flex: 1 }}>
                <p style={{ marginBottom: '4px' }}><strong>#{doc.index + 1}</strong> — {doc.title || 'Untitled'}</p>
                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                  <span style={{ fontSize: '13px', padding: '2px 8px', background: 'rgba(38,69,49,0.12)', borderRadius: '4px', fontFamily: 'Poppins, sans-serif', color: 'var(--moss)' }}>{doc.category}</span>
                  <span style={{ fontSize: '13px', padding: '2px 8px', background: 'rgba(26,107,121,0.1)', borderRadius: '4px', fontFamily: 'Poppins, sans-serif', color: 'var(--teal)' }}>{doc.section_type}</span>
                  <span style={{ fontSize: '13px', padding: '2px 8px', background: 'rgba(197,122,31,0.1)', borderRadius: '4px', fontFamily: 'Poppins, sans-serif', color: 'var(--accent)' }}>{doc.text_length} chars</span>
                </div>
              </div>
            </div>

            {expandedIdx === doc.index && (
              <div style={{ marginTop: '0.75rem', paddingTop: '0.75rem', borderTop: '1px solid var(--line)' }} onClick={(e) => e.stopPropagation()}>
                <p style={{ fontSize: '16px', lineHeight: '1.5', color: 'rgba(22,24,18,0.85)', whiteSpace: 'pre-wrap', background: 'rgba(255,255,255,0.6)', padding: '10px', borderRadius: '8px' }}>
                  {doc.text_preview}
                </p>
                {doc.url && (
                  <p style={{ fontSize: '14px', marginTop: '6px' }}>
                    <strong>Source:</strong>{' '}
                    <a href={doc.url} target="_blank" rel="noreferrer" style={{ color: 'var(--teal)', textDecoration: 'none' }}>{doc.url}</a>
                  </p>
                )}
              </div>
            )}
          </article>
        ))}
        {!filtered.length && <p className="muted">No documents match your filters.</p>}
      </div>
    </section>
  );
}


function AccessManagementPage() {
  const [activeTab, setActiveTab] = useState('departments');
  const roleData = useContext(RoleContext);
  
  if (roleData?.role !== 'super_admin') {
    return <div className="chrome-shell"><div className="empty-state">Access Denied</div></div>;
  }

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '16px', height: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ fontSize: '1.4rem', margin: 0, color: '#111827', letterSpacing: '-0.02em' }}>Access Control</h2>
          <p style={{ fontSize: '13px', color: '#6b7280', margin: '4px 0 0' }}>Manage RBAC, Departments, and Roles</p>
        </div>
      </div>
      <div className="dashboard-tabs" style={{ marginBottom: '16px', overflowX: 'auto', whiteSpace: 'nowrap' }}>
        <button className={`tab-btn ${activeTab === 'departments' ? 'active' : ''}`} onClick={() => setActiveTab('departments')}>Departments</button>
        <button className={`tab-btn ${activeTab === 'users' ? 'active' : ''}`} onClick={() => setActiveTab('users')}>Users</button>
        <button className={`tab-btn ${activeTab === 'settings' ? 'active' : ''}`} onClick={() => setActiveTab('settings')}>Settings</button>
      </div>
      <div className="tab-content" style={{ flex: 1, overflowY: 'auto' }}>
        {activeTab === 'departments' && <DepartmentsTab userEmail={roleData?.email} />}
        {activeTab === 'users' && <UsersTab userEmail={roleData?.email} />}
        {activeTab === 'settings' && <SettingsTab userEmail={roleData?.email} />}
      </div>
    </section>
  );
}

function AppRouter() {
  const roleData = useContext(RoleContext);
  const isSuper = !roleData?.role || roleData?.role === "super_admin";
  const isDept = roleData?.role === "dept_admin";
  const [status, setStatus] = useState(null);
  const [workflow, setWorkflow] = useState(null);

  const refresh = async () => {
    try {
      const [statusData, workflowData] = await Promise.all([
        apiFetch('/api/status'),
        apiFetch('/api/workflow/summary'),
      ]);
      setStatus(statusData);
      setWorkflow(workflowData);
    } catch {
      setStatus(null);
      setWorkflow(null);
    }
  };

  useEffect(() => {
    refresh();
    const id = window.setInterval(refresh, 20000);
    return () => window.clearInterval(id);
  }, []);

  return (
    <Shell status={status} workflow={workflow}>
      <Routes>
        <Route path="/" element={<Navigate to={isDept ? "/admin" : "/dashboard"} replace />} />
        {isSuper && <Route path="/dashboard" element={<DashboardPage status={status} workflow={workflow} />} />}
        {isSuper && <Route path="/chat" element={<ChatPage />} />}
        {isSuper && <Route path="/tester" element={<TesterPage />} />}
        <Route path="/admin" element={<OperationsCenter />} />
        {isSuper && <Route path="/blocked-terms" element={<BlockedWordsPage />} />}
        {isSuper && <Route path="/logs" element={<LogExportPage />} />}
        {isSuper && <Route path="/rag-knowledge" element={<RAGKnowledgePage />} />}
        {(isSuper || isDept) && <Route path="/upload" element={<UploadPage />} />}
        {isSuper && <Route path="/access" element={<AccessManagementPage />} />}
        <Route path="*" element={<Navigate to={isDept ? "/admin" : "/dashboard"} replace />} />
      </Routes>
    </Shell>
  );
}

function BlockedWordsPage() {
  const [words, setWords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [newWord, setNewWord] = useState('');
  const [newReason, setNewReason] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [search, setSearch] = useState('');

  const load = () => {
    setLoading(true);
    apiFetch('/api/admin/blocked-words')
      .then(d => setWords(d.items || []))
      .catch(() => setError('Failed to load blocked words'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleAdd = async (e) => {
    e.preventDefault();
    if (!newWord.trim()) return;
    setSaving(true); setError(''); setSuccess('');
    try {
      await apiFetch('/api/admin/blocked-words', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ word: newWord.trim(), reason: newReason.trim() || null }),
      });
      setSuccess(`"${newWord.trim()}" blocked successfully.`);
      setNewWord(''); setNewReason('');
      load();
    } catch (err) {
      setError('Failed to add blocked word. It may already exist.');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id, word) => {
    if (!window.confirm(`Remove "${word}" from blocked list?`)) return;
    try {
      await apiFetch(`/api/admin/blocked-words/${id}`, { method: 'DELETE' });
      setWords(prev => prev.filter(w => w.id !== id));
      setSuccess(`"${word}" removed from block list.`);
    } catch {
      setError('Failed to remove blocked word.');
    }
  };

  const filtered = words.filter(w =>
    w.word.toLowerCase().includes(search.toLowerCase()) ||
    (w.reason || '').toLowerCase().includes(search.toLowerCase())
  );

  const card = (children, style = {}) => (
    <div style={{ background: '#fff', border: '1px solid #f0f0f0', borderRadius: '10px', padding: '16px 18px', boxShadow: '0 1px 3px rgba(0,0,0,0.04)', ...style }}>{children}</div>
  );

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>

      {/* Header */}
      <div>
        <h2 style={{ fontSize: '1.2rem', margin: 0, color: '#111827' }}>🚫 Blocked Terms</h2>
        <p style={{ fontSize: '13px', color: '#6b7280', margin: '4px 0 0' }}>
          Questions containing any of these words or phrases will be automatically refused by the chatbot.
        </p>
      </div>

      {/* Add new word */}
      {card(<>
        <p style={{ fontSize: '13px', fontWeight: 600, color: '#374151', margin: '0 0 12px' }}>Add a Blocked Word or Phrase</p>
        <form onSubmit={handleAdd} style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr auto', gap: '8px', alignItems: 'end' }}>
            <div>
              <label style={{ fontSize: '11px', fontWeight: 600, color: '#6b7280', display: 'block', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Word / Phrase *</label>
              <input
                value={newWord}
                onChange={e => setNewWord(e.target.value)}
                placeholder="e.g. competitor, exam paper"
                required
                style={{ width: '100%', padding: '8px 10px', border: '1px solid #e5e7eb', borderRadius: '7px', fontSize: '13px', boxSizing: 'border-box', outline: 'none' }}
              />
            </div>
            <div>
              <label style={{ fontSize: '11px', fontWeight: 600, color: '#6b7280', display: 'block', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Reason (optional)</label>
              <input
                value={newReason}
                onChange={e => setNewReason(e.target.value)}
                placeholder="Why is this blocked?"
                style={{ width: '100%', padding: '8px 10px', border: '1px solid #e5e7eb', borderRadius: '7px', fontSize: '13px', boxSizing: 'border-box', outline: 'none' }}
              />
            </div>
            <button type="submit" disabled={saving || !newWord.trim()} style={{
              padding: '8px 18px', background: saving ? '#d1d5db' : '#111827', color: '#fff',
              border: 'none', borderRadius: '7px', fontSize: '13px', fontWeight: 600, cursor: saving ? 'not-allowed' : 'pointer',
              whiteSpace: 'nowrap',
            }}>
              {saving ? 'Saving...' : '+ Block Word'}
            </button>
          </div>
        </form>
        {error && <p style={{ color: '#ef4444', fontSize: '12px', margin: '6px 0 0' }}>{error}</p>}
        {success && <p style={{ color: '#059669', fontSize: '12px', margin: '6px 0 0' }}>{success}</p>}
      </>)}

      {/* List */}
      {card(<>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
          <p style={{ fontSize: '13px', fontWeight: 600, color: '#374151', margin: 0 }}>
            Blocked Terms <span style={{ color: '#9ca3af', fontWeight: 400 }}>({filtered.length})</span>
          </p>
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search..."
            style={{ padding: '5px 10px', border: '1px solid #e5e7eb', borderRadius: '7px', fontSize: '12px', width: '180px', outline: 'none' }}
          />
        </div>

        {loading
          ? <p style={{ color: '#9ca3af', fontSize: '13px' }}>Loading...</p>
          : filtered.length === 0
            ? <p style={{ color: '#9ca3af', fontSize: '13px' }}>
              {words.length === 0 ? 'No blocked terms yet. Add one above.' : 'No matches for your search.'}
            </p>
            : <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12.5px' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #f3f4f6' }}>
                  {['Word / Phrase', 'Reason', 'Added By', 'Date Added', ''].map(h => (
                    <th key={h} style={{ padding: '6px 10px', textAlign: 'left', fontSize: '10px', fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', color: '#9ca3af' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map(w => (
                  <tr key={w.id} style={{ borderBottom: '1px solid #fafafa' }}>
                    <td style={{ padding: '9px 10px' }}>
                      <span style={{ fontFamily: 'monospace', fontSize: '13px', fontWeight: 600, background: '#fee2e2', color: '#991b1b', padding: '2px 8px', borderRadius: '5px' }}>
                        {w.word}
                      </span>
                    </td>
                    <td style={{ padding: '9px 10px', color: '#6b7280', maxWidth: '220px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {w.reason || <span style={{ color: '#d1d5db', fontStyle: 'italic' }}>—</span>}
                    </td>
                    <td style={{ padding: '9px 10px', color: '#9ca3af' }}>{w.added_by || '—'}</td>
                    <td style={{ padding: '9px 10px', color: '#9ca3af', whiteSpace: 'nowrap' }}>
                      {w.created_at ? new Date(w.created_at).toLocaleDateString('en-IN') : '—'}
                    </td>
                    <td style={{ padding: '9px 10px', textAlign: 'right' }}>
                      <button onClick={() => handleDelete(w.id, w.word)} style={{
                        padding: '4px 10px', background: '#fef2f2', color: '#ef4444', border: '1px solid #fecaca',
                        borderRadius: '6px', fontSize: '11px', fontWeight: 600, cursor: 'pointer'
                      }}>
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
        }
      </>)}

      {/* How it works */}
      {card(<>
        <p style={{ fontSize: '13px', fontWeight: 600, color: '#374151', margin: '0 0 8px' }}>How Blocking Works</p>
        <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '12.5px', color: '#6b7280', lineHeight: 1.8 }}>
          <li>Matching is <strong>case-insensitive</strong> and checks if the word/phrase appears <em>anywhere</em> in the user's message.</li>
          <li>Blocked queries get a polite refusal message — the chatbot does not answer.</li>
          <li>The block list is cached in memory and updates within seconds of a change.</li>
          <li>Removed words are <strong>soft-deleted</strong> (can be re-added later).</li>
        </ul>
      </>)}

    </section>
  );
}

function AuthWrapper({ children }) {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [roleData, setRoleData] = useState(null);

  useEffect(() => {
    let isMounted = true;

    async function initAuth() {
      try {
        const { data: { session: activeSession } } = await supabase.auth.getSession();
        if (activeSession) {
          const r = await getRoleFromSession(activeSession);
          if (r && r.role) {
            if (isMounted) {
              setSession(activeSession);
              setRoleData(r);
            }
          } else {
            console.warn("AskGLA: Stale or unauthorized admin session. Clearing credentials.");
            try {
              supabase.auth.signOut().catch(() => {});
            } catch (err) {}
            if (isMounted) {
              setSession(null);
              setRoleData(null);
            }
          }
        } else {
          if (isMounted) {
            setSession(null);
            setRoleData(null);
          }
        }
      } catch (err) {
        console.error("Auth: Initialization error:", err);
        if (isMounted) {
          setSession(null);
          setRoleData(null);
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    initAuth();

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange(async (_event, newSession) => {
      if (_event === 'SIGNED_OUT') {
        clearRoleCache();
        if (isMounted) {
          setRoleData(null);
          setSession(null);
        }
      } else if (newSession) {
        try {
          const r = await getRoleFromSession(newSession);
          if (r && r.role) {
            if (isMounted) {
              setRoleData(r);
              setSession(newSession);
            }
          } else {
            try {
              supabase.auth.signOut().catch(() => {});
            } catch (err) {}
            if (isMounted) {
              setRoleData(null);
              setSession(null);
            }
          }
        } catch (err) {
          if (isMounted) {
            setRoleData(null);
            setSession(null);
          }
        }
      }
    });

    return () => {
      isMounted = false;
      subscription.unsubscribe();
    };
  }, []);

  if (loading) {
    return <div className="chrome-shell" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>Loading...</div>;
  }

  const handleCustomLogin = async (mockSession) => {
    try {
      const r = await getRoleFromSession(mockSession);
      if (r && r.role) {
        setRoleData(r);
        setSession(mockSession);
      } else {
        try {
          supabase.auth.signOut().catch(() => {});
        } catch (err) {}
      }
    } catch (err) {
      try {
        supabase.auth.signOut().catch(() => {});
      } catch (e) {}
    }
  };

  if (!session) {
    return <LoginPage onCustomLogin={handleCustomLogin} />;
  }

  return <RoleContext.Provider value={roleData}>{children}</RoleContext.Provider>;
}

function LoginPage({ onCustomLogin }) {
  const [activeTab, setActiveTab] = useState('admin'); // 'admin' or 'dept'
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  const handleAuth = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage('');

    try {
      if (activeTab === 'admin') {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
      } else {
        const res = await apiFetch('/api/admin/rbac/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password })
        });
        if (res.status === 'success') {
          onCustomLogin({ user: { email: res.user.email } });
        } else {
          throw new Error('Invalid email or password');
        }
      }
    } catch (error) {
      setMessage(error.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="chrome-shell" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', background: 'var(--bg-main)' }}>
      <section className="panel panel-feature" style={{ width: '100%', maxWidth: '400px', padding: '2.5rem' }}>
        <div className="panel-headline" style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
          <p className="panel-kicker">Secure Access</p>
          <h2 style={{ marginBottom: '1rem' }}>Admin Portal</h2>
        </div>

        <div style={{ display: 'flex', gap: '8px', marginBottom: '1.5rem', background: '#f3f4f6', padding: '4px', borderRadius: '8px' }}>
          <button 
            type="button"
            onClick={() => { setActiveTab('admin'); setMessage(''); }}
            style={{ flex: 1, padding: '8px', border: 'none', color: '#161812', background: activeTab === 'admin' ? '#fff' : 'transparent', borderRadius: '6px', fontWeight: 600, boxShadow: activeTab === 'admin' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none', cursor: 'pointer' }}
          >Super Admin</button>
          <button 
            type="button"
            onClick={() => { setActiveTab('dept'); setMessage(''); }}
            style={{ flex: 1, padding: '8px', border: 'none', color: '#161812', background: activeTab === 'dept' ? '#fff' : 'transparent', borderRadius: '6px', fontWeight: 600, boxShadow: activeTab === 'dept' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none', cursor: 'pointer' }}
          >Department</button>
        </div>

        <form onSubmit={handleAuth} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <div style={{ display: 'flex', justifyContent: 'center', marginTop: '1rem' }}>
            <span style={{ fontSize: '14px', color: 'var(--ink-muted)' }}>Use your admin credentials to sign in.</span>
          </div>

          <label style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <span style={{ fontWeight: '500', color: 'rgba(22,24,18,0.85)' }}>Email</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              style={{ padding: '0.85rem', borderRadius: '8px', border: '1px solid var(--line)', background: '#fff' }}
              placeholder={activeTab === 'admin' ? "admin@example.com" : "dept@example.com"}
            />
          </label>

          <label style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <span style={{ fontWeight: '500', color: 'rgba(22,24,18,0.85)' }}>Password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              style={{ padding: '0.85rem', borderRadius: '8px', border: '1px solid var(--line)', background: '#fff' }}
              placeholder="••••••••"
            />
          </label>

          <button type="submit" disabled={loading} style={{ background: 'var(--moss)', color: '#fff', padding: '0.85rem', borderRadius: '8px', border: 'none', cursor: 'pointer', marginTop: '0.5rem', fontWeight: 'bold', fontSize: '16px' }}>
            {loading ? 'Processing...' : 'Login'}
          </button>
        </form>

        {message && (
          <p style={{ marginTop: '1rem', textAlign: 'center', color: '#ef4444', fontWeight: '500' }}>
            {message}
          </p>
        )}
      </section>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthWrapper>
        <AppRouter />
      </AuthWrapper>
      <Analytics />
    </BrowserRouter>
  );
}
