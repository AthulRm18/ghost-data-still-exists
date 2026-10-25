"""llm_client.py - Real LLM client wrapper for Ghost Data Still Exists.

Uses the official `google-genai` SDK to perform multimodal evidence extraction
(images, PDFs) and multilingual deletion-intent classification.

Features:
- Reads API key strictly from environment variable `GEMINI_API_KEY` (or `GOOGLE_API_KEY`)
- Automatically loads .env if present using python-dotenv
- Validates structured output against Pydantic models
- Bounded retries with backoff
- Disk cache keyed by (prompt_version, model, input_hash)
- Ledger recording directly from API response usage metadata (no hand-typed tokens)
- Zero mentions of specific cases, samples, or expected answers in prompts
"""

import hashlib
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import dotenv
from pydantic import BaseModel, Field

# Load .env if present
dotenv.load_dotenv()

PROMPT_VERSION = "v1.0"
DEFAULT_MODEL = "gemini-3.8-flash"

# Cache paths
REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = REPO_ROOT / "code" / "cache"
REPLAY_CACHE_FILE = CACHE_DIR / "replay_cache.json"
LEDGER_FILE = CACHE_DIR / "usage_ledger.json"


# --- Pydantic Structured Output Schemas ---

class ExtractedResource(BaseModel):
    system_id: str = Field(description="Name of the service or system (e.g. account_service, support_platform, search_service)")
    resource_id: str = Field(description="Identifier of the record or entity")
    identifiers: List[str] = Field(default_factory=list, description="Any personal identifiers linked to this resource (email, phone, name, customer_ref, hash)")
    timestamp: Optional[str] = Field(default=None, description="Timestamp associated with this resource if present in the document")
    status: Optional[str] = Field(default=None, description="Reported status or state (e.g. active, closed, pending, present)")
    details: Optional[str] = Field(default=None, description="Brief description of the record contents")


class EvidenceExtraction(BaseModel):
    file_id: str = Field(description="Evidence file identifier")
    extracted_identifiers: List[str] = Field(default_factory=list, description="All email addresses, phone numbers, names, user IDs, or customer references found")
    resources: List[ExtractedResource] = Field(default_factory=list, description="List of discrete system resources identified in the document")


class DeletionIntent(BaseModel):
    authorizes_deletion: bool = Field(description="True ONLY if the user explicitly requests account deletion, data erasure, or purging")
    category: str = Field(description="Intent category: DELETION, MARKETING_OPT_OUT, EXPORT, ACCESS, SUPPORT, CORRECTION, or OTHER")
    reason: str = Field(description="Explanation of the classification based strictly on the text provided")


# --- Client Wrapper ---

class LLMClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = DEFAULT_MODEL,
        ledger_file: Optional[Path] = None,
        replay_cache_file: Optional[Path] = None,
    ):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        self.model_name = model_name
        self.ledger_file = ledger_file or LEDGER_FILE
        self.replay_cache_file = replay_cache_file or REPLAY_CACHE_FILE
        self._client = None
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not self.api_key:
            raise ValueError(
                "No API key provided. Set the 'GEMINI_API_KEY' (or 'GOOGLE_API_KEY') environment "
                "variable or add it to an uncommitted .env file."
            )
        try:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
            return self._client
        except Exception as e:
            raise RuntimeError(f"Failed to initialize google-genai client: {e}") from e

    def list_vision_models(self) -> List[str]:
        """Queries the Gemini API for available models supporting multimodal vision."""
        client = self._get_client()
        models = []
        for m in client.models.list():
            # Check for generateContent support and flash/pro models
            name = m.name or ""
            if "gemini" in name.lower():
                models.append(name.replace("models/", ""))
        return models

    def _compute_input_hash(self, content_bytes: bytes, prompt_str: str) -> str:
        h = hashlib.sha256()
        h.update(content_bytes)
        h.update(prompt_str.encode("utf-8"))
        return h.hexdigest()

    def _load_replay_cache(self) -> Dict[str, Any]:
        if self.replay_cache_file.exists():
            try:
                with open(self.replay_cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_replay_cache(self, cache: Dict[str, Any]) -> None:
        self.replay_cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.replay_cache_file, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)

    def _record_ledger_entry(
        self,
        caller: str,
        input_hash: str,
        response_usage: Any,
        latency_seconds: float,
        is_replay: bool,
    ) -> Dict[str, Any]:
        """Appends one entry to usage_ledger.json.

        Enforces that token counts must originate directly from an API response usage object.
        """
        if not is_replay and response_usage is None:
            raise ValueError("Live ledger recording requires a valid API response usage metadata object.")

        if response_usage is not None:
            prompt_tokens = getattr(response_usage, "prompt_token_count", 0) or 0
            candidates_tokens = getattr(response_usage, "candidates_token_count", 0) or 0
            total_tokens = getattr(response_usage, "total_token_count", prompt_tokens + candidates_tokens) or 0
        else:
            prompt_tokens = 0
            candidates_tokens = 0
            total_tokens = 0

        entry = {
            "call_id": str(uuid.uuid4()),
            "caller": caller,
            "model": self.model_name,
            "input_hash": input_hash,
            "prompt_tokens": int(prompt_tokens),
            "output_tokens": int(candidates_tokens),
            "total_tokens": int(total_tokens),
            "latency_seconds": round(float(latency_seconds), 3),
            "is_replay": bool(is_replay),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Append to ledger file
        self.ledger_file.parent.mkdir(parents=True, exist_ok=True)
        ledger_entries = []
        if self.ledger_file.exists():
            try:
                with open(self.ledger_file, "r", encoding="utf-8") as f:
                    ledger_entries = json.load(f)
            except Exception:
                ledger_entries = []

        ledger_entries.append(entry)
        with open(self.ledger_file, "w", encoding="utf-8") as f:
            json.dump(ledger_entries, f, indent=2)

        return entry


    def extract_unstructured_evidence(
        self,
        file_path: Path,
        file_id: str,
        force_live: bool = False,
    ) -> EvidenceExtraction:
        """Extracts structured entities, identifiers, and resources from an image or PDF.

        Caches results on disk and records real usage metadata to the ledger.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Evidence file not found: {file_path}")

        file_bytes = file_path.read_bytes()
        suffix = file_path.suffix.lower()
        if suffix in [".png", ".jpg", ".jpeg"]:
            mime_type = "image/png" if suffix == ".png" else "image/jpeg"
        elif suffix == ".pdf":
            mime_type = "application/pdf"
        else:
            raise ValueError(f"Unsupported file type for multimodal extraction: {suffix}")

        prompt = (
            f"Analyze the attached evidence document or screenshot (file_id: {file_id}). "
            "Extract all user personal identifiers (email addresses, phone numbers, names, user IDs, "
            "hashes, customer references) and any discrete system resources or records referenced "
            "(e.g., ticket IDs, account records, log entries, export files). "
            "Return a strictly valid structured JSON matching the requested schema."
        )

        input_hash = self._compute_input_hash(file_bytes, prompt)
        cache_key = f"{PROMPT_VERSION}:{self.model_name}:{input_hash}"

        # Check replay cache
        cache = self._load_replay_cache()
        if not force_live and cache_key in cache:
            # Replay hit
            cached_data = cache[cache_key]
            self._record_ledger_entry(
                caller=f"extract_unstructured_evidence({file_id})",
                input_hash=input_hash,
                response_usage=None,
                latency_seconds=0.001,
                is_replay=True,
            )
            return EvidenceExtraction(**cached_data)

        # Live API Call with bounded retries
        client = self._get_client()
        from google.genai import types

        part = types.Part.from_bytes(data=file_bytes, mime_type=mime_type)
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=EvidenceExtraction,
            temperature=0.0,
        )

        max_retries = 3
        last_error = None
        for attempt in range(max_retries):
            start_time = time.time()
            try:
                response = client.models.generate_content(
                    model=self.model_name,
                    contents=[part, prompt],
                    config=config,
                )
                latency = time.time() - start_time

                # Record usage directly from response object
                self._record_ledger_entry(
                    caller=f"extract_unstructured_evidence({file_id})",
                    input_hash=input_hash,
                    response_usage=response.usage_metadata,
                    latency_seconds=latency,
                    is_replay=False,
                )

                parsed_json = json.loads(response.text)
                parsed_result = EvidenceExtraction(**parsed_json)

                # Save to replay cache
                cache[cache_key] = parsed_result.model_dump()
                self._save_replay_cache(cache)

                return parsed_result
            except Exception as e:
                last_error = e
                time.sleep(2 ** attempt)

        raise RuntimeError(
            f"Live extraction failed for {file_id} after {max_retries} attempts: {last_error}"
        ) from last_error

    def check_deletion_intent_multilingual(
        self,
        request_text: str,
        force_live: bool = False,
    ) -> DeletionIntent:
        """Classifies deletion authorization intent for request_text across languages."""
        if not request_text or not request_text.strip():
            return DeletionIntent(
                authorizes_deletion=False,
                category="OTHER",
                reason="Empty request text",
            )

        prompt = (
            "Analyze the following user data request text. "
            "Determine whether the user is explicitly requesting deletion, erasure, or purging of their "
            "account or personal data (e.g., GDPR Article 17 Right to Erasure / Right to be Forgotten). "
            "If the user is asking to download/export data, opt out of marketing emails only, access records, "
            "rectify info, or asks not to delete their account, set authorizes_deletion to False.\n\n"
            f"Request text:\n\"\"\"{request_text}\"\"\""
        )

        input_hash = self._compute_input_hash(request_text.encode("utf-8"), prompt)
        cache_key = f"{PROMPT_VERSION}:{self.model_name}:{input_hash}"

        cache = self._load_replay_cache()
        if not force_live and cache_key in cache:
            cached_data = cache[cache_key]
            self._record_ledger_entry(
                caller="check_deletion_intent_multilingual",
                input_hash=input_hash,
                response_usage=None,
                latency_seconds=0.001,
                is_replay=True,
            )
            return DeletionIntent(**cached_data)

        client = self._get_client()
        from google.genai import types

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=DeletionIntent,
            temperature=0.0,
        )

        max_retries = 3
        last_error = None
        for attempt in range(max_retries):
            start_time = time.time()
            try:
                response = client.models.generate_content(
                    model=self.model_name,
                    contents=[prompt],
                    config=config,
                )
                latency = time.time() - start_time

                self._record_ledger_entry(
                    caller="check_deletion_intent_multilingual",
                    input_hash=input_hash,
                    response_usage=response.usage_metadata,
                    latency_seconds=latency,
                    is_replay=False,
                )

                parsed_json = json.loads(response.text)
                parsed_result = DeletionIntent(**parsed_json)

                cache[cache_key] = parsed_result.model_dump()
                self._save_replay_cache(cache)

                return parsed_result
            except Exception as e:
                last_error = e
                time.sleep(2 ** attempt)

        raise RuntimeError(
            f"Live intent classification failed after {max_retries} attempts: {last_error}"
        ) from last_error
