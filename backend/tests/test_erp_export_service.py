import unittest
from decimal import Decimal
from types import SimpleNamespace

from services.erp_export_service import build_export_filename, build_reconciliation_csv


def make_line(**overrides):
    defaults = dict(
        charge_code="OF",
        quoted_amount=Decimal("1200.00"),
        actual_amount=Decimal("1250.00"),
        variance=Decimal("50.00"),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def make_reconciliation(**overrides):
    defaults = dict(id="abc-123", lines=[make_line()])
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class BuildReconciliationCsvTest(unittest.TestCase):
    def test_starts_with_a_utf8_bom_so_excel_reads_vietnamese_text(self) -> None:
        csv_bytes = build_reconciliation_csv(make_reconciliation())
        self.assertTrue(csv_bytes.startswith(b"\xef\xbb\xbf"))

    def test_header_matches_the_misa_fast_column_shape(self) -> None:
        csv_bytes = build_reconciliation_csv(make_reconciliation())
        text = csv_bytes.decode("utf-8-sig")
        header_line = text.splitlines()[0]
        self.assertEqual(
            header_line, "Mã phí,Mô tả,Số tiền báo giá,Số tiền thực tế,Chênh lệch,VAT"
        )

    def test_every_line_becomes_one_csv_row_with_matching_amounts(self) -> None:
        rec = make_reconciliation(
            lines=[
                make_line(charge_code="OF", quoted_amount=Decimal("1200.00"), actual_amount=Decimal("1250.00"), variance=Decimal("50.00")),
                make_line(charge_code="THC", quoted_amount=Decimal("80.00"), actual_amount=Decimal("80.00"), variance=Decimal("0")),
            ]
        )
        csv_bytes = build_reconciliation_csv(rec)
        rows = csv_bytes.decode("utf-8-sig").splitlines()

        self.assertEqual(len(rows), 3)  # header + 2 lines
        self.assertIn("OF,OF,1200.00,1250.00,50.00,", rows[1])
        self.assertIn("THC,THC,80.00,80.00,0,", rows[2])

    def test_a_missing_actual_amount_exports_as_a_blank_cell_not_none(self) -> None:
        rec = make_reconciliation(
            lines=[make_line(charge_code="DOC", actual_amount=None, variance=Decimal("-30.00"))]
        )
        csv_bytes = build_reconciliation_csv(rec)
        row = csv_bytes.decode("utf-8-sig").splitlines()[1]
        self.assertEqual(row, "DOC,DOC,1200.00,,-30.00,")


class BuildExportFilenameTest(unittest.TestCase):
    def test_filename_includes_the_reconciliation_id(self) -> None:
        filename = build_export_filename(make_reconciliation(id="abc-123"))
        self.assertEqual(filename, "reconciliation-abc-123.csv")


if __name__ == "__main__":
    unittest.main()
