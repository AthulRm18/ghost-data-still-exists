# GHOST_DATA_PLAN.md - "Ghost Data Still Exists" (Orchestrate, Oct 2026)

Companion to ORCHESTRATE_PLAYBOOK.md. This one is task-specific. It is based on reading the
official repo (problem_statement.md, README.md, AGENTS.md, agent_trace_instructions.md), the
32 sample answers, the CSV files, and a peek at the SQL/log/txt evidence. I have NOT yet
read every log format, PDF or image. Your agent must audit those itself (Phase 1 below).

---

## 0. Corrections to what I told you earlier (the real repo differs)

1. **Transcript path:** the log is `log.txt` in the REPO ROOT (next to AGENTS.md), not in your home
   folder. Launch Antigravity with the repo root as the workspace.
2. **Every log entry needs exact `tool=` and `model=` lines.** Missing, blank, "unknown", inferred
   or generic values make an entry invalid. Tell the agent your exact model name yourself.
3. **Deadline is "not configured"** in AGENTS.md. Get the real end time from your email / the
   contest page. Do not guess.
4. **Submission link typo:** AGENTS.md section 4.1 gives `https://wwww.hackerrank.com/...`
   (four w's), which looks like a typo. I could not verify the correct one. Use the link from
   your registration email or the HackerRank contest page, not the one the agent prints.
5. **Reports must be Markdown inside `code/evaluation/`:** `evaluation_report.md` and
   `usage_report.md`. The README says the code judge IGNORES .csv .tsv .json .jsonl .sql .log
   files. Anything you want judged (metrics, custom cases, token/cost numbers, prompts) must
   live in .py or .md files.
6. **There is an extra "agent trace" ZIP** (agent_trace_instructions.md). See section 8.

---

## 1. The task in one paragraph

For each of 518 deletion requests: decide `COMPLETE` / `INCOMPLETE` / `NOT_APPLICABLE`, then
output an ordered JSON list of steps (findings -> remediation -> verification). Truth must be
reconstructed AT `audit_at` from evidence; `reported_status` and system_activity results are
only CLAIMS. Policy comes from `deletion_rules.csv` (15 rules: DELETE / REDACT / ANONYMIZE /
RETAIN, incl. account tombstone keeps `user_id` only). Output: `case_id,deletion_status,steps_json`,
exactly 518 rows sorted by `case_id`.

## 2. What the data looks like (verified)

- 518 requests; 32 samples with answers (22 INCOMPLETE, 10 COMPLETE, **0 NOT_APPLICABLE**).
  In the 518, many request texts are deletion requests in en/es/pt/fr/ko/ja, plus at least 8
  distinct non-deletion texts (update phone, stop promos, export my data, reset login, fix
  surname, marketing-only, "what do you hold", copy of invoices). The samples contain no
  NOT_APPLICABLE, so you must build your own test cases for that path.
- `reported_status` in the 518: 254 COMPLETE, 152 PARTIALLY_COMPLETE, 112 NOT_STARTED.
  In samples, 17 reported COMPLETE yet many are really INCOMPLETE. Never trust it.
- `user_identities.csv`: 850 users. `email_hash` = SHA-256 of the lowercase email (matches 850/850).
  `user_audit_log.csv`: 306 changes (email 107, email_hash 107, phone 92) = historical identifiers.
  Evidence may show emails in UPPERCASE; normalize case before matching/hashing.
- `system_activity.csv`: ~4,000 rows of other people's activity too (decoys). Event types:
  DELETE_RECORD, UPDATE_RECORD, SYNC_RECORD, INDEX_RECORD, SEND_EMAIL, REFRESH_CACHE,
  RETAIN_RECORD, ANONYMIZE_RECORD, REDACT_RECORD, CREATE_EXPORT, CHECK_DATA_FLOW,
  DISABLE_DATA_FLOW, BLOCK_RESTORE, CHECK_RESTORE_ACCESS. Results SUCCESS/FAILED/PARTIAL.
- `evidence_files.csv`: 94 files, each with `captured_at`: 24 SQL snapshots, 26 logs,
  29 records (json/txt), 11 images, 4 PDFs. The manifest does NOT say which user a file is about.
- SQL snapshots are SQLite-compatible. Tables seen: customer_profiles, customer_search_documents,
  customer_analytics_profiles, support_records, customer_exports, connector_subscriptions,
  backup_restore_entries, security_audit_records, plus snapshot_scope. Replicas (regional,
  reporting, read, failover) may disagree with the primary (replication drift) and use
  different table/column names (e.g. `customer_profiles_failover_replica`).
- Sample answers use systems: account_service, search_service, support_platform,
  analytics_platform, security_service, integration_service, backup_service, export_service,
  identity_service.
- Only ~94 evidence files, of which 15 are images/PDFs. Pre-processing ALL evidence once is cheap.

## 3. Rules the grader obviously checks

- Time cutoff: ignore evidence with `captured_at` after `audit_at`.
- Identity: request email may be a historical email -> resolve to `user_id` via audit log; then
  match evidence on all current + historical emails/phones/hashes + user_id/customer_reference.
- Status COMPLETE only if every copy has required treatment, retained records still exist, and no
  active flow/restore path can recreate data.
- Rules to apply per record category: USER_PROFILE, SECONDARY_IDENTIFIER, SEARCH_INDEX_ENTRY,
  CACHE_ENTRY, USER_EXPORT, MARKETING_PROFILE = DELETE; SUPPORT_ATTACHMENT only for the subject = DELETE;
  SUPPORT_MESSAGE with shared context = REDACT; ANALYTICS_PROFILE and PRODUCT_TELEMETRY still
  attributable = ANONYMIZE; EMAIL_DELIVERY_LOG with an email = REDACT; SECURITY_AUDIT_LOG within
  retention, LEGAL_HOLD_RECORD with active hold, BACKUP_ARCHIVE (if restore can be blocked) = RETAIN;
  ACCOUNT_TOMBSTONE = REDACT (keep stable user_id, remove name/email/phone/email_hash).
  Retention periods and legal holds come from the supplied evidence (e.g. the PDFs named
  `legal_retention_register`, `security_retention_extract`): read them.
- Step ordering is fully deterministic. Findings: REMAINING_RECORD, EXPOSED_PII, ACTIVE_DATA_FLOW,
  RESTORE_RISK. Remediation: DISABLE_DATA_FLOW, BLOCK_RESTORE, DELETE_RECORD, REDACT_RECORD,
  ANONYMIZE_RECORD. Verification: ABSENT, PRESENT, REDACTED, ANONYMIZED, DATA_FLOW_DISABLED,
  RESTORE_BLOCKED. Within an operation: system_id then resource_id ascending. The sample outputs
  follow this; test whether "ascending" is plain string sort or numeric-aware using all 32 samples.
- Evidence IDs: findings and COMPLETE-case verification cite a `file_id` / `activity_id` /
  `audit_id`; remediation and INCOMPLETE-case future verification use `""`.
- NOT_APPLICABLE -> `[]`, nothing else.

## 4. Recommended architecture (deterministic core, LLM only where code cannot read)

```
dataset/*.csv  evidence/*
   |                |
   |      [A] Evidence ingestion (once, cached)
   |         SQL -> run in in-memory SQLite, dump rows with table/topology/captured_at
   |         logs/json/txt -> format-specific parsers (code)
   |         PDF -> text extraction; images + scanned PDFs -> vision LLM, strict schema, cached
   |         => one normalized "observations" table: file_id, captured_at, system_id,
   |            resource_id, data_category, observed state, identifiers (email/phone/hash/user_id)
   v
[B] Request gate (LLM, cached, schema): does request_text authorize deletion? (multilingual)
[C] Identity resolution (code): request email -> user_id -> all current+historical identifiers
[D] State reconstruction at audit_at (code): link observations to the user, take the latest
    observation per resource with captured_at <= audit_at; compare primary vs replicas;
    treat system_activity as claims to cross-check, not truth
[E] Policy engine (code): rules x observed state -> findings (+ flows, restore risks)
[F] Planner (code): findings -> remediation -> verification, exact ordering, evidence ids
[G] Validator (code): schema, ordering, step_no, id existence, time cutoff; raise on violation
[H] Output writer: sorted, deterministic JSON
```

- **Where an agent loop fits (bounded):** an "investigator" for evidence code can't parse or for
  low-confidence identity/state links, with tools like `query_snapshot_sql`, `grep_evidence`,
  `read_evidence(file_id)`, `lookup_identity`, a hard max-iteration cap, schema-validated output,
  and deterministic validation after it. The final decision/plan stays in code. Be ready to say
  why: the task rewards reliable state reconstruction and exact ordering, and code does both
  better than a model. Unverified: whether the code judge this time still rewards "agentic"
  loops as in May; a bounded investigator covers both.
- **Do NOT** hardcode labels, case families, or use sample answers as a lookup table. Samples are
  for development and scoring only. Organizer-only files must never be used.
- Dedupe LLM calls by input hash (request texts repeat in templates). Cache every model response
  on disk keyed by (prompt version, schema, model, input hash). Log tokens for every call.

## 5. Phases (adapt to the real deadline; sleep and keep an hour for submission)

1. **Data audit (you + agent, 60-90 min).** You read some raw evidence yourself. Write
   `docs/data_audit.md`: file formats, naming, how a user appears in each source, decoys,
   duplicates, timestamps vs audit_at, replica drift examples, weird rows.
2. **Contract + design (30-45 min).** `docs/CONTRACT.md` (exact output rules, ordering,
   invariants) and `docs/architecture.md`. You decide trade-offs in your own words.
3. **Walking skeleton (1-2 h).** Ingestion for SQL + one log type -> policy -> planner -> valid
   CSV on the 32 samples. Commit.
4. **Scorer first (30 min).** `code/evaluation/main.py`: status accuracy, step-level
   precision/recall on (phase, system_id, resource_id, operation, state, evidence_id),
   field-level accuracy, exact sequence accuracy, per-case diffs. Run after every change.
5. **Widen coverage** (remaining log formats, JSON, txt, images, PDFs), one source at a time,
   tag each sample error as logic bug / parse gap / model misread / ambiguous spec.
6. **NOT_APPLICABLE + multilingual gate**, with your own test cases.
7. **Hardening on all 518:** crash-free, invariants pass, status distribution looks sane,
   spot-check 20+ cases by hand including every NOT_APPLICABLE and a few COMPLETE ones.
8. **Reports + packaging** (section 7), fresh-clone run, rest, interview prep.

## 6. Ready-to-paste prompts for Antigravity

Setup first: open the cloned repo ROOT as the workspace. If Antigravity offers a planning-style
mode, use it for design steps. Check the model dropdown and note the EXACT model name.

**Prompt 0 (first message of the session)**
```
Read AGENTS.md fully and follow it for this whole session. I am using the harness
"Google Antigravity" with model "<EXACT MODEL NAME FROM THE DROPDOWN>". Use these exact values for
tool= and model= in every log entry; if you cannot confirm them, ask me instead of guessing.
Create log.txt in the repo root if missing and write the SESSION START entry now. After every turn,
re-read your appended entry and confirm tool= and model= are populated. Do not write any code yet.
Then read problem_statement.md, README.md and the CSV headers in dataset/ and give me a 10-line
summary of the task in your own words, plus the 5 riskiest parts you see. Never put real personal
data or keys in log.txt.
```
After it answers: OPEN log.txt YOURSELF and check the format. If wrong, tell it to correct.

**Prompt 1 (data audit, no code for the pipeline)**
```
Do a data audit and write docs/data_audit.md. Use small throwaway scripts under scratch/ (not in
code/). Cover: every evidence format (list the distinct log layouts with one anonymized example
line each), the SQL snapshot tables and topology (primary vs regional/reporting/read/failover
replicas), how a person shows up in each source (email case, phone formats, email_hash,
customer_reference/user_id), how captured_at compares to audit_at across the requests, and
anything that looks like a decoy or a trap. Verify claims by running queries. Report numbers, not
impressions. Stop and show me the findings before designing.
```

**Prompt 2 (contract + architecture)**
```
Using the audit, propose two architectures with trade-offs and a recommendation. Constraints I
want: deterministic code for identity resolution, state reconstruction at audit_at, policy and
step ordering; LLM only for reading images/scanned PDFs, the multilingual deletion-intent gate and
hard ambiguous links, with strict JSON schemas, caching, a max-iteration cap and logged token usage.
Do not write code. Write docs/CONTRACT.md with output rules, exact ordering rules, and numbered
invariants that will be asserted at runtime. I will pick the architecture.
```

**Prompt 3 (scorer before the solver)**
```
Implement code/evaluation/main.py first. It scores a predictions CSV against dataset/sample_output.csv:
status accuracy; step-level precision/recall/F1 on (phase, system_id, resource_id, operation, state,
evidence_id); per-field accuracy; exact-sequence accuracy; per-case diff output. Type hints, small
functions, tests for the metric functions. Run it against sample_output.csv itself (must be 100%)
and against a deliberately shuffled copy (must drop).
```

**Prompt 4 (skeleton)** - "Implement only the identity resolver and SQL ingestion, with unit tests; show me
how request emails (current and historical) map to user_id for 5 sample cases, and print which
snapshot rows match each."

**Prompt 5 (planner)** - "Implement the policy engine and planner as pure functions with no I/O. Feed them
hand-made observation fixtures. Prove the ordering rule against all 32 sample_output.csv files by
re-sorting each sample's steps and diffing (tell me whether system/resource sorting is
string or numeric-aware)."

**Prompt 6 (iterate on errors)** - "Run the scorer on the 32 samples. For every mismatch, classify it as
logic bug, parse gap, model misread, or ambiguous spec and name the layer that owns it. Fix only
logic bugs and parse gaps this round. Re-run and show before/after numbers. Do not tune to
individual rows; if a rule helps one row only, tell me and ask."

**Prompt 7 (adversarial/edge cases)** - "Create at least 5 custom evaluation cases (fictional) under
code/evaluation/cases.py, documented in evaluation_report.md: request from a historical email;
evidence captured after audit_at that must be ignored; a non-deletion request in Korean and one in
Portuguese; a replica that still holds a profile the primary deleted; a legal-hold record that
must be kept. Predict the expected output by hand first, then run."

**Prompt 8 (hardening)** - "Run all 518 cases. Add runtime validation (consecutive step_no, allowed
phase/operation/state combos, evidence ids exist and are <= audit_at, remediation/verification use
empty evidence ids for INCOMPLETE, NOT_APPLICABLE is []). Print the status distribution and the 10
most unusual cases for my review."

**Prompt 9 (reports + package)** - "Generate code/evaluation/evaluation_report.md and usage_report.md
as Markdown with the real numbers from the final full run. For usage: models, call counts, input and
output tokens, totals and per-request averages, estimated cost. Do not fabricate: if results come
from cache, say which calls were made when, and report their recorded usage. Then write README.md
(setup, env vars, exact run command, how to reproduce offline), and package code.zip with the
command in README.md. Check it contains no dataset, no .env, no __pycache__, no nested archives."

## 7. Deliverable checklist

- [ ] `output.csv` at repo root, header `case_id,deletion_status,steps_json`, 518 rows sorted by case_id
- [ ] Every `steps_json` valid JSON array; step_no 1..n; allowed phase/operation/state combos only
- [ ] COMPLETE: verification steps only, each cites valid evidence <= audit_at
- [ ] INCOMPLETE: findings cite evidence; remediation + verification have `""` evidence_id
- [ ] NOT_APPLICABLE: exactly `[]`
- [ ] `code/evaluation/evaluation_report.md`: case accuracy, step/field accuracy, sequence accuracy,
      >= 3 custom cases, failures found, improvements made (Markdown, real numbers)
- [ ] `code/evaluation/usage_report.md`: providers/models, calls, in/out tokens, totals + per-request
      average, estimated cost (per-model and overall), for the FINAL full run
- [ ] `README.md` with setup + exact run command; secrets only from env; prompts in .py/.md
- [ ] `code.zip` made with the command in the repo README (no dataset, no venv, no caches, no nested zips)
- [ ] `log.txt` from repo root, unedited, every entry has tool= and model=
- [ ] agent-trace.zip prepared if requested (section 8)

## 8. Antigravity specifics

- Keep one workspace (repo root) and ideally few long conversations so the log and the trace stay coherent.
- The recap from the May edition found only ~half of transcripts were "clean". After the first
  turn, and again every hour, open log.txt and check the format. If Antigravity does not follow
  AGENTS.md logging reliably, switch harness rather than hand-edit the log. Do not hand-write
  or backfill entries.
- In May, Antigravity was the most-used tool overall but absent from the Top 10, while Claude Code
  led the Top 50. The recap says behavior (planning, iterating, complete logs) drove that, not the
  tool. You can win with Antigravity if you steer well.
- Agent trace (agent_trace_instructions.md): when finished, QUIT Antigravity, then copy the
  full `<conversation-id>` folders for this challenge from
  `~/.gemini/antigravity/brain/` (or `antigravity-cli/brain/` or `antigravity-ide/brain/` depending on
  which product you used; Windows: `%USERPROFILE%\.gemini\...`) into `agent-trace/antigravity/`.
  The transcript is at `.system_generated/logs/transcript.jsonl` inside each folder. Do not copy
  the whole `.gemini` directory. Redact secrets, then zip as `agent-trace.zip`. I could not tell
  whether this upload is mandatory; check the submission page and prepare it either way.
- Your solution needs its own model API key (not the Antigravity subscription). Choose a model
  with vision support, store the key in `.env` (gitignored), and never paste it into a prompt.

## 9. Interview angles for this task (prepare answers)

- Why deterministic planner + LLM only at the evidence boundary? What breaks if the model decides?
- How do you resolve historical identifiers, and what if a hash matches but the email text doesn't?
- How do you enforce the audit_at cutoff? Show a case where later evidence would have flipped the answer.
- How do you treat conflicting sources (primary vs replica; activity says SUCCESS, snapshot says present)?
- What does your system do with an ambiguous request text? What is your NOT_APPLICABLE precision/recall risk?
- Retention and legal hold: where do the retention windows come from, and how do you apply them?
- Failure modes, monitoring in production, cost per request, what you would improve next.
- Be honest about what the AI wrote, what you verified, and what you did not test.
