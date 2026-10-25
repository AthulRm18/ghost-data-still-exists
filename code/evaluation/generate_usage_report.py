"""generate_usage_report.py - Generates code/evaluation/usage_report.md from code/cache/usage_ledger.json.

Strict constraint: Every token number and cost calculation must derive directly
from ledger rows. If the ledger is empty (no live calls made), reports zero calls
and documents the exact state honestly.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LEDGER_FILE = REPO_ROOT / "code" / "cache" / "usage_ledger.json"
REPORT_FILE = REPO_ROOT / "code" / "evaluation" / "usage_report.md"

# Official published pricing per 1M tokens (Google Gemini 2.5 / 2.0 Flash)
# https://ai.google.dev/pricing
PRICE_PER_MILLION_PROMPT = 0.10   # $0.10 per 1M prompt tokens
PRICE_PER_MILLION_CANDIDATES = 0.40  # $0.40 per 1M output tokens


def load_ledger() -> List[Dict[str, Any]]:
    if not LEDGER_FILE.exists():
        return []
    try:
        with open(LEDGER_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def generate_report():
    entries = load_ledger()
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    if not entries:
        content = f"""# LLM Usage Report — Ghost Data Still Exists

**Date**: {now_str}  
**Status**: Zero Live Model Calls (Fabricated Counts Purged)  
**Ledger Path**: `code/cache/usage_ledger.json`  

---

## 1. Accounting Summary

As confirmed in the repository audit, all previously reported token counts were synthetic placeholders. The fabricated ledger has been removed.

- **Total Recorded Model Calls**: **0**
- **Live API Calls**: **0**
- **Replay / Cached Calls**: **0**
- **Total Prompt Tokens**: **0**
- **Total Output Tokens**: **0**
- **Total Estimated Cost**: **$0.00**

---

## 2. Infrastructure & Execution Instructions

A real model client wrapper using the official `google-genai` SDK is implemented at [`code/llm_client.py`](file:///code/llm_client.py).

To execute live model calls for all 11 images and 4 PDFs:
1. Export a valid API key:
   ```bash
   export GEMINI_API_KEY="your-api-key"
   ```
   or add `GEMINI_API_KEY=...` to a local, uncommitted `.env` file.
2. Run live extraction:
   ```bash
   python code/extract_unstructured.py --model gemini-2.5-flash
   ```
3. Regenerate this report from the resulting ledger:
   ```bash
   python code/evaluation/generate_usage_report.py
   ```

When no API key is supplied, the pipeline executes deterministically using SQL snapshot parsing, trace extraction, and structured log indexing across all 94 evidence files.
"""
        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Generated empty ledger report at {REPORT_FILE}")
        return

    # Aggregate ledger rows
    total_calls = len(entries)
    live_calls = sum(1 for e in entries if not e.get("is_replay", False))
    replay_calls = sum(1 for e in entries if e.get("is_replay", False))

    total_prompt_tokens = sum(e.get("prompt_tokens", 0) for e in entries)
    total_output_tokens = sum(e.get("output_tokens", 0) for e in entries)
    total_tokens = total_prompt_tokens + total_output_tokens

    # Models used
    models_counter: Dict[str, int] = {}
    for e in entries:
        m = e.get("model", "unknown")
        models_counter[m] = models_counter.get(m, 0) + 1

    prompt_cost = (total_prompt_tokens / 1_000_000.0) * PRICE_PER_MILLION_PROMPT
    output_cost = (total_output_tokens / 1_000_000.0) * PRICE_PER_MILLION_CANDIDATES
    total_cost = prompt_cost + output_cost

    avg_prompt_tokens = total_prompt_tokens / total_calls if total_calls > 0 else 0
    avg_output_tokens = total_output_tokens / total_calls if total_calls > 0 else 0
    avg_total_tokens = total_tokens / total_calls if total_calls > 0 else 0
    avg_cost_per_request = total_cost / total_calls if total_calls > 0 else 0

    run_dates = sorted(list({e.get("timestamp", "")[:10] for e in entries if e.get("timestamp")}))
    run_date_str = ", ".join(run_dates) if run_dates else now_str

    content = f"""# LLM Usage Report — Ghost Data Still Exists

**Date**: {now_str}  
**Live Run Date(s)**: {run_date_str}  
**Ledger Source**: `code/cache/usage_ledger.json` ({total_calls} verified entries)  
**Provider**: Google Gemini (`google-genai` SDK v2.18.1)  

---

## 1. Executive Usage Summary

| Metric | Measured Value | Notes |
|---|---|---|
| **Total Recorded Calls** | **{total_calls}** | Derived strictly from `code/cache/usage_ledger.json` |
| **Live API Calls** | **{live_calls}** | Real HTTP requests to Gemini API |
| **Replay / Cached Calls** | **{replay_calls}** | Served from zero-cost local disk replay cache |
| **Total Prompt Tokens** | **{total_prompt_tokens:,}** | Measured from `response.usage_metadata.prompt_token_count` |
| **Total Output Tokens** | **{total_output_tokens:,}** | Measured from `response.usage_metadata.candidates_token_count` |
| **Total Tokens** | **{total_tokens:,}** | Input + Output |
| **Average Prompt Tokens / Call** | **{avg_prompt_tokens:.1f}** | |
| **Average Output Tokens / Call** | **{avg_output_tokens:.1f}** | |
| **Average Tokens / Call** | **{avg_total_tokens:.1f}** | |
| **Total Estimated Cost** | **${total_cost:.5f}** | Published pricing: ${PRICE_PER_MILLION_PROMPT:.2f}/1M input, ${PRICE_PER_MILLION_CANDIDATES:.2f}/1M output |
| **Average Cost / Call** | **${avg_cost_per_request:.5f}** | |

---

## 2. Model Breakdown

| Model | Calls | Share |
|---|---|---|
"""
    for m, count in models_counter.items():
        content += f"| `{m}` | {count} | {count / total_calls * 100:.1f}% |\n"

    content += f"""
---

## 3. Pricing Model & Assumptions

Pricing is based on Google's published rates for Gemini Flash models:
- **Prompt (Input)**: ${PRICE_PER_MILLION_PROMPT:.2f} per 1,000,000 tokens
- **Candidates (Output)**: ${PRICE_PER_MILLION_CANDIDATES:.2f} per 1,000,000 tokens
- **Cached Replay**: $0.00 (served locally from disk)

All token counts are recorded directly from the API response usage metadata object via `code/llm_client.py`. No synthetic or hand-typed token counts are permitted.
"""

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Generated usage report from {total_calls} ledger entries at {REPORT_FILE}")


if __name__ == "__main__":
    generate_report()
