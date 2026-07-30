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

export interface ContainerListItem {
  id: string; container_no: string; booking_no: string | null;
  bl_no: string | null; po_no: string | null; do_no: string | null;
  vessel: string | null;
  voyage: string | null; pol: string | null; pod: string | null;
  etd: string | null; eta: string | null; ata: string | null;
  free_time_days: number | null; status_text: string | null;
  source_count: number; attachment_count: number; updated_at: string | null;
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
