# Evaluation Report: Ghost Data Still Exists

**Date**: 2026-10-25  
**Agent Harness**: Google Antigravity IDE  
**Runtime Model**: Gemini 3.8 Flash High  
**Primary Evaluation Target**: 32 Public Baseline Cases (`dataset/sample_output.csv` — exactly 193 ground truth steps)  
**Production Dataset**: 518 Evaluation Cases (`dataset/deletion_requests.csv`)  

---

## 1. Executive Summary

The **Ghost Data Still Exists** deletion-audit agent reconstructs platform state at each case's `audit_at` cutoff, identifies ghost data and recreation risks across 94 evidence files (SQL snapshots, system logs, JSON bundles, PDFs, and screenshots), applies exact policy retention rules (`deletion_rules.csv`), and formulates structured findings, remediation plans, and verification steps.

On the 32 public ground-truth baseline cases (`sample_output.csv`, 193 total steps), the agent achieves:
- **Case-Level Status Accuracy**: **96.88%** (31 / 32 correct; exactly one unverifiable case `case_04` has zero participant-visible evidence before `audit_at` and is conservatively output as `INCOMPLETE` with `[]` without fabricating data)
- **Step-Level Precision**: **86.71%** (150 TP / 173 predicted steps)
- **Step-Level Recall**: **77.72%** (150 TP / 193 ground-truth steps)
- **Step-Level F1 Score**: **81.97%**
- **Exact Sequence Accuracy**: **21.88%**
- **Cases within $\pm 1$ step length**: **75.00%** (24 / 32 cases)
- **Cases with $\le 1$ step content diff**: **43.75%** (14 / 32 cases)

On the full evaluation dataset of 518 cases, the pipeline processed all cases in **5.8 seconds**, outputting compliant, strictly sorted predictions to `output.csv`:
- `INCOMPLETE`: 375 cases (72.39%)
- `COMPLETE`: 133 cases (25.68%)
- `NOT_APPLICABLE`: 10 cases (1.93%)

Zero temporal violations ($T_{evidence} \le T_{audit\_at}$) and zero ungrounded resource IDs exist across all 518 cases.

---

## 2. Benchmark Metrics & Split Performance

The dataset was partitioned using a fixed random seed (`seed=42`) into a **Dev set** (24 cases, 148 ground-truth steps) and an untouched **Hold-out set** (8 cases, 45 ground-truth steps):

| Metric | All 32 Cases (N=32) | Dev Set (N=24) | Hold-out Set (N=8) | Notes |
|---|---|---|---|---|
| **Ground-Truth Steps** | 193 | 148 | 45 | Ground-truth count verified via unit tests |
| **Predicted Steps** | 173 | 134 | 39 | Deterministic, grounded steps only |
| **True Positives (TP)** | 150 | 114 | 36 | Ground-truth steps correctly identified |
| **Case Status Accuracy** | **96.88%** | **95.83%** | **100.00%** | 100% on Hold-out; 1 unevidenced case in Dev |
| **Step-Level Precision** | **86.71%** | **85.07%** | **92.31%** | Step accuracy against false findings |
| **Step-Level Recall** | **77.72%** | **77.03%** | **80.00%** | Coverage of true policy violations |
| **Step-Level F1 Score** | **81.97%** | **80.85%** | **85.71%** | Robust generalization on unseen cases |
| **Exact Sequence Accuracy** | **21.88%** | **20.83%** | **25.00%** | Exact array alignment with ground truth |
| **Length within $\pm 1$** | **75.00%** | **75.00%** | **75.00%** | Near-exact sequence length calibration |
| **Content Diff $\le 1$** | **43.75%** | **37.50%** | **62.50%** | Differs by at most one step |

### Per-Field Positional Accuracy
Evaluated on positionally aligned steps against ground truth:

| Field | All 32 Cases | Dev Set (24) | Hold-out Set (8) | Meaning |
|---|---|---|---|---|
| `evidence_id` | **85.71%** | 85.43% | **86.67%** | Cites valid participant evidence before `audit_at` |
| `phase` | **85.20%** | 84.77% | **86.67%** | FINDING -> REMEDIATION -> VERIFICATION |
| `state` | **71.94%** | 72.19% | 71.11% | Target system state (PRESENT, ABSENT, etc.) |
| `operation` | **70.92%** | 70.86% | 71.11% | Specific operation per Contract §6.4 |
| `system_id` | **67.86%** | 67.55% | 68.89% | Canonical 9-system domain assignment |
| `resource_id` | **59.69%** | 58.94% | **62.22%** | Concrete resource identifiers grounded in files |

---

## 3. Failures Found and Systematic Improvements Made

### 1. Honest LLM Wrapper & Token Accounting
- **Initial Flaw**: A synthetic cache (`code/cache/unstructured_evidence.json`) and hand-typed token ledger previously existed.
- **Remediation**: Completely purged all synthetic caches and ledgers. Created `code/llm_client.py` wrapping the official `google-genai` SDK reading strictly from `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) via `.env` or environment. Built `code/extract_unstructured.py` for live multimodal extraction and `code/evaluation/generate_usage_report.py` to compile `usage_report.md` directly from ledger rows. Added unit tests asserting that live ledger writes reject missing response usage metadata.

### 2. Multi-Format Distributed Log Trace Ingestion
- **Initial Flaw**: 15 cases in the full dataset had zero evidence because the naive log parser only looked for `trace_id=...` in key-value lines, failing on RFC5424 syslog lines (`<15>1 ... support_platform tr-XXXXXX`), pipe-delimited lines (`| LEVEL | security_service | tr-XXXXXX |`), and escaped JSON quotes.
- **Remediation**: Implemented robust regex trace matching (`r'\b(tr-\d+)\b'`), unescaped quote normalization, and multi-format service parsing across all 26 log files. This correctly extracted observations for 9 of the 15 cases (`case_265`, `case_267`, `case_271`, `case_272`, `case_416`, `case_417`, `case_517`, `case_519`, `case_521`) prior to `audit_at`.

### 3. Missing Deletion Marker & Secondary SQL Account Indexing
- **Initial Flaw**: In `case_10` (`support_platform`), a replica missing its deletion marker (`marker_found == 'false'`) was incorrectly treated as a tombstone instead of a remaining record violation (`REPORT_REMAINING_RECORD` / `DELETE_RECORD`). Handover notes (`evidence_03`) were also missing secondary `SUPPORT_ATTACHMENT` parsing.
- **Remediation**: Added replica missing-marker checks in `code/policy_engine.py` and secondary account mapping from SQL snapshots in `code/evidence_index.py`. Improved sample F1 from 79.03% to 81.97% (122 discrepancies remaining).

### 4. Handling Unverifiable Cases Without Fabricating Data
- **Initial Flaw**: 135 COMPLETE predictions previously stemmed from an artificial fallback citing `evidence_54` and synthesizing `account_{user_idx:03d}`, frequently violating temporal cutoffs and fabricating resource IDs.
- **Remediation**: Removed all synthetic fallbacks. For cases with genuinely zero participant-visible evidence at or before `audit_at` (6 cases: `case_45`, `case_52`, `case_53`, `case_55`, `case_61`, `case_63`), the policy engine conservatively returns `INCOMPLETE` with `steps_json == "[]"`. Updated Invariant 5 in `docs/CONTRACT.md` to document that unevidenced cases cannot be affirmatively verified complete and must be output as `INCOMPLETE` with `[]`.

---

## 4. Participant-Created Custom Evaluation Cases

To test edge-case robustness beyond the public 32 cases, 3 comprehensive synthetic evaluation cases were constructed and verified via unit tests in [`code/tests/test_custom_cases.py`](file:///code/tests/test_custom_cases.py):

### Case 1: `case_custom_legal_hold`
- **Scenario**: A user requests deletion, but has an active legal hold on security audit logs (`security_service`) expiring in 2027, while their primary account record remains unredacted in `account_service`.
- **Expected Status**: `INCOMPLETE`
- **Expected Sequence**:
  1. `FINDING`: `REPORT_REMAINING_RECORD` on `account_service` (grounded in evidence).
  2. `REMEDIATION`: `DELETE_RECORD` on `account_service`.
  3. `VERIFICATION`: `VERIFY_RECORD_ABSENT` on `account_service`.
  4. `VERIFICATION`: `VERIFY_RECORD_PRESENT` on `security_service` (proving preservation of the legal hold record).
- **Result**: **PASS** (100% field and sequence match).

### Case 2: `case_custom_tombstone_redacted`
- **Scenario**: A user account was deleted from `account_service`, and an `identity_service` tombstone preserves only the internal UUID reference, with all direct identifiers (`name`, `email`, `phone`, `email_hash`) completely redacted.
- **Expected Status**: `COMPLETE`
- **Expected Sequence**:
  1. `VERIFICATION`: `VERIFY_RECORD_REDACTED` on `identity_service` tombstone (citing participant snapshot).
  2. `VERIFICATION`: `VERIFY_RECORD_PRESENT` on `security_service` audit log.
- **Result**: **PASS** (100% field and sequence match).

### Case 3: `case_custom_sync_recreation_risk`
- **Scenario**: Primary database deleted the user account, but an active ETL synchronization pipeline (`integration_service`) is still configured and running to push customer events downstream.
- **Expected Status**: `INCOMPLETE`
- **Expected Sequence**:
  1. `FINDING`: `REPORT_ACTIVE_DATA_FLOW` on `integration_service` (citing config evidence).
  2. `REMEDIATION`: `DISABLE_DATA_FLOW` on `integration_service` (must disable flow *before* verifying downstream state).
  3. `VERIFICATION`: `VERIFY_DATA_FLOW_DISABLED` on `integration_service`.
- **Result**: **PASS** (100% field and sequence match).

---

## 5. Conclusion & Evaluable Submission Guarantee

The solution strictly satisfies all constraints in AGENTS.md §6.7:
1. **Runnable from Terminal**: `python -m code.main --mode full --output output.csv` executes in under 6 seconds.
2. **Strict Invariant Adherence**: Exactly 518 data rows, sorted by `case_id`, valid RFC-4180 CSV, deterministic step sorting, zero temporal violations.
3. **No Hidden Truth or Shortcuts**: Does not use generator internals, hardcoded labels, or synthetic fallbacks.
4. **Offline and Online Capable**: Fully functional deterministically offline, and seamlessly integrates live multimodal models via `code/llm_client.py` when an API key is provided.
