import { useState, useEffect, useCallback } from 'react';
import { AlertTriangle, ShieldCheck } from 'lucide-react';
import { api } from '../lib/api';
import type { AuditLog } from '../types/api';
import { fmtDateTime } from '../lib/format';

const ACTION_LABELS: Record<string, string> = {
  approve: 'Duyệt',
  edit: 'Sửa',
  export: 'Xuất file',
  confirm: 'Xác nhận',
};

const RESOURCE_LABELS: Record<string, string> = {
  exception: 'Ngoại lệ',
  container_fact: 'Fact container',
  reconciliation: 'Đối soát',
  credit_limit: 'Hạn mức công nợ',
};

export function AuditLogPage() {
  const [items, setItems] = useState<AuditLog[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [resourceType, setResourceType] = useState('');

  const load = useCallback(async (filter: string) => {
    setLoading(true); setError(null);
    try {
      const r = await api.listAuditLogs({ resource_type: filter || undefined, limit: 200 });
      setItems(r.items); setTotal(r.total);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Lỗi tải nhật ký audit');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(resourceType); }, [resourceType, load]);

  return (
    <div className="page-container page-wide">
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 600, color: 'var(--text-primary)' }}>Nhật ký audit</h1>
        <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 4 }}>
          Ai làm gì, lúc nào, trên các thao tác nhạy cảm — bằng chứng khi có tranh chấp giá/chi phí.
        </p>
      </div>

      <div style={{ display: 'flex', gap: 8 }}>
        {['', 'exception', 'container_fact', 'reconciliation'].map(rt => (
          <button
            key={rt}
            className={`btn btn-sm ${resourceType === rt ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setResourceType(rt)}
          >
            {rt ? (RESOURCE_LABELS[rt] ?? rt) : 'Tất cả'}
          </button>
        ))}
      </div>

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
          <ShieldCheck size={32} className="empty-state-icon" />
          <h2 style={{ fontSize: 16, marginBottom: 8 }}>Chưa có nhật ký nào</h2>
          <p style={{ color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            Các thao tác nhạy cảm (duyệt ngoại lệ nghiêm trọng, sửa tay, duyệt đối soát, xuất ERP) sẽ xuất hiện ở đây.
          </p>
        </div>
      )}

      {!loading && items.length > 0 && (
        <div className="card" style={{ padding: 0, overflowX: 'auto' }}>
          <div style={{ padding: '8px 16px', fontSize: 12, color: 'var(--text-muted)', borderBottom: '1px solid var(--border-subtle)' }}>
            {total} dòng
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: 'var(--bg-app)', borderBottom: '1px solid var(--border-subtle)' }}>
                {['Thời gian', 'Người', 'Vai trò', 'Hành động', 'Resource', 'Chi tiết'].map(h => (
                  <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontWeight: 500, color: 'var(--text-muted)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map(log => (
                <tr key={log.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  <td style={{ padding: '10px 14px', color: 'var(--text-muted)', fontSize: 12, whiteSpace: 'nowrap' }}>
                    {fmtDateTime(log.created_at)}
                  </td>
                  <td style={{ padding: '10px 14px' }}>{log.username ?? log.user_id}</td>
                  <td style={{ padding: '10px 14px' }}>
                    <span className="badge badge-neutral">{log.role_used}</span>
                  </td>
                  <td style={{ padding: '10px 14px' }}>{ACTION_LABELS[log.action] ?? log.action}</td>
                  <td style={{ padding: '10px 14px' }}>{RESOURCE_LABELS[log.resource_type] ?? log.resource_type}</td>
                  <td style={{ padding: '10px 14px', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-secondary)' }}>
                    {log.detail ? JSON.stringify(log.detail) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
