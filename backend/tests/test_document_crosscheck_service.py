import unittest
from decimal import Decimal

from services.document_crosscheck_service import (
    find_mismatches,
    parse_number,
    values_differ,
)


class ParseNumberTest(unittest.TestCase):
    def test_reads_a_plain_number(self) -> None:
        self.assertEqual(parse_number("940"), 940)

    def test_ignores_the_unit_written_after_it(self) -> None:
        # Chứng từ ghi số kiện đủ kiểu: "940 CTNS", "940 cartons".
        self.assertEqual(parse_number("940 CTNS"), 940)

    def test_strips_thousand_separators(self) -> None:
        self.assertEqual(parse_number("1,020"), 1020)

    def test_reads_a_decimal(self) -> None:
        self.assertEqual(parse_number("18500.40"), Decimal("18500.40"))

    def test_text_without_a_number_returns_nothing(self) -> None:
        self.assertIsNone(parse_number("chưa có"))


class ValuesDifferTest(unittest.TestCase):
    def test_same_number_written_differently_is_not_a_mismatch(self) -> None:
        self.assertFalse(values_differ("940", "940 CTNS"))
        self.assertFalse(values_differ("1,020", "1020"))

    def test_rounding_within_tolerance_is_not_a_mismatch(self) -> None:
        # Chứng từ hay làm tròn khác nhau; báo lệch giả nhiều lần thì người dùng
        # tắt luôn cảnh báo, và lúc đó lệch thật cũng trôi qua.
        self.assertFalse(values_differ("18500", "18500.4"))

    def test_a_real_difference_is_caught(self) -> None:
        self.assertTrue(values_differ("940", "904"))

    def test_identifiers_are_compared_as_text_not_numbers(self) -> None:
        # "INV-TL-0815" đem so kiểu số thì bộ tách số đọc ra "-815", và hai bản
        # ghi giống hệt nhau bị báo là vênh.
        self.assertFalse(values_differ("INV-TL-0815", "inv tl 0815", numeric=False))
        self.assertTrue(values_differ("INV-TL-0815", "INV-TL-0816", numeric=False))

    def test_the_same_identifier_across_documents_is_not_flagged(self) -> None:
        self.assertEqual(
            find_mismatches(
                {"invoice_no": {"invoice": "INV-TL-0815", "packing_list": "INV TL 0815"}}
            ),
            [],
        )


class FindMismatchesTest(unittest.TestCase):
    def test_packages_differing_between_invoice_and_packing_list(self) -> None:
        mismatches = find_mismatches(
            {"packages": {"invoice": "940 CTNS", "packing_list": "904 CTNS"}}
        )

        self.assertEqual(len(mismatches), 1)
        self.assertEqual(mismatches[0].field_name, "packages")
        self.assertIn("940", mismatches[0].describe())
        self.assertIn("904", mismatches[0].describe())
        self.assertIn("Số kiện", mismatches[0].describe())

    def test_matching_values_produce_nothing(self) -> None:
        self.assertEqual(
            find_mismatches({"packages": {"invoice": "940", "packing_list": "940"}}), []
        )

    def test_a_single_document_is_not_a_mismatch(self) -> None:
        # Chưa có gì để đối chiếu thì im lặng, không phải lỗi.
        self.assertEqual(find_mismatches({"packages": {"invoice": "940"}}), [])

    def test_documents_outside_the_compared_set_are_ignored(self) -> None:
        # Booking confirmation không phải nguồn khai báo số kiện.
        self.assertEqual(
            find_mismatches(
                {"packages": {"invoice": "940", "booking_confirmation": "904"}}
            ),
            [],
        )

    def test_several_fields_can_mismatch_at_once(self) -> None:
        mismatches = find_mismatches(
            {
                "packages": {"invoice": "940", "packing_list": "904"},
                "gross_weight_kg": {"invoice": "18500", "packing_list": "17100"},
            }
        )

        self.assertEqual({m.field_name for m in mismatches}, {"packages", "gross_weight_kg"})

    def test_three_documents_flag_when_any_pair_differs(self) -> None:
        mismatches = find_mismatches(
            {
                "packages": {
                    "invoice": "940",
                    "packing_list": "940",
                    "bill_of_lading": "904",
                }
            }
        )

        self.assertEqual(len(mismatches), 1)
        self.assertEqual(len(mismatches[0].values_by_document), 3)

    def test_empty_values_are_not_compared(self) -> None:
        self.assertEqual(
            find_mismatches({"packages": {"invoice": "940", "packing_list": ""}}), []
        )


if __name__ == "__main__":
    unittest.main()
