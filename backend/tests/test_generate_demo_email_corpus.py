import tempfile
import unittest
from email import policy
from email.parser import BytesParser
from pathlib import Path

from scripts.generate_demo_email_corpus import (
    AGENTIFY_SELF,
    DEMO_TAG,
    INBOUND,
    OUTBOUND,
    SCENARIOS,
    TARGET_TO,
    THREAD_PLANS,
    build_records,
    write_corpus,
)


def _parse(eml_path: Path):
    return BytesParser(policy=policy.default).parsebytes(eml_path.read_bytes())


def _dir_for(output_dir: Path, record) -> Path:
    return output_dir / f"email_{record.seq:02d}_{record.slug}"


class GenerateDemoEmailCorpusTest(unittest.TestCase):
    def test_write_corpus_creates_eml_with_pdf_attachment(self) -> None:
        records = build_records()[:1]

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "demo_email"

            write_corpus(records, output_dir=output_dir)

            email_dir = output_dir / "email_01_completed-booking-confirmation"
            eml_path = email_dir / "email.eml"

            self.assertTrue(eml_path.exists())

            message = _parse(eml_path)

            self.assertEqual(message["Subject"], records[0].title)
            self.assertEqual(message["To"], TARGET_TO)
            self.assertEqual(message["From"], records[0].from_email)
            self.assertEqual(message["X-Agentify-Direction"], INBOUND)

            attachments = list(message.iter_attachments())
            self.assertEqual(len(attachments), 1)
            self.assertEqual(attachments[0].get_filename(), records[0].pdf_name)
            self.assertEqual(attachments[0].get_content_type(), "application/pdf")

    def test_seq_and_slug_stay_unique_across_handwritten_and_thread_records(self) -> None:
        records = build_records()

        expected_thread_count = sum(
            len(SCENARIOS[plan.scenario]) for plan in THREAD_PLANS
        )

        self.assertEqual(len(records), 36 + expected_thread_count)
        self.assertEqual(len({record.seq for record in records}), len(records))
        self.assertEqual(len({record.slug for record in records}), len(records))
        self.assertEqual([record.seq for record in records], list(range(1, len(records) + 1)))

    def test_outbound_record_is_sent_from_the_test_mailbox_to_the_partner(self) -> None:
        records = build_records()
        outbound = next(record for record in records if record.direction == OUTBOUND)

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "demo_email"
            write_corpus([outbound], output_dir=output_dir)

            message = _parse(_dir_for(output_dir, outbound) / "email.eml")

            self.assertEqual(message["From"], AGENTIFY_SELF)
            self.assertNotEqual(message["To"], TARGET_TO)
            self.assertEqual(message["To"], outbound.to_email)
            # Hướng thư phải đọc được từ header: send_demo_emails.py ghi đè
            # From/To nên To không còn phân biệt được mail đi với mail đến.
            self.assertEqual(message["X-Agentify-Direction"], OUTBOUND)

    def test_record_without_attachment_writes_no_pdf(self) -> None:
        records = build_records()
        text_only = next(record for record in records if not record.pdf_name)

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "demo_email"
            write_corpus([text_only], output_dir=output_dir)

            email_dir = _dir_for(output_dir, text_only)
            message = _parse(email_dir / "email.eml")

            self.assertEqual(list(message.iter_attachments()), [])
            self.assertFalse((email_dir / "attachments").exists())
            self.assertTrue((email_dir / "body.txt").exists())

    def test_thread_replies_point_at_the_previous_message_id(self) -> None:
        records = build_records()
        thread = [
            record
            for record in records
            if record.container_key == THREAD_PLANS[0].profile_key
        ]
        self.assertEqual(len(thread), len(SCENARIOS[THREAD_PLANS[0].scenario]))

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "demo_email"
            write_corpus(thread, output_dir=output_dir)

            first = _parse(_dir_for(output_dir, thread[0]) / "email.eml")
            second = _parse(_dir_for(output_dir, thread[1]) / "email.eml")

            self.assertIsNone(first["In-Reply-To"])
            self.assertEqual(second["In-Reply-To"], first["Message-ID"])
            self.assertEqual(second["References"], first["Message-ID"])

    def test_round_trip_subjects_carry_the_demo_tag_and_their_leg(self) -> None:
        records = build_records()
        trip = [r for r in records if r.container_key == "roundtrip_rfq"]

        self.assertEqual(len(trip), 9)
        legs = [
            "KHACH>AGENTIFY", "AGENTIFY>HANGTAU", "HANGTAU>AGENTIFY",
            "AGENTIFY>KHACH", "AGENTIFY>HANGTAU", "HANGTAU>AGENTIFY",
            "KHACH>AGENTIFY", "KHACH>AGENTIFY", "HAIQUAN>AGENTIFY",
        ]
        for record, leg in zip(trip, legs, strict=True):
            self.assertTrue(record.title.startswith(f"{DEMO_TAG}[{leg}]"), record.title)

    def test_round_trip_alternates_between_inbound_and_outbound(self) -> None:
        trip = [r for r in build_records() if r.container_key == "roundtrip_rfq"]

        self.assertEqual(
            [r.direction for r in trip],
            [INBOUND, OUTBOUND, INBOUND, OUTBOUND, OUTBOUND, INBOUND,
             INBOUND, INBOUND, INBOUND],
        )

    def test_container_appears_only_in_the_booking_confirmation(self) -> None:
        # Năm chặng đầu xảy ra TRƯỚC khi hãng tàu cấp container, nên chưa thể có
        # số cont — để lọt vào sẽ dạy sai luồng. Chặng 6 là thư xác nhận, và đó
        # đúng là khoảnh khắc container xuất hiện lần đầu trong cả câu chuyện.
        trip = [r for r in build_records() if r.container_key == "roundtrip_rfq"]

        for record in trip[:5]:
            self.assertNotIn("MSKU6512347", record.title + record.body, record.slug)
        # Từ chặng xác nhận trở đi container đã tồn tại và phải được nhắc tới.
        for record in trip[5:]:
            self.assertIn("MSKU6512347", record.title + record.body, record.slug)

    def test_booking_confirmation_carries_all_three_cutoffs(self) -> None:
        # Ba mốc chốt là thứ Bước 2 tồn tại để theo dõi; thiếu một mốc trong thư
        # xác nhận nghĩa là demo không dựng lại được cảnh báo rớt chuyến.
        confirmation = next(
            r for r in build_records() if r.slug.endswith("06-hang-tau-xac-nhan")
        )

        for keyword in ("SI cut-off", "VGM cut-off", "Gate-in cut-off", "Empty pick-up depot"):
            self.assertIn(keyword, confirmation.body)

    def test_carrier_reply_carries_its_charge_table_in_the_body(self) -> None:
        # Đây là đầu vào của nút "Nạp phí từ thư hãng tàu trả lời"; đưa bảng phí
        # vào PDF thay vì thân thư sẽ làm chặng đó không test được.
        reply = next(
            r for r in build_records() if r.slug.endswith("03-hang-tau-bao-gia")
        )

        self.assertEqual(reply.pdf_name, "")
        for keyword in ("Ocean Freight", "Terminal Handling Charge", "Free time"):
            self.assertIn(keyword, reply.body)

    def test_quotation_document_carries_no_booking_or_container_yet(self) -> None:
        records = build_records()
        quotation = next(
            record for record in records if record.slug.endswith("-quotation")
        )

        joined = "\n".join(quotation.pdf_lines)

        self.assertIn("Document Type: Quotation", joined)
        self.assertNotIn("Container No:", joined)
        self.assertNotIn("Booking No:", joined)
        self.assertNotIn("MBL No:", joined)


if __name__ == "__main__":
    unittest.main()
