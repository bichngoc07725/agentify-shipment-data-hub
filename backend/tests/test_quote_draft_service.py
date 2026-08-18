import unittest
from decimal import Decimal

from services.quote_draft_service import (
    build_draft_from_fields,
    find_cargo_ready_date,
    find_commodity,
    find_container_type,
    find_customer_name,
    find_incoterm,
    find_route,
)

# Đúng nguyên văn thân thư hỏi giá trong corpus demo (`roundtrip-rfq-hpn`).
# Mail hỏi giá viết tuyến bằng câu tiếng Việt, không có nhãn "POL:" nào —
# nếu bộ đọc không bám được vào đây thì Bước 1 lẫn Bước 2 đều ra form trống.
RFQ_BODY = """Chào Agentify,

Bên mình có đơn hàng đi Nhật cần báo giá cước.
Hàng: Áo sơ mi cotton, đóng 2 x 40HC.
Lấy hàng tại Hai Phong, giao Yokohama. Hàng sẵn kho ngày 2026-08-20.
Điều kiện FOB, PO PO-JP-88315.

Nhờ Agentify báo giá sớm giúp, khách Nhật đang giục chốt lịch tàu.

Trân trọng,
Cong ty CP Det May Thanh Long"""


class ContainerTypeTest(unittest.TestCase):
    def test_reads_quantity_and_type_together(self) -> None:
        self.assertEqual(find_container_type("cần 2 x 40HC hàng vải"), ("40HC", 2))

    def test_type_alone_leaves_quantity_unknown(self) -> None:
        # Không có số lượng thì để trống, KHÔNG mặc định là 1 — một cont và
        # mười cont là hai mức giá hoàn toàn khác nhau.
        self.assertEqual(find_container_type("book giúp cont 20GP"), ("20GP", None))

    def test_is_case_insensitive_and_normalizes_upward(self) -> None:
        self.assertEqual(find_container_type("1x40hq"), ("40HQ", 1))

    def test_no_match_returns_nothing(self) -> None:
        self.assertEqual(find_container_type("hàng lẻ đi Singapore"), (None, None))

    def test_reefer_type_is_recognized(self) -> None:
        self.assertEqual(find_container_type("3 x 40RF hàng đông lạnh"), ("40RF", 3))


class IncotermTest(unittest.TestCase):
    def test_finds_incoterm_anywhere_in_the_text(self) -> None:
        self.assertEqual(find_incoterm("giá FOB Hai Phong nhé"), "FOB")

    def test_is_case_insensitive(self) -> None:
        self.assertEqual(find_incoterm("điều kiện cif"), "CIF")

    def test_returns_none_when_absent(self) -> None:
        self.assertIsNone(find_incoterm("báo giá giúp mình tuyến này"))

    def test_does_not_match_a_word_that_merely_contains_a_term(self) -> None:
        self.assertIsNone(find_incoterm("PACIFIC line"))


class RouteFromProseTest(unittest.TestCase):
    def test_reads_pickup_and_delivery_sentence(self) -> None:
        self.assertEqual(
            find_route("Lấy hàng tại Hai Phong, giao Yokohama."),
            ("Hai Phong", "Yokohama"),
        )

    def test_reads_from_to_sentence(self) -> None:
        self.assertEqual(
            find_route("cần cont đi từ Cat Lai đến Singapore trong tuần này"),
            ("Cat Lai", "Singapore"),
        )

    def test_reads_dash_form_in_a_subject_line(self) -> None:
        self.assertEqual(
            find_route("Cần báo giá Hai Phong - Yokohama cho lô áo sơ mi"),
            ("Hai Phong", "Yokohama"),
        )

    def test_same_port_on_both_ends_is_rejected(self) -> None:
        # Khớp kiểu đó gần như chắc chắn là bắt nhầm chữ, và một tuyến
        # Hai Phong → Hai Phong thì vô nghĩa với người đọc.
        self.assertEqual(find_route("chuyển hàng tại Hai Phong - Hai Phong"), (None, None))

    def test_no_route_returns_nothing(self) -> None:
        self.assertEqual(find_route("bên mình cần báo giá gấp"), (None, None))


class CargoReadyDateTest(unittest.TestCase):
    def test_reads_iso_date(self) -> None:
        self.assertEqual(find_cargo_ready_date("Hàng sẵn kho ngày 2026-08-20."), "2026-08-20")

    def test_day_first_slash_date_is_not_read_as_month_first(self) -> None:
        # `05/07/2026` trên chứng từ Việt Nam là 5 tháng 7, không phải 7 tháng 5.
        self.assertEqual(find_cargo_ready_date("Hàng sẵn ngày 05/07/2026"), "2026-07-05")

    def test_invalid_date_is_dropped(self) -> None:
        self.assertIsNone(find_cargo_ready_date("Hàng sẵn ngày 32/13/2026"))

    def test_absent_returns_nothing(self) -> None:
        self.assertIsNone(find_cargo_ready_date("hàng đóng xong tuần sau"))


class CustomerAndCommodityTest(unittest.TestCase):
    def test_reads_company_from_signature_line(self) -> None:
        self.assertEqual(
            find_customer_name(RFQ_BODY), "Cong ty CP Det May Thanh Long"
        )

    def test_reads_commodity_after_label(self) -> None:
        self.assertEqual(find_commodity(RFQ_BODY), "Áo sơ mi cotton")


class BuildDraftFromRfqEmailTest(unittest.TestCase):
    """Không có LLM thì `extract_fields` trả rỗng cho mail hỏi giá — đây là
    trạng thái mặc định khi hết quota, và hướng dẫn kiểm thử Bước 1–4 hứa là
    vẫn chạy được."""

    def test_fills_the_quote_form_with_rules_only(self) -> None:
        draft = build_draft_from_fields({"route": {}, "cargo": {}}, RFQ_BODY)

        self.assertEqual(draft["pol"], "Hai Phong")
        self.assertEqual(draft["pod"], "Yokohama")
        self.assertEqual(draft["customer_name"], "Cong ty CP Det May Thanh Long")
        self.assertEqual(draft["commodity"], "Áo sơ mi cotton")
        self.assertEqual(draft["container_type"], "40HC")
        self.assertEqual(draft["container_qty"], 2)
        self.assertEqual(draft["cargo_ready_date"], "2026-08-20")
        self.assertEqual(draft["incoterm"], "FOB")

    def test_extraction_wins_over_the_regex_fallback(self) -> None:
        # Có LLM thì bản đọc của nó tốt hơn regex; regex chỉ vá chỗ trống.
        draft = build_draft_from_fields(
            {"route": {"pol": "Haiphong Port", "pod": "Yokohama Port"}, "cargo": {}},
            RFQ_BODY,
        )

        self.assertEqual(draft["pol"], "Haiphong Port")
        self.assertEqual(draft["pod"], "Yokohama Port")


class BuildDraftTest(unittest.TestCase):
    def test_maps_route_and_cargo_onto_quote_fields(self) -> None:
        fields = {
            "customer_name": "Công ty TNHH Minh Phát",
            "route": {"pol": "Cat Lai", "pod": "Singapore"},
            "cargo": {"description": "Cà phê nhân", "gross_weight_kg": 18500},
            "payment_term": "TT 30 days",
        }

        draft = build_draft_from_fields(fields, "cần 1 x 20GP, giá FOB")

        self.assertEqual(draft["customer_name"], "Công ty TNHH Minh Phát")
        self.assertEqual(draft["pol"], "Cat Lai")
        self.assertEqual(draft["pod"], "Singapore")
        self.assertEqual(draft["commodity"], "Cà phê nhân")
        self.assertEqual(draft["container_type"], "20GP")
        self.assertEqual(draft["container_qty"], 1)
        self.assertEqual(draft["gross_weight_kg"], Decimal("18500"))
        self.assertEqual(draft["incoterm"], "FOB")
        self.assertEqual(draft["payment_term"], "TT 30 days")

    def test_missing_values_are_left_out_entirely(self) -> None:
        # Ô vắng mặt khác hẳn ô bằng rỗng: giao diện phải để người dùng tự điền,
        # không hiện một giá trị trông như đã đọc được.
        draft = build_draft_from_fields({"route": {}, "cargo": {}}, "hỏi giá")

        self.assertEqual(draft, {})

    def test_shipper_is_used_when_customer_name_is_absent(self) -> None:
        draft = build_draft_from_fields(
            {"shipper": "Tay Nguyen Coffee", "route": {}, "cargo": {}}, ""
        )

        self.assertEqual(draft["customer_name"], "Tay Nguyen Coffee")

    def test_etd_is_not_borrowed_as_cargo_ready_date(self) -> None:
        # Ngày tàu chạy và ngày hàng sẵn ở kho là hai mốc khác nhau; suy cái
        # này ra cái kia tạo một ngày trông như thật mà không ai kiểm.
        draft = build_draft_from_fields(
            {"route": {"etd": "2026-07-01"}, "cargo": {}}, ""
        )

        self.assertNotIn("cargo_ready_date", draft)

    def test_unparseable_weight_is_dropped_not_guessed(self) -> None:
        draft = build_draft_from_fields(
            {"route": {}, "cargo": {"gross_weight_kg": "khoảng 18 tấn"}}, ""
        )

        self.assertNotIn("gross_weight_kg", draft)


if __name__ == "__main__":
    unittest.main()
