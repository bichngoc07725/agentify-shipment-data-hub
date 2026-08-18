"""Smart reconciliation: match a container's quoted charges (GĐ4) against
its real costs (debit notes) so a fee quietly missing from the customer's
invoice doesn't quietly cost the company money. See
`plan/phase_6_reconciliation_brief.md`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import (
    CustomsDeclaration,
    DebitNote,
    DebitNoteCharge,
    Quote,
    QuoteCharge,
    Reconciliation,
    ReconciliationLine,
    ReconciliationMatchStatus,
    ReconciliationStatus,
)
from services.container_service import get_container_by_no
from services.exception_service import compute_free_time_deadline

# A variance smaller than this (in absolute currency, or as a % of the
# quoted amount — whichever allows more slack) counts as "close enough".
# Carriers round differently between quote and invoice; flagging every
# $0.10 difference as a discrepancy would bury the ones that matter.
VARIANCE_THRESHOLD_ABS = Decimal("1.00")
VARIANCE_THRESHOLD_PCT = Decimal("0.01")

# Total variance beyond this needs Admin/Manager sign-off, not just the
# accountant who ran the reconciliation.
ESCALATION_ABS_THRESHOLD = Decimal("100.00")
ESCALATION_PCT_THRESHOLD = Decimal("0.05")

DEFAULT_DAILY_DEMURRAGE_RATE = Decimal("50.00")
DEMURRAGE_CHARGE_CODE = "DEMURRAGE_EST"
CUSTOMS_TAX_CHARGE_CODE = "CUSTOMS_TAX"
# If a real demurrage/storage charge already came in on a debit note, the
# estimate would double-count it — skip generating one in that case.
_DEMURRAGE_LIKE_CODES = {"DEM", "DEMURRAGE", "DET", "DETENTION", "STORAGE"}

_LOAD_OPTIONS = (
    selectinload(Reconciliation.lines),
    selectinload(Reconciliation.container),
    selectinload(Reconciliation.quote),
)


def _normalize_code(code: str) -> str:
    return code.strip().upper()


@dataclass
class ReconciliationLineResult:
    charge_code: str
    quoted_amount: Decimal | None
    actual_amount: Decimal | None
    variance: Decimal
    match_status: str
    note: str | None = None


def build_reconciliation_lines(
    quote_charges: list[QuoteCharge],
    debit_note_charges: list[DebitNoteCharge],
) -> list[ReconciliationLineResult]:
    """Match quoted vs. real charges by `charge_code` (case/space-insensitive).
    Multiple lines with the same code on either side are summed first, so a
    debit note that splits one quoted fee across two rows still matches."""

    quoted_by_code: dict[str, Decimal] = {}
    for charge in quote_charges:
        code = _normalize_code(charge.charge_code)
        quoted_by_code[code] = quoted_by_code.get(code, Decimal("0")) + charge.amount

    actual_by_code: dict[str, Decimal] = {}
    for charge in debit_note_charges:
        code = _normalize_code(charge.charge_code)
        actual_by_code[code] = actual_by_code.get(code, Decimal("0")) + charge.amount

    lines: list[ReconciliationLineResult] = []
    for code in sorted(set(quoted_by_code) | set(actual_by_code)):
        quoted = quoted_by_code.get(code)
        actual = actual_by_code.get(code)
        variance = (actual or Decimal("0")) - (quoted or Decimal("0"))

        if quoted is not None and actual is not None:
            threshold = max(VARIANCE_THRESHOLD_ABS, quoted * VARIANCE_THRESHOLD_PCT)
            status = "matched" if abs(variance) <= threshold else "variance"
        elif quoted is not None:
            status = "missing_actual"
        else:
            status = "extra_actual"

        lines.append(ReconciliationLineResult(code, quoted, actual, variance, status))

    return lines


def compute_demurrage_estimate(
    container,
    today: date | None = None,
    daily_rate: Decimal = DEFAULT_DAILY_DEMURRAGE_RATE,
) -> ReconciliationLineResult | None:
    """A container still sitting past its free-time deadline is accruing a
    real cost before the carrier's storage invoice ever arrives. Surfacing it
    as an estimated `extra_actual` line means the accountant sees it during
    reconciliation instead of finding out when the bill lands. Returns None
    when there's no arrival data yet or the deadline hasn't passed."""

    deadline, is_assumed = compute_free_time_deadline(container)
    if deadline is None:
        return None

    today = today or datetime.now(UTC).date()
    overdue_days = (today - deadline).days
    if overdue_days <= 0:
        return None

    amount = Decimal(overdue_days) * daily_rate
    note = f"Ước tính {overdue_days} ngày quá free time x {daily_rate}/ngày"
    if is_assumed:
        note += " (free time chưa có trong chứng từ, đang tạm tính)"

    return ReconciliationLineResult(
        charge_code=DEMURRAGE_CHARGE_CODE,
        quoted_amount=None,
        actual_amount=amount,
        variance=amount,
        match_status="extra_actual",
        note=note,
    )


def totals_for(lines: list[ReconciliationLineResult]) -> tuple[Decimal, Decimal, Decimal]:
    total_quoted = sum((line.quoted_amount or Decimal("0") for line in lines), Decimal("0"))
    total_actual = sum((line.actual_amount or Decimal("0") for line in lines), Decimal("0"))
    return total_quoted, total_actual, total_actual - total_quoted


def needs_approval_for(total_quoted: Decimal, total_variance: Decimal) -> bool:
    threshold = max(ESCALATION_ABS_THRESHOLD, total_quoted * ESCALATION_PCT_THRESHOLD)
    return abs(total_variance) > threshold


def build_customs_tax_line(
    declaration,
) -> ReconciliationLineResult | None:
    """Thuế hải quan như một khoản chi thực của lô hàng.

    Thuế không nằm trong báo giá gửi khách — báo giá là tiền cước dịch vụ — nên
    nó luôn là `extra_actual`. Bỏ nó ra ngoài đối soát khiến bức tranh chi phí
    của lô thiếu đúng khoản thường lớn nhất, và kế toán phát hiện ra lúc quyết
    toán thay vì lúc đối soát.
    """
    if declaration is None or declaration.tax_amount is None:
        return None

    amount = Decimal(str(declaration.tax_amount))
    if amount <= 0:
        return None

    reference = f" theo tờ khai {declaration.declaration_no}" if declaration.declaration_no else ""
    return ReconciliationLineResult(
        charge_code=CUSTOMS_TAX_CHARGE_CODE,
        quoted_amount=None,
        actual_amount=amount,
        variance=amount,
        match_status="extra_actual",
        note=f"Thuế hải quan{reference} — không nằm trong báo giá dịch vụ",
    )


async def build_reconciliation(
    db: AsyncSession, container_no: str, quote_id: UUID, created_by: UUID
) -> Reconciliation:
    container = await get_container_by_no(db, container_no)
    if container is None:
        raise ValueError(f"Container '{container_no}' not found")

    quote_result = await db.execute(
        select(Quote).where(Quote.id == quote_id).options(selectinload(Quote.charges))
    )
    quote = quote_result.scalar_one_or_none()
    if quote is None:
        raise ValueError(f"Quote '{quote_id}' not found")
    if quote.container_id != container.id:
        raise ValueError("Quote does not belong to this container")

    debit_note_charges_result = await db.execute(
        select(DebitNoteCharge)
        .join(DebitNote, DebitNoteCharge.debit_note_id == DebitNote.id)
        .where(DebitNote.container_id == container.id)
    )
    debit_note_charges = list(debit_note_charges_result.scalars().all())

    lines = build_reconciliation_lines(quote.charges, debit_note_charges)

    existing_codes = {line.charge_code for line in lines}
    if not existing_codes & _DEMURRAGE_LIKE_CODES:
        demurrage_line = compute_demurrage_estimate(container)
        if demurrage_line is not None:
            lines.append(demurrage_line)

    if CUSTOMS_TAX_CHARGE_CODE not in {line.charge_code for line in lines}:
        declaration = (
            await db.execute(
                select(CustomsDeclaration)
                .where(CustomsDeclaration.container_id == container.id)
                .order_by(CustomsDeclaration.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        tax_line = build_customs_tax_line(declaration)
        if tax_line is not None:
            lines.append(tax_line)

    total_quoted, total_actual, total_variance = totals_for(lines)
    escalate = needs_approval_for(total_quoted, total_variance)

    reconciliation = Reconciliation(
        container_id=container.id,
        quote_id=quote.id,
        status=ReconciliationStatus.ESCALATED if escalate else ReconciliationStatus.DRAFT,
        total_quoted=total_quoted,
        total_actual=total_actual,
        total_variance=total_variance,
        needs_approval=escalate,
        created_by=created_by,
        lines=[
            ReconciliationLine(
                charge_code=line.charge_code,
                quoted_amount=line.quoted_amount,
                actual_amount=line.actual_amount,
                variance=line.variance,
                match_status=ReconciliationMatchStatus(line.match_status),
                note=line.note,
            )
            for line in lines
        ],
    )
    db.add(reconciliation)
    await db.flush()
    return await get_reconciliation(db, reconciliation.id)  # type: ignore[return-value]


async def get_reconciliation(
    db: AsyncSession, reconciliation_id: UUID
) -> Reconciliation | None:
    result = await db.execute(
        select(Reconciliation)
        .where(Reconciliation.id == reconciliation_id)
        .options(*_LOAD_OPTIONS)
    )
    return result.scalar_one_or_none()


async def list_reconciliations_for_container(
    db: AsyncSession, container_id: UUID
) -> list[Reconciliation]:
    result = await db.execute(
        select(Reconciliation)
        .where(Reconciliation.container_id == container_id)
        .options(*_LOAD_OPTIONS)
        .order_by(Reconciliation.created_at.desc())
    )
    return list(result.scalars().all())


async def approve_reconciliation(
    db: AsyncSession, reconciliation: Reconciliation, approved_by: UUID
) -> Reconciliation:
    reconciliation.status = ReconciliationStatus.APPROVED
    reconciliation.approved_by = approved_by
    await db.flush()
    return await get_reconciliation(db, reconciliation.id)  # type: ignore[return-value]
