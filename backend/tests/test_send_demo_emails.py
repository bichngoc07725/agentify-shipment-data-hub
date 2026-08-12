import tempfile
import unittest
from email import policy
from email.parser import BytesParser
from pathlib import Path

from scripts.generate_demo_email_corpus import build_records, write_corpus
from scripts.send_demo_emails import (
    DEFAULT_FROM,
    DEFAULT_TO,
    DEMO_MAILBOX,
    discover_email_jobs,
    prepare_message_for_send,
)


class SendDemoEmailsTest(unittest.TestCase):
    def test_discover_jobs_returns_sorted_eml_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "demo_email"
            write_corpus(build_records()[:2], output_dir=output_dir)

            jobs = discover_email_jobs(output_dir)

            self.assertEqual(len(jobs), 2)
            self.assertEqual(jobs[0].folder_name, "email_01_completed-booking-confirmation")
            self.assertEqual(jobs[1].folder_name, "email_02_completed-si-submission")
            self.assertTrue(jobs[0].eml_path.name == "email.eml")

    def test_demo_mailbox_sends_to_itself(self) -> None:
        # Bộ demo mô phỏng cả 4 chặng hội thoại trong MỘT tài khoản, nên người
        # gửi và người nhận phải là cùng một hộp thư. Lệch nhau nghĩa là cần
        # app password của một tài khoản thứ hai — hỏng ngay lúc đăng nhập SMTP.
        self.assertEqual(DEFAULT_FROM, DEMO_MAILBOX)
        self.assertEqual(DEFAULT_TO, DEMO_MAILBOX)

    def test_prepare_message_for_send_overrides_from_to_and_keeps_attachment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "demo_email"
            write_corpus(build_records()[:1], output_dir=output_dir)
            eml_path = output_dir / "email_01_completed-booking-confirmation" / "email.eml"

            prepared_bytes = prepare_message_for_send(
                eml_path,
                from_email="nguyendinhtung20072000@gmail.com",
                to_email="nguyendinhtung20072000@gmail.com",
            )
            message = BytesParser(policy=policy.default).parsebytes(prepared_bytes)

            self.assertEqual(message["From"], "nguyendinhtung20072000@gmail.com")
            self.assertEqual(message["To"], "nguyendinhtung20072000@gmail.com")
            self.assertEqual(
                message["X-Agentify-Original-From"],
                "cs.export@one-demo.com",
            )

            attachments = list(message.iter_attachments())
            self.assertEqual(len(attachments), 1)
            self.assertEqual(
                attachments[0].get_filename(),
                "booking_confirmation_oolu7215245.pdf",
            )

    def test_outbound_email_keeps_its_direction_after_the_from_to_rewrite(self) -> None:
        outbound = next(
            record for record in build_records() if record.direction == "outbound"
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "demo_email"
            write_corpus([outbound], output_dir=output_dir)
            eml_path = (
                output_dir / f"email_{outbound.seq:02d}_{outbound.slug}" / "email.eml"
            )

            prepared_bytes = prepare_message_for_send(
                eml_path,
                from_email="nguyendinhtung20072000@gmail.com",
                to_email="nguyendinhtung20072000@gmail.com",
            )
            message = BytesParser(policy=policy.default).parsebytes(prepared_bytes)

            # Thư được đẩy vào hộp thư test để pipeline đọc được, nhưng vẫn phải
            # tra ra được đây vốn là thư đi và gửi cho ai.
            self.assertEqual(message["To"], "nguyendinhtung20072000@gmail.com")
            self.assertEqual(message["X-Agentify-Direction"], "outbound")
            self.assertEqual(message["X-Agentify-Original-To"], outbound.to_email)


if __name__ == "__main__":
    unittest.main()
