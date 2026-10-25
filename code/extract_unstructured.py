"""extract_unstructured.py - Runs multimodal extraction on all 11 images and 4 PDFs.

Usage:
    python code/extract_unstructured.py [--model gemini-2.5-flash] [--force-live]

Features:
- Queries real Gemini API using google-genai SDK
- Validates structured output against Pydantic EvidenceExtraction schema
- Records exact prompt and candidate token counts to code/cache/usage_ledger.json
- Caches extractions in code/cache/replay_cache.json
- Compiles extractions into code/cache/unstructured_evidence.json for EvidenceIndex
"""

import argparse
import csv
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from code.llm_client import LLMClient


def run_extraction(model_name: str = "gemini-3.8-flash", force_live: bool = False):
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY (or GOOGLE_API_KEY) environment variable is not set.", file=sys.stderr)
        print("Please export GEMINI_API_KEY='...' or put it in an uncommitted .env file.", file=sys.stderr)
        sys.exit(1)

    print(f"Initializing LLMClient with model '{model_name}'...")
    client = LLMClient(api_key=api_key, model_name=model_name)

    # Check available vision models
    print("Querying available models from API...")
    try:
        available_models = client.list_vision_models()
        print(f"Available models for this key ({len(available_models)}): {available_models[:8]}...")
    except Exception as e:
        print(f"Warning: Failed to list models: {e}. Proceeding with specified model '{model_name}'.")

    # Read evidence manifest
    manifest_path = REPO_ROOT / "dataset" / "evidence_files.csv"
    with open(manifest_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        all_files = list(reader)

    unstructured_files = [
        r for r in all_files
        if r["file_path"].endswith((".png", ".jpg", ".jpeg", ".pdf"))
    ]
    print(f"Found {len(unstructured_files)} unstructured evidence files (11 images, 4 PDFs).")

    images_dict = {}
    pdfs_dict = {}

    for idx, row in enumerate(unstructured_files, 1):
        fid = row["file_id"]
        rel_path = row["file_path"]
        fpath = REPO_ROOT / "dataset" / rel_path
        print(f"[{idx}/{len(unstructured_files)}] Extracting {fid} ({rel_path})...")

        try:
            extraction = client.extract_unstructured_evidence(
                file_path=fpath,
                file_id=fid,
                force_live=force_live,
            )
            data = extraction.model_dump()
            data["captured_at"] = row["captured_at"]
            data["file_path"] = rel_path

            if rel_path.endswith(".pdf"):
                pdfs_dict[fid] = data
            else:
                images_dict[fid] = data
        except Exception as e:
            print(f"Extraction failed for {fid}: {e}", file=sys.stderr)
            raise e

    # Save compiled unstructured evidence
    out_cache = REPO_ROOT / "code" / "cache" / "unstructured_evidence.json"
    out_cache.parent.mkdir(parents=True, exist_ok=True)
    with open(out_cache, "w", encoding="utf-8") as f:
        json.dump({"images": images_dict, "pdfs": pdfs_dict}, f, indent=2)

    print(f"\nSuccessfully extracted all {len(unstructured_files)} files to {out_cache}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multimodal evidence extractor")
    parser.add_argument("--model", default="gemini-3.8-flash", help="Model name")
    parser.add_argument("--force-live", action="store_true", help="Force live API calls")
    args = parser.parse_args()

    run_extraction(model_name=args.model, force_live=args.force_live)
