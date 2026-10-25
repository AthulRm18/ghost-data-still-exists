"""test_llm_client.py - Unit tests for LLMClient wrapper and usage ledger integrity."""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

repo_root = str(Path(__file__).resolve().parent.parent.parent)
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from code.llm_client import (
    DeletionIntent,
    EvidenceExtraction,
    ExtractedResource,
    LLMClient,
)


import tempfile

class TestLLMClient(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_ledger = Path(self.temp_dir.name) / "test_ledger.json"
        self.test_cache = Path(self.temp_dir.name) / "test_cache.json"
        self.client = LLMClient(
            api_key="mock_key_for_testing",
            model_name="gemini-3.8-flash",
            ledger_file=self.test_ledger,
            replay_cache_file=self.test_cache,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_live_ledger_rejects_missing_response_usage(self):
        """A live ledger entry MUST fail if token counts did not come from a real response object."""
        with self.assertRaises(ValueError) as ctx:
            self.client._record_ledger_entry(
                caller="test_caller",
                input_hash="hash123",
                response_usage=None,  # No API response usage object!
                latency_seconds=1.2,
                is_replay=False,  # Live call without response object is prohibited
            )
        self.assertIn("valid API response usage metadata object", str(ctx.exception))

    def test_live_ledger_records_exact_response_tokens(self):
        """Verifies ledger row records token counts directly from the response usage metadata."""
        mock_usage = SimpleNamespace(
            prompt_token_count=1234,
            candidates_token_count=56,
            total_token_count=1290,
        )
        entry = self.client._record_ledger_entry(
            caller="test_live_caller",
            input_hash="hash_live_abc",
            response_usage=mock_usage,
            latency_seconds=0.85,
            is_replay=False,
        )
        self.assertEqual(entry["prompt_tokens"], 1234)
        self.assertEqual(entry["output_tokens"], 56)
        self.assertEqual(entry["total_tokens"], 1290)
        self.assertFalse(entry["is_replay"])

    def test_schemas(self):
        """Verifies schema validation for EvidenceExtraction and DeletionIntent."""
        ext = EvidenceExtraction(
            file_id="evidence_99",
            extracted_identifiers=["test@example.com"],
            resources=[
                ExtractedResource(
                    system_id="support_platform",
                    resource_id="support_123",
                    identifiers=["test@example.com"],
                )
            ],
        )
        self.assertEqual(ext.file_id, "evidence_99")
        self.assertEqual(len(ext.resources), 1)

        intent = DeletionIntent(
            authorizes_deletion=False,
            category="MARKETING_OPT_OUT",
            reason="User requested newsletter unsubscribe",
        )
        self.assertFalse(intent.authorizes_deletion)
        self.assertEqual(intent.category, "MARKETING_OPT_OUT")


if __name__ == "__main__":
    unittest.main()
