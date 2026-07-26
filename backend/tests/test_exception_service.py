import unittest
from datetime import UTC, date, datetime, timedelta

from db.models import Container
from services.exception_service import (
    DEFAULT_FREE_TIME_DAYS,
    SEVERITY_CRITICAL,
    SEVERITY_WARNING,
    build_risk_profile,
    canonical_document_types,
    compute_free_time_deadline,
    detect_exceptions,
    infer_direction,
    missing_documents,
)

TODAY = date(2026, 7, 20)


def make_container(**overrides) -> Container:
    defaults = {
        "container_no": "CSQU3054383",
        "first_seen_at": datetime(2026, 7, 1, tzinfo=UTC),
        "last_seen_at": datetime(2026, 7, 18, tzinfo=UTC),
    }
    return Container(**{**defaults, **overrides})


def codes(exceptions) -> set[str]:
    return {exception.code for exception in exceptions}


class FreeTimeDeadlineTest(unittest.TestCase):
    def test_deadline_counts_from_actual_arrival(self) -> None:
        container = make_container(ata=date(2026, 7, 15), free_time_days=5)

        deadline, assumed = compute_free_time_deadline(container)

        self.assertEqual(deadline, date(2026, 7, 20))
        self.assertFalse(assumed)

    def test_falls_back_to_eta_when_arrival_is_not_confirmed(self) -> None:
        container = make_container(eta=date(2026, 7, 18), free_time_days=3)

        deadline, assumed = compute_free_time_deadline(container)

        self.assertEqual(deadline, date(2026, 7, 21))
        self.assertFalse(assumed)

    def test_missing_free_time_is_assumed_and_flagged(self) -> None:
        container = make_container(ata=date(2026, 7, 15))

        deadline, assumed = compute_free_time_deadline(container)

        self.assertEqual(deadline, date(2026, 7, 15) + timedelta(days=DEFAULT_FREE_TIME_DAYS))
        self.assertTrue(assumed)

    def test_no_arrival_information_means_no_deadline(self) -> None:
        deadline, assumed = compute_free_time_deadline(make_container())

        self.assertIsNone(deadline)
        self.assertFalse(assumed)


class FreeTimeExceptionTest(unittest.TestCase):
    def test_fires_when_deadline_is_close_and_no_delivery_order(self) -> None:
        container = make_container(ata=date(2026, 7, 18), free_time_days=5)

        exceptions = detect_exceptions(container, set(), [], None, today=TODAY)

        found = next(e for e in exceptions if e.code == "free_time_expiring")
        self.assertEqual(found.severity, SEVERITY_CRITICAL)
        self.assertEqual(found.due_date, date(2026, 7, 23))
        self.assertEqual(found.days_remaining, 3)
        self.assertIn("Free time: 5 ngày", found.evidence)

    def test_reports_overdue_when_the_deadline_has_passed(self) -> None:
        container = make_container(ata=date(2026, 7, 10), free_time_days=5)

        exceptions = detect_exceptions(container, set(), [], None, today=TODAY)

        found = next(e for e in exceptions if e.code == "free_time_expiring")
        self.assertEqual(found.days_remaining, -5)
        self.assertIn("quá hạn", found.title + found.detail)

    def test_silent_once_a_delivery_order_document_exists(self) -> None:
        container = make_container(ata=date(2026, 7, 18), free_time_days=5)

        exceptions = detect_exceptions(
            container, {"delivery_order"}, [], None, today=TODAY
        )

        self.assertNotIn("free_time_expiring", codes(exceptions))

    def test_silent_once_a_delivery_order_number_is_known(self) -> None:
        container = make_container(
            ata=date(2026, 7, 18), free_time_days=5, do_no="DO-4471"
        )

        exceptions = detect_exceptions(container, set(), [], None, today=TODAY)

        self.assertNotIn("free_time_expiring", codes(exceptions))

    def test_silent_while_the_deadline_is_still_far_away(self) -> None:
        container = make_container(ata=date(2026, 7, 18), free_time_days=14)

        exceptions = detect_exceptions(container, set(), [], None, today=TODAY)

        self.assertNotIn("free_time_expiring", codes(exceptions))

    def test_says_so_when_the_free_time_value_was_assumed(self) -> None:
        container = make_container(ata=date(2026, 7, 18))

        exceptions = detect_exceptions(container, set(), [], None, today=TODAY)

        found = next(e for e in exceptions if e.code == "free_time_expiring")
        self.assertIn("tạm tính", found.detail)


class ArrivedWithoutDeliveryOrderTest(unittest.TestCase):
    def test_fires_after_arrival_with_no_delivery_order(self) -> None:
        container = make_container(ata=date(2026, 7, 17))

        exceptions = detect_exceptions(container, set(), [], None, today=TODAY)

        found = next(e for e in exceptions if e.code == "arrived_no_do")
        self.assertEqual(found.severity, SEVERITY_CRITICAL)
        self.assertIn("3 ngày trước", found.detail)

    def test_does_not_fire_on_an_estimated_arrival_alone(self) -> None:
        container = make_container(eta=date(2026, 7, 17))

        exceptions = detect_exceptions(container, set(), [], None, today=TODAY)

        self.assertNotIn("arrived_no_do", codes(exceptions))


class EtaChangeTest(unittest.TestCase):
    def test_fires_when_the_two_newest_eta_values_differ(self) -> None:
        history = [
            (date(2026, 7, 22), "arrival_notice_v2.pdf"),
            (date(2026, 7, 18), "arrival_notice_v1.pdf"),
        ]

        exceptions = detect_exceptions(make_container(), set(), history, None, today=TODAY)

        found = next(e for e in exceptions if e.code == "eta_changed")
        self.assertEqual(found.severity, SEVERITY_WARNING)
        self.assertIn("+4 ngày", found.detail)
        self.assertIn("ETA mới: 2026-07-22 — arrival_notice_v2.pdf", found.evidence)

    def test_silent_with_a_single_known_eta(self) -> None:
        history = [(date(2026, 7, 22), "arrival_notice.pdf")]

        exceptions = detect_exceptions(make_container(), set(), history, None, today=TODAY)

        self.assertNotIn("eta_changed", codes(exceptions))


class DocumentChecklistTest(unittest.TestCase):
    def test_import_checklist_applies_once_arrival_data_exists(self) -> None:
        self.assertEqual(infer_direction(make_container(ata=date(2026, 7, 15))), "import")
        self.assertEqual(infer_direction(make_container(do_no="DO-1")), "import")

    def test_arrival_notice_alone_proves_an_inbound_shipment(self) -> None:
        # A carrier's arrival notice often quotes only an ETA, so waiting for an
        # ATA would misfile a clearly inbound shipment as an export.
        self.assertEqual(
            infer_direction(make_container(eta=date(2026, 7, 18)), {"arrival_notice"}),
            "import",
        )
        self.assertEqual(
            infer_direction(make_container(), {"delivery_order"}), "import"
        )

    def test_export_checklist_is_the_default(self) -> None:
        self.assertEqual(infer_direction(make_container()), "export")
        self.assertEqual(
            infer_direction(make_container(), {"booking_confirmation"}), "export"
        )

    def test_missing_documents_are_listed(self) -> None:
        missing = missing_documents("import", {"arrival_notice", "invoice"})

        self.assertEqual(missing, ["bill_of_lading", "delivery_order"])

    def test_document_name_variants_count_towards_the_checklist(self) -> None:
        # A draft B/L is the bill of lading at draft stage, and the extractor
        # also emits `commercial_invoice` and `booking_note`.
        self.assertEqual(
            canonical_document_types({"draft_bl", "commercial_invoice", "booking_note"}),
            {"bill_of_lading", "invoice", "booking_confirmation"},
        )
        self.assertEqual(missing_documents("export", {"draft_bl"}),
                         ["booking_confirmation", "invoice", "packing_list"])

    def test_canonical_types_are_idempotent(self) -> None:
        already_canonical = {"bill_of_lading", "invoice"}

        self.assertEqual(canonical_document_types(already_canonical), already_canonical)

    def test_a_draft_bl_counts_as_present_in_the_profile(self) -> None:
        profile = build_risk_profile(
            make_container(), {"draft_bl", "shipping_instruction"}, [], None, today=TODAY
        )

        self.assertIn("bill_of_lading", profile.documents_present)
        self.assertNotIn("bill_of_lading", profile.documents_missing)

    def test_exception_names_the_missing_documents(self) -> None:
        container = make_container(ata=date(2026, 7, 15), free_time_days=30)

        exceptions = detect_exceptions(
            container, {"arrival_notice"}, [], None, today=TODAY
        )

        found = next(e for e in exceptions if e.code == "missing_documents")
        self.assertIn("Delivery Order (D/O)", found.detail)
        self.assertIn("Bill of Lading", found.detail)


class MentionedVersusOnFileTest(unittest.TestCase):
    """A message referring to a document is not the document."""

    def test_a_mention_does_not_satisfy_the_checklist(self) -> None:
        profile = build_risk_profile(
            make_container(ata=date(2026, 7, 15), free_time_days=30),
            {"arrival_notice"},
            [],
            None,
            today=TODAY,
            documents_mentioned={"delivery_order"},
        )

        self.assertNotIn("delivery_order", profile.documents_present)
        self.assertIn("delivery_order", profile.documents_missing)
        self.assertIn("delivery_order", profile.documents_mentioned)

    def test_completeness_counts_files_only(self) -> None:
        profile = build_risk_profile(
            make_container(ata=date(2026, 7, 15), free_time_days=30),
            {"arrival_notice"},
            [],
            None,
            today=TODAY,
            documents_mentioned={"delivery_order", "invoice"},
        )

        # 1 of 4 import documents on file, regardless of what was mentioned.
        self.assertEqual(profile.completeness, 0.25)

    def test_the_exception_separates_mentioned_from_unaccounted(self) -> None:
        exceptions = detect_exceptions(
            make_container(ata=date(2026, 7, 15), free_time_days=30),
            {"arrival_notice"},
            [],
            None,
            today=TODAY,
            documents_mentioned={"delivery_order"},
        )

        found = next(e for e in exceptions if e.code == "missing_documents")
        self.assertIn("Đã có thông tin nhưng chưa có file: Delivery Order (D/O)", found.detail)
        self.assertIn("Chưa thấy trong dữ liệu Agentify: Bill of Lading, Invoice", found.detail)
        self.assertIn("Đã có file: Arrival Notice", found.evidence)

    def test_a_do_number_still_silences_the_free_time_alarm(self) -> None:
        # The point of the split: the checklist gets stricter, but Ops does not
        # get a false cost alarm when a Zalo message already confirmed the D/O.
        container = make_container(
            ata=date(2026, 7, 18), free_time_days=5, do_no="DO-2026-4471"
        )

        exceptions = detect_exceptions(
            container, set(), [], None, today=TODAY, documents_mentioned={"delivery_order"}
        )

        self.assertNotIn("free_time_expiring", codes(exceptions))

    def test_a_bare_mention_without_a_number_does_not_silence_it(self) -> None:
        container = make_container(ata=date(2026, 7, 18), free_time_days=5)

        exceptions = detect_exceptions(
            container, set(), [], None, today=TODAY, documents_mentioned={"delivery_order"}
        )

        self.assertIn("free_time_expiring", codes(exceptions))

    def test_a_mention_still_counts_as_direction_evidence(self) -> None:
        profile = build_risk_profile(
            make_container(), set(), [], None, today=TODAY,
            documents_mentioned={"arrival_notice"},
        )

        self.assertEqual(profile.direction, "import")

    def test_a_mentioned_charge_document_does_not_raise_reconciliation(self) -> None:
        profile = build_risk_profile(
            make_container(ata=date(2026, 7, 15), free_time_days=30),
            {"arrival_notice"},
            [],
            None,
            today=TODAY,
            documents_mentioned={"debit_note"},
        )

        self.assertNotIn("unlinked_charges", codes(profile.exceptions))


class StaleShipmentTest(unittest.TestCase):
    def test_fires_after_a_week_of_silence(self) -> None:
        last_source = datetime(2026, 7, 10, tzinfo=UTC)

        exceptions = detect_exceptions(
            make_container(), set(), [], last_source, today=TODAY
        )

        found = next(e for e in exceptions if e.code == "stale_no_update")
        self.assertIn("10 ngày", found.title)

    def test_silent_for_a_recently_updated_shipment(self) -> None:
        last_source = datetime(2026, 7, 18, tzinfo=UTC)

        exceptions = detect_exceptions(
            make_container(), set(), [], last_source, today=TODAY
        )

        self.assertNotIn("stale_no_update", codes(exceptions))


class SeverityOrderingTest(unittest.TestCase):
    def test_critical_exceptions_are_listed_first(self) -> None:
        container = make_container(ata=date(2026, 7, 12), free_time_days=3)

        exceptions = detect_exceptions(
            container, set(), [], datetime(2026, 7, 1, tzinfo=UTC), today=TODAY
        )

        severities = [exception.severity for exception in exceptions]
        self.assertEqual(severities, sorted(severities, key={"critical": 0, "warning": 1, "info": 2}.get))
        self.assertEqual(severities[0], SEVERITY_CRITICAL)


class RiskProfileTest(unittest.TestCase):
    def test_completeness_reflects_documents_on_file(self) -> None:
        container = make_container(ata=date(2026, 7, 15), free_time_days=30)

        profile = build_risk_profile(
            container,
            {"arrival_notice", "bill_of_lading"},
            [],
            datetime(2026, 7, 18, tzinfo=UTC),
            today=TODAY,
        )

        self.assertEqual(profile.direction, "import")
        self.assertEqual(profile.completeness, 0.5)
        self.assertEqual(
            profile.documents_present, ["arrival_notice", "bill_of_lading"]
        )
        self.assertEqual(profile.documents_missing, ["delivery_order", "invoice"])
        self.assertEqual(profile.free_time_expires_on, date(2026, 8, 14))
        self.assertFalse(profile.free_time_is_assumed)

    def test_a_charge_document_raises_the_reconciliation_flag(self) -> None:
        container = make_container(ata=date(2026, 7, 15), free_time_days=30)

        profile = build_risk_profile(
            container,
            {"arrival_notice", "bill_of_lading", "delivery_order", "debit_note"},
            [],
            datetime(2026, 7, 18, tzinfo=UTC),
            today=TODAY,
        )

        self.assertIn("unlinked_charges", codes(profile.exceptions))


if __name__ == "__main__":
    unittest.main()
