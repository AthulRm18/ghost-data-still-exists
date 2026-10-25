# LLM Usage Report — Ghost Data Still Exists

**Date**: 2026-10-24 19:32:29 UTC  
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
