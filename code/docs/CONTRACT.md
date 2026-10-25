# CONTRACT.md — Solution & Evaluation Contract

This document specifies the strict technical contract that any pipeline implementation must satisfy for the **Ghost Data Still Exists** challenge. All invariants defined here are mandatory and verified by the evaluation scorer and contract tests.

---

## 1. Output Format Specification

### 1.1 Output File
- **Path**: `output.csv` (at repository root)
- **Header**: `case_id,deletion_status,steps_json`
- **Encoding**: UTF-8 without BOM, standard RFC-4180 CSV formatting.
- **Row Count**: Exactly 518 data rows plus 1 header row (matching all cases in `dataset/deletion_requests.csv`).
- **Row Ordering**: Sorted by `case_id` ascending.

### 1.2 Column Definitions
1. **`case_id`** (`string`, non-empty):
   - Exactly matches `case_id` in `dataset/deletion_requests.csv`.
2. **`deletion_status`** (`enum`):
   - Allowed values: `COMPLETE`, `INCOMPLETE`, `NOT_APPLICABLE`.
   - `NOT_APPLICABLE`: Request does not authorize deletion (opt-out, export, rectification, login reset, inquiry).
   - `COMPLETE`: All prohibited personal data is eliminated/redacted across all copies and replicas by `audit_at`, no active sync/restore risks exist, and all policy-required retained records remain intact.
   - `INCOMPLETE`: Prohibited personal data remains in primary or replica systems at `audit_at`, unredacted PII is exposed, or active synchronization/restore flows threaten recreation.
3. **`steps_json`** (`JSON string`):
   - Valid JSON array string representing an ordered list of step objects.
   - If `deletion_status == "NOT_APPLICABLE"`, `steps_json` **MUST** be `[]`.
   - If `deletion_status == "COMPLETE"`, `steps_json` contains **only** `VERIFICATION` steps proving the compliant state at `audit_at`.
   - If `deletion_status == "INCOMPLETE"`, `steps_json` contains `FINDING` steps, followed by `REMEDIATION` steps, followed by post-remediation `VERIFICATION` steps.

---

## 2. Step Object Schema & Ground-Truth Vocabulary

Each step in the `steps_json` array is a JSON object with exactly the following 7 fields:

```json
{
  "step_no": 1,
  "phase": "FINDING",
  "system_id": "account_service",
  "resource_id": "account_005",
  "operation": "REPORT_REMAINING_RECORD",
  "state": "PRESENT",
  "evidence_id": "evidence_54"
}
```

### 2.1 Ground-Truth System and Resource Vocabulary
Derived directly from empirical analysis of `sample_output.csv` and repository evidence, exactly 9 `system_id` values exist. Each maps 1-to-1 to a distinct `resource_id` prefix:

| System ID | Occurrence Count | Resource ID Prefix | Concrete Examples | Meaning / Domain |
|---|---|---|---|---|
| `account_service` | 38 | `account_` | `account_005`, `account_7566`, `account_994` | Primary & replica account databases |
| `search_service` | 36 | `search_` | `search_001`, `search_052`, `search_1308` | Customer search index clusters |
| `support_platform` | 27 | `support_` | `support_001`, `support_002`, `support_864` | Support tickets & customer service attachments |
| `analytics_platform` | 25 | `analytics_` | `analytics_9406`, `analytics_2034`, `analytics_9914` | Customer analytics reports & data warehouse |
| `security_service` | 24 | `audit_record_` | `audit_record_2016`, `audit_record_4902` | Security audit & access event logs |
| `integration_service` | 21 | `data_flow_` | `data_flow_9522`, `data_flow_9846` | Data synchronization pipelines & ETL jobs |
| `backup_service` | 12 | `backup_` | `backup_4978`, `backup_3870`, `backup_3245` | Backup snapshots & recovery archives |
| `export_service` | 6 | `export_` | `export_001` | Export job dumps & portable data bundles |
| `identity_service` | 4 | `tombstone_` | `tombstone_440`, `tombstone_9178` | Account tombstone identity references |

### 2.2 Field Constraints
- `step_no` (`integer >= 1`): Consecutively numbered starting at 1 (`1, 2, 3, ...`). No gaps, no duplicate numbers.
- `phase` (`enum`): `"FINDING"`, `"REMEDIATION"`, or `"VERIFICATION"`.
- `system_id` (`string`, non-empty): Must be one of the 9 valid system IDs listed above.
- `resource_id` (`string`, non-empty): Identifier of the record or flow matching the system's resource prefix.
- `operation` (`enum`): One of the 15 allowed operations listed in §3.
- `state` (`enum`): The state bound to the chosen operation (see §3).
- `evidence_id` (`string`):
  - In `FINDING` steps: Must be a non-empty participant-visible ID (`evidence_XX`, `activity_XXXX`, or `audit_XXXX`).
  - In `COMPLETE` case `VERIFICATION` steps: Must be a non-empty participant-visible ID proving compliant state as of `audit_at`.
  - In `INCOMPLETE` case `REMEDIATION` and `VERIFICATION` steps: **MUST be empty string `""`** (denoting future remediation plan).

---

## 3. Allowed Operations and Associated States

No operations or states outside this table are allowed.

### 3.1 Phase: FINDING
| Operation | Required State | Meaning |
|---|---|---|
| `REPORT_REMAINING_RECORD` | `PRESENT` | A record that should have been deleted still exists in primary or replica. |
| `REPORT_EXPOSED_PII` | `PRESENT` | Record is permitted to remain, but direct identifiers that policy requires redacted are exposed. |
| `REPORT_ACTIVE_DATA_FLOW` | `ACTIVE` | An active sync process can copy or recreate the user's data downstream. |
| `REPORT_RESTORE_RISK` | `ACTIVE` | A backup or restore path exists that could restore deleted user data. |

### 3.2 Phase: REMEDIATION
| Operation | Required State | Meaning |
|---|---|---|
| `DISABLE_DATA_FLOW` | `DISABLED` | Stop an active synchronization or data pipeline process. |
| `BLOCK_RESTORE` | `BLOCKED` | Mark or isolate an affected backup so it cannot restore deleted data. |
| `DELETE_RECORD` | `ABSENT` | Delete the entire prohibited record from the target system. |
| `REDACT_RECORD` | `REDACTED` | Retain the record but remove prohibited direct identifiers (name, email, phone). |
| `ANONYMIZE_RECORD` | `ANONYMIZED` | Irreversibly unlink the record from the subject. |

### 3.3 Phase: VERIFICATION
| Operation | Required State | Meaning |
|---|---|---|
| `VERIFY_RECORD_ABSENT` | `ABSENT` | Confirm that a prohibited record does not exist. |
| `VERIFY_RECORD_PRESENT` | `PRESENT` | Confirm that a policy-required retained record exists (e.g. audit log, legal hold). |
| `VERIFY_RECORD_REDACTED` | `REDACTED` | Confirm that required identifiers were removed from retained record/tombstone. |
| `VERIFY_RECORD_ANONYMIZED` | `ANONYMIZED` | Confirm that record is unlinked and anonymized. |
| `VERIFY_DATA_FLOW_DISABLED` | `DISABLED` | Confirm that synchronization pipeline is inactive. |
| `VERIFY_RESTORE_BLOCKED` | `BLOCKED` | Confirm that backup cannot restore affected data. |

---

## 4. Deterministic Step Sorting Key

Every `steps_json` array must be sorted deterministically using the following 4-tuple key:

```text
sort_key = (phase_rank, operation_rank, system_id, resource_id)
```

1. **`phase_rank`**:
   - `FINDING` = 0
   - `REMEDIATION` = 1
   - `VERIFICATION` = 2
2. **`operation_rank`**:
   - Within `FINDING`:
     - `REPORT_REMAINING_RECORD` = 0
     - `REPORT_EXPOSED_PII` = 1
     - `REPORT_ACTIVE_DATA_FLOW` = 2
     - `REPORT_RESTORE_RISK` = 3
   - Within `REMEDIATION`:
     - `DISABLE_DATA_FLOW` = 0
     - `BLOCK_RESTORE` = 1
     - `DELETE_RECORD` = 2
     - `REDACT_RECORD` = 3
     - `ANONYMIZE_RECORD` = 4
   - Within `VERIFICATION`:
     - `VERIFY_RECORD_ABSENT` = 0
     - `VERIFY_RECORD_PRESENT` = 1
     - `VERIFY_RECORD_REDACTED` = 2
     - `VERIFY_RECORD_ANONYMIZED` = 3
     - `VERIFY_DATA_FLOW_DISABLED` = 4
     - `VERIFY_RESTORE_BLOCKED` = 5
3. **`system_id`**: Plain string ascending (ASCII / lexicographical order).
4. **`resource_id`**: Plain string ascending (ASCII / lexicographical order).

After sorting by this key, `step_no` is reassigned consecutively: `1, 2, ..., N`.

---

## 5. Temporal Validity, Evidence Rules & Underspecified Edge Cases

### 5.1 Cutoff at `audit_at`
- State reconstruction for each case considers **only** facts, snapshots, logs, and activity entries timestamped **at or before** that case's `audit_at`.
- Any evidence file with `captured_at > audit_at` **must be completely ignored** for that case.

### 5.2 Decided Rule: Record State in Absence of Evidence (Synthesis of A and C; B Rejected)

**Binding Decision**: The pipeline adopts a synthesis of **Option A** (evidence strictly required for findings) and **Option C** (affirmative proof required for complete verification). **Option B is rejected**.

#### Grounding & Rejection of Option B from Sample Evidence:
1. `reported_status` must **never** decide or influence deletion status:
   - In `case_02`, `reported_status` is `PARTIALLY_COMPLETE`, but the ground-truth answer is **`COMPLETE`** because evidence proves the compliant state at `audit_at`.
   - In `case_09`, `reported_status` is `NOT_STARTED`, but the ground-truth answer is `INCOMPLETE` strictly because of the restore risk documented in `evidence_93`, **not** because of `reported_status`.
   - Workflow statuses and activity results are claims, not proof, and must never decide case status.
2. **Finding Evidence Rule (from Option A)**:
   - Every `FINDING` step strictly requires participant-visible evidence captured at or before `audit_at`. Across all 32 sample cases, 100% of finding steps cite a valid evidence ID.
   - An unevidenced system or record can **never** trigger a finding; ghost records, exposed PII, active sync flows, and restore risks cannot be assumed without evidence.
3. **Complete Case Verification Rule (from Option C)**:
   - A case is decided as **`COMPLETE`** only when:
     1. Zero findings exist (no remaining records, exposed PII, active sync flows, or restore risks evidenced at $T \le T_{audit\_at}$).
     2. Affirmative participant-visible evidence proves the required compliant state for every record emitted in `VERIFICATION` steps (e.g. `evidence_54` proving absence in `case_01`/`case_02`, or `evidence_94` readback logs in `case_03`).
   - If affirmative evidence is absent for a record that must be proven compliant, or if a finding exists, the case is `INCOMPLETE`.


### 5.3 Activity Logs vs. Database Snapshots (Assumption to be Tested)
- **Snapshot Newer than Activity ($T_{snap} > T_{activity}$)**:
  - When a database snapshot captured *after* an activity event contradicts that event (e.g. activity claimed `DELETE_RECORD / SUCCESS`, but the later replica snapshot still contains the record), the physical database snapshot takes precedence and proves the record is `PRESENT`.
- **Snapshot Older than Activity ($T_{snap} < T_{activity}$)**:
  - When a database snapshot at 10:00 shows a record `PRESENT`, but an activity event at 11:00 claims `DELETE_RECORD / SUCCESS` (with `audit_at` at 12:00), how is the record state decided?
  - *Hypothesis 1*: The subsequent activity log is accepted as successful execution, making the record `ABSENT`.
  - *Hypothesis 2*: The activity log is treated as an unverified claim; without a post-activity snapshot or readback log, absence cannot be confirmed.
  - *Empirical testing*: This assumption will be validated directly against the 32 sample cases during scorer development.

### 5.4 Citation Rules
- When citing evidence in `FINDING` or `COMPLETE` `VERIFICATION`, use the participant-visible `file_id` (from `evidence_files.csv`), `activity_id` (from `system_activity.csv`), or `audit_id` (from `user_audit_log.csv`).
- Never cite hidden truth or files outside `dataset/evidence/`.

### 5.5 Pre-Request Temporal Scoping (Design Assumption)
- **Assumption Formulation**: Evidence captured prior to the user's deletion request (`captured_at < requested_at`) is treated as historical operational data and **cannot support a post-request policy violation finding** (`REPORT_REMAINING_RECORD`, `REPORT_EXPOSED_PII`, etc.).
- **Spec Status**: While AGENTS.md §6.2 dictates that only evidence timestamped at or before `audit_at` may be considered, the specification does not explicitly state whether evidence captured before `requested_at` can support a finding.
- **Empirical Sensitivity Analysis**:
  - **Sample Cases (32 public requests)**: Exactly 3 cases depend directly on this rule: `case_21`, `case_27`, and `case_28` (all ground-truth `COMPLETE`). If pre-request evidence is evaluated for findings, older pre-request snapshots (such as June 2026 snapshot `evidence_26`, captured months before the user requested deletion in August or September) falsely trigger remaining record findings, misclassifying these cases as `INCOMPLETE` and dropping status accuracy from **100.0% (32/32)** to **90.6% (29/32)**.
  - **Evaluation Cases (518 requests)**: Exactly 1 prediction changes status if this rule is removed: `case_33` transitions from `COMPLETE` to `INCOMPLETE` (99.8% stability).
- **Binding Contract Decision**: Historical snapshots created before `requested_at` represent valid pre-request platform data and are excluded from generating non-compliance findings.

### 5.6 Activity Linking Heuristic for Primary Accounts
- **Rule Definition**: For a user whose `account_service` resource is not found in any other pre-audit evidence, the `deletion_worker` `DELETE_RECORD` activity on `account_service` closest in time to `reported_at` within a stated window of $\pm 600$s ($10$ minutes) identifies the user's primary account.
- **Disambiguation Guard**: The heuristic triggers **only** when exactly one candidate matches within that stated window (`len(candidates) == 1`). If multiple candidates or zero candidates match, the heuristic does not fire.
- **Empirical Validation**:
  - Validated on 32 sample cases with **100% precision** (2/2 matching ground truth: `case_08` -> `account_008`, `case_10` -> `account_010`).
  - Evaluated on the 518 hidden evaluation cases: affects exactly **37 cases**.

---

## 6. The 10 Binding Invariants

Any generated output must satisfy all 10 invariants:

- **Invariant 1 (Row Count & Case Integrity)**: Exactly 518 data rows matching `case_id`s in `dataset/deletion_requests.csv` with zero duplicates, zero missing rows, and sorted by `case_id`.
- **Invariant 2 (Strict Non-Deletion Handling)**: Any case whose `request_text` does not authorize deletion (as determined by semantic and intent classification, e.g. marketing opt-out, data export, credential reset, profile rectification, or data inquiry) must have `deletion_status == "NOT_APPLICABLE"` and `steps_json == "[]"`. Production code must not use hardcoded case IDs or case-range shortcuts.
- **Invariant 3 (Phase Monotonicity)**: For any step $i$ and $j$ where $i < j$, `phase_rank(step[i]) <= phase_rank(step[j])`.
- **Invariant 4 (Complete Case Phase Restriction)**: If `deletion_status == "COMPLETE"`, every step has `phase == "VERIFICATION"`. No `FINDING` or `REMEDIATION` steps exist.
- **Invariant 5 (Incomplete Case Phase Structure & Unverifiable Cases)**: For an evidenced `INCOMPLETE` case, at least one `FINDING` step must exist, followed by corresponding `REMEDIATION` steps, followed by post-remediation `VERIFICATION` steps. For an unverifiable case (where zero participant-visible evidence exists at or before `audit_at`), the pipeline conservatively outputs `deletion_status == "INCOMPLETE"` with `steps_json == "[]"`, since deletion completion cannot be affirmatively proven without fabricating ungrounded resource IDs or citing post-cutoff evidence.
- **Invariant 6 (Operation-State Coupling)**: Every step's `operation` and `state` strictly match the allowed mapping in §3.
- **Invariant 7 (Consecutive Step Numbering)**: Steps in `steps_json` are 1-indexed and increment strictly by 1 (`step_no == index + 1`).
- **Invariant 8 (Evidence Citation Temporal Invariant)**: For every cited `evidence_id`, its timestamp $T_{evidence} \le T_{audit\_at}$. No future evidence is cited.
- **Invariant 9 (Remediation Evidence Invariant)**: In `INCOMPLETE` cases, all `REMEDIATION` steps and future `VERIFICATION` steps have `evidence_id == ""`.
- **Invariant 10 (Deterministic Serialization)**: `steps_json` is serialized deterministically without trailing spaces, with uniform key ordering and UTF-8 encoding.
