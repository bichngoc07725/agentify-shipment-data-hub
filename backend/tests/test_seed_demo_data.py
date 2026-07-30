import unittest
from uuid import uuid4

from api.models import ProcessedEmailIngestRequest
from scripts.seed_demo_data import build_demo_payloads


class BuildDemoPayloadsTest(unittest.TestCase):
    def test_build_demo_payloads_match_ingest_contract(self) -> None:
        gmail_connection_id = uuid4()
        sync_job_id = uuid4()

        payloads = build_demo_payloads(gmail_connection_id, sync_job_id)

        self.assertEqual(len(payloads), 16)
        self.assertTrue(
            all(isinstance(payload, ProcessedEmailIngestRequest) for payload in payloads)
        )
        self.assertEqual(
            {payload.gmail_connection_id for payload in payloads},
            {gmail_connection_id},
        )
        self.assertEqual({payload.sync_job_id for payload in payloads}, {sync_job_id})
        self.assertEqual(sum(len(payload.attachments) for payload in payloads), 15)
        self.assertTrue(
            any(
                fact.field_name == "eta" and fact.normalized_value == "2026-06-14"
                for payload in payloads
                for fact in payload.extracted_facts
            )
        )
        self.assertEqual(
            {
                fact.container_no
                for payload in payloads
                for fact in payload.extracted_facts
                if fact.container_no
            },
            {
                "CAIU7788990",
                "MSCU1234567",
                "OOLU9988776",
                "SEGU5566778",
                "TGHU7654321",
                "TRHU3344556",
                "WHLU4455667",
                "FSCU2211334",
                "CMAU6677889",
                "TEMU5544332",
            },
        )
        self.assertTrue(any(not payload.attachments for payload in payloads))
        self.assertTrue(
            any(
                fact.field_name == "status_text"
                and fact.normalized_value == "Chỉ mới nhận email đặt chỗ, chưa có file PDF"
                for payload in payloads
                for fact in payload.extracted_facts
            )
        )
        self.assertTrue(
            any(
                fact.field_name == "po_no" and fact.container_no == "FSCU2211334"
                for payload in payloads
                for fact in payload.extracted_facts
            )
        )


if __name__ == "__main__":
    unittest.main()
