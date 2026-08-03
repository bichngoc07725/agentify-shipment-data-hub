import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { ShieldAlert } from 'lucide-react';
import { useAuth } from '../lib/auth';
import { canAccessSystemConfig, canUploadFieldImage, canViewAuditLog } from '../lib/permissions';

/** Not logged in -> `/login`, remembering where the user was headed so
 * `LoginPage` can send them back after a successful login. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const location = useLocation();

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  return <>{children}</>;
}

/** Gate for the `/setup` page: same `system_config` rule the backend
 * enforces on `/api/v1/gmail-connections` — Admin/Manager only. This is a
 * UX nicety (no confusing 403s while the page loads); the backend still
 * refuses the underlying calls for anyone else regardless. */
export function RequireSystemConfigAccess({ children }: { children: ReactNode }) {
  const { user } = useAuth();

  if (!user) {
    return <Navigate to="/login" replace />;
  }
  if (!canAccessSystemConfig(user.role)) {
    return (
      <div className="detail-panel">
        <div className="banner banner-danger">
          <ShieldAlert size={16} style={{ flexShrink: 0 }} />
          Vai trò "{user.role}" không có quyền truy cập trang cấu hình hệ thống.
        </div>
      </div>
    );
  }
  return <>{children}</>;
}

/** Gate for `/audit`: admin-only, per `config/permissions.py::PERMISSIONS["audit"]`. */
export function RequireAuditAccess({ children }: { children: ReactNode }) {
  const { user } = useAuth();

  if (!user) {
    return <Navigate to="/login" replace />;
  }
  if (!canViewAuditLog(user.role)) {
    return (
      <div className="detail-panel">
        <div className="banner banner-danger">
          <ShieldAlert size={16} style={{ flexShrink: 0 }} />
          Vai trò "{user.role}" không có quyền xem nhật ký audit.
        </div>
      </div>
    );
  }
  return <>{children}</>;
}

/** Gate for `/field-images`: `field_image.create` — Ops and Driver. Same
 * permission that decides whether the nav item shows, so the page and the
 * link into it can never disagree. */
export function RequireFieldImageUpload({ children }: { children: ReactNode }) {
  const { user } = useAuth();

  if (!user) {
    return <Navigate to="/login" replace />;
  }
  if (!canUploadFieldImage(user.role)) {
    return (
      <div className="detail-panel">
        <div className="banner banner-danger">
          <ShieldAlert size={16} style={{ flexShrink: 0 }} />
          Vai trò "{user.role}" không có quyền gửi ảnh hiện trường.
        </div>
      </div>
    );
  }
  return <>{children}</>;
}
