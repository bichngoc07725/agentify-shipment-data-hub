import unittest
from datetime import date

from gmail_service.deterministic_extract import (
    CONFIDENCE_CHECKSUM_BAD,
    CONFIDENCE_CHECKSUM_OK,
    classify_document,
    extract_deterministic,
    find_container_numbers,
    find_dates,
    find_free_time_days,
    find_vessel_voyage,
    is_valid_container_no,
    iso6346_check_digit,
    parse_date,
)


class Iso6346Test(unittest.TestCase):
    def test_check_digit_matches_reference_number(self) -> None:
        # CSQU3054383 is the worked example in the ISO 6346 documentation.
        self.assertEqual(iso6346_check_digit("CSQU3054383"), 3)
        self.assertTrue(is_valid_container_no("CSQU3054383"))

    def test_check_digit_rejects_wrong_final_digit(self) -> None:
        self.assertFalse(is_valid_container_no("CSQU3054384"))

    def test_malformed_input_has_no_check_digit(self) -> None:
        self.assertIsNone(iso6346_check_digit("12345678901"))
        self.assertFalse(is_valid_container_no("MSCU123"))

    def test_separators_and_case_are_normalized(self) -> None:
        self.assertTrue(is_valid_container_no("csqu 3054383"))
        self.assertTrue(is_valid_container_no("CSQU-3054383"))


class ContainerNumberTest(unittest.TestCase):
    def test_valid_numbers_are_ranked_before_invalid_ones(self) -> None:
        text = "Please handle MSCU1234567 first, then CSQU3054383."

        found = find_container_numbers(text)

        self.assertEqual(
            found,
            [
                ("CSQU3054383", CONFIDENCE_CHECKSUM_OK),
                ("MSCU1234567", CONFIDENCE_CHECKSUM_BAD),
            ],
        )

    def test_invalid_checksum_is_kept_because_real_documents_have_typos(self) -> None:
        found = find_container_numbers("Container MSCU1234567")

        self.assertEqual(found, [("MSCU1234567", CONFIDENCE_CHECKSUM_BAD)])

    def test_duplicates_are_collapsed(self) -> None:
        found = find_container_numbers("MSCU1234567 / MSCU 1234567 / MSCU-1234567")

        self.assertEqual(len(found), 1)


class DateParsingTest(unittest.TestCase):
    def test_supported_formats(self) -> None:
        self.assertEqual(parse_date("2026-07-15"), date(2026, 7, 15))
        self.assertEqual(parse_date("15/07/2026"), date(2026, 7, 15))
        self.assertEqual(parse_date("15-JUL-2026"), date(2026, 7, 15))
        self.assertEqual(parse_date("15 Jul 2026"), date(2026, 7, 15))
        self.assertEqual(parse_date("Jul 15, 2026"), date(2026, 7, 15))

    def test_day_first_is_assumed_for_slash_dates(self) -> None:
        # Vietnamese documents write DD/MM/YYYY, so 05/07 is 5 July.
        self.assertEqual(parse_date("05/07/2026"), date(2026, 7, 5))

    def test_impossible_date_returns_none(self) -> None:
        self.assertIsNone(parse_date("32/07/2026"))
        self.assertIsNone(parse_date("not a date"))

    def test_labelled_dates_are_picked_up(self) -> None:
        text = "ETD: 2026-07-01\nETA 15/07/2026\nATA: 16-JUL-2026"

        self.assertEqual(
            find_dates(text),
            {"etd": "2026-07-01", "eta": "2026-07-15", "ata": "2026-07-16"},
        )


class FreeTimeTest(unittest.TestCase):
    def test_english_phrasing(self) -> None:
        self.assertEqual(find_free_time_days("Free time: 5 days from arrival"), 5)
        self.assertEqual(find_free_time_days("7 days free time granted"), 7)

    def test_vietnamese_phrasing(self) -> None:
        self.assertEqual(find_free_time_days("Free time 10 ngay"), 10)
        self.assertEqual(
            find_free_time_days("Mien phi luu container 14 ngay ke tu ngay tau cap"), 14
        )

    def test_absent_or_implausible_values_return_none(self) -> None:
        self.assertIsNone(find_free_time_days("No free time information here"))
        self.assertIsNone(find_free_time_days("Free time: 99 days"))


class VesselVoyageTest(unittest.TestCase):
    def test_combined_line_is_split_on_the_slash(self) -> None:
        self.assertEqual(
            find_vessel_voyage("Vessel / Voyage: MSC ANNA / 235W"),
            ("MSC ANNA", "235W"),
        )

    def test_vietnamese_combined_line(self) -> None:
        self.assertEqual(
            find_vessel_voyage("Tau / Chuyen: WAN HAI 517 / V12E"),
            ("WAN HAI 517", "V12E"),
        )

    def test_separate_lines_still_work(self) -> None:
        self.assertEqual(
            find_vessel_voyage("Vessel: MSC ANNA\nVoyage No: 235W"),
            ("MSC ANNA", "235W"),
        )

    def test_absent_values_return_none(self) -> None:
        self.assertEqual(find_vessel_voyage("no shipping details"), (None, None))


class ClassificationTest(unittest.TestCase):
    def test_subject_match_outranks_body_match(self) -> None:
        doc_type, confidence = classify_document(
            "Arrival Notice - MSCU1234567", "commercial invoice attached"
        )

        self.assertEqual(doc_type, "arrival_notice")
        self.assertEqual(confidence, 0.85)

    def test_body_match_has_lower_confidence(self) -> None:
        doc_type, confidence = classify_document("FW: update", "DELIVERY ORDER no 123")

        self.assertEqual(doc_type, "delivery_order")
        self.assertEqual(confidence, 0.65)

    def test_unknown_document_is_other(self) -> None:
        self.assertEqual(classify_document("Hello", "nothing relevant"), ("other", 0.0))

    def test_customs_declaration_subject_match(self) -> None:
        doc_type, confidence = classify_document(
            "To khai Hai quan (thong quan) - MSCU1234567", "so to khai 108234567890"
        )

        self.assertEqual(doc_type, "customs_declaration")
        self.assertEqual(confidence, 0.85)


class ExtractDeterministicTest(unittest.TestCase):
    def test_extracts_a_full_arrival_notice(self) -> None:
        text = (
            "ARRIVAL NOTICE\n"
            "B/L No: MEDUHC1234567\n"
            "Booking No: BKG-778899\n"
            "Container No: CSQU3054383\n"
            "Seal No: C4123088\n"
            "Vessel: MSC ANNA\n"
            "Voyage: 235W\n"
            "POL: Shanghai\n"
            "POD: Ho Chi Minh\n"
            "ETA: 15/07/2026\n"
            "Free time: 5 days\n"
        )

        result = extract_deterministic("Arrival Notice", "ops@carrier.com", text)

        self.assertEqual(result["doc_type"], "arrival_notice")
        self.assertEqual(result["identifiers"]["container_no"], ["CSQU3054383"])
        self.assertEqual(result["identifiers"]["bl_no"], "MEDUHC1234567")
        self.assertEqual(result["identifiers"]["booking_no"], "BKG-778899")
        self.assertEqual(result["identifiers"]["seal_no"], ["C4123088"])
        self.assertEqual(result["route"]["eta"], "2026-07-15")
        self.assertEqual(result["route"]["voyage"], "235W")
        self.assertEqual(result["route"]["pol"], "Shanghai")
        self.assertEqual(result["free_time_days"], 5)
        self.assertEqual(
            result["container_confidences"]["CSQU3054383"], CONFIDENCE_CHECKSUM_OK
        )

    def test_extracts_delivery_order_number(self) -> None:
        result = extract_deterministic(
            "D/O released", "ops@carrier.com", "Delivery Order No: DO-2026-4471"
        )

        self.assertEqual(result["identifiers"]["do_no"], "DO-2026-4471")

    def test_hyphen_is_not_treated_as_a_label_separator(self) -> None:
        # `DO-2026-4471` must survive intact rather than being cut to `2026-4471`.
        result = extract_deterministic("", "", "D/O so DO-2026-4471")

        self.assertEqual(result["identifiers"]["do_no"], "DO-2026-4471")

    def test_stacked_punctuation_after_a_label(self) -> None:
        result = extract_deterministic("", "", "PO #: PO-4471-A")

        self.assertEqual(result["identifiers"]["po_no"], "PO-4471-A")

    def test_label_and_value_on_separate_lines(self) -> None:
        result = extract_deterministic("", "", "Booking No:\nBKG-778899")

        self.assertEqual(result["identifiers"]["booking_no"], "BKG-778899")

    def test_a_label_followed_by_prose_yields_no_identifier(self) -> None:
        # An identifier must contain a digit, so ordinary sentences are ignored.
        for text in (
            "Booking confirmation attached",
            "Please find the delivery order in the mail",
            "Invoice will follow shortly",
        ):
            identifiers = extract_deterministic("", "", text)["identifiers"]
            scalars = {
                key: value
                for key, value in identifiers.items()
                if value and key not in {"container_no", "seal_no"}
            }
            self.assertEqual(scalars, {}, f"false identifier from {text!r}")

    def test_extracts_declaration_no(self) -> None:
        result = extract_deterministic(
            "To khai Hai quan (thong quan) - MSCU1234567",
            "docs@forwarder-demo.com",
            "So to khai: 108234567890\nSo hieu container: MSCU1234567",
        )

        self.assertEqual(result["doc_type"], "customs_declaration")
        self.assertEqual(result["identifiers"]["declaration_no"], "108234567890")

    def test_bare_to_khai_in_title_does_not_yield_a_declaration_no(self) -> None:
        # The document's own title ("TO KHAI HANG HOA NHAP KHAU") contains
        # "to khai" constantly; only the full "so to khai" label should count.
        result = extract_deterministic(
            "",
            "",
            "HAI QUAN VIET NAM\nTO KHAI HANG HOA NHAP KHAU (THONG QUAN)\n"
            "Ngay dang ky: 10/07/2026",
        )

        self.assertIsNone(result["identifiers"].get("declaration_no"))

    def test_empty_input_yields_empty_result_not_an_error(self) -> None:
        result = extract_deterministic("", "", "")

        self.assertEqual(result["doc_type"], "other")
        self.assertEqual(result["identifiers"]["container_no"], [])
        self.assertEqual(result["route"], {})


if __name__ == "__main__":
    unittest.main()
