const BASE = '';

async function req<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json', ...opts?.headers },
    ...opts,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json();
}

function qs(p: Record<string, unknown>): string {
  const params = Object.entries(p)
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`);
  return params.length ? '?' + params.join('&') : '';
}

import type {
  AppHomeResponse, ContainerDetailResponse, ContainerFactsResponse,
  ContainerListResponse, ContainerRiskProfile, EmailDetail, EmailListResponse,
  GmailConnection, HealthResponse, ManualIngestPreview, ManualIngestRequest,
  ManualIngestResult, ShipmentExceptionListResponse,
  SyncJob, SyncJobListResponse,
} from '../types/api';

export const api = {
  health: () => req<HealthResponse>('/health'),
  home: () => req<AppHomeResponse>('/api/v1/app-home'),
  gmailConnections: () => req<GmailConnection[]>('/api/v1/gmail-connections'),
  startOAuth: (redirect_to?: string) =>
    req<{ authorization_url: string }>(`/api/v1/gmail-connections/oauth/start${qs({ redirect_to })}`),
  disconnectGmailConnection: (id: string) =>
    req<GmailConnection>(`/api/v1/gmail-connections/${encodeURIComponent(id)}/disconnect`, { method: 'POST' }),
  createSyncJob: (body: { gmail_connection_id: string; query?: string; max_results?: number }) =>
    req<SyncJob>('/api/v1/sync-jobs', { method: 'POST', body: JSON.stringify(body) }),
  runSyncJob: (id: string) =>
    req<SyncJob>(`/api/v1/sync-jobs/${encodeURIComponent(id)}/run`, { method: 'POST' }),
  listSyncJobs: (p?: { gmail_connection_id?: string; page?: number; page_size?: number }) =>
    req<SyncJobListResponse>(`/api/v1/sync-jobs${qs({ ...p, page: p?.page ?? 1, page_size: p?.page_size ?? 10 })}`),
  listContainers: (p?: { q?: string; page?: number; page_size?: number }) =>
    req<ContainerListResponse>(`/api/v1/containers${qs({ ...p, page: p?.page ?? 1, page_size: p?.page_size ?? 20 })}`),
  getContainer: (no: string) =>
    req<ContainerDetailResponse>(`/api/v1/containers/${encodeURIComponent(no)}`),
  getContainerFacts: (no: string) =>
    req<ContainerFactsResponse>(`/api/v1/containers/${encodeURIComponent(no)}/facts`),
  listExceptions: (p?: { severity?: string; code?: string; limit?: number }) =>
    req<ShipmentExceptionListResponse>(`/api/v1/exceptions${qs({ ...p })}`),
  getContainerExceptions: (no: string) =>
    req<ContainerRiskProfile>(`/api/v1/containers/${encodeURIComponent(no)}/exceptions`),
  previewManualIngest: (body: ManualIngestRequest) =>
    req<ManualIngestPreview>('/api/v1/manual-ingest/preview', { method: 'POST', body: JSON.stringify(body) }),
  createManualIngest: (body: ManualIngestRequest) =>
    req<ManualIngestResult>('/api/v1/manual-ingest', { method: 'POST', body: JSON.stringify(body) }),
  listEmails: (p?: { gmail_connection_id?: string; page?: number; page_size?: number }) =>
    req<EmailListResponse>(`/api/v1/emails${qs({ ...p, page: p?.page ?? 1, page_size: p?.page_size ?? 20 })}`),
  getEmail: (id: string) => req<EmailDetail>(`/api/v1/emails/${encodeURIComponent(id)}`),
};
