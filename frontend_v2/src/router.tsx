import { createBrowserRouter } from 'react-router-dom';
import { AppShell } from './components/layout/AppShell';
import { RequireAuth, RequireAuditAccess, RequireFieldImageUpload, RequireSystemConfigAccess } from './components/RequireAuth';
import { LoginPage } from './pages/LoginPage';
import { OverviewPage } from './pages/OverviewPage';
import { ContainersPage } from './pages/ContainersPage';
import { ContainerDetailPage } from './pages/ContainerDetailPage';
import { EmailsPage } from './pages/EmailsPage';
import { ExceptionsPage } from './pages/ExceptionsPage';
import { EmailDetailPage } from './pages/EmailDetailPage';
import { SetupPage } from './pages/SetupPage';
import { FieldImagesPage } from './pages/FieldImagesPage';
import { QuotesPage } from './pages/QuotesPage';
import { QuoteDetailPage } from './pages/QuoteDetailPage';
import { ReconciliationPage } from './pages/ReconciliationPage';
import { KanbanPage } from './pages/KanbanPage';
import { AuditLogPage } from './pages/AuditLogPage';
import { UsersPage } from './pages/admin/UsersPage';
import { PermissionMatrixPage } from './pages/admin/PermissionMatrixPage';

export const router = createBrowserRouter([
  { path: '/login', Component: LoginPage },
  {
    path: '/',
    element: (
      <RequireAuth>
        <AppShell />
      </RequireAuth>
    ),
    children: [
      { index: true, Component: OverviewPage },
      { path: 'exceptions', Component: ExceptionsPage },
      { path: 'containers', Component: ContainersPage },
      { path: 'containers/:containerNo', Component: ContainerDetailPage },
      { path: 'emails', Component: EmailsPage },
      { path: 'emails/:id', Component: EmailDetailPage },
      { path: 'quotes', Component: QuotesPage },
      { path: 'quotes/:quoteId', Component: QuoteDetailPage },
      { path: 'reconciliation', Component: ReconciliationPage },
      { path: 'kanban', Component: KanbanPage },
      {
        path: 'audit',
        element: (
          <RequireAuditAccess>
            <AuditLogPage />
          </RequireAuditAccess>
        ),
      },
      {
        path: 'admin/users',
        element: (
          <RequireSystemConfigAccess>
            <UsersPage />
          </RequireSystemConfigAccess>
        ),
      },
      {
        path: 'admin/permissions',
        element: (
          <RequireSystemConfigAccess>
            <PermissionMatrixPage />
          </RequireSystemConfigAccess>
        ),
      },
      {
        path: 'field-images',
        element: (
          <RequireFieldImageUpload>
            <FieldImagesPage />
          </RequireFieldImageUpload>
        ),
      },
      { path: 'setup', Component: SetupPage },
    ],
  },
]);
