from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    content: str = Field(default="", max_length=20000)
    source_label: str | None = Field(default=None, max_length=255)
    sender: str | None = Field(default=None, max_length=255)
    occurred_at: datetime | None = None
    # A pasted photo (e.g. a screenshot of a Zalo chat, a POD/EIR photo).
    # Base64-encoded rather than multipart so this stays a single JSON body
    # like the rest of this request, matching how the frontend paste handler
    # already reads clipboard images as data URLs.
    image_base64: str | None = Field(default=None, max_length=14_000_000)
    image_mime_type: str | None = Field(default=None, max_length=100)
    image_filename: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def _content_or_image_required(self) -> "ManualIngestRequest":
        if not self.content.strip() and not self.image_base64:
            raise ValueError("Provide message content, a pasted image, or both")
        return self


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


class ContainerShipmentSummary(BaseModel):
    id: UUID
    stage: Literal[
        "rfq", "booking", "documents", "customs", "delivery", "reconciliation", "closed"
    ]
    sla_breached: bool
    sla_due_at: datetime | None


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
    shipment: ContainerShipmentSummary | None = None


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
    # Null for a field photo (container/seal/EIR/POD) — it has no email behind it.
    email_id: UUID | None
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
    # Null for a fact sourced from a field photo — see `RelatedAttachmentSummary`.
    email_id: UUID | None
    attachment_id: UUID | None


class ContainerFactsListResponse(BaseModel):
    items: list[ContainerFactResponse]


class EditContainerFactRequest(BaseModel):
    field_value: str = Field(min_length=1)


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


class ExceptionActionRequest(BaseModel):
    note: str | None = None


class ExceptionActionResponse(BaseModel):
    container_no: str
    code: str
    action: str
    severity_tier: str
    acted_by_username: str
    acted_by_role: str
    note: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: UUID
    username: str
    display_name: str
    role: str


class QuoteChargeRequest(BaseModel):
    charge_group: Literal["ocean_freight", "surcharge", "local"]
    charge_code: str
    description: str | None = None
    unit_price: Decimal
    currency: str = "USD"
    quantity: Decimal = Decimal("1")


class QuoteChargeResponse(BaseModel):
    id: UUID
    charge_group: str
    charge_code: str
    description: str | None
    unit_price: Decimal
    currency: str
    quantity: Decimal
    amount: Decimal


class QuoteCreateRequest(BaseModel):
    customer_name: str
    status: Literal["draft", "sent", "accepted", "rejected", "expired"] = "draft"
    pol: str | None = None
    pod: str | None = None
    commodity: str | None = None
    is_dangerous: bool = False
    is_reefer: bool = False
    container_type: str | None = None
    container_qty: int | None = None
    gross_weight_kg: Decimal | None = None
    cargo_ready_date: date | None = None
    incoterm: str | None = None
    payment_term: str | None = None
    transit_time: str | None = None
    valid_until: date | None = None
    note: str | None = None
    currency: str = "USD"
    container_no: str | None = None
    charges: list[QuoteChargeRequest] = Field(default_factory=list)


class QuoteUpdateRequest(QuoteCreateRequest):
    pass


class QuoteResponse(BaseModel):
    id: UUID
    quote_no: str
    customer_name: str
    status: str
    pol: str | None
    pod: str | None
    commodity: str | None
    is_dangerous: bool
    is_reefer: bool
    container_type: str | None
    container_qty: int | None
    gross_weight_kg: Decimal | None
    cargo_ready_date: date | None
    incoterm: str | None
    payment_term: str | None
    transit_time: str | None
    valid_until: date | None
    note: str | None
    currency: str
    created_by: UUID
    container_id: UUID | None
    container_no: str | None = None
    charges: list[QuoteChargeResponse]
    total_amount: Decimal
    created_at: datetime
    updated_at: datetime | None


class QuoteListResponse(BaseModel):
    items: list[QuoteResponse]
    total: int


class FieldImagePreviewResponse(BaseModel):
    image_id: UUID
    filename: str
    mime_type: str
    file_url: str | None
    doc_kind: str | None
    container_no: str | None
    container_no_valid: bool
    matched_container: str | None
    seal_no: str | None
    license_plate: str | None
    depot: str | None
    datetime_text: str | None
    raw_text: str | None
    confidence: float | None
    extraction_status: Literal["ok", "skipped", "failed"]
    extraction_error: str | None


class FieldImageConfirmRequest(BaseModel):
    image_id: UUID
    container_no: str = Field(min_length=1)
    seal_no: str | None = None
    doc_kind: str | None = None


class FieldImageConfirmResponse(BaseModel):
    attachment_id: UUID
    container_no: str
    fact_count: int


class FieldImageListItem(BaseModel):
    id: UUID
    filename: str
    mime_type: str
    document_type: str | None
    file_url: str | None
    extracted_record: dict[str, Any] | None
    created_at: datetime


class FieldImageListResponse(BaseModel):
    items: list[FieldImageListItem]


class DebitNoteChargeRequest(BaseModel):
    charge_code: str
    description: str | None = None
    amount: Decimal
    currency: str = "USD"
    quantity: Decimal = Decimal("1")


class DebitNoteChargeResponse(BaseModel):
    id: UUID
    charge_code: str
    description: str | None
    amount: Decimal
    currency: str
    quantity: Decimal


class DebitNoteCreateRequest(BaseModel):
    container_no: str = Field(min_length=1)
    partner_name: str | None = None
    doc_no: str | None = None
    currency: str = "USD"
    issued_date: date | None = None
    source_attachment_id: UUID | None = None
    charges: list[DebitNoteChargeRequest] = Field(default_factory=list)


class DebitNoteResponse(BaseModel):
    id: UUID
    container_id: UUID
    container_no: str | None = None
    source_attachment_id: UUID | None
    partner_name: str | None
    doc_no: str | None
    currency: str
    issued_date: date | None
    created_by: UUID
    charges: list[DebitNoteChargeResponse]
    total_amount: Decimal
    created_at: datetime


class DebitNoteListResponse(BaseModel):
    items: list[DebitNoteResponse]
    total: int


class ReconciliationCreateRequest(BaseModel):
    container_no: str = Field(min_length=1)
    quote_id: UUID


class ReconciliationApproveRequest(BaseModel):
    note: str | None = None


class ReconciliationLineResponse(BaseModel):
    id: UUID
    charge_code: str
    quoted_amount: Decimal | None
    actual_amount: Decimal | None
    variance: Decimal
    match_status: Literal["matched", "variance", "missing_actual", "extra_actual"]
    note: str | None


class ReconciliationResponse(BaseModel):
    id: UUID
    container_id: UUID
    container_no: str | None = None
    quote_id: UUID
    quote_no: str | None = None
    status: Literal["draft", "reviewed", "approved", "escalated"]
    total_quoted: Decimal
    total_actual: Decimal
    total_variance: Decimal
    needs_approval: bool
    created_by: UUID
    approved_by: UUID | None
    lines: list[ReconciliationLineResponse]
    created_at: datetime


class ReconciliationListResponse(BaseModel):
    items: list[ReconciliationResponse]
    total: int


class CustomsChannelHistoryResponse(BaseModel):
    id: UUID
    from_channel: Literal["green", "yellow", "red"] | None
    to_channel: Literal["green", "yellow", "red"]
    changed_at: datetime
    changed_by: UUID
    reason: str | None


class CustomsDeclarationCreateRequest(BaseModel):
    container_no: str = Field(min_length=1)
    declaration_no: str | None = None
    declaration_type: Literal["import", "export"] = "import"
    channel: Literal["green", "yellow", "red"] | None = None
    hs_code: str | None = None
    registered_at: datetime | None = None
    cleared_at: datetime | None = None
    tax_amount: Decimal | None = None
    note: str | None = None


class CustomsDeclarationUpdateRequest(BaseModel):
    declaration_no: str | None = None
    declaration_type: Literal["import", "export"] = "import"
    channel: Literal["green", "yellow", "red"] | None = None
    hs_code: str | None = None
    registered_at: datetime | None = None
    cleared_at: datetime | None = None
    tax_amount: Decimal | None = None
    note: str | None = None
    channel_change_reason: str | None = None


class CustomsDeclarationResponse(BaseModel):
    id: UUID
    container_id: UUID
    container_no: str | None = None
    declaration_no: str | None
    declaration_type: Literal["import", "export"]
    channel: Literal["green", "yellow", "red"] | None
    hs_code: str | None
    registered_at: datetime | None
    cleared_at: datetime | None
    tax_amount: Decimal | None
    note: str | None
    created_by: UUID
    channel_history: list[CustomsChannelHistoryResponse]
    created_at: datetime
    updated_at: datetime | None


class CustomsDeclarationListResponse(BaseModel):
    items: list[CustomsDeclarationResponse]
    total: int


class QuoteDraftFields(BaseModel):
    """Các ô của form báo giá mà hệ thống rút được từ email. Mọi ô đều có thể
    vắng — vắng nghĩa là không tìm thấy trong email, không phải bằng 0."""

    customer_name: str | None = None
    pol: str | None = None
    pod: str | None = None
    commodity: str | None = None
    container_type: str | None = None
    container_qty: int | None = None
    gross_weight_kg: Decimal | None = None
    incoterm: str | None = None
    payment_term: str | None = None


class QuoteDraftResponse(BaseModel):
    source_email_id: UUID
    source_subject: str | None
    source_from: str | None
    fields: QuoteDraftFields
    # Tên các ô thực sự rút được, để giao diện nói rõ "đã điền N trường" thay vì
    # để người dùng tự dò xem máy đã đụng vào đâu.
    fields_found: list[str]
    extraction_error: str | None = None


class ComposedMailResponse(BaseModel):
    """Nội dung thư soạn sẵn. Agentify không gửi — người dùng bấm gửi trong hộp
    thư của chính họ, nên phản hồi chỉ có tiêu đề và thân thư."""

    subject: str
    body: str


class ChargeDraftLine(BaseModel):
    charge_group: Literal["ocean_freight", "surcharge", "local"]
    charge_code: str
    description: str
    unit_price: str
    currency: str
    quantity: str


class ChargeDraftResponse(BaseModel):
    source_email_id: UUID
    source_subject: str | None
    source_from: str | None
    charges: list[ChargeDraftLine]
    extraction_error: str | None = None


class ShipmentCreateRequest(BaseModel):
    customer_name: str | None = None
    direction: Literal["import", "export"] | None = None
    quote_id: UUID | None = None
    container_nos: list[str] = Field(default_factory=list)


class ShipmentAdvanceRequest(BaseModel):
    pass


class ShipmentMoveStageRequest(BaseModel):
    """Target column for a Kanban drag. Spelled out as a Literal like the rest
    of this module (which stays free of `db.models` imports), so an unknown
    stage is a 422 rather than a silently ignored write."""

    stage: Literal[
        "rfq", "booking", "documents", "customs", "delivery", "reconciliation", "closed"
    ]


class ShipmentResponse(BaseModel):
    id: UUID
    shipment_no: str
    customer_name: str | None
    direction: Literal["import", "export"] | None
    stage: Literal[
        "rfq", "booking", "documents", "customs", "delivery", "reconciliation", "closed"
    ]
    quote_id: UUID | None
    quote_no: str | None = None
    owner_role: str | None
    sla_due_at: datetime | None
    sla_breached: bool
    container_count: int
    container_nos: list[str]
    created_at: datetime
    updated_at: datetime | None


class ShipmentBoardColumn(BaseModel):
    stage: Literal[
        "rfq", "booking", "documents", "customs", "delivery", "reconciliation", "closed"
    ]
    jobs: list[ShipmentResponse]


class ShipmentBoardResponse(BaseModel):
    columns: list[ShipmentBoardColumn]


class ShipmentListResponse(BaseModel):
    items: list[ShipmentResponse]
    total: int


class AuditLogResponse(BaseModel):
    id: UUID
    user_id: UUID
    username: str | None = None
    role_used: str
    action: str
    resource_type: str
    resource_id: UUID | None
    detail: dict[str, Any] | None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int


UserRoleLiteral = Literal[
    "admin", "manager", "sales_cs", "docs", "ops", "accountant", "driver"
]


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=255)
    role: UserRoleLiteral
    password: str = Field(min_length=6)


class UserUpdateRequest(BaseModel):
    role: UserRoleLiteral | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=6)


class UserResponse(BaseModel):
    id: UUID
    username: str
    display_name: str
    role: UserRoleLiteral
    is_active: bool
    created_at: datetime


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int


class PermissionMatrixResponse(BaseModel):
    matrix: dict[str, dict[str, list[str]]]


class ExtractionCapability(BaseModel):
    ready: bool
    provider: str | None
    reason: str | None
    fallback: str


class ExtractionStatusResponse(BaseModel):
    provider_setting: str
    text_extraction: ExtractionCapability
    image_ocr: ExtractionCapability
    missing_keys: list[str]
    gemini_model: str | None
