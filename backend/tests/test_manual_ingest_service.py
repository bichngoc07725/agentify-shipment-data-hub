import unittest
from datetime import UTC, datetime
from unittest.mock import patch

from api.models import ManualIngestRequest
from gmail_service import field_extract
from services.manual_ingest_service import (
    _subject_from,
    build_facts,
    container_numbers_in,
    extract_from_content,
)

ZALO_MESSAGE = (
    "Ops: Xe 51F-12345 lay cont CSQU3054383 tai Cat Lai, cutoff 14h chieu nay.\n"
    "Tai xe B: Em nhan. Da co D/O so DO-2026-4471 chua anh?\n"
    "Ops: Co roi, free time 7 ngay ke tu ngay tau cap."
)


def make_request(**overrides) -> ManualIngestRequest:
    defaults = {
        "channel": "zalo",
        "content": ZALO_MESSAGE,
        "source_label": "Group Dieu xe Cat Lai",
        "sender": "Ops - Nguyen Van A",
    }
    return ManualIngestRequest(**{**defaults, **overrides})


class SubjectTest(unittest.TestCase):
    def test_subject_combines_source_label_and_first_line(self) -> None:
        subject = _subject_from("Line one\nLine two", "Group Dieu xe", "zalo")

        self.assertEqual(subject, "Group Dieu xe: Line one")

    def test_subject_falls_back_to_the_channel_name(self) -> None:
        self.assertEqual(_subject_from("", None, "zalo"), "Zalo")

    def test_leading_blank_lines_are_skipped(self) -> None:
        self.assertEqual(_subject_from("\n\n  Real line", None, "note"), "Ghi chú nội bộ: Real line")

    def test_subject_is_truncated(self) -> None:
        subject = _subject_from("x" * 500, None, "zalo")

        self.assertLessEqual(len(subject), 160)


class ExtractionTest(unittest.TestCase):
    def test_rules_alone_read_a_zalo_dispatch_message(self) -> None:
        # No LLM configured: a pasted dispatch message must still yield the
        # fields the exception engine needs.
        with patch.object(field_extract, "EXTRACTION_PROVIDER", "none"):
            fields = extract_from_content(make_request())

        self.assertEqual(container_numbers_in(fields), ["CSQU3054383"])
        self.assertEqual(fields["identifiers"]["do_no"], "DO-2026-4471")
        self.assertEqual(fields["free_time_days"], 7)


class BuildFactsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fields = {
            "doc_type": "delivery_order",
            "identifiers": {
                "container_no": ["CSQU3054383"],
                "do_no": "DO-2026-4471",
                "seal_no": ["C4123088"],
            },
            "route": {"eta": "2026-07-18"},
            "free_time_days": 7,
        }

    def test_every_fact_is_scoped_to_the_container(self) -> None:
        facts = build_facts(make_request(), self.fields)

        self.assertTrue(facts)
        self.assertTrue(all(fact.container_no == "CSQU3054383" for fact in facts))

    def test_facts_carry_the_channel_and_group_as_provenance(self) -> None:
        facts = build_facts(make_request(), self.fields)

        self.assertTrue(all(fact.source_type == "zalo_message" for fact in facts))
        self.assertTrue(
            all(fact.source_label == "Group Dieu xe Cat Lai" for fact in facts)
        )

    def test_the_fields_that_drive_exceptions_are_recorded(self) -> None:
        by_name = {fact.field_name: fact.normalized_value for fact in build_facts(make_request(), self.fields)}

        self.assertEqual(by_name["container_no"], "CSQU3054383")
        self.assertEqual(by_name["do_no"], "DO-2026-4471")
        self.assertEqual(by_name["free_time_days"], "7")
        self.assertEqual(by_name["eta"], "2026-07-18")
        self.assertEqual(by_name["seal_no"], "C4123088")

    def test_occurred_at_becomes_the_fact_timestamp(self) -> None:
        occurred = datetime(2026, 7, 25, 7, 30, tzinfo=UTC)

        facts = build_facts(make_request(occurred_at=occurred), self.fields)

        self.assertTrue(all(fact.source_sent_at == occurred for fact in facts))

    def test_no_container_means_no_facts(self) -> None:
        # Without a container there is nothing to attach data to, so Agentify
        # records the message but claims nothing about any shipment.
        facts = build_facts(
            make_request(), {"identifiers": {"container_no": []}, "route": {}}
        )

        self.assertEqual(facts, [])

    def test_a_message_naming_two_containers_produces_facts_for_both(self) -> None:
        fields = {
            **self.fields,
            "identifiers": {**self.fields["identifiers"],
                            "container_no": ["CSQU3054383", "MSCU1234567"]},
        }

        containers = {fact.container_no for fact in build_facts(make_request(), fields)}

        self.assertEqual(containers, {"CSQU3054383", "MSCU1234567"})

    def test_channel_is_reflected_in_source_type(self) -> None:
        facts = build_facts(make_request(channel="note"), self.fields)

        self.assertTrue(all(fact.source_type == "note_message" for fact in facts))


class RequestValidationTest(unittest.TestCase):
    def test_empty_content_is_rejected(self) -> None:
        with self.assertRaises(Exception):
            ManualIngestRequest(channel="zalo", content="")

    def test_unknown_channel_is_rejected(self) -> None:
        with self.assertRaises(Exception):
            ManualIngestRequest(channel="whatsapp", content="hello")


if __name__ == "__main__":
    unittest.main()
