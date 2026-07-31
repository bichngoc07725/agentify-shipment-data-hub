import { useState, useEffect, useCallback } from 'react';
import { AlertTriangle, Plus, Users } from 'lucide-react';
import { api } from '../../lib/api';
import { ROLE_LABELS } from '../../lib/permissions';
import type { AdminUser, Role } from '../../types/api';
import { fmtDate } from '../../lib/format';

const ROLE_OPTIONS = Object.keys(ROLE_LABELS) as Role[];

export function UsersPage() {
  const [items, setItems] = useState<AdminUser[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [formOpen, setFormOpen] = useState(false);
  const [createBusy, setCreateBusy] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [username, setUsername] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [role, setRole] = useState<Role>('ops');
  const [password, setPassword] = useState('');

  const [toggleBusyId, setToggleBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const r = await api.listUsers();
      setItems(r.items); setTotal(r.total);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Lỗi tải danh sách người dùng');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function handleCreate() {
    setCreateBusy(true); setCreateError(null);
    try {
      await api.createUser({ username, display_name: displayName, role, password });
      setFormOpen(false);
      setUsername(''); setDisplayName(''); setRole('ops'); setPassword('');
      await load();
    } catch (e: unknown) {
      setCreateError(e instanceof Error ? e.message : 'Không tạo được user');
    } finally {
      setCreateBusy(false);
    }
  }

  async function handleToggleActive(user: AdminUser) {
    setToggleBusyId(user.id);
    try {
      await api.updateUser(user.id, { is_active: !user.is_active });
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Không đổi được trạng thái');
    } finally {
      setToggleBusyId(null);
    }
  }

  return (
    <div className="page-container">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 600, color: 'var(--text-primary)' }}>Quản lý người dùng</h1>
          <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 4 }}>
            Tạo tài khoản và đổi vai trò — mỗi tài khoản đúng 1 vai trò, không cộng dồn.
          </p>
        </div>
        <button className="btn btn-primary btn-sm" onClick={() => setFormOpen(v => !v)}>
          <Plus size={14} /> Tạo user
        </button>
      </div>

      {formOpen && (
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 8, maxWidth: 420 }}>
          <input
            className="form-input"
            placeholder="Username"
            value={username}
            onChange={e => setUsername(e.target.value)}
            disabled={createBusy}
          />
          <input
            className="form-input"
            placeholder="Tên hiển thị"
            value={displayName}
            onChange={e => setDisplayName(e.target.value)}
            disabled={createBusy}
          />
          <select
            className="form-input"
            value={role}
            onChange={e => setRole(e.target.value as Role)}
            disabled={createBusy}
          >
            {ROLE_OPTIONS.map(r => (
              <option key={r} value={r}>{ROLE_LABELS[r]}</option>
            ))}
          </select>
          <input
            className="form-input"
            type="password"
            placeholder="Mật khẩu (tối thiểu 6 ký tự)"
            value={password}
            onChange={e => setPassword(e.target.value)}
            disabled={createBusy}
          />
          {createError && <div style={{ color: 'var(--danger)', fontSize: 12 }}>{createError}</div>}
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn-primary btn-sm" onClick={handleCreate} disabled={createBusy}>Lưu</button>
            <button className="btn btn-ghost btn-sm" onClick={() => setFormOpen(false)} disabled={createBusy}>Huỷ</button>
          </div>
        </div>
      )}

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
          <Users size={32} className="empty-state-icon" />
          <h2 style={{ fontSize: 16, marginBottom: 8 }}>Chưa có user nào</h2>
        </div>
      )}

      {!loading && items.length > 0 && (
        <div className="card" style={{ padding: 0, overflowX: 'auto' }}>
          <div style={{ padding: '8px 16px', fontSize: 12, color: 'var(--text-muted)', borderBottom: '1px solid var(--border-subtle)' }}>
            {total} user
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: 'var(--bg-app)', borderBottom: '1px solid var(--border-subtle)' }}>
                {['Tên hiển thị', 'Username', 'Vai trò', 'Trạng thái', 'Ngày tạo', ''].map(h => (
                  <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontWeight: 500, color: 'var(--text-muted)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map(u => (
                <tr key={u.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  <td style={{ padding: '10px 14px' }}>{u.display_name}</td>
                  <td style={{ padding: '10px 14px', fontFamily: 'var(--font-mono)' }}>{u.username}</td>
                  <td style={{ padding: '10px 14px' }}>
                    <span className="badge badge-info">{ROLE_LABELS[u.role]}</span>
                  </td>
                  <td style={{ padding: '10px 14px' }}>
                    <span className={`badge ${u.is_active ? 'badge-success' : 'badge-neutral'}`}>
                      {u.is_active ? 'Đang hoạt động' : 'Đã khoá'}
                    </span>
                  </td>
                  <td style={{ padding: '10px 14px', color: 'var(--text-muted)', fontSize: 12 }}>{fmtDate(u.created_at)}</td>
                  <td style={{ padding: '10px 14px' }}>
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={() => handleToggleActive(u)}
                      disabled={toggleBusyId === u.id}
                    >
                      {u.is_active ? 'Khoá' : 'Mở khoá'}
                    </button>
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
