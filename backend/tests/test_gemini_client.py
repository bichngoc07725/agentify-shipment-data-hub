"""Độ bền của nhánh Gemini (`call_gemini`) và fallback của `extract_fields`.

Bối cảnh: khi bật `EXTRACTION_PROVIDER=gemini`, mọi lần ingest email/PDF đều đi
qua Gemini. Một nhà cung cấp ngoài tầm kiểm soát thì phải coi mọi kiểu hỏng là
chuyện bình thường: sai key, sai model, hết quota, trả rỗng, trả JSON hỏng, và
treo. Ingest KHÔNG được sập vì bất kỳ cái nào trong số đó — kết quả regex vẫn
phải dùng được.

Không test nào ở đây gọi mạng thật.
"""

import json
import unittest

import pytest
from unittest.mock import MagicMock, patch

import gmail_service.field_extract as field_extract
import gmail_service.llm_client as llm_client
from gmail_service.field_extract import extract_fields
from gmail_service.llm_client import ExtractionUnavailable, call_gemini

ARRIVAL_NOTICE = """MAERSK LINE - ARRIVAL NOTICE
Container No: CSQU3054383
Booking No: BKG-99001
ETA: 2026-08-20
"""


def _fake_client(text):
    """Client giả trả về `text` cho `models.generate_content`."""
    client = MagicMock()
    client.models.generate_content.return_value = MagicMock(text=text)
    return client


class CallGeminiTest(unittest.TestCase):
    def test_missing_key_raises_a_clear_unavailable_error(self) -> None:
        with patch.object(llm_client, "GEMINI_API_KEY", ""):
            with self.assertRaises(ExtractionUnavailable):
                call_gemini("prompt")

    def test_a_timeout_is_always_passed_to_the_sdk(self) -> None:
        """SDK google-genai mặc định `timeout=None` (chờ vô hạn). Thiếu timeout
        thì một lần Gemini treo sẽ làm đứng worker ingestion, và `extract_fields`
        không cứu được vì treo không sinh exception để bắt."""
        # Chỉ giả lập `Client`, KHÔNG giả lập cả module `google.genai` — nếu
        # giả lập cả module thì `types.HttpOptions` cũng thành MagicMock và
        # phép kiểm tra bên dưới trở nên vô nghĩa (luôn đúng với mọi giá trị).
        fake_client_cls = MagicMock(return_value=_fake_client('{"doc_type": "other"}'))

        with (
            patch.object(llm_client, "GEMINI_API_KEY", "k"),
            patch.object(llm_client, "GEMINI_TIMEOUT_SECONDS", 45),
            patch("google.genai.Client", fake_client_cls),
        ):
            call_gemini("prompt")

        http_options = fake_client_cls.call_args.kwargs["http_options"]
        self.assertEqual(http_options.timeout, 45_000)  # SDK dùng mili-giây

    def test_a_fenced_json_block_is_unwrapped(self) -> None:
        fake_client_cls = MagicMock(
            return_value=_fake_client('```json\n{"doc_type": "invoice"}\n```')
        )

        with (
            patch.object(llm_client, "GEMINI_API_KEY", "k"),
            patch("google.genai.Client", fake_client_cls),
        ):
            self.assertEqual(call_gemini("prompt"), {"doc_type": "invoice"})

    def test_empty_response_raises_a_readable_error_not_AttributeError(self) -> None:
        """`response.text` là None khi bị safety filter chặn. Nếu không chặn
        trước, `.strip()` ném AttributeError vô nghĩa và người vận hành không
        biết vì sao trích xuất hỏng."""
        fake_client_cls = MagicMock(return_value=_fake_client(None))

        with (
            patch.object(llm_client, "GEMINI_API_KEY", "k"),
            patch("google.genai.Client", fake_client_cls),
        ):
            with self.assertRaises(RuntimeError) as ctx:
                call_gemini("prompt")

        self.assertNotIsInstance(ctx.exception, AttributeError)
        self.assertIn("no text", str(ctx.exception))

    def test_malformed_json_error_names_the_cause_and_shows_the_payload(self) -> None:
        fake_client_cls = MagicMock(
            return_value=_fake_client("xin loi, toi khong hieu yeu cau")
        )

        with (
            patch.object(llm_client, "GEMINI_API_KEY", "k"),
            patch("google.genai.Client", fake_client_cls),
        ):
            with self.assertRaises(RuntimeError) as ctx:
                call_gemini("prompt")

        message = str(ctx.exception)
        self.assertIn("JSON", message)
        self.assertIn("xin loi", message)  # kèm đoạn đầu để chẩn đoán


class ExtractFieldsNeverCrashesTest(unittest.TestCase):
    """Mỗi kiểu hỏng của Gemini đều phải degrade về regex, không ném ra ngoài."""

    def _run_with_failure(self, exc: Exception) -> dict:
        with (
            patch.object(field_extract, "EXTRACTION_PROVIDER", "gemini"),
            patch.object(field_extract, "call_gemini", side_effect=exc),
        ):
            return extract_fields("Arrival Notice", "ops@carrier.com", ARRIVAL_NOTICE)

    def test_invalid_key_401_degrades_to_deterministic(self) -> None:
        result = self._run_with_failure(RuntimeError("401 UNAUTHENTICATED"))
        self.assertEqual(result["extraction_method"], "deterministic")
        self.assertEqual(result["extraction_status"], "partial")
        self.assertIn("401", result["extraction_error"])
        # Quan trọng nhất: dữ liệu regex vẫn dùng được, ingest không bị chặn.
        self.assertEqual(result["identifiers"]["container_no"], ["CSQU3054383"])

    def test_unknown_model_404_degrades_to_deterministic(self) -> None:
        result = self._run_with_failure(RuntimeError("404 NOT_FOUND: model not found"))
        self.assertEqual(result["extraction_method"], "deterministic")
        self.assertIn("404", result["extraction_error"])

    def test_quota_exhausted_429_degrades_to_deterministic(self) -> None:
        result = self._run_with_failure(RuntimeError("429 RESOURCE_EXHAUSTED"))
        self.assertEqual(result["extraction_method"], "deterministic")
        self.assertIn("429", result["extraction_error"])

    def test_timeout_degrades_to_deterministic(self) -> None:
        result = self._run_with_failure(TimeoutError("timed out"))
        self.assertEqual(result["extraction_method"], "deterministic")
        self.assertEqual(result["extraction_status"], "partial")

    def test_a_working_gemini_produces_hybrid_and_adds_what_regex_missed(self) -> None:
        """Bằng chứng pipeline KHÔNG "luôn rơi về deterministic": khi Gemini
        chạy được, `extraction_method` thành `hybrid` và các trường regex không
        đọc nổi (vessel/voyage) mới xuất hiện.

        Lưu ý: giá trị báo thành công là `hybrid` chứ không phải `llm`, vì kết
        quả là hợp nhất regex + LLM (`merge_records`), không phải thuần LLM.
        """
        llm_payload = {
            "doc_type": "arrival_notice",
            "identifiers": {"container_no": [], "seal_no": []},
            "route": {"vessel": "MAERSK HANOI", "voyage": "034W"},
            "free_time_days": 7,
        }
        with (
            patch.object(field_extract, "EXTRACTION_PROVIDER", "gemini"),
            patch.object(field_extract, "call_gemini", return_value=llm_payload),
        ):
            result = extract_fields("Arrival Notice", "ops@carrier.com", ARRIVAL_NOTICE)

        self.assertEqual(result["extraction_method"], "hybrid")
        self.assertEqual(result["route"]["vessel"], "MAERSK HANOI")
        self.assertEqual(result["free_time_days"], 7)
        self.assertEqual(result["identifiers"]["container_no"], ["CSQU3054383"])


class GeminiVisionTest(unittest.TestCase):
    """Nhánh vision của Gemini — trước đây OCR ảnh chỉ chạy được với Azure."""

    IMAGE_REPLY = {
        "container_no": "MSDU4438269", "seal_no": None, "license_plate": "15R-024.96",
        "doc_kind": "container_photo", "depot": None, "datetime_text": None,
        "raw_text": "MSDU 443826 9", "confidence": 0.95,
    }

    def _call(self, schema=None):
        from gmail_service.llm_client import call_gemini_vision
        fake_client_cls = MagicMock(
            return_value=_fake_client(json.dumps(self.IMAGE_REPLY))
        )
        with (
            patch.object(llm_client, "GEMINI_API_KEY", "k"),
            patch.object(llm_client, "GEMINI_TIMEOUT_SECONDS", 45),
            patch("google.genai.Client", fake_client_cls),
        ):
            out = call_gemini_vision(
                "prompt", b"anh-bytes", "image/jpeg",
                schema or {"type": "object", "properties": {}},
            )
        return out, fake_client_cls

    def test_returns_the_parsed_reading(self) -> None:
        out, _ = self._call()
        self.assertEqual(out["container_no"], "MSDU4438269")

    def test_the_image_schema_is_enforced(self) -> None:
        """Giống nhánh văn bản: không ép schema thì Gemini tự đặt tên trường và
        `extract_from_image` sẽ đọc ra toàn None."""
        from gmail_service.image_extract import IMAGE_EXTRACTION_SCHEMA

        _, cls = self._call(IMAGE_EXTRACTION_SCHEMA)
        config = cls.return_value.models.generate_content.call_args.kwargs["config"]
        self.assertEqual(config.response_mime_type, "application/json")
        # SDK giữ nguyên dict nếu truyền dict, nên đọc theo cả hai kiểu.
        schema = config.response_schema
        props = schema["properties"] if isinstance(schema, dict) else schema.properties
        self.assertIn("container_no", props)
        self.assertIn("doc_kind", props)

    def test_a_timeout_is_applied_to_the_vision_call_too(self) -> None:
        _, cls = self._call()
        self.assertEqual(cls.call_args.kwargs["http_options"].timeout, 45_000)

    def test_empty_reply_raises_a_readable_error(self) -> None:
        from gmail_service.llm_client import call_gemini_vision

        fake_client_cls = MagicMock(return_value=_fake_client(None))
        with (
            patch.object(llm_client, "GEMINI_API_KEY", "k"),
            patch("google.genai.Client", fake_client_cls),
        ):
            with pytest.raises(RuntimeError) as ctx:
                call_gemini_vision("p", b"x", "image/jpeg", {"type": "object"})
        self.assertIn("ảnh", str(ctx.value))


if __name__ == "__main__":
    unittest.main()


class GeminiSchemaEnforcementTest(unittest.TestCase):
    """Ép Gemini trả đúng cấu trúc, ngang với `strict: True` của Azure.

    Không ép thì Gemini vẫn trả JSON hợp lệ nhưng tự đặt tên trường
    (`vessel_name`, `container_numbers`...). `merge_records` chỉ đọc
    `llm["identifiers"]` / `llm["route"]`, nên toàn bộ dữ liệu LLM bị vứt lặng
    lẽ: `route` rỗng trơn dù model đã đọc ra tàu/chuyến/cảng, đồng thời các key
    lạ lọt vào bản ghi. Tệ nhất là `extraction_method` vẫn báo "hybrid" nên
    nhìn từ ngoài tưởng LLM đang chạy tốt.
    """

    def test_union_nullable_types_become_a_single_type_plus_nullable(self) -> None:
        from gmail_service.llm_client import to_gemini_schema

        converted = to_gemini_schema({"type": ["string", "null"]})
        self.assertEqual(converted["type"], "STRING")
        self.assertTrue(converted["nullable"])

    def test_plain_types_are_uppercased_and_enums_kept(self) -> None:
        from gmail_service.llm_client import to_gemini_schema

        converted = to_gemini_schema({"type": "string", "enum": ["invoice", "other"]})
        self.assertEqual(converted["type"], "STRING")
        self.assertEqual(converted["enum"], ["invoice", "other"])

    def test_nested_objects_and_arrays_are_converted_recursively(self) -> None:
        from gmail_service.llm_client import to_gemini_schema

        converted = to_gemini_schema(
            {
                "type": "object",
                "required": ["identifiers"],
                "properties": {
                    "identifiers": {
                        "type": "object",
                        "properties": {
                            "container_no": {"type": "array", "items": {"type": "string"}},
                            "bl_no": {"type": ["string", "null"]},
                        },
                    }
                },
            }
        )
        ids = converted["properties"]["identifiers"]["properties"]
        self.assertEqual(ids["container_no"]["items"]["type"], "STRING")
        self.assertTrue(ids["bl_no"]["nullable"])
        self.assertEqual(converted["required"], ["identifiers"])

    def test_additionalProperties_is_dropped(self) -> None:
        """Gemini không hỗ trợ khoá này; giữ lại sẽ bị SDK từ chối."""
        from gmail_service.llm_client import to_gemini_schema

        converted = to_gemini_schema({"type": "object", "additionalProperties": False})
        self.assertNotIn("additionalProperties", converted)

    def test_the_real_extraction_schema_converts_without_error(self) -> None:
        from gmail_service.field_extract import EXTRACTION_SCHEMA
        from gmail_service.llm_client import to_gemini_schema

        converted = to_gemini_schema(EXTRACTION_SCHEMA)
        self.assertEqual(converted["type"], "OBJECT")
        self.assertIn("identifiers", converted["properties"])
        self.assertIn("route", converted["properties"])

    def test_call_llm_passes_the_schema_to_gemini(self) -> None:
        """Hồi quy: `call_llm` phải truyền schema, nếu quên thì lỗi mất dữ liệu
        quay lại ngay mà mọi test khác vẫn xanh."""
        from gmail_service.field_extract import EXTRACTION_SCHEMA, call_llm

        with (
            patch.object(field_extract, "EXTRACTION_PROVIDER", "gemini"),
            patch.object(field_extract, "call_gemini", return_value={}) as spy,
        ):
            call_llm("subject", "sender", "text")

        self.assertIs(spy.call_args.args[1], EXTRACTION_SCHEMA)

    def test_schema_is_forwarded_to_the_sdk_as_response_schema(self) -> None:
        fake_client_cls = MagicMock(return_value=_fake_client('{"doc_type": "other"}'))

        with (
            patch.object(llm_client, "GEMINI_API_KEY", "k"),
            patch("google.genai.Client", fake_client_cls),
        ):
            call_gemini("prompt", {"type": "object", "properties": {}})

        config = fake_client_cls.return_value.models.generate_content.call_args.kwargs["config"]
        self.assertEqual(config.response_mime_type, "application/json")
        self.assertIsNotNone(config.response_schema)

    def test_no_schema_means_no_config_so_old_callers_still_work(self) -> None:
        fake_client_cls = MagicMock(return_value=_fake_client('{"doc_type": "other"}'))

        with (
            patch.object(llm_client, "GEMINI_API_KEY", "k"),
            patch("google.genai.Client", fake_client_cls),
        ):
            call_gemini("prompt")

        config = fake_client_cls.return_value.models.generate_content.call_args.kwargs["config"]
        self.assertIsNone(config)
