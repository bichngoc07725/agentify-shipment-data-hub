"""Export a completed reconciliation to a MISA/Fast-importable CSV — no ERP
API integration, just a file in the column shape those tools expect. See
`plan/phase_8_audit_zalo_brief.md` Part 8B.
"""

from __future__ import annotations

import csv
import io

from db.models import Reconciliation

CSV_HEADER = [
    "Mã phí",
    "Mô tả",
    "Số tiền báo giá",
    "Số tiền thực tế",
    "Chênh lệch",
    "VAT",
]


def build_reconciliation_csv(reconciliation: Reconciliation) -> bytes:
    """UTF-8 with a BOM so Excel/MISA opens Vietnamese text correctly.

    `description`/VAT aren't tracked anywhere on `ReconciliationLine` — the
    charge code is reused as the description rather than inventing data the
    system never captured; VAT is left blank for the same reason.
    """

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_HEADER)
    for line in reconciliation.lines:
        writer.writerow(
            [
                line.charge_code,
                line.charge_code,
                line.quoted_amount if line.quoted_amount is not None else "",
                line.actual_amount if line.actual_amount is not None else "",
                line.variance,
                "",
            ]
        )
    return b"\xef\xbb\xbf" + buffer.getvalue().encode("utf-8")


def build_export_filename(reconciliation: Reconciliation) -> str:
    return f"reconciliation-{reconciliation.id}.csv"
