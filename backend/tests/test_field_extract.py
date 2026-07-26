import json
import unittest
from unittest.mock import patch

from gmail_service import field_extract, llm_client
from gmail_service.field_extract import extract_fields, merge_records
from gmail_service.llm_client import ExtractionUnavailable, _azure_output_text

ARRIVAL_NOTICE = (
    "ARRIVAL NOTICE\n"
    "B/L No: MEDUHC1234567\n"
    "Container No: CSQU3054383\n"
    "ETA: 15/07/2026\n"
    "Free time: 5 days\n"
)


class AzureResponseParsingTest(unittest.TestCase):
    def test_reads_the_message_item_and_skips_reasoning_items(self) -> None:
        body = {
            "status": "completed",
            "output": [
                {"type": "reasoning", "summary": []},
                {"type": "message", "content": [{"type": "output_text", "text": "{}"}]},
            ],
        }

        self.assertEqual(_azure_output_text(body), "{}")

    def test_incomplete_response_is_an_error_not_silent_data_loss(self) -> None:
        body = {"status": "incomplete", "incomplete_details": {"reason": "max_tokens"}}

        with self.assertRaises(RuntimeError) as ctx:
            _azure_output_text(body)

        self.assertIn("max_tokens", str(ctx.exception))

    def test_missing_message_content_is_an_error(self) -> None:
        with self.assertRaises(RuntimeError):
            _azure_output_text({"status": "completed", "output": []})


class AzureConfigurationTest(unittest.TestCase):
    def test_call_is_refused_when_the_deployment_is_not_configured(self) -> None:
        with patch.object(llm_client, "AZURE_OPENAI_ENDPOINT", ""):
            with self.assertRaises(ExtractionUnavailable):
                llm_client.call_azure_openai("prompt", {"type": "object"})


class ExtractionSchemaTest(unittest.TestCase):
    def test_schema_satisfies_azure_strict_mode(self) -> None:
        """Strict mode rejects objects that omit `required` or allow extra keys."""

        def check(node: dict, path: str) -> None:
            if node.get("type") == "object" or "object" in (node.get("type") or []):
                self.assertIs(
                    node.get("additionalProperties"), False, f"{path}: extra keys allowed"
                )
                self.assertEqual(
                    sorted(node.get("required", [])),
                    sorted(node.get("properties", {})),
                    f"{path}: required must list every property",
                )
            for name, child in (node.get("properties") or {}).items():
                check(child, f"{path}.{name}")
            if isinstance(node.get("items"), dict):
                check(node["items"], f"{path}[]")

        check(field_extract.EXTRACTION_SCHEMA, "root")

    def test_schema_is_json_serializable(self) -> None:
        json.dumps(field_extract.EXTRACTION_SCHEMA)


class MergeRecordsTest(unittest.TestCase):
    def test_rule_identifiers_win_over_the_model(self) -> None:
        rules = {"identifiers": {"container_no": ["CSQU3054383"], "bl_no": "REAL-BL"}}
        llm = {"identifiers": {"container_no": ["WRONG1111111"], "bl_no": "HALLUCINATED"}}

        merged = merge_records(rules, llm)

        self.assertEqual(merged["identifiers"]["container_no"], ["CSQU3054383"])
        self.assertEqual(merged["identifiers"]["bl_no"], "REAL-BL")

    def test_model_fills_identifiers_the_rules_missed(self) -> None:
        rules = {"identifiers": {"container_no": []}}
        llm = {"identifiers": {"container_no": ["CSQU3054383"], "hs_code": "8471.30"}}

        merged = merge_records(rules, llm)

        self.assertEqual(merged["identifiers"]["container_no"], ["CSQU3054383"])
        self.assertEqual(merged["identifiers"]["hs_code"], "8471.30")

    def test_model_wins_for_narrative_fields(self) -> None:
        rules = {"identifiers": {}, "route": {"pod": "HO CHI MINH"}}
        llm = {
            "identifiers": {},
            "route": {"pod": "Ho Chi Minh City (Cat Lai)"},
            "carrier": "Maersk",
        }

        merged = merge_records(rules, llm)

        self.assertEqual(merged["route"]["pod"], "Ho Chi Minh City (Cat Lai)")
        self.assertEqual(merged["carrier"], "Maersk")

    def test_rules_fill_route_fields_the_model_missed(self) -> None:
        rules = {"identifiers": {}, "route": {"pol": "SHANGHAI"}}
        llm = {"identifiers": {}, "route": {"pol": None, "pod": "Cat Lai"}}

        merged = merge_records(rules, llm)

        self.assertEqual(merged["route"]["pol"], "SHANGHAI")
        self.assertEqual(merged["route"]["pod"], "Cat Lai")

    def test_rule_dates_override_the_model(self) -> None:
        rules = {"identifiers": {}, "route": {"eta": "2026-07-15"}}
        llm = {"identifiers": {}, "route": {"eta": "2026-05-07", "etd": "2026-07-01"}}

        merged = merge_records(rules, llm)

        self.assertEqual(merged["route"]["eta"], "2026-07-15")
        self.assertEqual(merged["route"]["etd"], "2026-07-01")

    def test_free_time_falls_back_to_whichever_source_found_it(self) -> None:
        merged = merge_records(
            {"identifiers": {}, "route": {}, "free_time_days": 5},
            {"identifiers": {}, "route": {}, "free_time_days": None},
        )

        self.assertEqual(merged["free_time_days"], 5)

    def test_more_confident_classification_wins(self) -> None:
        rules = {
            "identifiers": {},
            "route": {},
            "doc_type": "arrival_notice",
            "doc_type_confidence": 0.85,
        }
        llm = {
            "identifiers": {},
            "route": {},
            "doc_type": "other",
            "doc_type_confidence": 0.3,
        }

        merged = merge_records(rules, llm)

        self.assertEqual(merged["doc_type"], "arrival_notice")


class ExtractFieldsTest(unittest.TestCase):
    def test_rules_only_when_no_provider_is_configured(self) -> None:
        with patch.object(field_extract, "EXTRACTION_PROVIDER", "none"):
            result = extract_fields("Arrival Notice", "ops@carrier.com", ARRIVAL_NOTICE)

        self.assertEqual(result["extraction_method"], "deterministic")
        self.assertEqual(result["identifiers"]["container_no"], ["CSQU3054383"])
        self.assertEqual(result["free_time_days"], 5)

    def test_provider_failure_degrades_instead_of_raising(self) -> None:
        with patch.object(field_extract, "EXTRACTION_PROVIDER", "azure_openai"), patch.object(
            field_extract, "call_llm", side_effect=RuntimeError("429 rate limited")
        ):
            result = extract_fields("Arrival Notice", "ops@carrier.com", ARRIVAL_NOTICE)

        self.assertEqual(result["extraction_method"], "deterministic")
        self.assertEqual(result["extraction_status"], "partial")
        self.assertIn("429", result["extraction_error"])
        # Rule output still usable, so ingestion is not blocked by an outage.
        self.assertEqual(result["identifiers"]["container_no"], ["CSQU3054383"])

    def test_successful_llm_call_produces_a_hybrid_record(self) -> None:
        llm_payload = {
            "doc_type": "arrival_notice",
            "doc_type_confidence": 0.95,
            "identifiers": {"container_no": [], "hs_code": "8471.30"},
            "route": {"pod": "Ho Chi Minh City"},
            "carrier": "MSC",
        }

        with patch.object(field_extract, "EXTRACTION_PROVIDER", "azure_openai"), patch.object(
            field_extract, "call_llm", return_value=llm_payload
        ):
            result = extract_fields("Arrival Notice", "ops@carrier.com", ARRIVAL_NOTICE)

        self.assertEqual(result["extraction_method"], "hybrid")
        self.assertEqual(result["identifiers"]["container_no"], ["CSQU3054383"])
        self.assertEqual(result["identifiers"]["hs_code"], "8471.30")
        self.assertEqual(result["route"]["pod"], "Ho Chi Minh City")
        self.assertEqual(result["carrier"], "MSC")

    def test_none_inputs_are_tolerated(self) -> None:
        with patch.object(field_extract, "EXTRACTION_PROVIDER", "none"):
            result = extract_fields(None, None, None)

        self.assertEqual(result["doc_type"], "other")


if __name__ == "__main__":
    unittest.main()
