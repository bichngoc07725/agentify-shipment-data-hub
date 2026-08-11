import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Search, Mail, Paperclip, AlertTriangle } from 'lucide-react';
import { api } from '../lib/api';
import type { EmailListItem } from '../types/api';
import { fmtRelative, emailStatusLabel } from '../lib/format';

const FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'has_pdf', label: 'Has PDF' },
  { id: 'linked', label: 'Linked to container' },
  { id: 'failed', label: 'Processing failed' },
];

export function EmailsPage() {
  const [items, setItems] = useState<EmailListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState('all');
  const [inputQ, setInputQ] = useState('');
  const [selected, setSelected] = useState<EmailListItem | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const r = await api.listEmails({ page_size: 50 });
      setItems(r.items); setTotal(r.total);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Lỗi tải email');
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  let displayed = items;
  if (filter === 'has_pdf') displayed = items.filter(e => e.has_pdf_attachments);
  else if (filter === 'linked') displayed = items.filter(e => e.linked_containers.length > 0);
  else if (filter === 'failed') displayed = items.filter(e => e.processing_status === 'failed');

  if (inputQ) {
    const lq = inputQ.toLowerCase();
    displayed = displayed.filter(e =>
      e.subject.toLowerCase().includes(lq) || e.from_email.toLowerCase().includes(lq)
    );
  }

  return (
    <div className="split-view" style={{ height: '100%' }}>
      {/* List pane */}
      <div className="split-list" style={{ width: 440 }}>
        <div className="split-list-header">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h1 style={{ fontSize: 16, fontWeight: 600 }}>Email</h1>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{total} tổng</span>
          </div>
          <div className="toolbar-search" style={{ maxWidth: '100%', height: 34 }}>
            <Search size={14} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
            <input
              id="email-search"
              value={inputQ}
              onChange={e => setInputQ(e.target.value)}
              placeholder="Subject, sender…"
              aria-label="Tìm email"
            />
          </div>
          <div className="filter-chips">
            {FILTERS.map(f => (
              <button key={f.id} className={`chip${filter === f.id ? ' active' : ''}`} onClick={() => setFilter(f.id)}>
                {f.label}
              </button>
            ))}
          </div>
        </div>

        <div className="split-list-scroll">
          {loading && [...Array(8)].map((_, i) => (
            <div key={i} style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-subtle)' }}>
              <div className="skeleton" style={{ height: 14, width: '75%', marginBottom: 6 }} />
              <div className="skeleton" style={{ height: 11, width: '50%' }} />
            </div>
          ))}

          {!loading && error && (
            <div className="banner banner-danger" style={{ margin: 12 }}>
              <AlertTriangle size={15} /> {error}
            </div>
          )}

          {!loading && !error && displayed.length === 0 && (
            <div className="empty-state">
              <Mail size={32} className="empty-state-icon" />
              <h3>No synced emails yet</h3>
              <p>Email xuất hiện sau khi Gmail được kết nối và sync hoàn tất.</p>
              <Link to="/setup" className="btn btn-primary btn-sm" style={{ marginTop: 12 }}>Connect Gmail</Link>
            </div>
          )}

          {!loading && displayed.map(e => {
            const { label, cls } = emailStatusLabel(e.processing_status);
            return (
              <div
                key={e.id}
                className={`list-row${selected?.id === e.id ? ' selected' : ''}`}
                onClick={() => setSelected(e)}
                role="button" tabIndex={0}
                aria-selected={selected?.id === e.id}
                onKeyDown={k => k.key === 'Enter' && setSelected(e)}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                  <span className="email-row-subject truncate" style={{ maxWidth: 220 }}>{e.subject}</span>
                  <span style={{ fontSize: 11, color: 'var(--text-muted)', flexShrink: 0 }}>{fmtRelative(e.sent_at)}</span>
                </div>
                <div className="email-row-meta">
                  <span className="truncate" style={{ maxWidth: 180 }}>{e.from_email}</span>
                  {e.has_pdf_attachments && <Paperclip size={12} style={{ color: 'var(--text-muted)' }} />}
                  <span className={`badge ${cls}`} style={{ fontSize: 10, marginLeft: 'auto' }}>{label}</span>
                </div>
                {e.linked_containers.length > 0 && (
                  <div style={{ marginTop: 4, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                    {e.linked_containers.map(cn => (
                      <span key={cn} className="mono" style={{ fontSize: 10, background: 'var(--accent-soft)', color: 'var(--accent)', padding: '1px 6px', borderRadius: 4 }}>{cn}</span>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Detail pane */}
      <div className="split-detail">
        {selected ? (
          <EmailPreviewPanel email={selected} />
        ) : (
          <div className="empty-state" style={{ height: '100%' }}>
            <Mail size={36} className="empty-state-icon" />
            <h3>Chọn một email</h3>
            <p>Chọn email từ danh sách bên trái để xem nội dung và thông tin trích xuất.</p>
          </div>
        )}
      </div>
    </div>
  );
}

function EmailPreviewPanel({ email: e }: { email: EmailListItem }) {
  const { label, cls } = emailStatusLabel(e.processing_status);
  return (
    <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="detail-header">
        <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>{e.subject}</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 13, color: 'var(--text-secondary)' }}>
          <div><strong style={{ color: 'var(--text-primary)', fontWeight: 500 }}>From:</strong> {e.from_email}</div>
        </div>
        <div style={{ marginTop: 10, display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <span className={`badge ${cls}`}>{label}</span>
          {e.has_pdf_attachments && <span className="badge badge-neutral"><Paperclip size={10} style={{ marginRight: 4 }} /> {e.attachment_count} PDF</span>}
          {e.linked_containers.map(cn => (
            <Link key={cn} to={`/containers/${cn}`}>
              <span className="mono badge badge-info">{cn}</span>
            </Link>
          ))}
        </div>
      </div>
      {e.snippet && (
        <div className="card" style={{ color: 'var(--text-secondary)', fontStyle: 'italic', fontSize: 13 }}>
          {e.snippet}…
        </div>
      )}
      <Link to={`/emails/${e.id}`} className="btn btn-primary" style={{ alignSelf: 'flex-start' }}>
        Mở email đầy đủ
      </Link>
    </div>
  );
}
