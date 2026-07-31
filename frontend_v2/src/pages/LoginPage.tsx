import { useState, type FormEvent } from 'react';
import { Navigate, useLocation, useNavigate, type Location } from 'react-router-dom';
import { AlertTriangle, LogIn } from 'lucide-react';
import { useAuth } from '../lib/auth';
import { landingPathFor } from '../lib/permissions';

interface LocationState { from?: Location; }

/** Mirrors `backend/scripts/seed_users.py::DEMO_USERS`. */
const DEMO_ACCOUNTS: { username: string; password: string; role: string }[] = [
  { username: 'admin', password: 'admin@123', role: 'Quản trị hệ thống' },
  { username: 'manager', password: 'manager@123', role: 'Quản lý' },
  { username: 'sales', password: 'sales@123', role: 'Sales / CS' },
  { username: 'docs', password: 'docs@123', role: 'Chứng từ' },
  { username: 'ops', password: 'ops@123', role: 'Vận hành' },
  { username: 'ketoan', password: 'ketoan@123', role: 'Kế toán' },
  { username: 'taixe', password: 'taixe@123', role: 'Tài xế' },
];

/** Printing passwords on the login screen is a testing convenience, never a
 * production one. On by default in `vite dev`; a built bundle only shows them
 * when `VITE_SHOW_DEMO_ACCOUNTS=true` is set explicitly at build time. */
const SHOW_DEMO_ACCOUNTS =
  import.meta.env.DEV || import.meta.env.VITE_SHOW_DEMO_ACCOUNTS === 'true';

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (user) {
    const from = (location.state as LocationState | null)?.from?.pathname ?? landingPathFor(user.role);
    return <Navigate to={from} replace />;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const loggedIn = await login(username, password);
      const from = (location.state as LocationState | null)?.from?.pathname ?? landingPathFor(loggedIn.role);
      navigate(from, { replace: true });
    } catch {
      setError('Sai tên đăng nhập hoặc mật khẩu');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      style={{
        minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: 'var(--bg-app)', padding: 24,
      }}
    >
      <form
        onSubmit={handleSubmit}
        className="card"
        style={{ width: 400, display: 'flex', flexDirection: 'column', gap: 16 }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div className="sidebar-logo">A</div>
          <div>
            <h1 style={{ fontSize: 18, fontWeight: 600, color: 'var(--text-primary)' }}>Agentify</h1>
            <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>Đăng nhập để tiếp tục</p>
          </div>
        </div>

        <div className="form-group">
          <label className="form-label" htmlFor="login-username">Tên đăng nhập</label>
          <input
            id="login-username"
            className="form-input"
            value={username}
            onChange={e => setUsername(e.target.value)}
            autoFocus
            autoComplete="username"
            required
          />
        </div>

        <div className="form-group">
          <label className="form-label" htmlFor="login-password">Mật khẩu</label>
          <input
            id="login-password"
            type="password"
            className="form-input"
            value={password}
            onChange={e => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </div>

        {error && (
          <div className="banner banner-danger">
            <AlertTriangle size={15} style={{ flexShrink: 0 }} /> {error}
          </div>
        )}

        <button type="submit" className="btn btn-primary" disabled={busy || !username || !password}>
          <LogIn size={15} /> {busy ? 'Đang đăng nhập…' : 'Đăng nhập'}
        </button>

        {SHOW_DEMO_ACCOUNTS && (
          <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: 14, display: 'flex', flexDirection: 'column', gap: 8 }}>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.5 }}>
              Tài khoản demo — bấm để điền sẵn. Mỗi tài khoản đúng 1 vai trò,
              quyền khác nhau hoàn toàn.
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {DEMO_ACCOUNTS.map(acc => (
                <button
                  key={acc.username}
                  type="button"
                  onClick={() => { setUsername(acc.username); setPassword(acc.password); setError(null); }}
                  disabled={busy}
                  style={{
                    display: 'flex', alignItems: 'baseline', gap: 8,
                    background: username === acc.username ? 'var(--accent-soft)' : 'transparent',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-control)',
                    padding: '6px 10px', cursor: busy ? 'default' : 'pointer',
                    textAlign: 'left', font: 'inherit', width: '100%',
                  }}
                >
                  <span className="mono" style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', minWidth: 62 }}>
                    {acc.username}
                  </span>
                  <span className="mono" style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                    {acc.password}
                  </span>
                  <span style={{ fontSize: 11, color: 'var(--text-secondary)', marginLeft: 'auto' }}>
                    {acc.role}
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}
      </form>
    </div>
  );
}
