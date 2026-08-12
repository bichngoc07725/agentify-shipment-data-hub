import enum
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class UserRole(str, enum.Enum):
    """A user has exactly one role — roles are not additive."""

    ADMIN = "admin"
    MANAGER = "manager"
    SALES_CS = "sales_cs"
    DOCS = "docs"
    OPS = "ops"
    ACCOUNTANT = "accountant"
    DRIVER = "driver"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("username", name="uq_users_username"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(100), nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=False)
    role = Column(
        Enum(
            UserRole,
            name="user_role",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class GmailConnection(Base):
    __tablename__ = "gmail_connections"
    __table_args__ = (
        UniqueConstraint("account_email", name="uq_gmail_connections_account_email"),
        UniqueConstraint(
            "google_account_id", name="uq_gmail_connections_google_account_id"
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_email = Column(String(255), nullable=False, index=True)
    display_name = Column(String(255), nullable=True)
    google_account_id = Column(String(255), nullable=True)
    encrypted_refresh_token = Column(Text, nullable=True)
    access_scope = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default="connected")
    sync_cursor = Column(Text, nullable=True)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    extra_metadata = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    sync_jobs = relationship("SyncJob", back_populates="gmail_connection")
    emails = relationship("Email", back_populates="gmail_connection")


class SyncJob(Base):
    __tablename__ = "sync_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    gmail_connection_id = Column(
        UUID(as_uuid=True), ForeignKey("gmail_connections.id"), nullable=False, index=True
    )
    query = Column(Text, nullable=True)
    date_from = Column(Date, nullable=True)
    date_to = Column(Date, nullable=True)
    max_results = Column(Integer, nullable=False, default=200)
    status = Column(String(50), nullable=False, default="queued", index=True)
    emails_fetched = Column(Integer, nullable=False, default=0)
    attachments_found = Column(Integer, nullable=False, default=0)
    pdf_text_extracted = Column(Integer, nullable=False, default=0)
    containers_upserted = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    gmail_connection = relationship("GmailConnection", back_populates="sync_jobs")
    emails = relationship("Email", back_populates="sync_job")


class Email(Base):
    __tablename__ = "emails"
    __table_args__ = (
        UniqueConstraint("gmail_message_id", name="uq_emails_gmail_message_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Null for messages that did not come from a mailbox, e.g. a Zalo message
    # pasted in by hand.
    gmail_connection_id = Column(
        UUID(as_uuid=True), ForeignKey("gmail_connections.id"), nullable=True, index=True
    )
    sync_job_id = Column(
        UUID(as_uuid=True), ForeignKey("sync_jobs.id"), nullable=True
    )
    # Which channel this message arrived on: email, zalo, note.
    channel = Column(String(32), nullable=False, default="email", index=True)
    gmail_message_id = Column(String(255), nullable=False, index=True)
    gmail_thread_id = Column(String(255), nullable=True)
    subject = Column(Text, nullable=False)
    from_email = Column(String(255), nullable=False)
    to_emails = Column(JSONB, nullable=False, default=list)
    cc_emails = Column(JSONB, nullable=False, default=list)
    sent_at = Column(DateTime(timezone=True), nullable=False, index=True)
    snippet = Column(Text, nullable=True)
    body_text = Column(Text, nullable=True)
    body_html = Column(Text, nullable=True)
    raw_labels = Column(JSONB, nullable=False, default=list)
    has_pdf_attachments = Column(Boolean, nullable=False, default=False)
    processing_status = Column(String(50), nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    gmail_connection = relationship("GmailConnection", back_populates="emails")
    sync_job = relationship("SyncJob", back_populates="emails")
    attachments = relationship("Attachment", back_populates="email")
    container_facts = relationship("ContainerFact", back_populates="email")


class Attachment(Base):
    __tablename__ = "attachments"
    __table_args__ = (
        UniqueConstraint("email_id", "filename", name="uq_attachments_email_filename"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Null for a field photo (container/seal/EIR/POD) — it didn't arrive on an
    # email message, so there is nothing to attach it to.
    email_id = Column(UUID(as_uuid=True), ForeignKey("emails.id"), nullable=True, index=True)
    gmail_attachment_id = Column(Text, nullable=True)
    filename = Column(String(500), nullable=False)
    mime_type = Column(String(255), nullable=False)
    size_bytes = Column(Integer, nullable=True)
    storage_path = Column(Text, nullable=True)
    is_text_pdf = Column(Boolean, nullable=False, default=True)
    text_extract_status = Column(String(50), nullable=False, default="pending")
    extracted_text = Column(Text, nullable=True)
    document_type = Column(String(100), nullable=True)
    extracted_record = Column(JSONB, nullable=True)
    # "gmail" (default) or "field_upload" — a driver/ops photo from the field.
    source_channel = Column(String(20), nullable=False, default="gmail")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    email = relationship("Email", back_populates="attachments")
    container_facts = relationship("ContainerFact", back_populates="attachment")


class Container(Base):
    __tablename__ = "containers"
    __table_args__ = (
        UniqueConstraint("container_no", name="uq_containers_container_no"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    container_no = Column(String(32), nullable=False, index=True)
    booking_no = Column(String(255), nullable=True, index=True)
    bl_no = Column(String(255), nullable=True, index=True)
    po_no = Column(String(255), nullable=True, index=True)
    do_no = Column(String(255), nullable=True, index=True)
    seal_no = Column(String(255), nullable=True)
    vessel = Column(String(255), nullable=True)
    voyage = Column(String(255), nullable=True)
    pol = Column(String(255), nullable=True)
    pod = Column(String(255), nullable=True)
    etd = Column(Date, nullable=True)
    eta = Column(Date, nullable=True)
    ata = Column(Date, nullable=True)
    # Free days before demurrage/detention starts, as stated on the arrival notice.
    free_time_days = Column(Integer, nullable=True)
    status_text = Column(Text, nullable=True)
    source_count = Column(Integer, nullable=False, default=0)
    attachment_count = Column(Integer, nullable=False, default=0)
    first_seen_at = Column(DateTime(timezone=True), nullable=False)
    last_seen_at = Column(DateTime(timezone=True), nullable=False)
    # A shipment/job (GĐ7B) groups several containers under one Kanban card.
    # Nullable: most containers still stand alone until assigned to a job.
    shipment_id = Column(
        UUID(as_uuid=True), ForeignKey("shipments.id"), nullable=True, index=True
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    facts = relationship("ContainerFact", back_populates="container")
    shipment = relationship("Shipment", back_populates="containers")


class ContainerFact(Base):
    __tablename__ = "container_facts"
    __table_args__ = (
        Index(
            "ix_container_facts_container_field_sent_at",
            "container_id",
            "field_name",
            "source_sent_at",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    container_id = Column(
        UUID(as_uuid=True), ForeignKey("containers.id"), nullable=False, index=True
    )
    # Null for a fact sourced from a field photo — see `Attachment.email_id`.
    email_id = Column(UUID(as_uuid=True), ForeignKey("emails.id"), nullable=True, index=True)
    attachment_id = Column(
        UUID(as_uuid=True), ForeignKey("attachments.id"), nullable=True, index=True
    )
    field_name = Column(String(100), nullable=False, index=True)
    field_value = Column(Text, nullable=False)
    normalized_value = Column(Text, nullable=True)
    source_type = Column(String(100), nullable=False)
    source_label = Column(Text, nullable=True)
    document_type = Column(String(100), nullable=True)
    confidence = Column(Numeric(5, 4), nullable=True)
    source_sent_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    container = relationship("Container", back_populates="facts")
    email = relationship("Email", back_populates="container_facts")
    attachment = relationship("Attachment", back_populates="container_facts")


class ExceptionAction(Base):
    """Audit trail for resolve/approve on a shipment exception.

    Exceptions themselves are computed live from container/fact data (there is
    no `exceptions` table), so this records the human action taken on one
    (container, code) pair rather than mutating exception state directly.
    """

    __tablename__ = "exception_actions"
    __table_args__ = (
        Index(
            "ix_exception_actions_container_code",
            "container_id",
            "code",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    container_id = Column(
        UUID(as_uuid=True), ForeignKey("containers.id"), nullable=False, index=True
    )
    code = Column(String(100), nullable=False)
    action = Column(String(20), nullable=False)  # resolve | approve
    # Collapsed 2-tier model (not the 3-level UI severity): normal | critical.
    severity_tier = Column(String(20), nullable=False)
    acted_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    acted_by_username = Column(String(100), nullable=False)
    acted_by_role = Column(String(50), nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    container = relationship("Container")


class QuoteStatus(str, enum.Enum):
    DRAFT = "draft"
    SENT = "sent"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ChargeGroup(str, enum.Enum):
    """The 3 blocks a quote's price breaks into (BA Spec Bước 1 Luồng C)."""

    OCEAN_FREIGHT = "ocean_freight"
    SURCHARGE = "surcharge"
    LOCAL = "local"


class Quote(Base):
    """A price quoted to a customer — the baseline Bước 6 reconciliation
    compares real costs against. Owned by `sales_cs`."""

    __tablename__ = "quotes"
    __table_args__ = (
        UniqueConstraint("quote_no", name="uq_quotes_quote_no"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quote_no = Column(String(50), nullable=False, index=True)
    customer_name = Column(String(255), nullable=False)
    status = Column(
        Enum(
            QuoteStatus,
            name="quote_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=QuoteStatus.DRAFT,
    )
    pol = Column(String(255), nullable=True)
    pod = Column(String(255), nullable=True)
    commodity = Column(String(255), nullable=True)
    is_dangerous = Column(Boolean, nullable=False, default=False)
    is_reefer = Column(Boolean, nullable=False, default=False)
    container_type = Column(String(50), nullable=True)
    container_qty = Column(Integer, nullable=True)
    gross_weight_kg = Column(Numeric(12, 2), nullable=True)
    cargo_ready_date = Column(Date, nullable=True)
    incoterm = Column(String(20), nullable=True)
    payment_term = Column(String(255), nullable=True)
    transit_time = Column(String(100), nullable=True)
    valid_until = Column(Date, nullable=True)
    note = Column(Text, nullable=True)
    currency = Column(String(10), nullable=False, default="USD")
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    # Nullable: an RFQ may not have a matched container yet.
    container_id = Column(
        UUID(as_uuid=True), ForeignKey("containers.id"), nullable=True, index=True
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    charges = relationship(
        "QuoteCharge", back_populates="quote", cascade="all, delete-orphan"
    )
    container = relationship("Container")


class QuoteCharge(Base):
    __tablename__ = "quote_charges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quote_id = Column(
        UUID(as_uuid=True),
        ForeignKey("quotes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    charge_group = Column(
        Enum(
            ChargeGroup,
            name="quote_charge_group",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    charge_code = Column(String(50), nullable=False)
    description = Column(String(255), nullable=True)
    unit_price = Column(Numeric(14, 2), nullable=False)
    currency = Column(String(10), nullable=False, default="USD")
    quantity = Column(Numeric(10, 2), nullable=False, default=1)
    amount = Column(Numeric(14, 2), nullable=False)

    quote = relationship("Quote", back_populates="charges")


class BookingStatus(str, enum.Enum):
    """Vòng đời một chỗ đặt trên tàu. `requested` = đã hỏi hãng tàu nhưng chưa
    có số booking; `amended` = hãng tàu đổi tàu/lịch sau khi đã xác nhận —
    trạng thái phải phân biệt được, vì đổi lịch là lúc giờ cut-off dịch chuyển
    và lô hàng có nguy cơ rớt chuyến."""

    REQUESTED = "requested"
    CONFIRMED = "confirmed"
    AMENDED = "amended"
    CANCELLED = "cancelled"


class Booking(Base):
    """Chỗ đặt trên tàu (Bước 2). Thuộc sở hữu `ops`.

    Tách khỏi `container_facts` vì đây là thứ nhân viên CHỦ ĐỘNG nhập và sửa
    theo tiến trình đàm phán với hãng tàu, không phải giá trị bóc ra từ chứng
    từ — trộn vào facts sẽ mất phân biệt giữa "hệ thống đọc được" và "người
    quyết định". Giá cước ở đây là giá MUA từ hãng tàu; giá BÁN cho khách nằm
    ở `Quote`, và chênh lệch hai bên là biên lợi nhuận của lô.
    """

    __tablename__ = "bookings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Nullable có chủ đích: lúc gửi yêu cầu đặt chỗ, hãng tàu CHƯA cấp
    # container — số container chỉ có khi booking được xác nhận. Bắt buộc phải
    # có container ở đây đồng nghĩa không thể ghi nhận trạng thái `requested`,
    # tức là mất đúng khoảnh khắc mà bước này cần được theo dõi.
    container_id = Column(
        UUID(as_uuid=True), ForeignKey("containers.id"), nullable=True, index=True
    )
    # Báo giá đã gửi khách cho lô này: vừa để so giá mua với giá bán, vừa là
    # nguồn thông tin để điền form đặt chỗ khi chưa có container nào.
    quote_id = Column(UUID(as_uuid=True), ForeignKey("quotes.id"), nullable=True)

    booking_no = Column(String(100), nullable=True, index=True)
    status = Column(
        Enum(
            BookingStatus,
            name="booking_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=BookingStatus.REQUESTED,
    )
    carrier = Column(String(255), nullable=True)
    vessel = Column(String(255), nullable=True)
    voyage = Column(String(100), nullable=True)
    pol = Column(String(255), nullable=True)
    pod = Column(String(255), nullable=True)
    etd = Column(Date, nullable=True)
    eta = Column(Date, nullable=True)

    # Ba mốc chốt của bước đặt chỗ. Đây là lý do bảng này tồn tại: rủi ro gốc
    # của Bước 2 là trễ giờ chốt → rớt chuyến → phát sinh phí lưu kho.
    si_cutoff_at = Column(DateTime(timezone=True), nullable=True)
    vgm_cutoff_at = Column(DateTime(timezone=True), nullable=True)
    gate_in_cutoff_at = Column(DateTime(timezone=True), nullable=True)

    container_type = Column(String(50), nullable=True)
    container_qty = Column(Integer, nullable=True)
    empty_pickup_depot = Column(String(255), nullable=True)

    # Giá cước hãng tàu chào (giá mua).
    freight_rate = Column(Numeric(14, 2), nullable=True)
    currency = Column(String(10), nullable=False, default="USD")

    note = Column(Text, nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    container = relationship("Container")
    quote = relationship("Quote")


class DebitNote(Base):
    """Real costs invoiced for a shipment (carrier debit note / invoice) —
    the "actual" side reconciliation compares against `Quote` (the "quoted"
    side, from GĐ4). Owned by `accountant`."""

    __tablename__ = "debit_notes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    container_id = Column(
        UUID(as_uuid=True), ForeignKey("containers.id"), nullable=False, index=True
    )
    # The PDF this was entered from, if any — kept for provenance only; the
    # charges below are always typed in (or corrected) by hand.
    source_attachment_id = Column(
        UUID(as_uuid=True), ForeignKey("attachments.id"), nullable=True
    )
    partner_name = Column(String(255), nullable=True)
    doc_no = Column(String(255), nullable=True)
    currency = Column(String(10), nullable=False, default="USD")
    issued_date = Column(Date, nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    charges = relationship(
        "DebitNoteCharge", back_populates="debit_note", cascade="all, delete-orphan"
    )
    container = relationship("Container")


class DebitNoteCharge(Base):
    """Mirrors `QuoteCharge`'s shape so the two sides line up 1:1 when
    reconciliation matches them by `charge_code`."""

    __tablename__ = "debit_note_charges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    debit_note_id = Column(
        UUID(as_uuid=True),
        ForeignKey("debit_notes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    charge_code = Column(String(50), nullable=False)
    description = Column(String(255), nullable=True)
    amount = Column(Numeric(14, 2), nullable=False)
    currency = Column(String(10), nullable=False, default="USD")
    quantity = Column(Numeric(10, 2), nullable=False, default=1)

    debit_note = relationship("DebitNote", back_populates="charges")


class ReconciliationStatus(str, enum.Enum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    ESCALATED = "escalated"


class ReconciliationMatchStatus(str, enum.Enum):
    MATCHED = "matched"
    VARIANCE = "variance"
    MISSING_ACTUAL = "missing_actual"
    EXTRA_ACTUAL = "extra_actual"


class Reconciliation(Base):
    """One run of matching a container's quoted charges against its real
    costs. `needs_approval`/`status=escalated` gates the total variance
    behind Admin/Manager sign-off — see `services/reconciliation_service.py`.
    """

    __tablename__ = "reconciliations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    container_id = Column(
        UUID(as_uuid=True), ForeignKey("containers.id"), nullable=False, index=True
    )
    quote_id = Column(
        UUID(as_uuid=True), ForeignKey("quotes.id"), nullable=False, index=True
    )
    status = Column(
        Enum(
            ReconciliationStatus,
            name="reconciliation_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=ReconciliationStatus.DRAFT,
    )
    total_quoted = Column(Numeric(14, 2), nullable=False, default=0)
    total_actual = Column(Numeric(14, 2), nullable=False, default=0)
    total_variance = Column(Numeric(14, 2), nullable=False, default=0)
    needs_approval = Column(Boolean, nullable=False, default=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    lines = relationship(
        "ReconciliationLine", back_populates="reconciliation", cascade="all, delete-orphan"
    )
    container = relationship("Container")
    quote = relationship("Quote")


class ReconciliationLine(Base):
    __tablename__ = "reconciliation_lines"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reconciliation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("reconciliations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    charge_code = Column(String(50), nullable=False)
    quoted_amount = Column(Numeric(14, 2), nullable=True)
    actual_amount = Column(Numeric(14, 2), nullable=True)
    variance = Column(Numeric(14, 2), nullable=False)
    match_status = Column(
        Enum(
            ReconciliationMatchStatus,
            name="reconciliation_match_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    note = Column(Text, nullable=True)

    reconciliation = relationship("Reconciliation", back_populates="lines")


class CustomsDeclarationType(str, enum.Enum):
    IMPORT = "import"
    EXPORT = "export"


class CustomsChannel(str, enum.Enum):
    """VNACCS phân luồng: Green clears immediately, Yellow needs a paper-file
    check, Red needs a physical inspection — the slow, cost-accruing one."""

    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class CustomsDeclaration(Base):
    __tablename__ = "customs_declarations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    container_id = Column(
        UUID(as_uuid=True), ForeignKey("containers.id"), nullable=False, index=True
    )
    declaration_no = Column(String(100), nullable=True)
    declaration_type = Column(
        Enum(
            CustomsDeclarationType,
            name="customs_declaration_type",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    channel = Column(
        Enum(
            CustomsChannel,
            name="customs_channel",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=True,
    )
    hs_code = Column(String(50), nullable=True)
    registered_at = Column(DateTime(timezone=True), nullable=True)
    cleared_at = Column(DateTime(timezone=True), nullable=True)
    tax_amount = Column(Numeric(14, 2), nullable=True)
    note = Column(Text, nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    container = relationship("Container")
    channel_history = relationship(
        "CustomsChannelHistory",
        back_populates="declaration",
        cascade="all, delete-orphan",
        order_by="CustomsChannelHistory.changed_at",
    )


class CustomsChannelHistory(Base):
    """One row per "bẻ luồng" (channel re-assignment) — required audit trail
    for a decision that can add real days and cost to a shipment."""

    __tablename__ = "customs_channel_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    declaration_id = Column(
        UUID(as_uuid=True),
        ForeignKey("customs_declarations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_channel = Column(
        Enum(
            CustomsChannel,
            name="customs_channel",
            native_enum=True,
            create_constraint=False,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=True,
    )
    to_channel = Column(
        Enum(
            CustomsChannel,
            name="customs_channel",
            native_enum=True,
            create_constraint=False,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    changed_at = Column(DateTime(timezone=True), server_default=func.now())
    changed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    reason = Column(Text, nullable=True)

    declaration = relationship("CustomsDeclaration", back_populates="channel_history")


class ShipmentStage(str, enum.Enum):
    """Kanban columns — the 6 business steps plus a terminal `closed`."""

    RFQ = "rfq"
    BOOKING = "booking"
    DOCUMENTS = "documents"
    CUSTOMS = "customs"
    DELIVERY = "delivery"
    RECONCILIATION = "reconciliation"
    CLOSED = "closed"


class Shipment(Base):
    """A job: the unit Sales/Ops/Manager track on the Kanban board. Groups one
    or more `Container` rows and references the entities each step produces
    (quote from GĐ4; customs from 7A; reconciliation from GĐ6 is looked up by
    container, not referenced directly here)."""

    __tablename__ = "shipments"
    __table_args__ = (UniqueConstraint("shipment_no", name="uq_shipments_shipment_no"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_no = Column(String(50), nullable=False, index=True)
    customer_name = Column(String(255), nullable=True)
    direction = Column(
        Enum(
            CustomsDeclarationType,
            name="shipment_direction",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=True,
    )
    stage = Column(
        Enum(
            ShipmentStage,
            name="shipment_stage",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=ShipmentStage.RFQ,
    )
    quote_id = Column(UUID(as_uuid=True), ForeignKey("quotes.id"), nullable=True)
    owner_role = Column(
        Enum(
            UserRole,
            name="user_role",
            native_enum=True,
            create_constraint=False,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=True,
    )
    sla_due_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    containers = relationship("Container", back_populates="shipment")
    quote = relationship("Quote")


class AuditLog(Base):
    """Who did what, when, on a sensitive operation — generalizes the
    `ExceptionAction` pattern (GĐ2) to every resource that needs a trail for
    a cost/data dispute: critical-exception approvals, manual fact edits,
    reconciliation approvals, ERP exports. See GĐ8A brief."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    role_used = Column(
        Enum(
            UserRole,
            name="user_role",
            native_enum=True,
            create_constraint=False,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    action = Column(String(50), nullable=False)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(UUID(as_uuid=True), nullable=True)
    detail = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    user = relationship("User")
