import { useState, useEffect } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, Package, Mail, Settings, Menu, X, Search,
  RefreshCw, TriangleAlert
} from 'lucide-react';
import { api } from '../../lib/api';
import type { AppHomeResponse } from '../../types/api';

const NAV = [
  { to: '/', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/exceptions', label: 'Exceptions', icon: TriangleAlert },
  { to: '/containers', label: 'Containers', icon: Package },
  { to: '/emails', label: 'Emails', icon: Mail },
  { to: '/setup', label: 'Data Sources', icon: Settings },
];

export function AppShell() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [home, setHome] = useState<AppHomeResponse | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    api.home().then(setHome).catch(() => null);
  }, []);

  function handleGlobalSearch(e: React.FormEvent) {
    e.preventDefault();
    const q = searchQuery.trim();
    if (!q) return;
    navigate(`/containers?q=${encodeURIComponent(q)}`);
    setSearchQuery('');
  }

  const mailbox = home?.connected_mailboxes[0];

  return (
    <div className="app-shell">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.3)', zIndex: 199 }}
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`sidebar${sidebarOpen ? ' mobile-open' : ''}`}>
        <div className="sidebar-header">
          <div className="sidebar-logo">A</div>
          <span className="sidebar-brand">Agentify</span>
          <button
            className="btn btn-ghost btn-icon"
            style={{ marginLeft: 'auto', display: 'none' }}
            onClick={() => setSidebarOpen(false)}
            aria-label="Đóng menu"
          >
            <X size={18} />
          </button>
        </div>

        <nav className="sidebar-nav" aria-label="Navigation chính">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
              onClick={() => setSidebarOpen(false)}
            >
              <Icon size={18} aria-hidden />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="mailbox-status">
            <span className={`status-dot ${mailbox ? 'connected' : 'disconnected'}`} />
            <div style={{ flex: 1, minWidth: 0 }} className="flex-1">
              <div className="truncate" style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)' }}>
                {mailbox?.account_email ?? 'Gmail chưa kết nối'}
              </div>
            </div>
          </div>
        </div>
      </aside>

      {/* Main */}
      <div className="main-area">
        {/* Toolbar */}
        <header className="toolbar">
          <button
            className="btn btn-ghost btn-icon"
            style={{ display: 'none' }}
            onClick={() => setSidebarOpen(true)}
            aria-label="Mở menu"
          >
            <Menu size={18} />
          </button>

          {/* Global search */}
          <form
            onSubmit={handleGlobalSearch}
            className="toolbar-search"
            style={{ maxWidth: 480 }}
            role="search"
          >
            <Search size={15} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
            <input
              id="global-search"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Container, booking, B/L or PO  /"
              aria-label="Tìm kiếm container, booking, B/L hoặc PO"
            />
          </form>

          <div className="toolbar-spacer" />

          <div className="toolbar-actions">
            {mailbox && (
              <button
                className="btn btn-secondary btn-sm"
                title="Sync ngay"
                onClick={() => navigate('/setup')}
              >
                <RefreshCw size={14} />
                Sync now
              </button>
            )}
            {mailbox && (
              <div style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '4px 10px', borderRadius: 999,
                background: 'var(--bg-app)', border: '1px solid var(--border-subtle)',
                fontSize: 12, color: 'var(--text-secondary)',
              }}>
                <span className="status-dot connected" />
                <span className="truncate" style={{ maxWidth: 160 }}>{mailbox.account_email}</span>
              </div>
            )}
          </div>
        </header>

        {/* Page outlet */}
        <main className="page-content" id="main-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
