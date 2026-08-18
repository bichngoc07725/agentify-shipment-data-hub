import unittest
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from db.models import CustomsDeclarationType
from services.customs_worksheet_service import (
    MISSING_PREFIX,
    build_sections,
    render_docx,
)


def make_quote(**overrides):
    defaults = dict(
        customer_name="Cong ty CP Det May Thanh Long",
        commodity="Áo sơ mi cotton",
        pol="Hai Phong",
        pod="Yokohama",
        incoterm="FOB",
        currency="USD",
        payment_term="TT 30 days",
        container_type="40HC",
        container_qty=2,
        gross_weight_kg=Decimal("18500"),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def make_booking(**overrides):
    defaults = dict(
        booking_no="ONE-BKG-260805",
        carrier="Ocean Network Express",
        vessel="ONE COMMITMENT",
        voyage="145E",
        pol="Hai Phong",
        pod="Yokohama",
        etd=date(2026, 8, 20),
        eta=date(2026, 8, 29),
        container_type="40HC",
        container_qty=2,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def flat(sections):
    return {f.label: f for s in sections for f in s.fields}


class WorksheetSectionsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.container = SimpleNamespace(id="x", container_no="ONEU7041287")

    def test_fields_are_filled_from_quote_and_booking(self) -> None:
        fields = flat(
            build_sections(self.container, make_quote(), make_booking(), None, {})
        )

        self.assertEqual(fields["Tên tàu"].value, "ONE COMMITMENT")
        self.assertEqual(fields["Số chuyến"].value, "145E")
        self.assertEqual(fields["Cảng xếp hàng (POL)"].value, "Hai Phong")
        self.assertEqual(fields["Mô tả hàng hoá"].value, "Áo sơ mi cotton")
        self.assertEqual(fields["Số container"].value, "ONEU7041287")
        self.assertEqual(fields["Điều kiện giao hàng (Incoterm)"].value, "FOB")

    def test_a_missing_field_says_so_and_names_where_to_look(self) -> None:
        # Ô trống trên tờ in trông y hệt ô đã kiểm và đúng là rỗng; nhầm hai thứ
        # đó ở khâu khai hải quan dẫn tới tờ khai sai.
        fields = flat(build_sections(self.container, None, None, None, {}))

        origin = fields["Xuất xứ"]
        self.assertTrue(origin.is_missing)
        self.assertIn(MISSING_PREFIX, origin.display)
        self.assertIn("C/O", origin.display)

    def test_invoice_total_is_never_taken_from_the_quote_total(self) -> None:
        # Tổng báo giá là tiền CƯỚC bán cho khách, không phải trị giá lô hàng.
        # Điền nhầm vào tờ khai là khai sai trị giá.
        fields = flat(
            build_sections(self.container, make_quote(), make_booking(), None, {})
        )

        total = fields["Tổng trị giá hoá đơn"]
        self.assertTrue(total.is_missing)
        self.assertIn("KHÔNG dùng tổng báo giá", total.display)

    def test_facts_fill_the_paper_trail_fields(self) -> None:
        facts = {"bl_no": "ONEYHPH260805", "seal_no": "SL-77120", "invoice_no": "INV-TL-0815"}

        fields = flat(build_sections(self.container, None, None, None, facts))

        self.assertEqual(fields["Số vận đơn (B/L)"].value, "ONEYHPH260805")
        self.assertEqual(fields["Số seal"].value, "SL-77120")
        self.assertEqual(fields["Số hoá đơn thương mại"].value, "INV-TL-0815")

    def test_declaration_hs_code_wins_over_the_extracted_one(self) -> None:
        # Mã HS trên tờ khai là mã người khai đã chốt; mã bóc từ hoá đơn chỉ là
        # gợi ý và có thể sai biểu thuế.
        declaration = SimpleNamespace(
            declaration_no="105892374610",
            declaration_type=CustomsDeclarationType.EXPORT,
            hs_code="6205.20.00",
        )

        fields = flat(
            build_sections(self.container, None, None, declaration, {"hs_code": "9999.99.99"})
        )

        self.assertEqual(fields["Mã HS"].value, "6205.20.00")

    def test_booking_values_win_over_quote_values(self) -> None:
        # Báo giá là dự kiến, đặt chỗ là đã chốt với hãng tàu.
        fields = flat(
            build_sections(
                self.container,
                make_quote(pol="Cat Lai"),
                make_booking(pol="Hai Phong"),
                None,
                {},
            )
        )

        self.assertEqual(fields["Cảng xếp hàng (POL)"].value, "Hai Phong")

    def test_container_count_and_type_are_combined(self) -> None:
        fields = flat(
            build_sections(self.container, make_quote(), make_booking(), None, {})
        )

        self.assertEqual(fields["Loại & số lượng container"].value, "2 x 40HC")


class RenderDocxTest(unittest.TestCase):
    def test_produces_a_real_docx_file(self) -> None:
        sections = build_sections(
            SimpleNamespace(id="x", container_no="ONEU7041287"),
            make_quote(),
            make_booking(),
            None,
            {},
        )

        content = render_docx("ONEU7041287", sections)

        # .docx là zip; kiểm chữ ký để chắc đây là file mở được, không phải
        # một chuỗi rỗng lọt qua.
        self.assertTrue(content.startswith(b"PK"))
        self.assertGreater(len(content), 5000)

    def test_missing_count_is_reported_in_the_document(self) -> None:
        from docx import Document
        from io import BytesIO

        sections = build_sections(
            SimpleNamespace(id="x", container_no="ONEU7041287"), None, None, None, {}
        )
        document = Document(BytesIO(render_docx("ONEU7041287", sections)))
        text = "\n".join(p.text for p in document.paragraphs)

        self.assertIn("ô cần tự bổ sung", text)


if __name__ == "__main__":
    unittest.main()
