# Data Audit — Ghost Data Still Exists

> Every number in this document was produced by a throwaway script under `scratch/`.
> Real-looking personal data is replaced with `[EMAIL]`, `[PHONE]`, `[HASH]`.

---

## 1. Evidence Format Inventory

**94 evidence files** across 5 directories.

### 1.1 SQL Snapshots — `evidence/databases/` (24 files)

Readable text files containing SQLite-compatible SQL. Each file can be loaded into an in-memory SQLite database with `executescript()`.

| Topology | File count | Example tables |
|---|---|---|
| `customer_data_inventory_*.sql` (primary) | 5 | `snapshot_scope`, `customer_profiles`, `customer_search_documents`, `customer_analytics_profiles`, `support_records`, `customer_exports`, `connector_subscriptions`, `backup_restore_entries`, `security_audit_records` |
| `customer_data_read_replica_*.sql` | 5 | `customer_data_primary`, `customer_data_read_replica` |
| `customer_data_regional_replicas_*.sql` | 3 | `customer_data_primary`, `customer_data_replica_ap_south`, `customer_data_replica_eu_west` |
| `customer_data_reporting_replica_*.sql` | 2 | `customer_data_primary`, `customer_data_reporting_replica` |
| `customer_accounts_failover_replica_*.sql` | 1 | `customer_profiles_primary` (3 rows), `customer_profiles_failover_replica` (4 rows) |
| `customer_data_failover_replica_*.sql` | 1 | `customer_data_primary` (16 rows), `customer_data_failover_replica` (16 rows) |
| `customer_search_primary_*.sql` | 5 | `customer_search_documents` |
| `customer_data_primary_*.sql` | 2 | `customer_data_primary` |

### 1.2 Log Files — `evidence/logs/` (26 files)

All plain text. Multiple format families, all parseable:

| Format | Count | Example first-line pattern |
|---|---|---|
| syslog (RFC 5424-like) | 2 | `2026-03-25T08:51:13Z <15>1 node-8 log_router ...` |
| Structured key-value (`level=INFO service=...`) | ~14 | `2026-05-14T11:51:20Z level=INFO service=account_service ...` |
| Pipe-separated fields | 2 | `2026-02-03T05:51:23Z \| DEBUG \| security_service ...` |
| Bracket-timestamp | 2 | `2026-02-22T10:58:43Z [DEBUG] [log_router] ...` |
| JSON-lines in body | 2 | `2026-04-19T06:51:11Z {"severity":"DEBUG",...}` |
| Cloud-runtime wrapper | 2 | `2026-06-08T06:52:07Z requestId=collector-1 ...` |
| Support-replica log | 1 | `2026-09-17T22:00:00Z level=DEBUG service=support_replica ...` |

All log files contain ISO-8601 timestamps and use identifiers like `resource_id`, `subject_ref`/`subject_reference`, `email`, `system`, and `event` names that can be parsed for state information (e.g., `result="NOT_FOUND"` vs `result="FOUND"`).

The `resource_lookup_trace_*.log` files (12 files) are **readback collector** logs. They enumerate records across systems for specific users at point-in-time and report `FOUND`, `NOT_FOUND`, `ANONYMIZED`, `IDENTIFIABLE`, `BLOCKED`, `ACTIVE`, `DISABLED`, etc. These are the **most important** log evidence files.

### 1.3 Records — `evidence/records/` (29 files)

| Type | Count | Shape |
|---|---|---|
| JSON `service_resource_export` | ~14 | `{"export_id":..., "service_exports":[{"system":..., "records":[...]}]}` — lists records per system with `customer_reference`, `email`, `phone`, `email_hash`, and record fields |
| JSON `snapshot_bundle` | ~14 | `{"bundle_id":..., "snapshots":[{"system":..., "records":[...]}]}` — similar to export but timestamped snapshots |
| TXT `customer_account_handover` | 1 | Plaintext table: `timestamp \| system \| resource_id \| category \| state \| identifier` |

All JSON records are valid JSON. The TXT handover file has 30+ lines of pipe-separated state checks at `2026-10-01T12:00:00Z`.

### 1.4 Images — `evidence/images/` (11 files, all PNG)

All are **readable** application screenshots from the "Northstar Shop" platform. Each shows a specific user and system with extractable data:

| Image | Application | Key data visible |
|---|---|---|
| `account_admin_console_20260926.png` | Customer Operations | user_11, account_5762, email, phone, 2 orders, support ref |
| `analytics_profile_view_20260713.png` | Pulse Analytics | user_20, analytics_7438, email, market AE, session/revenue data |
| `backup_restore_console_20260429.png` | Vault Recovery Manager | 4 archive entries with emails, retention end dates, restore activity |
| `connector_management_console_20260807.png` | BridgeOps | 4 connectors incl. `data_flow_1121` with email selector, continuous sync |
| `customer_export_console_20260618.png` | Customer Download Center | 4 exports with owner emails, statuses (Ready/Collecting/Packaging) |
| `deleted_account_reference_20260310.png` | Customer Reference Registry | user_17, "Retained reference", linked orders/support/finance |
| `marketing_profile_console.png` | Audience Operations | marketing_001, email, phone, market/language, audience segments |
| `object_storage_browser_20260213.png` | Nimbus Object Storage | 8 objects: PDFs, images, zips with version history, uploader info |
| `search_index_inspector_20260901.png` | Search Console | search_428 for user_13, email in index, `customer_directory_v3` |
| `security_audit_explorer_20260905.png` | Sentinel | user_03, 6 signed security events, account closure, journal 2026-Q3 |
| `support_ticket_console_20260524.png` | Helpline Console | CS-5034, support_1034, customer email, order ORD-20265034 |

### 1.5 PDF Documents — `evidence/documents/` (4 files)

All are **readable** via PyMuPDF text extraction.

| PDF | Content | Key data |
|---|---|---|
| `account_history_report_20260718.pdf` | Customer statement | user_18, [EMAIL], order ORD-20261260, items, delivery address |
| `delivery_correction_attachment.pdf` | Support attachment | CS-4827/support_001, [EMAIL], [PHONE], order ORD-20264827 |
| `legal_retention_register_20260529.pdf` | **Disputed orders and tax records** | 6 entries: user_08/12/17/21/24/29 with order IDs and **retain-until dates** (7 years out) |
| `security_retention_extract.pdf` | Compliance journal signed record | user_03, audit_record_003, account closure event, **retain-until 25 Aug 2027**, journal 2026-Q3 |

> **Critical:** `legal_retention_register_20260529.pdf` and `security_retention_extract.pdf` contain explicit retention periods that must be honoured.

---

## 2. SQL Snapshots — Topology and Replication Drift

### 2.1 Topology Summary

| Topology | Tables | record_json? | Identity fields |
|---|---|---|---|
| Primary inventory | `customer_profiles`, `customer_search_documents`, `customer_analytics_profiles`, `support_records`, `customer_exports`, `connector_subscriptions`, `backup_restore_entries`, `security_audit_records` | No (structured columns) | `customer_reference`, `email`, `phone`, `email_hash`, `full_name`, `display_name`, `requester_email`, `owner_email`, etc. |
| Read / Regional / Reporting replicas | `customer_data_primary`, `customer_data_{read_replica,replica_*,reporting_replica}` | Yes | JSON blob with email, phone, email_hash, user_id, full_name |
| Failover (accounts) | `customer_profiles_primary`, `customer_profiles_failover_replica` | No (structured columns) | `user_id`, `full_name`, `email`, `phone`, `account_status` |
| Failover (data) | `customer_data_primary`, `customer_data_failover_replica` | Yes | Same as read/regional |
| Search primary | `customer_search_documents` | No (structured columns) | `customer_reference`, `display_name`, `email`, `email_hash` |

### 2.2 Replication Drift — Concrete Examples

**Pattern observed:** Replicas consistently have **extra rows** not in the primary. The primary never has rows missing from the replica. There is no field-level drift within shared resource_ids.

| SQL file | Primary | Replica | Extra in replica |
|---|---|---|---|
| `customer_data_read_replica_20260613.sql` | 24 | 26 | `account_3150`, `account_9608` |
| `customer_data_read_replica_20260708.sql` | 31 | 32 | `account_4348` |
| `customer_data_read_replica_20260802.sql` | 24 | 25 | `account_8023` |
| `customer_data_read_replica_20260827.sql` | 29 | 30 | `account_6345` |
| `customer_data_read_replica_20260921.sql` | 30 | 31 | `account_994` |
| `regional_replicas_20260330.sql` (ap_south) | 28 | 29 | `account_5389` |
| `regional_replicas_20260424.sql` (eu_west) | 29 | 31 | `account_6539`, `account_8105` |
| `accounts_failover_replica_20260902.sql` | 3 | 4 | **`account_005` (user_05)** |
| `reporting_replica_20260208.sql` | 24 | 25 | 1 extra |
| `reporting_replica_20260305.sql` | 25 | 26 | 1 extra |

**Example 1 — Failover drift (user_05 ghost):**
`customer_accounts_failover_replica_20260902.sql`: Primary has 3 rows; the failover replica has 4 rows. The extra row in failover is `account_005` belonging to `user_05` with status `ACTIVE` and `updated_at=2026-09-02T22:45:00Z`. This is the ghost record — the primary deleted it but the failover still has it. This is the exact finding in sample case_05 (`INCOMPLETE` because account_005 persists in the failover).

**Example 2 — Read replica lag:**
`customer_data_read_replica_20260613.sql`: The read replica has 2 extra resource_ids (`account_3150`, `account_9608`) not in the primary. These represent records that were deleted from the primary but have not been garbage-collected from the replica yet.

---

## 3. Identity Resolution — How One Person Appears in Each Source

### 3.1 Identifier Fields Per Source

| Source | Identifier fields |
|---|---|
| `user_identities.csv` | `user_id`, `name`, `email`, `phone`, `email_hash` |
| `user_audit_log.csv` | `user_id`, `field_name` (email/email_hash/phone), `old_value`, `new_value` |
| SQL inventory (`customer_profiles`) | `customer_reference` (= user_id), `email`, `phone`, `email_hash`, `full_name` |
| SQL inventory (other tables) | `customer_reference`, `requester_email`, `requester_phone`, `owner_email`, `customer_email`, `subject_reference` |
| SQL replica `record_json` | JSON blob: `email`, `phone`, `email_hash`, `user_id`, `full_name`, `display_name` |
| JSON exports/snapshots | `customer_reference`, `email`, `phone`, `email_hash` in record objects |
| Log files | `subject_reference` or `correlation_key` (email), `subject_ref` (user_id) |
| Images | Visible on screen: email, phone, user_id, resource_id |
| PDFs | In text: user_id, email, phone, order IDs |
| TXT handover | Pipe-separated: resource_id, identifier (email or user_id) |
| `system_activity.csv` | `resource_id` only (no direct user identifier — must link via evidence) |
| `deletion_requests.csv` | `email` (may be current or historical) |

### 3.2 Key Statistics

- **user_identities.csv**: 850 users
- **user_audit_log.csv**: 306 changes — 107 email, 107 email_hash, 92 phone
  - Email and email_hash always change together (107 each, verified)
- **Requests using current email**: 417 / 518 (80.5%)
- **Requests using historical (old) email**: 100 / 518 (19.3%)
- **Requests using email in neither source**: 0
- **Distinct user_ids in the 518 requests**: 517 (out of 850 total users)
- **Duplicate email in requests**: 1 pair — case_33 and case_52 share the same email but have different `audit_at` times

### 3.3 Email Hash Rule

`email_hash` = SHA-256 of the lowercase email. Evidence emails can appear in any case. Always normalize to lowercase before hashing/comparing.

---

## 4. `captured_at` vs `audit_at`

### 4.1 Time Ranges

| Metric | Value |
|---|---|
| Earliest `audit_at` | `2026-01-29T12:00:00Z` |
| Latest `audit_at` | `2026-10-01T12:00:00Z` |
| Earliest `captured_at` | `2026-01-29T11:44:59Z` |
| Latest `captured_at` | `2026-10-01T12:00:00Z` |

### 4.2 Impact Distribution

- **511 out of 518 cases** (98.6%) have at least 1 evidence file captured after their `audit_at`.
- Only **7 cases** have all 94 evidence files captured at or before `audit_at` (these have the latest `audit_at` times).
- The case with earliest `audit_at` (case_523, `2026-01-29T12:00:00Z`) must ignore **93 of 94** evidence files.
- Distribution is roughly even: cases spread across having 0 to 93 later files.

### 4.3 Consequence

Evidence files are **shared across all cases** but each case has a different temporal window. The pipeline must filter evidence by `captured_at <= audit_at` on a per-case basis. The same evidence file may be usable for one case and excluded for another.

### 4.4 Example Where Later Evidence Would Flip an Answer

Case_05 has `audit_at=2026-09-08T13:40:00Z`. Evidence `evidence_54` (`customer_accounts_failover_replica_20260902.sql`, `captured_at=2026-09-02T23:00:00Z`) shows `account_005` still in the failover replica. If we instead used evidence captured after `audit_at` (e.g., a later snapshot where the record was cleaned up), we might incorrectly conclude COMPLETE. The contract requires using only evidence captured at or before `audit_at`.

---

## 5. Reverse-Engineered Sample Cases

### 5.1 case_05 — INCOMPLETE (reported_status: COMPLETE -> answer: INCOMPLETE)

- **User**: user_05, resolved via current email
- **Reported**: COMPLETE, but evidence contradicts
- **Finding**: `account_005` exists in `customer_profiles_failover_replica` (evidence_54, captured before audit_at). Deleted from primary but failover still has it.
- **Steps** (3):
  1. FINDING / REPORT_REMAINING_RECORD / PRESENT -> `account_service` / `account_005` / evidence_54
  2. REMEDIATION / DELETE_RECORD / ABSENT -> `account_service` / `account_005` / "" (future work)
  3. VERIFICATION / VERIFY_RECORD_ABSENT / ABSENT -> `account_service` / `account_005` / "" (future check)
- **Lesson**: A `reported_status=COMPLETE` can be overridden to `INCOMPLETE` when evidence shows a ghost record in a replica.

### 5.2 case_06 — INCOMPLETE (reported_status: PARTIALLY_COMPLETE)

- **User**: user_06, resolved via current email
- **Finding**: `search_001` still in `customer_search_primary` (evidence_57, captured before audit_at).
- **Steps** (4):
  1. FINDING / REPORT_REMAINING_RECORD / PRESENT -> `search_service` / `search_001` / evidence_57
  2. REMEDIATION / DELETE_RECORD / ABSENT -> `search_service` / `search_001` / ""
  3. VERIFICATION / VERIFY_RECORD_ABSENT / ABSENT -> `account_service` / `account_006` / ""
  4. VERIFICATION / VERIFY_RECORD_ABSENT / ABSENT -> `search_service` / `search_001` / ""
- **Lesson**: Verification covers both the found system AND the account. Steps sorted by system_id within same operation.

### 5.3 case_01 — COMPLETE (reported_status: COMPLETE)

- **User**: user_01, resolved via current email
- **Steps** (1):
  1. VERIFICATION / VERIFY_RECORD_ABSENT / ABSENT -> `account_service` / `account_001` / evidence_54
- **Lesson**: A truly complete case has only VERIFICATION steps with evidence citations. Evidence_54 confirms user_01's account is NOT in the failover.

### 5.4 case_03 — COMPLETE with RETENTION (reported_status: COMPLETE)

- **User**: user_43, resolved via current email
- **Steps** (3):
  1. VERIFICATION / VERIFY_RECORD_ABSENT / ABSENT -> `account_service` / `account_7566` / evidence_94
  2. VERIFICATION / VERIFY_RECORD_PRESENT / PRESENT -> `security_service` / `audit_record_2016` / evidence_94
  3. VERIFICATION / VERIFY_RECORD_ANONYMIZED / ANONYMIZED -> `analytics_platform` / `analytics_9406` / evidence_94
- **Lesson**: COMPLETE can include retained records (VERIFY_RECORD_PRESENT for security audit logs per rule_12) and anonymized records (per rule_07). Readback log provides all checks. Ordering: system_id ascending (`account_service` < `analytics_platform` < `security_service`).

### 5.5 Tombstone / Retention Patterns

- **VERIFY_RECORD_PRESENT** appears in 24 of 32 sample cases, most commonly for `security_service` / `audit_record_*` (rule_12: SECURITY_AUDIT_LOG -> RETAIN).
- **rule_15 (ACCOUNT_TOMBSTONE -> REDACT)**: No sample case explicitly uses REDACT_RECORD on an account tombstone, but `deleted_account_reference_20260310.png` shows user_17 with a "Retained reference" badge, meaning the tombstone has only `user_id` and linked record IDs — direct identifiers removed.
- **Legal hold**: `legal_retention_register_20260529.pdf` lists 6 users (user_08/12/17/21/24/29) with retain-until dates 7 years out. Orders for these users must be retained.
- **Security retention**: `security_retention_extract.pdf` explicitly states retain-until `25 Aug 2027` for user_03's audit_record_003.

---

## 6. Decoys and Traps

### 6.1 Duplicate Email in Requests

Only 1 pair: **case_33 and case_52** share the same email (same user). Different `audit_at` times (2026-07-19 vs 2026-06-19), so each evaluated independently. Both authorize deletion.

### 6.2 Activity Results Contradicting Snapshots

`system_activity.csv` contains 4,011 rows. Key contradiction surface:

| Event type | SUCCESS | FAILED | PARTIAL |
|---|---|---|---|
| DELETE_RECORD | 302 | **368** | **220** |
| REDACT_RECORD | 47 | **117** | **9** |
| ANONYMIZE_RECORD | 132 | **64** | **8** |
| SYNC_RECORD | 381 | 20 | 46 |

- **DELETE_RECORD FAILED (368) + PARTIAL (220)** outnumber SUCCESS (302). A SUCCESS claim does not prove the record is gone.
- **SYNC_RECORD SUCCESS (381)**: Can recreate data in downstream systems after deletion.
- **RESTORE_BACKUP**: 1 actual restore event (`activity_3387`): "Restore job repopulated downstream resource search_4882" from backup_9287. Evidence that restores create ghost data.
- **CHECK_RESTORE_ACCESS (28)**: Confirm archives "can still be restored" — these are risks.
- **CHECK_DATA_FLOW (89)**: Confirm data flows "remain enabled" — active sync risks.

### 6.3 NOT_APPLICABLE Requests (Non-Deletion) & Intent Audit

#### 6.3.1 Cause of the Earlier 4-Case Undercount
The initial audit script used naive substring matching against deletion keywords (`delet*`, `eras*`, `close`, `remov*`). Whenever any of those substrings appeared, the script assumed deletion intent.
Consequently, it missed 6 non-deletion cases (`case_534`, `case_536`, `case_537`, `case_538`, `case_539`, `case_542`) because each contained a deletion keyword negated or qualified by context ("not asking for deletion", "Do not close", "without removing", "remove me from marketing lists only", "not a request to erase", "please don't delete"). Only the 4 cases that had zero deletion words (`case_533`, `case_535`, `case_540`, `case_541`) were flagged.

#### 6.3.2 Complete List of Non-Deletion Requests (10 Cases)
All 10 non-deletion requests are located contiguously in `case_533` through `case_542`. For each of these, `deletion_status` must be `NOT_APPLICABLE` and `steps_json` must be `[]`:

| case_id | Request Text | Primary Action Requested | Negation / Constraint Present | Reason for NOT_APPLICABLE |
|---|---|---|---|---|
| `case_533` | "The mobile number on my profile is out of date. Please replace it with the new one and leave the account active." | Phone number update (Rectification) | "leave the account active" | Requests profile update, explicitly asks to keep account active |
| `case_534` | "Please stop the promotional emails. I still need the account and my order history, so I am not asking for deletion." | Marketing email opt-out | "not asking for deletion", "need the account" | Opt-out only, explicitly states not requesting deletion |
| `case_535` | "I'd like to download my account information in a portable format. Please keep the account as it is." | Data portability (Access / Export) | "keep the account as it is" | Request for export copy under portability, asks to keep account |
| `case_536` | "I can't access my profile and need help resetting the login. Do not close the account." | Login assistance / Credential reset | "Do not close the account" | Account recovery request, explicitly orders not to close account |
| `case_537` | "My surname is misspelled on the account. Can you correct it without removing any of my records?" | Name correction (Rectification) | "without removing any of my records" | Rectification request, explicitly forbids removing records |
| `case_538` | "Please remove me from marketing lists only. I still want receipts and service messages for this account." | Marketing communication opt-out | "marketing lists only", "still want receipts" | Partial opt-out, explicitly retains transactional account records |
| `case_539` | "Can you tell me what personal information you hold about me? This is an information request, not a request to erase it." | Subject Access Request (Inquiry) | "not a request to erase it" | Information inquiry, explicitly disclaims erasure |
| `case_540` | "I need a copy of last year's invoices for my records. Please leave my profile and purchase history in place." | Invoice document request | "leave my profile and purchase history in place" | Document copy request, explicitly keeps account and purchase history |
| `case_541` | "Please change the email address used for this account. I want to continue using the service." | Email update (Rectification) | "want to continue using the service" | Profile email change, explicitly confirms ongoing active service |
| `case_542` | "Could you send me a copy of the information held on my account? I still use it, so please don't delete or change anything." | Subject Access Request (Access) | "please don't delete or change anything" | Data access request, explicitly forbids deleting or modifying data |

#### 6.3.3 Analysis of Negations and Edge Cases
Across all 518 cases, exactly 6 request texts contain explicit negation or qualifying phrases modifying deletion verbs:

1. **`case_534` ("not asking for deletion")**: **NOT DELETION**. Explicit negation attached to the noun "deletion". User is opting out of marketing while retaining profile and order history.
2. **`case_536` ("Do not close the account")**: **NOT DELETION**. Direct imperative negation ("Do not") attached to verb "close". User is requesting password/login reset.
3. **`case_537` ("without removing any of my records")**: **NOT DELETION**. Prepositional negation ("without") qualifying participle "removing". User is fixing surname typo.
4. **`case_538` ("remove me from marketing lists only")**: **NOT DELETION**. Scope qualifier ("only") restricting the verb "remove" to marketing lists, followed by explicit instruction to keep transactional messages.
5. **`case_539` ("not a request to erase it")**: **NOT DELETION**. Explicit predicate negation ("not a request to erase"). User is exercising Article 15 (access/inquiry), not Article 17 (erasure).
6. **`case_542` ("please don't delete or change anything")**: **NOT DELETION**. Direct contraction negation ("don't delete"). User is requesting a copy of data while actively maintaining the account.

**Crucial finding on remaining 508 cases**: Zero cases among the other 508 contain any negation pattern, qualification pattern, or conflicting instructions. None say "do not delete", "don't close", "without removing", or "only". All 508 are genuine, unconditional deletion requests.

#### 6.3.4 Classification Methodology (Hand vs Rule Breakdown)
To guarantee 100% precision across all 518 evaluation requests:
1. **Hand-reviewed (100% of semantic templates, 22 templates total)**:
   - All 10 non-deletion cases (`case_533` to `case_542`) were read individually and verified by hand.
   - All 5 multilingual request templates (French 12 cases, Spanish 12 cases, Japanese 12 cases, Korean 12 cases, Portuguese 14 cases — 62 cases total) were translated and verified by hand as unambiguous deletion requests.
   - All 17 distinct English opening sentence structures (covering all 446 remaining English requests) were extracted and inspected by hand. Every single one opens with an explicit deletion demand (e.g., "Please treat this message as a request for permanent account deletion", "I would like to submit a request to delete this account and its personal data", "Please erase the account linked to this email address").
2. **Rule / Script-verified (518 of 518 cases)**:
   - Exhaustive script checked every case against regex negation patterns, non-deletion intent phrases, and opening clause clusters.
   - Verified that exactly 10 cases are `NOT_APPLICABLE` and exactly 508 cases are valid deletion requests.

### 6.4 Evidence Mentioning Users Not in Requests


Evidence files are global — they contain data for users not in the 518 requests. The pipeline must filter evidence to only the user(s) relevant to each case.

---

## 7. Step Sorting Verification

### 7.1 Verified Sort Order

Across all 32 sample output cases, **zero sorting violations** found for:

1. **Phase order**: FINDING -> REMEDIATION -> VERIFICATION (never reversed)
2. **Operation order within phase**: Follows the table order in the problem statement
3. **system_id within same (phase, operation)**: **Plain string ascending** (e.g., `account_service` < `analytics_platform` < `search_service`)
4. **resource_id within same (phase, operation, system_id)**: **Plain string ascending**

### 7.2 String vs Numeric Sorting

**Zero conflicts found.** No adjacent resource_id pair would sort differently under plain string vs numeric-aware order. **Conclusion: Use plain string ascending sort.**

### 7.3 Full Sort Key (Verified)

Steps are sorted by: `(phase_rank, operation_rank, system_id ASC, resource_id ASC)` where:
- `phase_rank`: FINDING=0, REMEDIATION=1, VERIFICATION=2
- `operation_rank`: Position in the problem statement's operation table for that phase

---

## Appendix: File Counts Summary

| Directory | Count | Formats |
|---|---|---|
| `evidence/databases/` | 24 | `.sql` (SQLite-compatible) |
| `evidence/logs/` | 26 | `.log` (various structured text) |
| `evidence/records/` | 29 | `.json` (28) + `.txt` (1) |
| `evidence/images/` | 11 | `.png` |
| `evidence/documents/` | 4 | `.pdf` |
| **Total** | **94** | |
