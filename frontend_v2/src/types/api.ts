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

export interface EmailListItem {
  id: string; gmail_connection_id: string; sync_job_id: string | null;
  gmail_message_id: string; subject: string; from_email: string;
  sent_at: string; snippet: string | null; has_pdf_attachments: boolean;
  processing_status: string; linked_containers: string[];
  attachment_count: number; fact_count: number;
}
export interface EmailListResponse { items: EmailListItem[]; total: number; page: number; page_size: number; }

export interface ContainerListItem {
  id: string; container_no: string; booking_no: string | null;
  bl_no: string | null; po_no: string | null; vessel: string | null;
  voyage: string | null; pol: string | null; pod: string | null;
  etd: string | null; eta: string | null; status_text: string | null;
  source_count: number; attachment_count: number; updated_at: string | null;
}
export interface ContainerListResponse { items: ContainerListItem[]; total: number; page: number; page_size: number; }

export interface RelatedEmailSummary { id: string; subject: string; from_email: string; sent_at: string; }
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
export interface EmailDetail {
  email: {
    id: string; gmail_message_id: string; gmail_thread_id: string | null;
    subject: string; from_email: string; to_emails: string[]; cc_emails: string[];
    sent_at: string; snippet: string | null; body_text: string | null;
    body_html: string | null; has_pdf_attachments: boolean; processing_status: string;
  };
  attachments: EmailAttachment[];
  extracted_facts: EmailExtractedFact[];
  linked_containers: string[];
}

export interface HealthResponse { status: string; database: string; }
