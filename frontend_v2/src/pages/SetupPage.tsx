import { useState, useEffect, useRef } from 'react';
import { AlertTriangle, CheckCircle, RefreshCw, Mail } from 'lucide-react';
import { api } from '../lib/api';
import type { GmailConnection, SyncJob } from '../types/api';
import { fmtDateTime, fmtRelative, syncStatusLabel } from '../lib/format';
import { SOURCES, SOURCE_STATE_BADGE, SOURCE_STATE_LABELS } from '../lib/channels';
import { ZaloIngestCard } from '../components/sources/ZaloIngestCard';
import { Link } from 'react-router-dom';

export function SetupPage() {
  const [connections, setConnections] = useState<GmailConnection[]>([]);
  const [jobs, setJobs] = useState<SyncJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [oauthLoading, setOauthLoading] = useState(false);

  // Sync form state
  const [syncQuery, setSyncQuery] = useState('newer_than:30d');
  const [syncMax, setSyncMax] = useState(100);
  const [syncLoading, setSyncLoading] = useState(false);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [activeJob, setActiveJob] = useState<SyncJob | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  async function load() {
    setLoading(true); setError(null);
    try {
      const [conns, jobsRes] = await Promise.all([
        api.gmailConnections(),
        api.listSyncJobs({ page_size: 10 }),
      ]);
      setConnections(conns);
      setJobs(jobsRes.items);
      const running = jobsRes.items.find(j => j.status === 'running' || j.status === 'pending');
      if (running) setActiveJob(running);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Lỗi tải dữ liệu');
    } finally { setLoading(false); }
  }

  useEffect(() => {
    load();
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  // Poll active job
  useEffect(() => {
    if (activeJob && (activeJob.status === 'running' || activeJob.status === 'pending')) {
      pollRef.current = setInterval(async () => {
        try {
          const jobsRes = await api.listSyncJobs({ page_size: 10 });
          setJobs(jobsRes.items);
          const updated = jobsRes.items.find(j => j.id === activeJob.id);
          if (updated) {
            setActiveJob(updated);
            if (updated.status !== 'running' && updated.status !== 'pending') {
              if (pollRef.current) clearInterval(pollRef.current);
            }
          }
        } catch {}
      }, 3000);
      return () => { if (pollRef.current) clearInterval(pollRef.current); };
    }
  }, [activeJob?.id, activeJob?.status]);

  async function handleConnectGmail() {
    setOauthLoading(true); setError(null);
    try {
      const { authorization_url } = await api.startOAuth(window.location.href);
      window.location.href = authorization_url;
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Lỗi kết nối Gmail');
      setOauthLoading(false);
    }
  }

  async function handleStartSync() {
    const conn = connections[0];
    if (!conn) return;
    setSyncLoading(true); setSyncError(null);
    try {
      const job = await api.createSyncJob({
        gmail_connection_id: conn.id,
        query: syncQuery || undefined,
        max_results: syncMax,
      });
      const started = await api.runSyncJob(job.id);
      setActiveJob(started);
      setJobs(prev => [started, ...prev]);
    } catch (e: unknown) {
      setSyncError(e instanceof Error ? e.message : 'Lỗi tạo sync job');
    } finally { setSyncLoading(false); }
  }

  const mainConn = connections[0];

  return (
    <div style={{ maxWidth: 780, margin: '0 auto', padding: '32px 24px', display: 'flex', flexDirection: 'column', gap: 28 }}>
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 600 }}>Nguồn dữ liệu</h1>
        <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 4, lineHeight: 1.6 }}>
          Agentify gom dữ liệu lô hàng từ các kênh vận hành đang dùng hằng ngày.
          Mỗi kênh ghi rõ trạng thái thật, không hứa cái chưa làm được.
        </p>
      </div>

      <SourceOverview />

      <div id="gmail">
        <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
          📧 Gmail
          <span className="badge badge-success">Đang chạy</span>
        </h2>
      </div>

      {loading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {[...Array(2)].map((_, i) => <div key={i} className="skeleton" style={{ height: 80, borderRadius: 10 }} />)}
        </div>
      )}

      {error && <div className="banner banner-danger"><AlertTriangle size={16} /> {error}</div>}

      {!loading && !mainConn ? (
        /* Not connected */
        <div className="connection-panel">
          <div className="gmail-logo">📧</div>
          <h2 style={{ fontSize: 20, marginBottom: 8 }}>Connect Gmail</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginBottom: 6, lineHeight: 1.6 }}>
            Kết nối Gmail để Agentify đọc email và attachment liên quan đến logistics.
          </p>
          <p style={{ color: 'var(--text-muted)', fontSize: 13, marginBottom: 20 }}>
            Quyền truy cập: <strong>Read email and attachments only.</strong><br />
            Agentify không gửi, sửa hoặc xóa email.
          </p>
          <button
            className="btn btn-primary"
            onClick={handleConnectGmail}
            disabled={oauthLoading}
            style={{ width: '100%', justifyContent: 'center', gap: 8, height: 44 }}
          >
            <Mail size={16} />
            {oauthLoading ? 'Đang chuyển hướng…' : 'Continue with Google'}
          </button>
        </div>
      ) : mainConn && (
        <>
          {/* Connection row */}
          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{
                width: 40, height: 40, borderRadius: '50%',
                background: 'var(--accent-soft)', color: 'var(--accent)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontWeight: 700, fontSize: 16, flexShrink: 0
              }}>
                {mainConn.account_email[0].toUpperCase()}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 500 }}>{mainConn.account_email}</div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
                  Read-only · Last sync: {fmtRelative(mainConn.last_synced_at)}
                </div>
              </div>
              <span className="badge badge-success"><CheckCircle size={11} style={{ marginRight: 4 }} /> Connected</span>
            </div>
          </div>

          {/* Active sync progress */}
          {activeJob && (activeJob.status === 'running' || activeJob.status === 'pending') && (
            <div className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <h2 style={{ fontSize: 14, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
                  <RefreshCw size={14} style={{ animation: 'spin 1s linear infinite' }} />
                  Sync đang chạy
                </h2>
                <span className="badge badge-info">{activeJob.status}</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 13, color: 'var(--text-secondary)' }}>
                <div>Bắt đầu: {fmtDateTime(activeJob.started_at)}</div>
                <div>Email đã xử lý: <strong>{activeJob.emails_fetched}</strong></div>
                <div>Container tìm thấy: <strong>{activeJob.containers_upserted}</strong></div>
              </div>
            </div>
          )}

          {/* Sync form */}
          <div className="card">
            <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Sync configuration</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div className="form-group">
                <label className="form-label" htmlFor="sync-mailbox">Mailbox</label>
                <input id="sync-mailbox" className="form-input" value={mainConn.account_email} disabled />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="sync-query">Gmail query</label>
                <input
                  id="sync-query"
                  className="form-input"
                  value={syncQuery}
                  onChange={e => setSyncQuery(e.target.value)}
                  placeholder="newer_than:30d"
                />
                <p className="form-helper">Ví dụ: <code>newer_than:30d</code>, <code>subject:booking</code>, <code>has:attachment</code></p>
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="sync-max">Maximum emails</label>
                <input
                  id="sync-max"
                  className="form-input"
                  type="number"
                  min={1} max={500}
                  value={syncMax}
                  onChange={e => setSyncMax(Number(e.target.value))}
                  style={{ maxWidth: 160 }}
                />
              </div>
              {syncError && <div className="banner banner-danger"><AlertTriangle size={15} /> {syncError}</div>}
              <button
                className="btn btn-primary"
                onClick={handleStartSync}
                disabled={syncLoading || !!(activeJob && (activeJob.status === 'running' || activeJob.status === 'pending'))}
                style={{ alignSelf: 'flex-start', minWidth: 120 }}
              >
                {syncLoading ? 'Đang tạo…' : 'Start sync'}
              </button>
            </div>
          </div>

          {/* Sync history */}
          <div>
            <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Sync history</h2>
            {jobs.length === 0 ? (
              <div className="card">
                <div className="empty-state" style={{ padding: '24px 16px' }}>
                  <p>Chưa có sync job nào. Bấm "Start sync" để bắt đầu.</p>
                </div>
              </div>
            ) : (
              <div className="card" style={{ padding: 0, overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead>
                    <tr style={{ background: 'var(--bg-app)', borderBottom: '1px solid var(--border-subtle)' }}>
                      {['Started', 'Query', 'Status', 'Emails', 'Containers'].map(h => (
                        <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontWeight: 500, color: 'var(--text-muted)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.04em', whiteSpace: 'nowrap' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {jobs.map(j => {
                      const { label, cls } = syncStatusLabel(j.status);
                      return (
                        <tr key={j.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                          <td style={{ padding: '10px 14px', whiteSpace: 'nowrap', color: 'var(--text-secondary)' }}>{fmtDateTime(j.created_at)}</td>
                          <td style={{ padding: '10px 14px', fontFamily: 'var(--font-mono)', fontSize: 12, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{j.query ?? '—'}</td>
                          <td style={{ padding: '10px 14px' }}><span className={`badge ${cls}`}>{label}</span></td>
                          <td style={{ padding: '10px 14px', textAlign: 'right' }}>{j.emails_fetched}</td>
                          <td style={{ padding: '10px 14px', textAlign: 'right' }}>{j.containers_upserted}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Recent emails preview */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <h2 style={{ fontSize: 15, fontWeight: 600 }}>Email gần đây</h2>
              <Link to="/emails" style={{ fontSize: 12, color: 'var(--accent)', textDecoration: 'none' }}>Xem tất cả →</Link>
            </div>
            <RecentEmailsMini />
          </div>
        </>
      )}

      {/* Zalo — manual, reviewed ingest */}
      <div id="zalo" style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: 24 }}>
        <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 4, display: 'flex', alignItems: 'center', gap: 8 }}>
          💬 Zalo
          <span className="badge badge-info">Thủ công, có kiểm duyệt</span>
        </h2>
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 14, lineHeight: 1.6 }}>
          Zalo là kênh điều phối số 1 trong logistics Việt Nam, nhưng Agentify không đọc
          tự động — việc đó cần quyền truy cập toàn bộ hội thoại cá nhân mà sản phẩm không
          nên xin. Bạn quyết định tin nào vào hồ sơ.
        </p>
        <ZaloIngestCard onIngested={load} />
      </div>

      {/* Sources still ahead */}
      <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: 24 }}>
        <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>Nguồn chưa mở</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {SOURCES.filter(s => s.state === 'roadmap' || s.state === 'out_of_scope').map(source => (
            <div key={source.id} className="card">
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
                <span style={{ fontSize: 18 }}>{source.icon}</span>
                <strong style={{ fontSize: 14 }}>{source.name}</strong>
                <span className={`badge ${SOURCE_STATE_BADGE[source.state]}`} style={{ marginLeft: 'auto' }}>
                  {SOURCE_STATE_LABELS[source.state]}
                </span>
              </div>
              <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>{source.detail}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function SourceOverview() {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 10 }}>
      {SOURCES.map(source => (
        <div
          key={source.id}
          className="card"
          style={{ padding: 14, opacity: source.state === 'out_of_scope' ? 0.7 : 1 }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <span style={{ fontSize: 16 }}>{source.icon}</span>
            <strong style={{ fontSize: 13 }}>{source.name}</strong>
          </div>
          <span className={`badge ${SOURCE_STATE_BADGE[source.state]}`}>
            {SOURCE_STATE_LABELS[source.state]}
          </span>
          <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 8, lineHeight: 1.5 }}>
            {source.summary}
          </p>
        </div>
      ))}
    </div>
  );
}

function RecentEmailsMini() {
  const [items, setItems] = useState<{ id: string; subject: string; from_email: string; sent_at: string }[]>([]);
  useEffect(() => {
    api.listEmails({ page_size: 5 }).then(r => setItems(r.items)).catch(() => null);
  }, []);
  if (!items.length) return null;
  return (
    <div className="card" style={{ padding: 0 }}>
      {items.map(e => (
        <Link key={e.id} to={`/emails/${e.id}`} style={{ textDecoration: 'none', color: 'inherit', display: 'block' }}>
          <div className="list-row">
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
              <span style={{ fontWeight: 500, fontSize: 13 }} className="truncate">{e.subject}</span>
              <span style={{ fontSize: 11, color: 'var(--text-muted)', flexShrink: 0 }}>{fmtRelative(e.sent_at)}</span>
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>{e.from_email}</div>
          </div>
        </Link>
      ))}
    </div>
  );
}
