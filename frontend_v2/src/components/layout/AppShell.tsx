import { useState, useEffect } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, Package, Mail, Scale, Settings, Menu, X, Search,
  RefreshCw, TriangleAlert, LogOut, FileText, Kanban, ShieldCheck, Sun, Moon, Users, KeyRound, Camera
} from 'lucide-react';
import { api } from '../../lib/api';
import { useAuth } from '../../lib/auth';
import {
  canAccessSystemConfig, canCreateManualIngest, canManageUsers, canUploadFieldImage, canViewAuditLog,
  canViewCostData, canViewFleetData, canViewQuote, canViewShipment, ROLE_LABELS,
} from '../../lib/permissions';
import { applyTheme, getStoredTheme, type ThemeMode } from '../../lib/theme';
import type { AppHomeResponse } from '../../types/api';

const NAV = [
  // The four fleet-wide pages below all 403 for Driver on the backend, so
  // they are hidden rather than shown-and-broken.
  { to: '/', label: 'Tổng quan', icon: LayoutDashboard, end: true, requiresFleetAccess: true },
  { to: '/exceptions', label: 'Ngoại lệ', icon: TriangleAlert, requiresFleetAccess: true },
  { to: '/containers', label: 'Container', icon: Package, requiresFleetAccess: true },
  { to: '/quotes', label: 'Báo giá', icon: FileText, requiresQuoteAccess: true },
  { to: '/reconciliation', label: 'Đối soát', icon: Scale, requiresCostDataAccess: true },
  { to: '/kanban', label: 'Kanban lô hàng', icon: Kanban, requiresShipmentAccess: true },
  { to: '/audit', label: 'Nhật ký thao tác', icon: ShieldCheck, requiresAuditAccess: true },
  { to: '/emails', label: 'Email', icon: Mail, requiresFleetAccess: true },
  // Gated by the same `field_image.create` check as the route itself, so a
  // Driver always has at least this one working entry point.
  { to: '/field-images', label: 'Ảnh hiện trường', icon: Camera, requiresFieldImageUpload: true },
];

// "Hệ thống" group (GĐ9B, `plan/agentify_slash_admin_design.docx` §3.3):
// Gmail/Zalo config, user management, and the read-only permission matrix —
// all admin-facing, kept visually separate from the day-to-day nav above.
const SYSTEM_NAV = [
  // Data Sources hosts both Gmail admin (system_config) and the Zalo paste
  // card (manual_ingest) — visible if the role can do either.
  { to: '/setup', label: 'Nguồn dữ liệu', icon: Settings, requiresDataSourceAccess: true },
  { to: '/admin/users', label: 'Quản lý người dùng', icon: Users, requiresUserManagementAccess: true },
  { to: '/admin/permissions', label: 'Ma trận quyền', icon: KeyRound, requiresUserManagementAccess: true },
];

export function AppShell() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [themeMode, setThemeMode] = useState<ThemeMode>(getStoredTheme());
  const [home, setHome] = useState<AppHomeResponse | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  // `/app-home` is gated by the same fleet-wide view permission as the pages
  // it summarises, so skip the call for roles that would only get a 403.
  const canSeeHome = canViewFleetData(user?.role);
  useEffect(() => {
    if (!canSeeHome) return;
    api.home().then(setHome).catch(() => null);
  }, [canSeeHome]);

  function toggleTheme() {
    const next: ThemeMode = themeMode === 'dark' ? 'light' : 'dark';
    applyTheme(next);
    setThemeMode(next);
  }

  function handleLogout() {
    logout();
    navigate('/login', { replace: true });
  }

  const nav = NAV.filter(item => {
    if (item.requiresFleetAccess) return canViewFleetData(user?.role);
    if (item.requiresFieldImageUpload) return canUploadFieldImage(user?.role);
    if (item.requiresQuoteAccess) return canViewQuote(user?.role);
    if (item.requiresCostDataAccess) return canViewCostData(user?.role);
    if (item.requiresShipmentAccess) return canViewShipment(user?.role);
    if (item.requiresAuditAccess) return canViewAuditLog(user?.role);
    return true;
  });

  const systemNav = SYSTEM_NAV.filter(item => {
    if (item.requiresDataSourceAccess) {
      return canAccessSystemConfig(user?.role) || canCreateManualIngest(user?.role);
    }
    if (item.requiresUserManagementAccess) return canManageUsers(user?.role);
    return true;
  });

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
          {nav.map(({ to, label, icon: Icon, end }) => (
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
          {systemNav.length > 0 && (
            <>
              <div className="nav-group-label">Hệ thống</div>
              {systemNav.map(({ to, label, icon: Icon }) => (
                <NavLink
                  key={to}
                  to={to}
                  className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
                  onClick={() => setSidebarOpen(false)}
                >
                  <Icon size={18} aria-hidden />
                  <span>{label}</span>
                </NavLink>
              ))}
            </>
          )}
        </nav>

        <div className="sidebar-footer">
          {user && (
            <div className="mailbox-status" style={{ marginBottom: 8 }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="truncate" style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)' }}>
                  {user.display_name}
                </div>
                <div className="truncate" style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                  {ROLE_LABELS[user.role]}
                </div>
              </div>
              <button
                className="btn btn-ghost btn-icon"
                onClick={handleLogout}
                title="Đăng xuất"
                aria-label="Đăng xuất"
              >
                <LogOut size={15} />
              </button>
            </div>
          )}
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
            <button
              className="btn btn-ghost btn-icon"
              onClick={toggleTheme}
              title={themeMode === 'dark' ? 'Chuyển sang giao diện sáng' : 'Chuyển sang giao diện tối'}
              aria-label="Đổi giao diện sáng/tối"
            >
              {themeMode === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
            </button>
            {mailbox && canAccessSystemConfig(user?.role) && (
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
            {user && (
              <div style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '4px 10px', borderRadius: 999,
                background: 'var(--accent-soft)', border: '1px solid var(--border-subtle)',
                fontSize: 12, color: 'var(--accent)', fontWeight: 500,
              }}>
                {ROLE_LABELS[user.role]}
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
