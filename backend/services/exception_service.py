"""Shipment exception detection.

Turns the container profile from a lookup surface into a worklist: instead of the
user having to know which container to search for, Agentify surfaces the ones
that need attention today.

Every rule here is computed from data the ingestion pipeline already stores —
container summary fields, extracted facts and attachment document types. Nothing
is inferred: a rule either has the evidence to fire or it stays silent, and each
exception carries the evidence it fired on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Attachment, Container, ContainerFact

# Days before free time runs out that we start warning.
FREE_TIME_WARNING_DAYS = 3
# Free days assumed when the arrival notice did not state a number. Kept
# deliberately low so the warning fires early rather than late; the exception
# says the value was assumed.
DEFAULT_FREE_TIME_DAYS = 5
# A container with no new source for this long is treated as going quiet.
STALE_AFTER_DAYS = 7

SEVERITY_CRITICAL = "critical"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"

_SEVERITY_ORDER = {SEVERITY_CRITICAL: 0, SEVERITY_WARNING: 1, SEVERITY_INFO: 2}

# Documents that close out an exception when present.
DELIVERY_ORDER_TYPES = {"delivery_order"}
CHARGE_DOCUMENT_TYPES = {"debit_note", "invoice"}

# Minimum document set per shipment direction. Import is the default because the
# beachhead segment is import-heavy.
REQUIRED_DOCUMENTS: dict[str, tuple[str, ...]] = {
    "import": (
        "arrival_notice",
        "bill_of_lading",
        "delivery_order",
        "invoice",
        "customs_declaration",
    ),
    "export": (
        "booking_confirmation",
        "bill_of_lading",
        "invoice",
        "packing_list",
        "customs_declaration",
    ),
}

# Extractors and carriers name the same document differently. Without this the
# checklist silently ignores a document that is sitting right there in the mailbox.
DOCUMENT_TYPE_ALIASES = {
    "draft_bl": "bill_of_lading",
    "draft_b_l": "bill_of_lading",
    "master_bl": "bill_of_lading",
    "house_bl": "bill_of_lading",
    "commercial_invoice": "invoice",
    "booking_note": "booking_confirmation",
    "notice_of_arrival": "arrival_notice",
}

DOCUMENT_LABELS = {
    "arrival_notice": "Arrival Notice",
    "booking_confirmation": "Booking Confirmation",
    "bill_of_lading": "Bill of Lading",
    "delivery_order": "Delivery Order (D/O)",
    "invoice": "Invoice",
    "packing_list": "Packing List",
    "debit_note": "Debit Note",
    "certificate_of_origin": "Certificate of Origin",
    "customs_declaration": "Tờ khai Hải quan",
}


@dataclass
class ShipmentException:
    container_no: str
    code: str
    severity: str
    title: str
    detail: str
    evidence: list[str] = field(default_factory=list)
    due_date: date | None = None
    days_remaining: int | None = None


@dataclass
class ContainerRiskProfile:
    container_no: str
    direction: str
    exceptions: list[ShipmentException]
    # A document counts as present only when the file itself is in Agentify.
    documents_present: list[str]
    # Required documents a message refers to but whose file has not arrived.
    # Docs staff still have to collect these, so they are not "present".
    documents_mentioned: list[str]
    documents_missing: list[str]
    completeness: float
    free_time_expires_on: date | None
    free_time_is_assumed: bool


def _today() -> date:
    return datetime.now(UTC).date()


# Any of these means the shipment is inbound: they only exist on the arrival side.
IMPORT_EVIDENCE_DOCUMENTS = {"arrival_notice", "delivery_order", "notice_of_arrival"}


def infer_direction(container: Container, document_types: set[str] | None = None) -> str:
    """Import when we have arrival-side evidence, export otherwise.

    The document types matter as much as the dates: an arrival notice is proof of
    an inbound shipment even when it only quotes an ETA and no actual arrival has
    been recorded yet.
    """
    if container.ata or container.do_no:
        return "import"
    if document_types and IMPORT_EVIDENCE_DOCUMENTS & document_types:
        return "import"
    return "export"


def _as_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def compute_free_time_deadline(
    container: Container,
) -> tuple[date | None, bool]:
    """Return `(deadline, days_were_assumed)`.

    The clock starts at actual arrival, falling back to the estimate when the
    vessel has not been confirmed as arrived.
    """
    arrival = _as_date(container.ata) or _as_date(container.eta)
    if arrival is None:
        return None, False

    if container.free_time_days is not None:
        return arrival + timedelta(days=container.free_time_days), False
    return arrival + timedelta(days=DEFAULT_FREE_TIME_DAYS), True


def detect_exceptions(
    container: Container,
    document_types: set[str],
    eta_history: list[tuple[date, str]],
    last_source_at: datetime | None,
    has_unlinked_charges: bool = False,
    today: date | None = None,
    documents_mentioned: set[str] | None = None,
) -> list[ShipmentException]:
    """Apply every rule to one container and return the exceptions that fired.

    `document_types` is what is actually on file. `documents_mentioned` is what a
    message referred to without the file arriving — a Zalo message saying the D/O
    has been issued is good enough to stop the free-time alarm, but it is not the
    D/O, so it never satisfies the document checklist.
    """
    today = today or _today()
    document_types = canonical_document_types(document_types)
    documents_mentioned = canonical_document_types(documents_mentioned or set())
    exceptions: list[ShipmentException] = []
    # A D/O number extracted from any source proves the order exists; a bare
    # mention with no number does not.
    has_delivery_order = bool(
        DELIVERY_ORDER_TYPES & document_types or container.do_no
    )

    deadline, assumed = compute_free_time_deadline(container)
    if deadline is not None and not has_delivery_order:
        days_remaining = (deadline - today).days
        if days_remaining <= FREE_TIME_WARNING_DAYS:
            overdue = days_remaining < 0
            basis = "ATA" if container.ata else "ETA"
            assumed_note = (
                f" Số ngày free time chưa có trong chứng từ, tạm tính "
                f"{DEFAULT_FREE_TIME_DAYS} ngày."
                if assumed
                else ""
            )
            exceptions.append(
                ShipmentException(
                    container_no=container.container_no,
                    code="free_time_expiring",
                    severity=SEVERITY_CRITICAL,
                    title=(
                        "Đã quá hạn free time"
                        if overdue
                        else "Sắp hết free time"
                    ),
                    detail=(
                        f"Hết free time ngày {deadline.isoformat()} "
                        f"({abs(days_remaining)} ngày "
                        f"{'quá hạn' if overdue else 'còn lại'}) "
                        f"nhưng chưa thấy D/O trong dữ liệu Agentify.{assumed_note}"
                    ),
                    evidence=_free_time_evidence(container, basis),
                    due_date=deadline,
                    days_remaining=days_remaining,
                )
            )

    arrival = _as_date(container.ata)
    if arrival is not None and not has_delivery_order and arrival < today:
        exceptions.append(
            ShipmentException(
                container_no=container.container_no,
                code="arrived_no_do",
                severity=SEVERITY_CRITICAL,
                title="Tàu đã cập nhưng chưa có D/O",
                detail=(
                    f"Ghi nhận ATA {arrival.isoformat()} "
                    f"({(today - arrival).days} ngày trước) "
                    "nhưng chưa thấy Delivery Order trong dữ liệu Agentify."
                ),
                evidence=[f"ATA: {arrival.isoformat()}"],
                due_date=arrival,
            )
        )

    if len(eta_history) >= 2:
        (newest, newest_source), (previous, previous_source) = (
            eta_history[0],
            eta_history[1],
        )
        if newest != previous:
            shift = (newest - previous).days
            exceptions.append(
                ShipmentException(
                    container_no=container.container_no,
                    code="eta_changed",
                    severity=SEVERITY_WARNING,
                    title="ETA thay đổi",
                    detail=(
                        f"ETA đổi từ {previous.isoformat()} sang {newest.isoformat()} "
                        f"({shift:+d} ngày). Kiểm tra đã báo khách chưa."
                    ),
                    evidence=[
                        f"ETA mới: {newest.isoformat()} — {newest_source}",
                        f"ETA trước: {previous.isoformat()} — {previous_source}",
                    ],
                    due_date=newest,
                )
            )

    direction = infer_direction(container, document_types | documents_mentioned)
    missing = missing_documents(direction, document_types)
    if missing:
        # Split the gap: some documents have been referred to in a message, the
        # rest are unaccounted for. Chasing a file that exists is a different job
        # from chasing one nobody has mentioned.
        mentioned_only = [doc for doc in missing if doc in documents_mentioned]
        unaccounted = [doc for doc in missing if doc not in documents_mentioned]

        detail_parts = []
        if unaccounted:
            detail_parts.append(
                "Chưa thấy trong dữ liệu Agentify: "
                + ", ".join(DOCUMENT_LABELS.get(doc, doc) for doc in unaccounted)
            )
        if mentioned_only:
            detail_parts.append(
                "Đã có thông tin nhưng chưa có file: "
                + ", ".join(DOCUMENT_LABELS.get(doc, doc) for doc in mentioned_only)
            )

        exceptions.append(
            ShipmentException(
                container_no=container.container_no,
                code="missing_documents",
                severity=SEVERITY_WARNING,
                title=f"Thiếu {len(missing)} chứng từ",
                detail=". ".join(detail_parts) + ".",
                evidence=[
                    f"Bộ chứng từ chuẩn: {direction}",
                    "Đã có file: "
                    + (
                        ", ".join(
                            DOCUMENT_LABELS.get(doc, doc) for doc in sorted(document_types)
                        )
                        or "chưa có file nào"
                    ),
                ],
            )
        )

    if last_source_at is not None:
        quiet_days = (today - last_source_at.date()).days
        if quiet_days >= STALE_AFTER_DAYS:
            exceptions.append(
                ShipmentException(
                    container_no=container.container_no,
                    code="stale_no_update",
                    severity=SEVERITY_WARNING,
                    title=f"Không có cập nhật {quiet_days} ngày",
                    detail=(
                        "Nguồn dữ liệu mới nhất là "
                        f"{last_source_at.date().isoformat()}. "
                        "Lô này có thể đang bị bỏ quên."
                    ),
                    evidence=[f"Nguồn gần nhất: {last_source_at.date().isoformat()}"],
                )
            )

    if has_unlinked_charges:
        exceptions.append(
            ShipmentException(
                container_no=container.container_no,
                code="unlinked_charges",
                severity=SEVERITY_INFO,
                title="Có chi phí chưa đối soát",
                detail=(
                    "Đã nhận debit note hoặc invoice cho lô này nhưng chưa "
                    "đối chiếu với báo giá."
                ),
                evidence=["Chứng từ chi phí: debit note / invoice"],
            )
        )

    exceptions.sort(key=lambda item: (_SEVERITY_ORDER[item.severity], item.code))
    return exceptions


def _free_time_evidence(container: Container, basis: str) -> list[str]:
    arrival = _as_date(container.ata) if basis == "ATA" else _as_date(container.eta)
    evidence = [f"{basis}: {arrival.isoformat() if arrival else '—'}"]
    if container.free_time_days is not None:
        evidence.append(f"Free time: {container.free_time_days} ngày")
    else:
        evidence.append(f"Free time: chưa có (tạm tính {DEFAULT_FREE_TIME_DAYS} ngày)")
    return evidence


def canonical_document_types(document_types: set[str]) -> set[str]:
    """Map carrier-specific document names onto the checklist vocabulary."""
    return {
        DOCUMENT_TYPE_ALIASES.get(document_type, document_type)
        for document_type in document_types
    }


def missing_documents(direction: str, document_types: set[str]) -> list[str]:
    required = REQUIRED_DOCUMENTS.get(direction, REQUIRED_DOCUMENTS["import"])
    present = canonical_document_types(document_types)
    return [doc for doc in required if doc not in present]


def build_risk_profile(
    container: Container,
    document_types: set[str],
    eta_history: list[tuple[date, str]],
    last_source_at: datetime | None,
    today: date | None = None,
    documents_mentioned: set[str] | None = None,
) -> ContainerRiskProfile:
    on_file = canonical_document_types(document_types)
    mentioned = canonical_document_types(documents_mentioned or set())

    direction = infer_direction(container, on_file | mentioned)
    required = REQUIRED_DOCUMENTS.get(direction, REQUIRED_DOCUMENTS["import"])
    present = [doc for doc in required if doc in on_file]
    missing = [doc for doc in required if doc not in on_file]
    # Mentioned-only documents stay in `missing`: the file still has to be
    # collected. They are listed separately so the UI can say why.
    mentioned_only = [doc for doc in missing if doc in mentioned]
    deadline, assumed = compute_free_time_deadline(container)

    return ContainerRiskProfile(
        container_no=container.container_no,
        direction=direction,
        exceptions=detect_exceptions(
            container,
            document_types,
            eta_history,
            last_source_at,
            has_unlinked_charges=bool(CHARGE_DOCUMENT_TYPES & on_file),
            today=today,
            documents_mentioned=mentioned,
        ),
        documents_present=present,
        documents_mentioned=mentioned_only,
        documents_missing=missing,
        completeness=round(len(present) / len(required), 2) if required else 1.0,
        free_time_expires_on=deadline,
        free_time_is_assumed=assumed,
    )


async def load_container_context(
    db: AsyncSession, container_ids: list
) -> dict:
    """Fetch document evidence, ETA history and last-source time for containers.

    Two kinds of document evidence are collected and kept apart:

    - `document_types`: the file is in Agentify, as an attachment classified as
      that document type. Only these satisfy the checklist.
    - `documents_mentioned`: a message body was classified as that document type
      without the file being attached — an email or a pasted Zalo message saying
      the D/O has been issued. Useful context, but not the document.

    Batched so the exception list stays cheap as the mailbox grows.
    """
    if not container_ids:
        return {}

    context: dict = {
        container_id: {
            "document_types": set(),
            "documents_mentioned": set(),
            "eta_history": [],
            "last_source_at": None,
        }
        for container_id in container_ids
    }

    doc_rows = await db.execute(
        select(ContainerFact.container_id, Attachment.document_type)
        .join(Attachment, ContainerFact.attachment_id == Attachment.id)
        .where(
            ContainerFact.container_id.in_(container_ids),
            Attachment.document_type.is_not(None),
        )
    )
    for container_id, document_type in doc_rows.all():
        context[container_id]["document_types"].add(document_type)

    # Facts with no attachment behind them came from a message body, so their
    # `document_type` describes what the message was about, not a file on file.
    mention_rows = await db.execute(
        select(ContainerFact.container_id, ContainerFact.document_type).where(
            ContainerFact.container_id.in_(container_ids),
            ContainerFact.attachment_id.is_(None),
            ContainerFact.document_type.is_not(None),
            ContainerFact.document_type != "other",
        )
    )
    for container_id, document_type in mention_rows.all():
        context[container_id]["documents_mentioned"].add(document_type)

    eta_rows = await db.execute(
        select(
            ContainerFact.container_id,
            ContainerFact.normalized_value,
            ContainerFact.field_value,
            ContainerFact.source_label,
            ContainerFact.source_sent_at,
        )
        .where(
            ContainerFact.container_id.in_(container_ids),
            ContainerFact.field_name == "eta",
        )
        .order_by(
            ContainerFact.source_sent_at.desc().nullslast(),
            ContainerFact.created_at.desc(),
        )
    )
    for container_id, normalized, raw, source_label, _sent_at in eta_rows.all():
        parsed = _parse_iso_date(normalized or raw)
        if parsed is None:
            continue
        history = context[container_id]["eta_history"]
        if any(existing == parsed for existing, _ in history):
            continue
        history.append((parsed, source_label or "nguồn không rõ"))

    latest_rows = await db.execute(
        select(ContainerFact.container_id, ContainerFact.source_sent_at).where(
            ContainerFact.container_id.in_(container_ids),
            ContainerFact.source_sent_at.is_not(None),
        )
    )
    for container_id, sent_at in latest_rows.all():
        current = context[container_id]["last_source_at"]
        if current is None or sent_at > current:
            context[container_id]["last_source_at"] = sent_at

    return context


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


async def list_shipment_exceptions(
    db: AsyncSession,
    severity: str | None = None,
    code: str | None = None,
    limit: int = 200,
) -> list[ShipmentException]:
    result = await db.execute(select(Container))
    containers = list(result.scalars().all())
    context = await load_container_context(db, [c.id for c in containers])

    exceptions: list[ShipmentException] = []
    for container in containers:
        ctx = context.get(container.id, {})
        exceptions.extend(
            detect_exceptions(
                container,
                ctx.get("document_types", set()),
                ctx.get("eta_history", []),
                ctx.get("last_source_at"),
                has_unlinked_charges=bool(
                    CHARGE_DOCUMENT_TYPES
                    & canonical_document_types(ctx.get("document_types", set()))
                ),
                documents_mentioned=ctx.get("documents_mentioned", set()),
            )
        )

    if severity:
        exceptions = [item for item in exceptions if item.severity == severity]
    if code:
        exceptions = [item for item in exceptions if item.code == code]

    exceptions.sort(
        key=lambda item: (
            _SEVERITY_ORDER[item.severity],
            item.days_remaining if item.days_remaining is not None else 999,
            item.container_no,
        )
    )
    return exceptions[:limit]


async def get_container_risk_profile(
    db: AsyncSession, container: Container
) -> ContainerRiskProfile:
    context = await load_container_context(db, [container.id])
    ctx = context.get(container.id, {})
    return build_risk_profile(
        container,
        ctx.get("document_types", set()),
        ctx.get("eta_history", []),
        ctx.get("last_source_at"),
        documents_mentioned=ctx.get("documents_mentioned", set()),
    )
