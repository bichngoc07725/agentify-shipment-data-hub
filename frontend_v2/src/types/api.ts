// API types matching existing backend schema

export interface GmailConnection {
  id: string;
  account_email: string;
  display_name: string | null;
  status: string;
  last_synced_at: string | null;
  created_at: string;
}

export interface AppHomeMailbox { id: string; account_email: string; status: string; }
export interface AppHomeRecentContainer {
  container_no: string; booking_no: string | null; bl_no: string | null;
  pod: string | null; etd: string | null; eta: string | null;
  status_text: string | null; source_count: number; attachment_count: number;
  updated_at: string | null;
}
export interface AppHomeResponse {
  has_data: boolean; container_count: number; last_sync_at: string | null;
  connected_mailboxes: AppHomeMailbox[]; recent_containers: AppHomeRecentContainer[];
}

export interface SyncJob {
  id: string; gmail_connection_id: string; query: string | null;
  max_results: number; status: string; emails_fetched: number;
  attachments_found: number; pdf_text_extracted: number; containers_upserted: number;
  error_message: string | null; started_at: string | null; completed_at: string | null;
  created_at: string; updated_at: string | null;
}
export interface SyncJobListResponse { items: SyncJob[]; total: number; page: number; page_size: number; }

export type MessageChannel = 'email' | 'zalo' | 'note' | 'other';

export interface EmailListItem {
  id: string; gmail_connection_id: string | null; sync_job_id: string | null;
  channel: MessageChannel;
  gmail_message_id: string; subject: string; from_email: string;
  sent_at: string; snippet: string | null; has_pdf_attachments: boolean;
  processing_status: string; linked_containers: string[];
  attachment_count: number; fact_count: number;
}
export interface EmailListResponse { items: EmailListItem[]; total: number; page: number; page_size: number; }

export interface ContainerShipmentSummary {
  id: string;
  stage: ShipmentStage;
  sla_breached: boolean;
  sla_due_at: string | null;
}

export interface ContainerListItem {
  id: string; container_no: string; booking_no: string | null;
  bl_no: string | null; po_no: string | null; do_no: string | null;
  vessel: string | null;
  voyage: string | null; pol: string | null; pod: string | null;
  etd: string | null; eta: string | null; ata: string | null;
  free_time_days: number | null; status_text: string | null;
  source_count: number; attachment_count: number; updated_at: string | null;
  shipment: ContainerShipmentSummary | null;
}

export type ExceptionSeverity = 'critical' | 'warning' | 'info';

export interface ShipmentException {
  container_no: string;
  code: string;
  severity: ExceptionSeverity;
  title: string;
  detail: string;
  evidence: string[];
  due_date: string | null;
  days_remaining: number | null;
}

export interface ShipmentExceptionListResponse {
  items: ShipmentException[];
  total: number;
  counts_by_severity: Partial<Record<ExceptionSeverity, number>>;
}

export interface ContainerRiskProfile {
  container_no: string;
  direction: string;
  exceptions: ShipmentException[];
  /** Files actually in Agentify. */
  documents_present: string[];
  /** Referred to by a message, file not received yet — still counts as missing. */
  documents_mentioned: string[];
  documents_missing: string[];
  completeness: number;
  free_time_expires_on: string | null;
  free_time_is_assumed: boolean;
}
export interface ContainerListResponse { items: ContainerListItem[]; total: number; page: number; page_size: number; }

export interface RelatedEmailSummary {
  id: string; subject: string; from_email: string; sent_at: string;
  channel: MessageChannel;
}
export interface RelatedAttachmentSummary { id: string; filename: string; email_id: string; document_type: string | null; file_url: string | null; }
export interface ContainerDetailResponse {
  container: ContainerListItem;
  related_emails: RelatedEmailSummary[];
  related_attachments: RelatedAttachmentSummary[];
}

export interface ContainerFact {
  id: string; field_name: string; field_value: string; normalized_value: string | null;
  source_type: string; source_label: string | null; document_type: string | null;
  confidence: number | null; source_sent_at: string | null;
  email_id: string; attachment_id: string | null;
}
export interface ContainerFactsResponse { items: ContainerFact[]; }

export interface EmailAttachment {
  id: string; filename: string; mime_type: string; size_bytes: number | null;
  text_extract_status: string; document_type: string | null;
  extracted_record: Record<string, unknown> | null; file_url: string | null;
}
export interface EmailExtractedFact {
  id: string; container_id: string; attachment_id: string | null;
  field_name: string; field_value: string; normalized_value: string | null;
  source_type: string; source_label: string | null; document_type: string | null;
  confidence: number | null; source_sent_at: string | null;
}
export interface ManualIngestRequest {
  channel: 'zalo' | 'note' | 'other';
  content: string;
  source_label?: string;
  sender?: string;
  occurred_at?: string;
  image_base64?: string;
  image_mime_type?: string;
  image_filename?: string;
}

export interface ManualIngestPreview {
  channel: string;
  container_nos: string[];
  document_type: string | null;
  extraction_method: string;
  extraction_status: string;
  extraction_error: string | null;
  fields: {
    identifiers?: Record<string, unknown>;
    route?: Record<string, unknown>;
    free_time_days?: number | null;
  };
  matched_containers: string[];
  new_containers: string[];
}

export interface ManualIngestResult {
  message_id: string;
  channel: string;
  linked_containers: string[];
  fact_count: number;
  extraction_method: string;
  extraction_status: string;
}

export interface EmailDetail {
  email: {
    id: string; channel: MessageChannel;
    gmail_message_id: string; gmail_thread_id: string | null;
    subject: string; from_email: string; to_emails: string[]; cc_emails: string[];
    sent_at: string; snippet: string | null; body_text: string | null;
    body_html: string | null; has_pdf_attachments: boolean; processing_status: string;
  };
  attachments: EmailAttachment[];
  extracted_facts: EmailExtractedFact[];
  linked_containers: string[];
}

export interface HealthResponse { status: string; database: string; }

export type Role = 'admin' | 'manager' | 'sales_cs' | 'docs' | 'ops' | 'accountant' | 'driver';

export interface LoginRequest { username: string; password: string; }
export interface LoginResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  username: string;
  display_name: string;
  role: Role;
}

export interface ExceptionActionResult {
  container_no: string;
  code: string;
  action: 'resolve' | 'approve';
  severity_tier: 'normal' | 'critical';
  acted_by_username: string;
  acted_by_role: string;
  note: string | null;
}

export type QuoteStatus = 'draft' | 'sent' | 'accepted' | 'rejected' | 'expired';
export type ChargeGroup = 'ocean_freight' | 'surcharge' | 'local';

export interface QuoteChargeInput {
  charge_group: ChargeGroup;
  charge_code: string;
  description?: string | null;
  unit_price: string;
  currency?: string;
  quantity?: string;
}

export interface QuoteCharge {
  id: string;
  charge_group: ChargeGroup;
  charge_code: string;
  description: string | null;
  unit_price: string;
  currency: string;
  quantity: string;
  amount: string;
}

export interface QuoteInput {
  customer_name: string;
  status?: QuoteStatus;
  pol?: string | null;
  pod?: string | null;
  commodity?: string | null;
  is_dangerous?: boolean;
  is_reefer?: boolean;
  container_type?: string | null;
  container_qty?: number | null;
  gross_weight_kg?: string | null;
  cargo_ready_date?: string | null;
  incoterm?: string | null;
  payment_term?: string | null;
  transit_time?: string | null;
  valid_until?: string | null;
  note?: string | null;
  currency?: string;
  container_no?: string | null;
  charges: QuoteChargeInput[];
}

export interface Quote {
  id: string;
  quote_no: string;
  customer_name: string;
  status: QuoteStatus;
  pol: string | null;
  pod: string | null;
  commodity: string | null;
  is_dangerous: boolean;
  is_reefer: boolean;
  container_type: string | null;
  container_qty: number | null;
  gross_weight_kg: string | null;
  cargo_ready_date: string | null;
  incoterm: string | null;
  payment_term: string | null;
  transit_time: string | null;
  valid_until: string | null;
  note: string | null;
  currency: string;
  created_by: string;
  container_id: string | null;
  container_no: string | null;
  charges: QuoteCharge[];
  total_amount: string;
  created_at: string;
  updated_at: string | null;
}

export interface QuoteListResponse {
  items: Quote[];
  total: number;
}

export type ExtractionStatus = 'ok' | 'skipped' | 'failed';

export interface FieldImagePreview {
  image_id: string;
  filename: string;
  mime_type: string;
  file_url: string | null;
  doc_kind: string | null;
  container_no: string | null;
  container_no_valid: boolean;
  matched_container: string | null;
  seal_no: string | null;
  license_plate: string | null;
  depot: string | null;
  datetime_text: string | null;
  raw_text: string | null;
  confidence: number | null;
  extraction_status: ExtractionStatus;
  extraction_error: string | null;
}

export interface FieldImageConfirmResult {
  attachment_id: string;
  container_no: string;
  fact_count: number;
}

export interface FieldImageListItem {
  id: string;
  filename: string;
  mime_type: string;
  document_type: string | null;
  file_url: string | null;
  extracted_record: Record<string, unknown> | null;
  created_at: string;
}

export interface FieldImageListResponse {
  items: FieldImageListItem[];
}

export interface DebitNoteChargeInput {
  charge_code: string;
  description?: string | null;
  amount: string;
  currency?: string;
  quantity?: string;
}

export interface DebitNoteCharge {
  id: string;
  charge_code: string;
  description: string | null;
  amount: string;
  currency: string;
  quantity: string;
}

export interface DebitNoteInput {
  container_no: string;
  partner_name?: string | null;
  doc_no?: string | null;
  currency?: string;
  issued_date?: string | null;
  source_attachment_id?: string | null;
  charges: DebitNoteChargeInput[];
}

export interface DebitNote {
  id: string;
  container_id: string;
  container_no: string | null;
  source_attachment_id: string | null;
  partner_name: string | null;
  doc_no: string | null;
  currency: string;
  issued_date: string | null;
  created_by: string;
  charges: DebitNoteCharge[];
  total_amount: string;
  created_at: string;
}

export interface DebitNoteListResponse {
  items: DebitNote[];
  total: number;
}

export type ReconciliationStatus = 'draft' | 'reviewed' | 'approved' | 'escalated';
export type ReconciliationMatchStatus = 'matched' | 'variance' | 'missing_actual' | 'extra_actual';

export interface ReconciliationLine {
  id: string;
  charge_code: string;
  quoted_amount: string | null;
  actual_amount: string | null;
  variance: string;
  match_status: ReconciliationMatchStatus;
  note: string | null;
}

export interface Reconciliation {
  id: string;
  container_id: string;
  container_no: string | null;
  quote_id: string;
  quote_no: string | null;
  status: ReconciliationStatus;
  total_quoted: string;
  total_actual: string;
  total_variance: string;
  needs_approval: boolean;
  created_by: string;
  approved_by: string | null;
  lines: ReconciliationLine[];
  created_at: string;
}

export interface ReconciliationListResponse {
  items: Reconciliation[];
  total: number;
}

export type CustomsDeclarationType = 'import' | 'export';
export type CustomsChannel = 'green' | 'yellow' | 'red';

export interface CustomsChannelHistoryEntry {
  id: string;
  from_channel: CustomsChannel | null;
  to_channel: CustomsChannel;
  changed_at: string;
  changed_by: string;
  reason: string | null;
}

export interface CustomsDeclaration {
  id: string;
  container_id: string;
  container_no: string | null;
  declaration_no: string | null;
  declaration_type: CustomsDeclarationType;
  channel: CustomsChannel | null;
  hs_code: string | null;
  registered_at: string | null;
  cleared_at: string | null;
  tax_amount: string | null;
  note: string | null;
  created_by: string;
  channel_history: CustomsChannelHistoryEntry[];
  created_at: string;
  updated_at: string | null;
}

export interface CustomsDeclarationListResponse {
  items: CustomsDeclaration[];
  total: number;
}

/** Bản nháp báo giá rút từ một email hỏi giá. Ô vắng = không tìm thấy trong
 *  email, không phải bằng rỗng. */
export interface QuoteDraftFields {
  customer_name?: string | null;
  pol?: string | null;
  pod?: string | null;
  commodity?: string | null;
  container_type?: string | null;
  container_qty?: number | null;
  gross_weight_kg?: string | null;
  incoterm?: string | null;
  payment_term?: string | null;
}

export interface QuoteDraft {
  source_email_id: string;
  source_subject: string | null;
  source_from: string | null;
  fields: QuoteDraftFields;
  fields_found: string[];
  extraction_error: string | null;
}

/** Thư soạn sẵn. Agentify không gửi — người dùng bấm gửi trong hộp thư của họ. */
export interface ComposedMail {
  subject: string;
  body: string;
}

export interface ChargeDraftLine {
  charge_group: ChargeGroup;
  charge_code: string;
  description: string;
  unit_price: string;
  currency: string;
  quantity: string;
}

export interface ChargeDraft {
  source_email_id: string;
  source_subject: string | null;
  source_from: string | null;
  charges: ChargeDraftLine[];
  extraction_error: string | null;
}


export type ShipmentStage =
  | 'rfq'
  | 'booking'
  | 'documents'
  | 'customs'
  | 'delivery'
  | 'reconciliation'
  | 'closed';

export interface Shipment {
  id: string;
  shipment_no: string;
  customer_name: string | null;
  direction: CustomsDeclarationType | null;
  stage: ShipmentStage;
  quote_id: string | null;
  quote_no: string | null;
  owner_role: string | null;
  sla_due_at: string | null;
  sla_breached: boolean;
  container_count: number;
  container_nos: string[];
  created_at: string;
  updated_at: string | null;
}

export interface ShipmentBoardColumn {
  stage: ShipmentStage;
  jobs: Shipment[];
}

export interface ShipmentBoardResponse {
  columns: ShipmentBoardColumn[];
}

export interface ShipmentListResponse {
  items: Shipment[];
  total: number;
}

export interface AuditLog {
  id: string;
  user_id: string;
  username: string | null;
  role_used: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  detail: Record<string, unknown> | null;
  created_at: string;
}

export interface AuditLogListResponse {
  items: AuditLog[];
  total: number;
}

export interface AdminUser {
  id: string;
  username: string;
  display_name: string;
  role: Role;
  is_active: boolean;
  created_at: string;
}

export interface AdminUserListResponse {
  items: AdminUser[];
  total: number;
}

export type PermissionMatrix = Record<string, Record<string, Role[]>>;

export interface PermissionMatrixResponse {
  matrix: PermissionMatrix;
}

export interface ExtractionCapability {
  ready: boolean;
  provider: string | null;
  reason: string | null;
  fallback: string;
}

export interface ExtractionCapabilityStatus {
  provider_setting: string;
  text_extraction: ExtractionCapability;
  image_ocr: ExtractionCapability;
  missing_keys: string[];
  gemini_model: string | null;
}
