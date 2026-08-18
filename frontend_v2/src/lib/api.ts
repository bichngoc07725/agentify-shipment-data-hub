import { AUTH_EXPIRED_EVENT, clearStoredAuth, getToken } from './authStorage';

const BASE = '';

async function req<T>(path: string, opts?: RequestInit): Promise<T> {
  const token = getToken();
  // FormData needs fetch to set its own multipart boundary — a forced
  // `Content-Type: application/json` here would break the upload.
  const isFormData = opts?.body instanceof FormData;
  const res = await fetch(BASE + path, {
    headers: {
      ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...opts?.headers,
    },
    ...opts,
  });
  if (res.status === 401) {
    // Token missing/expired/invalid — drop it and let `AuthProvider` (which
    // listens for this event) send the user back to `/login`.
    clearStoredAuth();
    window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
  }
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    // FastAPI error bodies are `{"detail": "..."}` — surface the message
    // itself instead of the raw JSON blob wherever a page just does
    // `e.message` in a banner.
    let message = text || `HTTP ${res.status}`;
    try {
      const parsed = JSON.parse(text);
      if (typeof parsed?.detail === 'string') message = parsed.detail;
    } catch {
      // Not JSON (e.g. a plain-text 500) — fall back to the raw text above.
    }
    throw new Error(message);
  }
  if (res.status === 204) {
    return undefined as T;
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
  AdminUser, AdminUserListResponse, AppHomeResponse, AuditLogListResponse,
  Booking, BookingInput, BookingListResponse, BookingPrefill, ContainerDetailResponse,
  ContainerFact, ContainerFactsResponse, ContainerListResponse, ContainerRiskProfile, CustomsDeclaration,
  CustomsDeclarationListResponse, CustomsWorksheet, DebitNote, DebitNoteInput, DebitNoteListResponse,
  EmailDetail, EmailListResponse,
  ExceptionActionResult, ExtractionCapabilityStatus, FieldImageConfirmResult, FieldImageListResponse, FieldImagePreview,
  GmailConnection, HealthResponse, LoginRequest, LoginResponse,
  ManualIngestPreview, ManualIngestRequest,
  ManualIngestResult, PermissionMatrixResponse, Quote, QuoteInput, QuoteListResponse,
  ChargeDraft, ComposedMail, QuoteDraft,
  Reconciliation, ReconciliationListResponse, Shipment, ShipmentBoardResponse, ShipmentStage,
  ShipmentExceptionListResponse, ShipmentListResponse,
  SyncJob, SyncJobListResponse,
} from '../types/api';

export const api = {
  health: () => req<HealthResponse>('/health'),
  login: (body: LoginRequest) =>
    req<LoginResponse>('/api/v1/auth/login', { method: 'POST', body: JSON.stringify(body) }),
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
  editContainerFact: (no: string, factId: string, field_value: string) =>
    req<ContainerFact>(
      `/api/v1/containers/${encodeURIComponent(no)}/facts/${encodeURIComponent(factId)}`,
      { method: 'PATCH', body: JSON.stringify({ field_value }) },
    ),
  resolveException: (no: string, code: string, note?: string) =>
    req<ExceptionActionResult>(
      `/api/v1/containers/${encodeURIComponent(no)}/exceptions/${encodeURIComponent(code)}/resolve`,
      { method: 'POST', body: JSON.stringify({ note }) },
    ),
  approveException: (no: string, code: string, note?: string) =>
    req<ExceptionActionResult>(
      `/api/v1/containers/${encodeURIComponent(no)}/exceptions/${encodeURIComponent(code)}/approve`,
      { method: 'POST', body: JSON.stringify({ note }) },
    ),
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
  listQuotes: (p?: { customer_name?: string; status?: string; container_no?: string; page?: number; page_size?: number }) =>
    req<QuoteListResponse>(`/api/v1/quotes${qs({ ...p, page: p?.page ?? 1, page_size: p?.page_size ?? 20 })}`),
  getQuote: (id: string) => req<Quote>(`/api/v1/quotes/${encodeURIComponent(id)}`),
  createQuote: (body: QuoteInput) =>
    req<Quote>('/api/v1/quotes', { method: 'POST', body: JSON.stringify(body) }),
  updateQuote: (id: string, body: QuoteInput) =>
    req<Quote>(`/api/v1/quotes/${encodeURIComponent(id)}`, { method: 'PUT', body: JSON.stringify(body) }),
  deleteQuote: (id: string) =>
    req<void>(`/api/v1/quotes/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  getContainerQuotes: (no: string) =>
    req<QuoteListResponse>(`/api/v1/containers/${encodeURIComponent(no)}/quotes`),
  previewFieldImage: (file: File) => {
    const form = new FormData();
    form.append('file', file);
    return req<FieldImagePreview>('/api/v1/field-images/preview', { method: 'POST', body: form });
  },
  confirmFieldImage: (body: { image_id: string; container_no: string; seal_no?: string; doc_kind?: string }) =>
    req<FieldImageConfirmResult>('/api/v1/field-images', { method: 'POST', body: JSON.stringify(body) }),
  getContainerFieldImages: (no: string) =>
    req<FieldImageListResponse>(`/api/v1/containers/${encodeURIComponent(no)}/images`),
  createDebitNote: (body: DebitNoteInput) =>
    req<DebitNote>('/api/v1/debit-notes', { method: 'POST', body: JSON.stringify(body) }),
  getDebitNote: (id: string) => req<DebitNote>(`/api/v1/debit-notes/${encodeURIComponent(id)}`),
  getContainerDebitNotes: (no: string) =>
    req<DebitNoteListResponse>(`/api/v1/containers/${encodeURIComponent(no)}/debit-notes`),
  createReconciliation: (body: { container_no: string; quote_id: string }) =>
    req<Reconciliation>('/api/v1/reconciliation', { method: 'POST', body: JSON.stringify(body) }),
  getReconciliation: (id: string) =>
    req<Reconciliation>(`/api/v1/reconciliation/${encodeURIComponent(id)}`),
  approveReconciliation: (id: string, note?: string) =>
    req<Reconciliation>(`/api/v1/reconciliation/${encodeURIComponent(id)}/approve`, {
      method: 'POST',
      body: JSON.stringify({ note }),
    }),
  getContainerReconciliations: (no: string) =>
    req<ReconciliationListResponse>(`/api/v1/containers/${encodeURIComponent(no)}/reconciliation`),
  createCustomsDeclaration: (body: {
    container_no: string;
    declaration_no?: string;
    declaration_type?: string;
    channel?: string;
    hs_code?: string;
    registered_at?: string;
    cleared_at?: string;
    tax_amount?: string;
    note?: string;
  }) =>
    req<CustomsDeclaration>('/api/v1/customs/declarations', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  updateCustomsDeclaration: (
    id: string,
    body: {
      declaration_no?: string;
      declaration_type?: string;
      channel?: string;
      hs_code?: string;
      registered_at?: string;
      cleared_at?: string;
      tax_amount?: string;
      note?: string;
      channel_change_reason?: string;
    },
  ) =>
    req<CustomsDeclaration>(`/api/v1/customs/declarations/${encodeURIComponent(id)}`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),
  getCustomsDeclaration: (id: string) =>
    req<CustomsDeclaration>(`/api/v1/customs/declarations/${encodeURIComponent(id)}`),
  getCustomsPrefill: (no: string) =>
    req<Record<string, string>>(`/api/v1/containers/${encodeURIComponent(no)}/customs-prefill`),
  getCustomsWorksheet: (no: string) =>
    req<CustomsWorksheet>(`/api/v1/containers/${encodeURIComponent(no)}/customs-worksheet`),
  customsWorksheetDocxUrl: (no: string) =>
    `/api/v1/containers/${encodeURIComponent(no)}/customs-worksheet/docx`,
  getContainerCustoms: (no: string) =>
    req<CustomsDeclarationListResponse>(`/api/v1/containers/${encodeURIComponent(no)}/customs`),
  createBooking: (body: BookingInput) =>
    req<Booking>('/api/v1/bookings', { method: 'POST', body: JSON.stringify(body) }),
  updateBooking: (id: string, body: BookingInput) =>
    req<Booking>(`/api/v1/bookings/${encodeURIComponent(id)}`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),
  getContainerBookings: (no: string) =>
    req<BookingListResponse>(`/api/v1/containers/${encodeURIComponent(no)}/bookings`),
  getBookingPrefill: (no: string) =>
    req<BookingPrefill>(`/api/v1/containers/${encodeURIComponent(no)}/booking-prefill`),
  getQuoteBookings: (quoteId: string) =>
    req<BookingListResponse>(`/api/v1/quotes/${encodeURIComponent(quoteId)}/bookings`),
  getQuoteBookingPrefill: (quoteId: string) =>
    req<BookingPrefill>(`/api/v1/quotes/${encodeURIComponent(quoteId)}/booking-prefill`),
  getBookingPrefillFromEmail: (emailId: string) =>
    req<BookingPrefill>(`/api/v1/emails/${encodeURIComponent(emailId)}/booking-prefill`),
  getBookingRequestMail: (bookingId: string) =>
    req<ComposedMail>(`/api/v1/bookings/${encodeURIComponent(bookingId)}/request-mail`),
  getQuoteDraftFromEmail: (emailId: string) =>
    req<QuoteDraft>(`/api/v1/emails/${encodeURIComponent(emailId)}/quote-draft`),
  getChargeDraftFromEmail: (emailId: string) =>
    req<ChargeDraft>(`/api/v1/emails/${encodeURIComponent(emailId)}/charge-draft`),
  getRateRequestMail: (quoteId: string) =>
    req<ComposedMail>(`/api/v1/quotes/${encodeURIComponent(quoteId)}/rate-request-mail`),
  getCustomerQuoteMail: (quoteId: string) =>
    req<ComposedMail>(`/api/v1/quotes/${encodeURIComponent(quoteId)}/customer-mail`),
  createShipment: (body: {
    customer_name?: string;
    direction?: string;
    quote_id?: string;
    container_nos?: string[];
  }) => req<Shipment>('/api/v1/shipments', { method: 'POST', body: JSON.stringify(body) }),
  listShipments: () => req<ShipmentListResponse>('/api/v1/shipments'),
  getShipment: (id: string) => req<Shipment>(`/api/v1/shipments/${encodeURIComponent(id)}`),
  getShipmentBoard: () => req<ShipmentBoardResponse>('/api/v1/shipments/board'),
  advanceShipment: (id: string) =>
    req<Shipment>(`/api/v1/shipments/${encodeURIComponent(id)}/advance`, {
      method: 'POST',
      body: JSON.stringify({}),
    }),
  // Kanban drag: an explicit target column, forwards or backwards, unlike
  // `advanceShipment` which only ever steps one column forward.
  moveShipmentStage: (id: string, stage: ShipmentStage) =>
    req<Shipment>(`/api/v1/shipments/${encodeURIComponent(id)}/stage`, {
      method: 'POST',
      body: JSON.stringify({ stage }),
    }),
  listAuditLogs: (p?: { resource_type?: string; user_id?: string; limit?: number }) =>
    req<AuditLogListResponse>(`/api/v1/audit${qs({ ...p })}`),
  exportReconciliation: async (reconciliationId: string): Promise<{ blob: Blob; filename: string }> => {
    const token = getToken();
    const res = await fetch(
      `/api/v1/erp-export/reconciliation/${encodeURIComponent(reconciliationId)}`,
      { headers: token ? { Authorization: `Bearer ${token}` } : {} },
    );
    if (!res.ok) {
      const text = await res.text().catch(() => res.statusText);
      throw new Error(text || `HTTP ${res.status}`);
    }
    const disposition = res.headers.get('content-disposition') ?? '';
    const match = /filename="?([^"]+)"?/.exec(disposition);
    const filename = match?.[1] ?? `reconciliation-${reconciliationId}.csv`;
    return { blob: await res.blob(), filename };
  },
  listUsers: () => req<AdminUserListResponse>('/api/v1/users'),
  createUser: (body: { username: string; display_name: string; role: string; password: string }) =>
    req<AdminUser>('/api/v1/users', { method: 'POST', body: JSON.stringify(body) }),
  updateUser: (id: string, body: { role?: string; is_active?: boolean; password?: string }) =>
    req<AdminUser>(`/api/v1/users/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
  getPermissionMatrix: () => req<PermissionMatrixResponse>('/api/v1/admin/permissions'),
  getExtractionStatus: () => req<ExtractionCapabilityStatus>('/api/v1/system/extraction-status'),
};
