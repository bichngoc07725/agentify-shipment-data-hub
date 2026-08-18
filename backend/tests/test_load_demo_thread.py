"""Thứ tự và thời điểm của thư demo.

Cả hai thứ này đều không "chỉ là hiển thị": `container_facts` chọn giá trị mới
nhất theo `source_sent_at`, nên khi Invoice và Packing List khai khác nhau về
cùng một số liệu, bên thắng được quyết định bởi đúng cái timestamp này.
"""

import tempfile
import unittest
from pathlib import Path

from scripts.load_demo_thread import discover, read_meta, sent_at_of


def _make_email_dir(root: Path, name: str, sent_at: str | None = None) -> Path:
    folder = root / name
    folder.mkdir()
    (folder / "body.txt").write_text("Chào bạn", encoding="utf-8")
    (folder / "title.txt").write_text(name, encoding="utf-8")
    lines = ["Direction: inbound", "From: a@b.com"]
    if sent_at:
        lines.append(f"Sent At: {sent_at}")
    (folder / "meta.txt").write_text("\n".join(lines), encoding="utf-8")
    return folder


class SentAtTest(unittest.TestCase):
    def test_reads_the_offset_written_in_the_corpus(self) -> None:
        self.assertEqual(
            sent_at_of({"Sent At": "2026-08-03 08:30 +07"}), "2026-08-03T08:30:00+07:00"
        )

    def test_a_mail_without_a_date_yields_nothing_rather_than_today(self) -> None:
        # Trả về "bây giờ" ở đây thì cả kịch bản bị nén vào thời điểm chạy
        # script, và thứ tự thật của lô hàng biến mất.
        self.assertIsNone(sent_at_of({"From": "a@b.com"}))

    def test_an_unparseable_date_is_dropped_not_guessed(self) -> None:
        self.assertIsNone(sent_at_of({"Sent At": "thứ ba tuần trước"}))

    def test_seconds_are_accepted(self) -> None:
        self.assertEqual(
            sent_at_of({"Sent At": "2026-08-05 16:05:30 +07"}),
            "2026-08-05T16:05:30+07:00",
        )


class DiscoverOrderTest(unittest.TestCase):
    def test_folders_are_ordered_by_number_not_by_string(self) -> None:
        # `sorted()` trên tên cho ra email_100 trước email_96. Corpus đánh số
        # theo trình tự nghiệp vụ, nên xếp sai số là nạp thư xác nhận đặt chỗ
        # trước cả thư hỏi giá.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("email_96_hoi-gia", "email_100_dat-cho", "email_101_xac-nhan"):
                _make_email_dir(root, name)

            names = [folder.name for folder in discover(root, None)]

        self.assertEqual(
            names, ["email_96_hoi-gia", "email_100_dat-cho", "email_101_xac-nhan"]
        )

    def test_folders_without_a_body_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_email_dir(root, "email_1_co-noi-dung")
            (root / "email_2_rong").mkdir()

            self.assertEqual([f.name for f in discover(root, None)], ["email_1_co-noi-dung"])

    def test_filter_matches_on_folder_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_email_dir(root, "email_1_roundtrip-rfq-hpn-01")
            _make_email_dir(root, "email_2_khac")

            names = [f.name for f in discover(root, "roundtrip-rfq-hpn")]

        self.assertEqual(names, ["email_1_roundtrip-rfq-hpn-01"])


class MetaTest(unittest.TestCase):
    def test_reads_keys_and_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = _make_email_dir(Path(tmp), "email_1_x", "2026-08-03 08:30 +07")
            meta = read_meta(folder)

        self.assertEqual(meta["Direction"], "inbound")
        self.assertEqual(meta["Sent At"], "2026-08-03 08:30 +07")


if __name__ == "__main__":
    unittest.main()
