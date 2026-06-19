import { createBrowserRouter } from 'react-router-dom';
import { AppShell } from './components/layout/AppShell';
import { OverviewPage } from './pages/OverviewPage';
import { ContainersPage } from './pages/ContainersPage';
import { ContainerDetailPage } from './pages/ContainerDetailPage';
import { EmailsPage } from './pages/EmailsPage';
import { EmailDetailPage } from './pages/EmailDetailPage';
import { SetupPage } from './pages/SetupPage';

export const router = createBrowserRouter([
  {
    path: '/',
    Component: AppShell,
    children: [
      { index: true, Component: OverviewPage },
      { path: 'containers', Component: ContainersPage },
      { path: 'containers/:containerNo', Component: ContainerDetailPage },
      { path: 'emails', Component: EmailsPage },
      { path: 'emails/:id', Component: EmailDetailPage },
      { path: 'setup', Component: SetupPage },
    ],
  },
]);
