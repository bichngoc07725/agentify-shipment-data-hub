import { useState, useEffect } from 'react';
import { AlertTriangle } from 'lucide-react';
import { api } from '../../lib/api';
import { ROLE_LABELS } from '../../lib/permissions';
import type { PermissionMatrix, Role } from '../../types/api';

export function PermissionMatrixPage() {
  const [matrix, setMatrix] = useState<PermissionMatrix | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getPermissionMatrix()
      .then(r => setMatrix(r.matrix))
      .catch(e => setError(e instanceof Error ? e.message : 'Lỗi tải ma trận quyền'))
      .finally(() => setLoading(false));
  }, []);

  const resources = matrix ? Object.keys(matrix) : [];

  return (
    <div className="page-container page-wide">
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 600, color: 'var(--text-primary)' }}>Ma trận quyền</h1>
        <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 4 }}>
          Đọc trực tiếp từ <span className="mono">backend/config/permissions.py</span> — chỉ xem, không sửa qua UI.
        </p>
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

      {!loading && matrix && (
        <div className="card" style={{ padding: 0, overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: 'var(--bg-app)', borderBottom: '1px solid var(--border-subtle)' }}>
                <th style={{ padding: '10px 14px', textAlign: 'left', fontWeight: 500, color: 'var(--text-muted)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  Resource
                </th>
                <th style={{ padding: '10px 14px', textAlign: 'left', fontWeight: 500, color: 'var(--text-muted)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  Action
                </th>
                <th style={{ padding: '10px 14px', textAlign: 'left', fontWeight: 500, color: 'var(--text-muted)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  Vai trò được phép
                </th>
              </tr>
            </thead>
            <tbody>
              {resources.map(resource =>
                Object.entries(matrix[resource]).map(([action, roles], i) => (
                  <tr key={`${resource}-${action}`} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                    {i === 0 && (
                      <td
                        rowSpan={Object.keys(matrix[resource]).length}
                        style={{ padding: '10px 14px', fontFamily: 'var(--font-mono)', fontWeight: 600, verticalAlign: 'top' }}
                      >
                        {resource}
                      </td>
                    )}
                    <td style={{ padding: '10px 14px', color: 'var(--text-secondary)' }}>{action}</td>
                    <td style={{ padding: '10px 14px' }}>
                      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                        {(roles as Role[]).length > 0 ? (
                          (roles as Role[]).map(role => (
                            <span key={role} className="badge badge-info">{ROLE_LABELS[role] ?? role}</span>
                          ))
                        ) : (
                          <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>Không role nào</span>
                        )}
                      </div>
                    </td>
                  </tr>
                )),
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
