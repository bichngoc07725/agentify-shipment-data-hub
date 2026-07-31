import unittest
from unittest.mock import patch

from gmail_service import image_extract
from gmail_service.image_extract import extract_from_image


class UnconfiguredTest(unittest.TestCase):
    def test_skips_without_crashing_when_no_vision_provider_is_configured(self) -> None:
        with patch.object(image_extract, "VISION_PROVIDER", "none"):
            result = extract_from_image(b"fake-bytes", "image/jpeg")

        self.assertEqual(result["extraction_status"], "skipped")
        self.assertIsNone(result["extraction_error"])
        self.assertIsNone(result["container_no"])
        self.assertFalse(result["container_no_valid"])


class ValidContainerTest(unittest.TestCase):
    def test_a_checksum_valid_container_no_is_marked_valid_and_normalized(self) -> None:
        vision_reply = {
            "container_no": "csqu 305-4383",  # valid checksum, messy formatting
            "seal_no": "SL-99887",
            "license_plate": "51F-12345",
            "doc_kind": "container_photo",
            "depot": "Cat Lai",
            "datetime_text": "2026-07-29 14:05",
            "raw_text": "CSQU3054383",
            "confidence": 0.92,
        }
        with (
            patch.object(image_extract, "VISION_PROVIDER", "azure_openai"),
            patch.object(
                image_extract, "call_azure_openai_vision", return_value=vision_reply
            ),
        ):
            result = extract_from_image(b"fake-bytes", "image/jpeg")

        self.assertEqual(result["extraction_status"], "ok")
        self.assertTrue(result["container_no_valid"])
        self.assertEqual(result["container_no"], "CSQU3054383")
        self.assertEqual(result["seal_no"], "SL-99887")


class InvalidContainerTest(unittest.TestCase):
    def test_a_checksum_invalid_container_no_is_not_marked_valid(self) -> None:
        """A blurry photo the model still guesses at must not silently
        auto-attach to the wrong container."""
        vision_reply = {
            "container_no": "CSQU3054380",  # wrong check digit
            "seal_no": None,
            "license_plate": None,
            "doc_kind": "container_photo",
            "depot": None,
            "datetime_text": None,
            "raw_text": "blurry",
            "confidence": 0.31,
        }
        with (
            patch.object(image_extract, "VISION_PROVIDER", "azure_openai"),
            patch.object(
                image_extract, "call_azure_openai_vision", return_value=vision_reply
            ),
        ):
            result = extract_from_image(b"fake-bytes", "image/jpeg")

        self.assertEqual(result["extraction_status"], "ok")
        self.assertFalse(result["container_no_valid"])
        self.assertEqual(result["container_no"], "CSQU3054380")


class VisionFailureTest(unittest.TestCase):
    def test_a_provider_error_degrades_instead_of_raising(self) -> None:
        with (
            patch.object(image_extract, "VISION_PROVIDER", "azure_openai"),
            patch.object(
                image_extract,
                "call_azure_openai_vision",
                side_effect=RuntimeError("Azure extraction unreachable: timed out"),
            ),
        ):
            result = extract_from_image(b"fake-bytes", "image/jpeg")

        self.assertEqual(result["extraction_status"], "failed")
        # The person holding the phone gets a next step, not the provider's
        # raw text — that goes to the log.
        self.assertIn("quá thời gian chờ", result["extraction_error"])
        self.assertNotIn("Azure extraction unreachable", result["extraction_error"])
        self.assertIsNone(result["container_no"])


if __name__ == "__main__":
    unittest.main()


class GeminiVisionBranchTest(unittest.TestCase):
    """Đường ảnh chọn nhà cung cấp theo `VISION_PROVIDER`.

    Trước đây `image_extract` gọi cứng Azure, nên một hệ thống chỉ có khoá
    Gemini thì OCR ảnh im lặng trả rỗng — nhìn y hệt "AI đọc không ra".
    """

    VISION_REPLY = {
        "container_no": "MSDU 443826 9",
        "seal_no": None,
        "license_plate": "15R-024.96",
        "doc_kind": "container_photo",
        "depot": None,
        "datetime_text": None,
        "raw_text": "MSDU 443826 9 42G1",
        "confidence": 0.95,
    }

    def test_gemini_provider_uses_the_gemini_call_not_azure(self) -> None:
        with (
            patch.object(image_extract, "VISION_PROVIDER", "gemini"),
            patch.object(
                image_extract, "call_gemini_vision", return_value=self.VISION_REPLY
            ) as gemini,
            patch.object(image_extract, "call_azure_openai_vision") as azure,
        ):
            result = extract_from_image(b"anh-that", "image/jpeg")

        gemini.assert_called_once()
        azure.assert_not_called()
        self.assertEqual(result["extraction_status"], "ok")
        self.assertEqual(result["container_no"], "MSDU4438269")
        self.assertTrue(result["container_no_valid"])

    def test_gemini_receives_raw_bytes_not_base64(self) -> None:
        """Azure cần chuỗi base64, Gemini nhận thẳng bytes — gửi nhầm kiểu thì
        nhà cung cấp trả lỗi khó hiểu."""
        with (
            patch.object(image_extract, "VISION_PROVIDER", "gemini"),
            patch.object(
                image_extract, "call_gemini_vision", return_value=self.VISION_REPLY
            ) as gemini,
        ):
            extract_from_image(b"anh-that", "image/jpeg")

        self.assertIsInstance(gemini.call_args.args[1], bytes)

    def test_a_gemini_failure_degrades_instead_of_raising(self) -> None:
        with (
            patch.object(image_extract, "VISION_PROVIDER", "gemini"),
            patch.object(
                image_extract,
                "call_gemini_vision",
                side_effect=RuntimeError("429 RESOURCE_EXHAUSTED"),
            ),
        ):
            result = extract_from_image(b"anh-that", "image/jpeg")

        self.assertEqual(result["extraction_status"], "failed")
        # A quota wall is the one failure a driver can actually act on
        # (nhập tay + báo Admin), so it gets its own message rather than the
        # raw 429 JSON blob.
        self.assertIn("Hết hạn mức", result["extraction_error"])
        self.assertNotIn("RESOURCE_EXHAUSTED", result["extraction_error"])
        self.assertFalse(result["container_no_valid"])

    def test_azure_provider_still_uses_azure(self) -> None:
        """Không được phá cấu hình Azure đang chạy của người khác."""
        with (
            patch.object(image_extract, "VISION_PROVIDER", "azure_openai"),
            patch.object(
                image_extract, "call_azure_openai_vision", return_value=self.VISION_REPLY
            ) as azure,
            patch.object(image_extract, "call_gemini_vision") as gemini,
        ):
            extract_from_image(b"anh-that", "image/jpeg")

        azure.assert_called_once()
        gemini.assert_not_called()
