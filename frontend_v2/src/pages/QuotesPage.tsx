import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { FileText, Plus, Search, AlertTriangle } from 'lucide-react';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { canManageQuote } from '../lib/permissions';
import type { Quote, QuoteStatus } from '../types/api';
import { fmtDate, fmtRelative } from '../lib/format';

const STATUS_LABELS: Record<QuoteStatus, string> = {
  draft: 'Nháp',
  sent: 'Đã gửi',
  accepted: 'Khách chấp nhận',
  rejected: 'Khách từ chối',
  expired: 'Hết hạn',
};

const STATUS_BADGE: Record<QuoteStatus, string> = {
  draft: 'badge-neutral',
  sent: 'badge-info',
  accepted: 'badge-success',
  rejected: 'badge-danger',
  expired: 'badge-warning',
};

export function QuotesPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<Quote[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState('');
  const [inputQ, setInputQ] = useState('');

  const load = useCallback(async (customerName: string) => {
    setLoading(true); setError(null);
    try {
      const r = await api.listQuotes({ customer_name: customerName || undefined, page_size: 50 });
      setItems(r.items); setTotal(r.total);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Lỗi tải danh sách báo giá');
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(q); }, [q, load]);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setQ(inputQ.trim());
  }

  return (
    <div className="page-container">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 600, color: 'var(--text-primary)' }}>Báo giá</h1>
          <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 4 }}>
            Báo giá đã gửi khách — baseline để đối soát chi phí thực về sau.
          </p>
        </div>
        {canManageQuote(user?.role) && (
          <Link to="/quotes/new" className="btn btn-primary btn-sm">
            <Plus size={14} /> Tạo báo giá
          </Link>
        )}
      </div>

      <form onSubmit={handleSearch} style={{ maxWidth: 360 }}>
        <div className="toolbar-search" style={{ maxWidth: '100%', height: 36 }}>
          <Search size={14} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
          <input
            value={inputQ}
            onChange={e => setInputQ(e.target.value)}
            placeholder="Tìm theo tên khách hàng…"
            aria-label="Tìm báo giá theo khách hàng"
          />
        </div>
      </form>

      {error && (
        <div className="banner banner-danger"><AlertTriangle size={16} /> {error}</div>
      )}

      {loading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {[...Array(4)].map((_, i) => (
            <div key={i} className="card">
              <div className="skeleton" style={{ height: 14, width: '40%', marginBottom: 10 }} />
              <div className="skeleton" style={{ height: 12, width: '70%' }} />
            </div>
          ))}
        </div>
      )}

      {!loading && !error && items.length === 0 && (
        <div className="card" style={{ textAlign: 'center', padding: '48px 24px', border: '1px dashed var(--border-strong)' }}>
          <FileText size={32} className="empty-state-icon" />
          <h2 style={{ fontSize: 16, marginBottom: 8 }}>Chưa có báo giá nào</h2>
          <p style={{ color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            {canManageQuote(user?.role)
              ? 'Tạo báo giá đầu tiên để bắt đầu theo dõi giá đã gửi khách.'
              : 'Vai trò Sales/CS chưa tạo báo giá nào trong Agentify.'}
          </p>
        </div>
      )}

      {!loading && items.length > 0 && (
        <div className="card" style={{ padding: 0 }}>
          <div style={{ padding: '8px 16px', fontSize: 12, color: 'var(--text-muted)', borderBottom: '1px solid var(--border-subtle)' }}>
            {total} báo giá
          </div>
          {items.map(quote => (
            <Link
              key={quote.id}
              to={`/quotes/${quote.id}`}
              style={{ textDecoration: 'none', color: 'inherit', display: 'block' }}
            >
              <div className="list-row">
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'flex-start' }}>
                  <div>
                    <span className="mono" style={{ fontWeight: 600, fontSize: 14 }}>{quote.quote_no}</span>
                    <span style={{ marginLeft: 10, fontSize: 13 }}>{quote.customer_name}</span>
                  </div>
                  <span className={`badge ${STATUS_BADGE[quote.status]}`}>{STATUS_LABELS[quote.status]}</span>
                </div>
                <div className="container-row-meta" style={{ marginTop: 4 }}>
                  {quote.pol && quote.pod && <span>{quote.pol} → {quote.pod}</span>}
                  {quote.container_no && <span className="mono">Container: {quote.container_no}</span>}
                  <span>{quote.currency} {quote.total_amount}</span>
                  <span style={{ marginLeft: 'auto' }}>{fmtRelative(quote.created_at)}</span>
                </div>
                {quote.valid_until && (
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
                    Hiệu lực đến {fmtDate(quote.valid_until)}
                  </div>
                )}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
