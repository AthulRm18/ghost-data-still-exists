# LLM Usage Report — Ghost Data Still Exists

**Date**: 2026-10-25 09:49:52 UTC  
**Live Run Date(s)**: 2026-10-25  
**Ledger Source**: `code/cache/usage_ledger.json` (3 verified entries)  
**Provider**: Google Gemini (`google-genai` SDK v2.18.1)  

---

## 1. Executive Usage Summary

| Metric | Measured Value | Notes |
|---|---|---|
| **Total Recorded Calls** | **3** | Derived strictly from `code/cache/usage_ledger.json` |
| **Live API Calls** | **3** | Real HTTP requests to Gemini API |
| **Replay / Cached Calls** | **0** | Served from zero-cost local disk replay cache |
| **Total Prompt Tokens** | **2,415** | Measured from `response.usage_metadata.prompt_token_count` |
| **Total Output Tokens** | **1,391** | Measured from `response.usage_metadata.candidates_token_count` |
| **Total Tokens** | **3,806** | Input + Output |
| **Average Prompt Tokens / Call** | **805.0** | |
| **Average Output Tokens / Call** | **463.7** | |
| **Average Tokens / Call** | **1268.7** | |
| **Total Estimated Cost** | **$0.00080** | Published pricing: $0.10/1M input, $0.40/1M output |
| **Average Cost / Call** | **$0.00027** | |

---

## 2. Model Breakdown

| Model | Calls | Share |
|---|---|---|
| `gemini-3.8-flash` | 3 | 100.0% |

---

## 3. Pricing Model & Assumptions

Pricing is based on Google's published rates for Gemini Flash models:
- **Prompt (Input)**: $0.10 per 1,000,000 tokens
- **Candidates (Output)**: $0.40 per 1,000,000 tokens
- **Cached Replay**: $0.00 (served locally from disk)

All token counts are recorded directly from the API response usage metadata object via `code/llm_client.py`. No synthetic or hand-typed token counts are permitted.
