from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str
    database: str


class GmailConnectionUpsertRequest(BaseModel):
    account_email: str
    display_name: str | None = None
    google_account_id: str | None = None
    encrypted_refresh_token: str | None = None
    access_scope: str | None = None
    status: str = "connected"


class GmailConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    account_email: str
    display_name: str | None
    google_account_id: str | None
    access_scope: str | None
    status: str
    sync_cursor: str | None
    last_synced_at: datetime | None
    created_at: datetime
    updated_at: datetime | None


class GmailOAuthStartResponse(BaseModel):
    authorization_url: str


class AppHomeMailbox(BaseModel):
    id: UUID
    account_email: str
    status: str


class AppHomeRecentContainer(BaseModel):
    container_no: str
    booking_no: str | None
    bl_no: str | None
    pod: str | None
    etd: date | None
    status_text: str | None
    eta: date | None
    source_count: int
    attachment_count: int
    updated_at: datetime | None


class AppHomeResponse(BaseModel):
    has_data: bool
    container_count: int
    last_sync_at: datetime | None
    connected_mailboxes: list[AppHomeMailbox]
    recent_containers: list[AppHomeRecentContainer]


class CreateSyncJobRequest(BaseModel):
    gmail_connection_id: UUID
    query: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    max_results: int = Field(default=200, ge=1, le=1000)


class UpdateSyncJobRequest(BaseModel):
    status: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    emails_fetched: int | None = None
    attachments_found: int | None = None
    pdf_text_extracted: int | None = None
    containers_upserted: int | None = None
    error_message: str | None = None


class SyncJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    gmail_connection_id: UUID
    query: str | None
    date_from: date | None
    date_to: date | None
    max_results: int
    status: str
    emails_fetched: int
    attachments_found: int
    pdf_text_extracted: int
    containers_upserted: int
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime | None


class SyncJobListResponse(BaseModel):
    items: list[SyncJobResponse]
    total: int
    page: int
    page_size: int


class IngestAttachmentRequest(BaseModel):
    gmail_attachment_id: str | None = None
    filename: str
    mime_type: str
    size_bytes: int | None = None
    storage_path: str | None = None
    is_text_pdf: bool = True
    text_extract_status: str = "extracted"
    extracted_text: str | None = None
    document_type: str | None = None
    extracted_record: dict[str, Any] | None = None


class IngestFactRequest(BaseModel):
    field_name: str
    field_value: str
    normalized_value: str | None = None
    container_no: str | None = None
    source_type: str
    source_label: str | None = None
    document_type: str | None = None
    confidence: Decimal | None = None
    source_sent_at: datetime | None = None
    attachment_filename: str | None = None


class ProcessedEmailIngestRequest(BaseModel):
    gmail_connection_id: UUID | None = None
    sync_job_id: UUID | None = None
    channel: str = "email"
    gmail_message_id: str
    gmail_thread_id: str | None = None
    subject: str
    from_email: str
    to_emails: list[str] = Field(default_factory=list)
    cc_emails: list[str] = Field(default_factory=list)
    sent_at: datetime
    snippet: str | None = None
    body_text: str | None = None
    body_html: str | None = None
    raw_labels: list[str] = Field(default_factory=list)
    has_pdf_attachments: bool = False
    attachments: list[IngestAttachmentRequest] = Field(default_factory=list)
    extracted_facts: list[IngestFactRequest] = Field(default_factory=list)


class ProcessedEmailIngestResponse(BaseModel):
    email_id: UUID
    created: bool
    attachment_count: int
    fact_count: int
    linked_containers: list[str]


class ManualIngestRequest(BaseModel):
    """Content a user pastes or forwards in by hand, typically from Zalo.

    Agentify deliberately does not read Zalo automatically: that would need
    consent and access it should not ask for. The user stays the gatekeeper and
    decides what enters the shipment record.
    """

    channel: Literal["zalo", "note", "other"] = "zalo"
    content: str = Field(min_length=1, max_length=20000)
    source_label: str | None = Field(default=None, max_length=255)
    sender: str | None = Field(default=None, max_length=255)
    occurred_at: datetime | None = None


class ManualIngestPreviewResponse(BaseModel):
    """What extraction read, shown for review before anything is written."""

    channel: str
    container_nos: list[str] = Field(default_factory=list)
    document_type: str | None = None
    extraction_method: str
    extraction_status: str
    extraction_error: str | None = None
    fields: dict[str, Any] = Field(default_factory=dict)
    matched_containers: list[str] = Field(default_factory=list)
    new_containers: list[str] = Field(default_factory=list)


class ManualIngestResponse(BaseModel):
    message_id: UUID
    channel: str
    linked_containers: list[str]
    fact_count: int
    extraction_method: str
    extraction_status: str


class ContainerListItem(BaseModel):
    id: UUID
    container_no: str
    booking_no: str | None
    bl_no: str | None
    po_no: str | None
    do_no: str | None = None
    vessel: str | None
    voyage: str | None
    pol: str | None
    pod: str | None
    etd: date | None
    eta: date | None
    ata: date | None = None
    free_time_days: int | None = None
    status_text: str | None
    source_count: int
    attachment_count: int
    updated_at: datetime | None


class ContainerListResponse(BaseModel):
    items: list[ContainerListItem]
    total: int
    page: int
    page_size: int


class RelatedEmailSummary(BaseModel):
    id: UUID
    subject: str
    from_email: str
    sent_at: datetime
    channel: str = "email"


class RelatedAttachmentSummary(BaseModel):
    id: UUID
    filename: str
    email_id: UUID
    document_type: str | None
    file_url: str | None = None


class ShipmentExceptionResponse(BaseModel):
    container_no: str
    code: str
    severity: str
    title: str
    detail: str
    evidence: list[str] = Field(default_factory=list)
    due_date: date | None = None
    days_remaining: int | None = None


class ShipmentExceptionListResponse(BaseModel):
    items: list[ShipmentExceptionResponse]
    total: int
    counts_by_severity: dict[str, int] = Field(default_factory=dict)


class ContainerRiskProfileResponse(BaseModel):
    container_no: str
    direction: str
    exceptions: list[ShipmentExceptionResponse]
    documents_present: list[str]
    documents_mentioned: list[str] = Field(default_factory=list)
    documents_missing: list[str]
    completeness: float
    free_time_expires_on: date | None = None
    free_time_is_assumed: bool = False


class ContainerDetailResponse(BaseModel):
    container: ContainerListItem
    related_emails: list[RelatedEmailSummary]
    related_attachments: list[RelatedAttachmentSummary]


class ContainerFactResponse(BaseModel):
    id: UUID
    field_name: str
    field_value: str
    normalized_value: str | None
    source_type: str
    source_label: str | None
    document_type: str | None
    confidence: Decimal | None
    source_sent_at: datetime | None
    email_id: UUID
    attachment_id: UUID | None


class ContainerFactsListResponse(BaseModel):
    items: list[ContainerFactResponse]


class EmailDetailResponse(BaseModel):
    email: dict
    attachments: list[dict]
    extracted_facts: list[dict]
    linked_containers: list[str]


class EmailListItem(BaseModel):
    id: UUID
    gmail_connection_id: UUID | None
    sync_job_id: UUID | None
    channel: str = "email"
    gmail_message_id: str
    subject: str
    from_email: str
    sent_at: datetime
    snippet: str | None
    has_pdf_attachments: bool
    processing_status: str
    linked_containers: list[str] = Field(default_factory=list)
    attachment_count: int = 0
    fact_count: int = 0


class EmailListResponse(BaseModel):
    items: list[EmailListItem]
    total: int
    page: int
    page_size: int
