import { useState, useEffect } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Search, Database, Mail, AlertTriangle, ChevronRight, RefreshCw } from 'lucide-react';
import { api } from '../lib/api';
import type { AppHomeResponse, ContainerListItem } from '../types/api';
import { fmtDateTime, fmtRelative, fmtDate } from '../lib/format';

function toListItem(c: AppHomeResponse['recent_containers'][number]): ContainerListItem {
  return {
    id: c.container_no, container_no: c.container_no, booking_no: c.booking_no,
    bl_no: c.bl_no, po_no: null, vessel: null, voyage: null, pol: null,
    pod: c.pod, etd: c.etd, eta: c.eta, status_text: c.status_text,
    source_count: c.source_count, attachment_count: c.attachment_count, updated_at: c.updated_at,
  };
}

export function OverviewPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [home, setHome] = useState<AppHomeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState(searchParams.get('q') ?? '');

  useEffect(() => {
    setLoading(true);
    api.home()
      .then(setHome)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    const q = query.trim();
    if (q) navigate(`/containers?q=${encodeURIComponent(q)}`);
  }

  const mailbox = home?.connected_mailboxes[0];

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', padding: '32px 24px', display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Page heading */}
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 600, color: 'var(--text-primary)' }}>Overview</h1>
        <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 4 }}>
          Tra cứu container, booking, B/L hoặc PO từ email và PDF đã sync.
        </p>
      </div>

      {/* Search block */}
      <form onSubmit={handleSearch} role="search">
        <div className="search-box">
          <span className="search-box-icon"><Search size={18} /></span>
          <input
            id="overview-search"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Container, booking, B/L or PO"
            aria-label="Tìm kiếm container"
            autoFocus
          />
          <button type="submit" className="search-box-btn">Tìm</button>
        </div>
        <p style={{ marginTop: 6, fontSize: 12, color: 'var(--text-muted)' }}>
          Nhập mã container, booking, B/L hoặc PO để tra cứu trực tiếp.
        </p>
      </form>

      {/* Gmail not connected banner */}
      {!loading && !mailbox && (
        <div className="banner banner-warning">
          <AlertTriangle size={16} style={{ flexShrink: 0 }} />
          <div style={{ flex: 1 }}>
            <strong>Chưa kết nối Gmail.</strong> Kết nối Gmail để bắt đầu đồng bộ email và PDF vào Agentify.
          </div>
          <Link to="/setup" className="btn btn-primary btn-sm">Connect Gmail</Link>
        </div>
      )}

      {/* Status strip */}
      {!loading && (
        <div className="status-strip">
          <div className="status-strip-item">
            <span className="status-strip-label">Gmail</span>
            <span className="status-strip-value" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span className={`status-dot ${mailbox ? 'connected' : 'disconnected'}`} />
              {mailbox ? 'Connected' : 'Not connected'}
            </span>
          </div>
          <div className="status-strip-item">
            <span className="status-strip-label">Last sync</span>
            <span className="status-strip-value">{fmtRelative(home?.last_sync_at)}</span>
          </div>
          <div className="status-strip-item">
            <span className="status-strip-label">Containers found</span>
            <span className="status-strip-value">{loading ? '…' : (home?.container_count ?? 0)}</span>
          </div>
          <div className="status-strip-item" style={{ flexShrink: 0 }}>
            <span className="status-strip-label">&nbsp;</span>
            <Link to="/setup" style={{ fontSize: 13, color: 'var(--accent)', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 4 }}>
              <RefreshCw size={13} /> Sync
            </Link>
          </div>
        </div>
      )}

      {error && (
        <div className="banner banner-danger">
          <AlertTriangle size={16} style={{ flexShrink: 0 }} />
          {error}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {[...Array(2)].map((_, i) => (
            <div key={i} className="card">
              <div className="skeleton" style={{ height: 16, width: 120, marginBottom: 12 }} />
              {[...Array(5)].map((_, j) => (
                <div key={j} className="skeleton" style={{ height: 40, marginBottom: 4, borderRadius: 6 }} />
              ))}
            </div>
          ))}
        </div>
      )}

      {!loading && home && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
          {/* Recent containers */}
          <section>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <h2 style={{ fontSize: 14, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
                <Database size={15} /> Container gần đây
              </h2>
              <Link to="/containers" style={{ fontSize: 12, color: 'var(--accent)', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 4 }}>
                Xem tất cả <ChevronRight size={13} />
              </Link>
            </div>
            <div className="card" style={{ padding: 0 }}>
              {home.recent_containers.length === 0 ? (
                <div className="empty-state" style={{ padding: '32px 16px' }}>
                  <p>Chưa có container nào. Kết nối Gmail và sync email để bắt đầu.</p>
                </div>
              ) : home.recent_containers.slice(0, 5).map(c => (
                <Link
                  key={c.container_no}
                  to={`/containers/${c.container_no}`}
                  style={{ textDecoration: 'none', color: 'inherit', display: 'block' }}
                >
                  <div className="list-row">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <span className="container-row-no">{c.container_no}</span>
                      <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{fmtDate(c.eta ?? c.etd)}</span>
                    </div>
                    <div className="container-row-meta">
                      {c.booking_no && <span>BK: {c.booking_no}</span>}
                      {c.bl_no && <span>B/L: {c.bl_no}</span>}
                      {c.status_text && <span style={{ color: 'var(--text-primary)' }}>{c.status_text}</span>}
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          </section>

          {/* Recent emails */}
          <section>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <h2 style={{ fontSize: 14, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
                <Mail size={15} /> Email mới sync
              </h2>
              <Link to="/emails" style={{ fontSize: 12, color: 'var(--accent)', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 4 }}>
                Xem tất cả <ChevronRight size={13} />
              </Link>
            </div>
            <RecentEmails />
          </section>
        </div>
      )}

      {/* No data empty state */}
      {!loading && home && !home.has_data && (
        <div className="card" style={{ textAlign: 'center', padding: '48px 24px', border: '1px dashed var(--border-strong)' }}>
          <h2 style={{ fontSize: 18, marginBottom: 8 }}>Chưa có dữ liệu để tra cứu</h2>
          <p style={{ color: 'var(--text-secondary)', marginBottom: 20, lineHeight: 1.6 }}>
            Kết nối Gmail và tạo lần đồng bộ đầu tiên. Container sẽ xuất hiện tại đây khi email hoặc PDF có mã container được trích xuất.
          </p>
          <Link to="/setup" className="btn btn-primary">Thiết lập dữ liệu</Link>
        </div>
      )}
    </div>
  );
}

function RecentEmails() {
  const [items, setItems] = useState<{ id: string; subject: string; from_email: string; sent_at: string; has_pdf_attachments: boolean }[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.listEmails({ page_size: 5 })
      .then(r => setItems(r.items))
      .catch(() => null)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="card" style={{ padding: 0 }}>
      {[...Array(5)].map((_, i) => (
        <div key={i} style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-subtle)' }}>
          <div className="skeleton" style={{ height: 14, width: '70%', marginBottom: 6 }} />
          <div className="skeleton" style={{ height: 11, width: '40%' }} />
        </div>
      ))}
    </div>
  );

  if (!items.length) return (
    <div className="card">
      <div className="empty-state" style={{ padding: '32px 16px' }}>
        <p>No synced emails yet. Kết nối Gmail và sync để email xuất hiện.</p>
        <Link to="/setup" className="btn btn-primary btn-sm" style={{ marginTop: 12 }}>Connect Gmail</Link>
      </div>
    </div>
  );

  return (
    <div className="card" style={{ padding: 0 }}>
      {items.map(e => (
        <Link key={e.id} to={`/emails/${e.id}`} style={{ textDecoration: 'none', color: 'inherit', display: 'block' }}>
          <div className="list-row">
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
              <span className="email-row-subject truncate">{e.subject}</span>
              <span style={{ fontSize: 11, color: 'var(--text-muted)', flexShrink: 0 }}>{fmtRelative(e.sent_at)}</span>
            </div>
            <div className="email-row-meta">
              <span className="truncate">{e.from_email}</span>
              {e.has_pdf_attachments && <span className="badge badge-neutral" style={{ fontSize: 10 }}>PDF</span>}
            </div>
          </div>
        </Link>
      ))}
    </div>
  );
}
