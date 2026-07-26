import uuid

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
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
    email_id = Column(UUID(as_uuid=True), ForeignKey("emails.id"), nullable=False, index=True)
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
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    facts = relationship("ContainerFact", back_populates="container")


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
    email_id = Column(UUID(as_uuid=True), ForeignKey("emails.id"), nullable=False, index=True)
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
