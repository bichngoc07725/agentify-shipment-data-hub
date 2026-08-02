"""Quy thuộc tính về đúng container khi paste nhiều container (P0-3).

Lỗi gốc: `build_facts` trích ra MỘT dict phẳng cho cả đoạn chat rồi rải nó lên
mọi container được nhắc tới. Hậu quả tái hiện được trên DB thật: seal của
container A bị gán cho cả B và C, ETA của B gán cho cả A và C. Đây là hành vi
"bịa dữ liệu" mà nguyên tắc provenance của dự án cấm — mọi giá trị phải giữ
đúng nguồn gốc. Nó chảy thẳng vào exception engine, sinh
cảnh báo free-time sai.
"""

import unittest
from unittest.mock import patch

from api.models import ManualIngestRequest
from gmail_service import field_extract
from services.manual_ingest_service import (
    build_facts,
    extract_from_content,
    segment_by_container,
)

# Mỗi container nói về một thứ khác nhau — đúng dạng chat điều xe thật.
MULTI = (
    "[08:15] Ops A: Xe 51F-12345 lay cont MSKU1234567 tai Cat Lai\n"
    "[08:47] Tai xe B: da lay xong seal SL889900\n"
    "[09:20] Ops A: cont thu 2 TGHU7654321 ETA 2026-08-20, free time 7 ngay\n"
)


def request(content: str = MULTI, **overrides) -> ManualIngestRequest:
    defaults = {
        "channel": "zalo",
        "content": content,
        "source_label": "Group Dieu xe Cat Lai",
        "sender": "Ops - Nguyen Van A",
    }
    return ManualIngestRequest(**{**defaults, **overrides})


def facts_by_container(payload: ManualIngestRequest) -> dict[str, dict[str, str]]:
    """Chạy với LLM tắt.

    Bài test này nói về việc QUY THUỘC TÍNH về đúng container — thuần logic tách
    cụm, không liên quan tới nhà cung cấp LLM. Nếu để `EXTRACTION_PROVIDER` thật
    thì test sẽ gọi mạng ra Gemini: chậm, phập phù, và fail trên máy không có
    API key. Khoá về "none" để kết quả chỉ phụ thuộc bộ trích deterministic.
    """
    with patch.object(field_extract, "EXTRACTION_PROVIDER", "none"):
        fields = extract_from_content(payload)
        grouped: dict[str, dict[str, str]] = {}
        for fact in build_facts(payload, fields):
            grouped.setdefault(fact.container_no, {})[fact.field_name] = fact.field_value
        return grouped


class SegmentByContainerTest(unittest.TestCase):
    def test_a_line_mentioning_a_container_opens_its_segment(self) -> None:
        segments = segment_by_container(MULTI)
        self.assertEqual([no for no, _ in segments], ["MSKU1234567", "TGHU7654321"])

    def test_following_lines_belong_to_the_container_named_above_them(self) -> None:
        segments = dict(segment_by_container(MULTI))
        self.assertIn("SL889900", segments["MSKU1234567"])
        self.assertNotIn("SL889900", segments["TGHU7654321"])

    def test_lines_before_the_first_container_belong_to_nobody(self) -> None:
        """Thà bỏ còn hơn gán cho một container mà đoạn chat chưa hề nhắc tới."""
        segments = segment_by_container("Chao ca nha, hom nay chay 3 chuyen\nMSKU1234567 di Cat Lai")
        self.assertEqual(len(segments), 1)
        self.assertNotIn("Chao ca nha", segments[0][1])

    def test_text_without_any_container_yields_no_segment(self) -> None:
        self.assertEqual(segment_by_container("Khong co ma cont nao o day"), [])


class NoCrossContaminationTest(unittest.TestCase):
    def test_seal_stays_with_its_own_container(self) -> None:
        grouped = facts_by_container(request())
        self.assertEqual(grouped["MSKU1234567"].get("seal_no"), "SL889900")
        self.assertIsNone(grouped["TGHU7654321"].get("seal_no"))

    def test_eta_and_free_time_stay_with_their_own_container(self) -> None:
        grouped = facts_by_container(request())
        self.assertEqual(grouped["TGHU7654321"].get("eta"), "2026-08-20")
        self.assertEqual(grouped["TGHU7654321"].get("free_time_days"), "7")
        self.assertIsNone(grouped["MSKU1234567"].get("eta"))
        self.assertIsNone(grouped["MSKU1234567"].get("free_time_days"))

    def test_status_text_is_the_containers_own_line_not_the_first_line_of_all(self) -> None:
        grouped = facts_by_container(request())
        self.assertIn("MSKU1234567", grouped["MSKU1234567"]["status_text"])
        self.assertIn("TGHU7654321", grouped["TGHU7654321"]["status_text"])

    def test_a_container_the_chat_says_nothing_about_gets_no_borrowed_attributes(self) -> None:
        content = MULTI + "[10:05] Docs C: kiem tra ho cont HLXU8899001 voi\n"
        grouped = facts_by_container(request(content))
        borrowed = {"seal_no", "eta", "free_time_days"} & grouped["HLXU8899001"].keys()
        self.assertEqual(borrowed, set(), f"gan bua: {borrowed}")
        self.assertEqual(grouped["HLXU8899001"]["container_no"], "HLXU8899001")


class SingleContainerIsUnchangedTest(unittest.TestCase):
    """Đường phổ biến nhất phải giữ nguyên hành vi — kể cả thuộc tính nằm ở
    dòng trước mã container — vì khi chỉ có một container thì không có gì để
    nhầm lẫn, và ta vẫn muốn hưởng LLM nếu được cấu hình."""

    def test_attributes_above_the_container_line_are_still_captured(self) -> None:
        content = "Seal SL889900 da kep xong\nCont MSKU1234567 roi kho luc 9h\n"
        grouped = facts_by_container(request(content))
        self.assertEqual(grouped["MSKU1234567"].get("seal_no"), "SL889900")


class NoContainerIsSilentlyDroppedTest(unittest.TestCase):
    def test_a_container_only_present_in_fields_still_gets_its_identity_fact(self) -> None:
        """Hồi quy: `fields` có thể chứa mã không xuất hiện nguyên văn trong
        text (LLM suy ra). Mã đó không có cụm, nhưng bỏ luôn thì mất cả fact
        `container_no` — tức là mất hẳn container khỏi hệ thống."""
        payload = request()
        with patch.object(field_extract, "EXTRACTION_PROVIDER", "none"):
            fields = extract_from_content(payload)
            fields["identifiers"]["container_no"] = [
                "MSKU1234567", "TGHU7654321", "CSQU3054383",
            ]

            grouped: dict[str, dict[str, str]] = {}
            for fact in build_facts(payload, fields):
                grouped.setdefault(fact.container_no, {})[fact.field_name] = fact.field_value

        self.assertIn("CSQU3054383", grouped)
        self.assertEqual(grouped["CSQU3054383"]["container_no"], "CSQU3054383")
        # Nhưng không được mượn thuộc tính của ai.
        self.assertEqual(
            {"seal_no", "eta", "free_time_days"} & grouped["CSQU3054383"].keys(), set()
        )


if __name__ == "__main__":
    unittest.main()
