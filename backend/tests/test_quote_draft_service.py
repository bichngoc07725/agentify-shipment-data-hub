import unittest
from decimal import Decimal

from services.quote_draft_service import (
    build_draft_from_fields,
    find_container_type,
    find_incoterm,
)


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
