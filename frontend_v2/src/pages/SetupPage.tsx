import { useState, useEffect, useRef } from 'react';
import { AlertTriangle, CheckCircle, RefreshCw, Mail, ShieldAlert } from 'lucide-react';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { canAccessSystemConfig } from '../lib/permissions';
import type { ExtractionCapabilityStatus, GmailConnection, SyncJob } from '../types/api';
import { fmtDateTime, fmtRelative, syncStatusLabel } from '../lib/format';
import { SOURCES, SOURCE_STATE_BADGE, SOURCE_STATE_LABELS } from '../lib/channels';
import { ZaloIngestCard } from '../components/sources/ZaloIngestCard';
import { Link } from 'react-router-dom';

export function SetupPage() {
  const { user } = useAuth();
  // Gmail connection management is `system_config` (Admin/Manager only) —
  // same rule the backend enforces on `/api/v1/gmail-connections`. The Zalo
  // card below is a separate resource (`manual_ingest`) with its own gate,
  // so it stays visible to everyone who can reach this page.
  const canManageGmail = canAccessSystemConfig(user?.role);
  const [ocrStatus, setOcrStatus] = useState<ExtractionCapabilityStatus | null>(null);

  const [connections, setConnections] = useState<GmailConnection[]>([]);
  const [jobs, setJobs] = useState<SyncJob[]>([]);
  const [loading, setLoading] = useState(canManageGmail);
  const [error, setError] = useState<string | null>(null);
  const [oauthLoading, setOauthLoading] = useState(false);
  const [disconnecting, setDisconnecting] = useState<'logout' | 'switch' | null>(null);

  // Sync form state
  const [syncQuery, setSyncQuery] = useState('newer_than:30d');
  const [syncMax, setSyncMax] = useState(100);
  // Which connected mailbox the next sync runs against; defaults to the first
  // one loaded (see the effect that fetches connections).
  const [syncConnectionId, setSyncConnectionId] = useState<string | null>(null);
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
      setSyncConnectionId(prev => prev ?? conns[0]?.id ?? null);
      setJobs(jobsRes.items);
      const running = jobsRes.items.find(j => j.status === 'running' || j.status === 'pending');
      if (running) setActiveJob(running);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Lỗi tải dữ liệu');
    } finally { setLoading(false); }
  }

  useEffect(() => {
    // Skip the Gmail calls entirely for roles that can't reach them — the
    // backend would 403 anyway, and this avoids a confusing error banner
    // when all a Docs/Ops user wants is the Zalo card below.
    if (!canManageGmail) return;
    load();
    // Trạng thái trích xuất là phụ trợ: lỗi ở đây không được làm hỏng trang,
    // nên nuốt lỗi và coi như "chưa rõ" (không hiện cảnh báo).
    api.getExtractionStatus().then(setOcrStatus).catch(() => setOcrStatus(null));
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [canManageGmail]);

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
              // Refresh the mailbox card so "Last sync" reflects the run
              // that just finished instead of the previous one.
              api.gmailConnections().then(setConnections).catch(() => {});
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

  // "Thoát tài khoản": revoke + forget the current mailbox, stay on this page.
  async function handleLogout(connectionId: string) {
    setDisconnecting('logout'); setError(null);
    try {
      await api.disconnectGmailConnection(connectionId);
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Không thoát được tài khoản');
    } finally { setDisconnecting(null); }
  }

  // "Dùng email khác": revoke the current mailbox, then immediately restart
  // OAuth so Google's account chooser shows up (see prompt=select_account).
  async function handleSwitchAccount(connectionId: string) {
    setDisconnecting('switch'); setError(null);
    try {
      await api.disconnectGmailConnection(connectionId);
      await handleConnectGmail();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Không đổi được tài khoản');
      setDisconnecting(null);
    }
  }

  async function handleStartSync() {
    // Whichever mailbox the user picked. This used to hard-code
    // `connections[0]`, so with more than one account connected the sync
    // silently ran against the wrong inbox.
    const conn = connections.find(c => c.id === syncConnectionId) ?? connections[0];
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
    <div className="page-container page-narrow" style={{ gap: 28 }}>
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 600 }}>Nguồn dữ liệu</h1>
        <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 4, lineHeight: 1.6 }}>
          Agentify gom dữ liệu lô hàng từ các kênh vận hành đang dùng hằng ngày.
          Mỗi kênh ghi rõ trạng thái thật, không hứa cái chưa làm được.
        </p>
      </div>

      <SourceOverview />

      {/* Người sửa được cấu hình là Admin/Manager, nhưng họ KHÔNG upload ảnh
          (quyền đó là ops/driver), nên cảnh báo đặt trong khu upload ảnh sẽ
          không bao giờ đến mắt họ. Vì vậy trạng thái trích xuất phải xuất hiện
          ở đây — kèm đúng tên biến môi trường còn thiếu để hành động được ngay. */}
      {canManageGmail && ocrStatus && !ocrStatus.image_ocr.ready && (
        <div className="banner banner-warning" style={{ alignItems: 'flex-start' }}>
          <AlertTriangle size={15} style={{ flexShrink: 0, marginTop: 2 }} />
          <div style={{ lineHeight: 1.6 }}>
            <strong>Đọc ảnh tự động (OCR) đang TẮT.</strong>{' '}
            Nhân viên vẫn upload được ảnh hiện trường, nhưng mọi trường trả về rỗng
            và phải nhập tay — nhìn giống hệt “AI đọc không ra”.
            {ocrStatus.image_ocr.reason && (
              <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
                Lý do: {ocrStatus.image_ocr.reason}
              </div>
            )}
            {ocrStatus.missing_keys.length > 0 && (
              <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
                Cần đặt trong <span className="mono">backend/.env</span>:{' '}
                <span className="mono">{ocrStatus.missing_keys.join(', ')}</span>
              </div>
            )}
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
              Trích xuất văn bản (email/PDF):{' '}
              {ocrStatus.text_extraction.ready
                ? `đang chạy (${ocrStatus.text_extraction.provider})`
                : `cũng đang tắt — ${ocrStatus.text_extraction.fallback.toLowerCase()}`}
            </div>
          </div>
        </div>
      )}

      {!canManageGmail && (
        <div className="banner banner-info">
          <ShieldAlert size={15} style={{ flexShrink: 0 }} />
          Quản lý kết nối Gmail chỉ dành cho Admin/Manager. Vai trò của bạn chỉ thấy được phần Zalo bên dưới.
        </div>
      )}

      {canManageGmail && <div id="gmail">
        <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
          📧 Gmail
          <span className="badge badge-success">Đang chạy</span>
        </h2>
      </div>}

      {canManageGmail && loading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {[...Array(2)].map((_, i) => <div key={i} className="skeleton" style={{ height: 80, borderRadius: 10 }} />)}
        </div>
      )}

      {canManageGmail && error && <div className="banner banner-danger"><AlertTriangle size={16} /> {error}</div>}

      {canManageGmail && (!loading && !mainConn ? (
        /* Not connected */
        <div className="connection-panel">
          <div className="gmail-logo">📧</div>
          <h2 style={{ fontSize: 20, marginBottom: 8 }}>Kết nối Gmail</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginBottom: 6, lineHeight: 1.6 }}>
            Kết nối Gmail để Agentify đọc email và tệp đính kèm liên quan đến logistics.
          </p>
          <p style={{ color: 'var(--text-muted)', fontSize: 13, marginBottom: 20 }}>
            Quyền truy cập: <strong>Chỉ đọc email và tệp đính kèm.</strong><br />
            Agentify không gửi, sửa hoặc xóa email.
          </p>
          <button
            className="btn btn-primary"
            onClick={handleConnectGmail}
            disabled={oauthLoading}
            style={{ width: '100%', justifyContent: 'center', gap: 8, height: 44 }}
          >
            <Mail size={16} />
            {oauthLoading ? 'Đang chuyển hướng…' : 'Tiếp tục với Google'}
          </button>
        </div>
      ) : mainConn && (
        <>
          {/* Every connected mailbox, not just the first. Showing only
              `connections[0]` hid any additional account and — together with
              the "Connect Gmail" panel rendering only when there are zero
              connections — left no way at all to link a second mailbox. */}
          {connections.map(conn => (
            <div className="card" key={conn.id}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{
                  width: 40, height: 40, borderRadius: '50%',
                  background: 'var(--accent-soft)', color: 'var(--accent)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontWeight: 700, fontSize: 16, flexShrink: 0
                }}>
                  {conn.account_email[0].toUpperCase()}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 500 }}>{conn.account_email}</div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
                    Chỉ đọc · Đồng bộ gần nhất: {fmtRelative(conn.last_synced_at)}
                  </div>
                </div>
                <span className="badge badge-success"><CheckCircle size={11} style={{ marginRight: 4 }} /> Đã kết nối</span>
              </div>
              {/* Thao tác gắn với `conn` của vòng lặp, không phải `mainConn` —
                  nếu không thì có nhiều hộp thư, mọi nút đều tác động lên
                  đúng tài khoản đầu tiên. */}
              <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => handleSwitchAccount(conn.id)}
                  disabled={disconnecting !== null}
                >
                  {disconnecting === 'switch' ? 'Đang chuyển…' : 'Dùng email khác'}
                </button>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() => handleLogout(conn.id)}
                  disabled={disconnecting !== null}
                >
                  {disconnecting === 'logout' ? 'Đang thoát…' : 'Thoát tài khoản'}
                </button>
              </div>
            </div>
          ))}

          <button
            className="btn btn-secondary"
            onClick={handleConnectGmail}
            disabled={oauthLoading}
            style={{ alignSelf: 'flex-start' }}
          >
            <Mail size={15} />
            {oauthLoading ? 'Đang chuyển hướng…' : 'Kết nối thêm tài khoản Gmail'}
          </button>

          {/* Active sync progress */}
          {activeJob && (activeJob.status === 'running' || activeJob.status === 'pending') && (
            <div className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <h2 style={{ fontSize: 14, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
                  <RefreshCw size={14} style={{ animation: 'spin 1s linear infinite' }} />
                  Sync đang chạy
                </h2>
                <span className="badge badge-info">{syncStatusLabel(activeJob.status).label}</span>
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
            <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Cấu hình đồng bộ</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div className="form-group">
                <label className="form-label" htmlFor="sync-mailbox">Hộp thư</label>
                <select
                  id="sync-mailbox"
                  className="form-input"
                  value={syncConnectionId ?? mainConn.id}
                  onChange={e => setSyncConnectionId(e.target.value)}
                >
                  {connections.map(conn => (
                    <option key={conn.id} value={conn.id}>{conn.account_email}</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="sync-query">Truy vấn Gmail</label>
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
                <label className="form-label" htmlFor="sync-max">Số email tối đa</label>
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
                {syncLoading ? 'Đang tạo…' : 'Bắt đầu đồng bộ'}
              </button>
            </div>
          </div>

          {/* Sync history */}
          <div>
            <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Lịch sử đồng bộ</h2>
            {jobs.length === 0 ? (
              <div className="card">
                <div className="empty-state" style={{ padding: '24px 16px' }}>
                  <p>Chưa có lần đồng bộ nào. Bấm "Bắt đầu đồng bộ" để bắt đầu.</p>
                </div>
              </div>
            ) : (
              <div className="card" style={{ padding: 0, overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead>
                    <tr style={{ background: 'var(--bg-app)', borderBottom: '1px solid var(--border-subtle)' }}>
                      {['Bắt đầu', 'Truy vấn', 'Trạng thái', 'Email', 'Container'].map(h => (
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
      ))}

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
        <ZaloIngestCard onIngested={canManageGmail ? load : undefined} />
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
