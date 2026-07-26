import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, ShieldCheck, ChevronRight, RefreshCw } from 'lucide-react';
import { api } from '../lib/api';
import type { ShipmentException, ShipmentExceptionListResponse, ExceptionSeverity } from '../types/api';
import { fmtDate } from '../lib/format';
import { SEVERITY_BADGE, SEVERITY_LABELS, formatDaysRemaining } from '../lib/exceptions';

const FILTERS: { id: string; label: string; severity?: ExceptionSeverity }[] = [
  { id: 'all', label: 'Tất cả' },
  { id: 'critical', label: 'Nguy cấp', severity: 'critical' },
  { id: 'warning', label: 'Cảnh báo', severity: 'warning' },
  { id: 'info', label: 'Thông tin', severity: 'info' },
];

export function ExceptionsPage() {
  const [data, setData] = useState<ShipmentExceptionListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState('all');

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      setData(await api.listExceptions({ limit: 200 }));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Không tải được danh sách ngoại lệ');
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const counts = data?.counts_by_severity ?? {};
  const items = data?.items ?? [];
  const active = FILTERS.find(f => f.id === filter);
  const displayed = active?.severity ? items.filter(i => i.severity === active.severity) : items;

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', padding: '32px 24px', display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 600, color: 'var(--text-primary)' }}>Ngoại lệ cần xử lý</h1>
          <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 4 }}>
            Lô hàng đang có rủi ro phát sinh chi phí hoặc thiếu chứng từ, tính từ dữ liệu email và PDF đã sync.
          </p>
        </div>
        <button className="btn btn-secondary btn-sm" onClick={load} disabled={loading}>
          <RefreshCw size={14} /> Tải lại
        </button>
      </div>

      <div className="status-strip">
        <div className="status-strip-item">
          <span className="status-strip-label">Nguy cấp</span>
          <span className="status-strip-value" style={{ color: 'var(--danger)' }}>{counts.critical ?? 0}</span>
        </div>
        <div className="status-strip-item">
          <span className="status-strip-label">Cảnh báo</span>
          <span className="status-strip-value" style={{ color: 'var(--warning)' }}>{counts.warning ?? 0}</span>
        </div>
        <div className="status-strip-item">
          <span className="status-strip-label">Thông tin</span>
          <span className="status-strip-value">{counts.info ?? 0}</span>
        </div>
        <div className="status-strip-item">
          <span className="status-strip-label">Tổng</span>
          <span className="status-strip-value">{data?.total ?? 0}</span>
        </div>
      </div>

      <div className="filter-chips">
        {FILTERS.map(f => (
          <button
            key={f.id}
            className={`chip${filter === f.id ? ' active' : ''}`}
            onClick={() => setFilter(f.id)}
          >
            {f.label}
            {f.severity ? ` (${counts[f.severity] ?? 0})` : ` (${data?.total ?? 0})`}
          </button>
        ))}
      </div>

      {error && (
        <div className="banner banner-danger">
          <AlertTriangle size={16} style={{ flexShrink: 0 }} /> {error}
        </div>
      )}

      {loading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {[...Array(4)].map((_, i) => (
            <div key={i} className="card">
              <div className="skeleton" style={{ height: 14, width: '40%', marginBottom: 10 }} />
              <div className="skeleton" style={{ height: 12, width: '80%' }} />
            </div>
          ))}
        </div>
      )}

      {!loading && !error && displayed.length === 0 && (
        <div className="card" style={{ textAlign: 'center', padding: '48px 24px', border: '1px dashed var(--border-strong)' }}>
          <ShieldCheck size={32} className="empty-state-icon" />
          <h2 style={{ fontSize: 16, marginBottom: 8 }}>Không có ngoại lệ nào</h2>
          <p style={{ color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            Không có lô nào đang sắp hết free time, thiếu D/O hoặc thiếu chứng từ trong dữ liệu Agentify hiện có.
          </p>
        </div>
      )}

      {!loading && displayed.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {displayed.map((exception, index) => (
            <ExceptionCard key={`${exception.container_no}-${exception.code}-${index}`} exception={exception} />
          ))}
        </div>
      )}
    </div>
  );
}

export function ExceptionCard({ exception }: { exception: ShipmentException }) {
  const countdown = formatDaysRemaining(exception.days_remaining);

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span className={`badge ${SEVERITY_BADGE[exception.severity]}`}>
            {SEVERITY_LABELS[exception.severity]}
          </span>
          <span style={{ fontWeight: 600, fontSize: 14, color: 'var(--text-primary)' }}>
            {exception.title}
          </span>
          {countdown && (
            <span
              className="badge badge-neutral"
              style={{ color: exception.days_remaining !== null && exception.days_remaining < 0 ? 'var(--danger)' : undefined }}
            >
              {countdown}
            </span>
          )}
        </div>
        <Link
          to={`/containers/${exception.container_no}`}
          className="mono"
          style={{ fontSize: 13, color: 'var(--accent)', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 2, flexShrink: 0 }}
        >
          {exception.container_no} <ChevronRight size={14} />
        </Link>
      </div>

      <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
        {exception.detail}
      </p>

      {exception.evidence.length > 0 && (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', paddingTop: 4, borderTop: '1px solid var(--border-subtle)' }}>
          <span style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Căn cứ
          </span>
          {exception.evidence.map(item => (
            <span key={item} style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{item}</span>
          ))}
          {exception.due_date && (
            <span style={{ fontSize: 12, color: 'var(--text-muted)', marginLeft: 'auto' }}>
              Hạn: {fmtDate(exception.due_date)}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
