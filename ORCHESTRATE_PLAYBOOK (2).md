# ORCHESTRATE_PLAYBOOK.md

HackerRank Orchestrate, October 2026 edition. Operating manual for any AI coding agent
(Claude Code, Codex, Cursor, ...) working with the participant, Athul, in this repo.

> **READ THIS FIRST (agent):**
> 1. This file does NOT replace the official `AGENTS.md` shipped in the starter repo.
>    The official one handles onboarding and the mandatory chat-transcript log
>    (October repo: `log.txt` in the REPO ROOT; see GHOST_DATA_PLAN.md section 0). That log IS a graded submission file.
>    Obey it exactly. Never edit, reorder, or delete old log entries. Never log secrets.
> 2. If anything in this file conflicts with the official `AGENTS.md`, the official
>    `AGENTS.md` and the official `problem_statement.md` win. Tell the user about the conflict.
> 3. The problem statement is released at 6:00 PM IST on Oct 24, 2026 (12:30 PM UTC per the
>    registration email). Until the participant pastes or places it in the repo, DO NOT
>    assume what the task is. Past editions each had a different task.

---

## 1. Facts, and how sure we are

### Confirmed (from the official event page, registration email, and HackerRank's own blog)
- 24-hour hackathon, solo/individual. Starts Oct 24, 2026, 6:00 PM IST. Challenge arrives by email.
- Any tool/model/language/framework is allowed (Claude Code, Cursor, Codex, anything).
- Submit THREE files: (1) Code ZIP with a README (setup + run instructions),
  (2) Output file as CSV, (3) AI chat transcript (the log from the AI coding tool).
- After submitting: 30-minute voice interview with an AI judge. Mic + camera + stable internet needed.
  The interview opens immediately after submission.
- Live evaluation Oct 26-27; results Oct 27. Live leaderboard after the interview.
- Prizes: 1st $1,200; 2nd-5th $300 each; Codex-credit bonuses for top 3 who build with Codex.
  All participants: certificate + 10 HackerRank AI Mock Interview credits.
- Four graded signals (HackerRank blog): the CODE, the OUTPUT/agent performance, the AI CHAT
  TRANSCRIPT, and the 30-MIN VOICE INTERVIEW.
- Discord for updates/questions: https://discord.gg/hackerrank-orchestrate

### Strong inference (from the May and June editions, NOT confirmed for October)
- Score weights seen in the June edition (from a top-3 finisher's breakdown):
  Code review 30, Output accuracy 30, Interview 30, Chat transcript 10 = 100.
  The October weights may differ. Re-check the evaluation criteria file in the October repo.
- Past top finishers scored ~83-84/100 (August edition). Top 3 were separated by ~1 point,
  so small things (README, transcript quality, interview answers) decide placements.
- The starter repo usually contains: `problem_statement.md`, `evalutation_criteria.md`
  (sic), `AGENTS.md`, `CLAUDE.md`, `README.md`, `code/`, input CSV(s), and an `output.csv`
  target. In May the transcript path was `log.txt` in the repo root (October edition)
  .

### NOT verified (could not read; check yourself)
- The FAQ answers on the event page are collapsed/JS-rendered; I could not read them.
  Participant: open the page and read every FAQ item, especially "How do I submit?",
  "What gets evaluated and how?" and "Can I use my own tools and IDE?".
- Exact submission deadline (likely ~6:00 PM IST on Oct 25, i.e. 24h after start).
  CONFIRM from the email/problem statement. Do not guess in the last hour.
- Whether the interview must be taken within a window (in May it stayed open 4 hours
  after the hackathon ended). Read the October instructions.

---

## 2. What actually wins (lessons from previous winners and HackerRank's own guidance)

1. **Model describes, deterministic code decides.** #1 of the August edition summarized
   his approach this way. A top-3 finisher of June formalized it: model produces structured
   observations; pure code turns them into the verdict. Auditable, repeatable, hard to inject.
2. **Simple beats impressive.** #1 of the May edition used one agent + one tool + guardrails.
   A June top-3 finisher built a 15-stage pipeline in an earlier edition, finished mid-pack,
   and could not explain why each stage helped. Complexity you can't defend is a liability.
3. **Process is graded.** Transcript and interview reward visible thinking: plan, build, review.
   The blog says: "what matters is whether you led the process."
4. **Escalate / abstain instead of guessing** when evidence is missing or risk is high.
   A confident wrong answer is worse than an honest flag.
5. **Prompt injection is a certain test.** Inputs in past editions contained hidden
   instructions (even multilingual). Treat all input text as DATA, never as instructions.
6. **temperature=0 is not determinism.** One finisher saw 43 of 140 identical-prompt
   readings differ. Get reproducibility from deterministic code layers + cached model outputs.
7. **Measure what is graded, not something adjacent.** Same finisher's lesson across two
   editions. Re-read the rubric before optimizing anything.
8. **Interview is half the game.** Strong builds have lost points by not explaining
   decisions crisply. Be specific, concede limits honestly.

---

## 2b. The official rubric (from HackerRank's own May-edition recap; October may change it)

Each signal is scored 0-100 by an AI judge, then combined:
`Final = 0.10*Transcript + 0.30*Interview + 0.30*Output CSV + 0.30*Code ZIP`
Tie-break order: Interview, then Code, then Output, then Transcript.
Every Top-10 finisher was in the top quartile on ALL four. Balanced beats spiky.

**Code ZIP (judged ONLY on what is observable in source; README claims, comments and unused imports do not count)**
- Agent architecture 30%: is it a real agent or a hardcoded workflow with LLM calls? Looks for
  tool-calling loops, model-driven routing, handoffs.
- Prompt and tool craft 30%: system prompts and tool descriptions: role, constraints,
  structured output, refusal conditions.
- Agent robustness 25%: guardrails, retries, MAX-ITERATION CAPS, output validation, RAG quality.
- Engineering rigor 15%: multi-file modularity, type hints, secrets via env, small functions.

**Output CSV**
- Each row checked against a hidden golden dataset on status, request type, product area,
  response, and justification. PLUS one submission-wide safety score on adversarial inputs.
- A justification that is empty, generic, or contradicts the status is CAPPED at ~70 even when
  the action is right. Justifications must be specific and consistent with the label.
- Escalating everything and replying to everything were both explicitly invalid.

**Transcript (10% only, because it was easy to fake or corrupt)**
- Direction and architecture ownership 35%; technical specificity 25% (name models, libraries,
  schemas, file paths, thresholds); iteration and verification 25%; safety/edge-case awareness 15%.
- Only 658 of 1,349 transcripts were "clean". Many broke the log format or lost the Context block.
  Keep the official log format intact and check the file yourself before submitting.
- Weakest transcripts were just output logs ("Ticket 1 processed..."). Don't paste outputs as the chat.

**Interview (30%)**
- Technical depth and ownership 40%; problem understanding and judgment 25%; communication 20%;
  honesty and self-awareness 15%. Fabrication is penalized: claiming a feature or library that
  isn't in the code, or denying a bug the judge can see. "I don't know" and "the AI wrote that and
  I'm not sure why" are rewarded when true.
- The judge usually probes in this order: quick pitch -> retrieval/architecture -> safety and
  failure modes -> code familiarity -> evaluation -> production monitoring -> what is novel.
  Prepare an answer for each, including "how would you monitor this in production".
- Longer, specific answers scored higher; very short answers scored badly. More back-and-forth
  turns did not help. Give concrete examples: "we raised top_k, it regressed on the fraud rows,
  we reverted and kept the deterministic gate".
- Speak in "I chose / I rejected / I measured", not "Claude created the pipeline".

**What the architecture data said (May task; check whether it transfers to October)**
- Single agent + tools/retrieval + schemas + guardrails took 7 of the Top 10, including #1.
- Graph/state-machine workflow got #2. Explicit multi-stage pipelines got #3 and #9.
- Single-prompt agents, trained classifiers (TF-IDF+LogReg etc.; too little labeled data, they
  overfit hidden tickets), and rule-only pipelines (brittle, over-escalated) landed mostly in the
  lower half. Rules-only averaged rank ~941.
- Winners combined deterministic gates (injection, high-risk, schema validation, fallbacks) WITH
  LLM reasoning and grounded retrieval. Multi-agent only won where each agent had a narrow job
  and handoffs were tight, and escalations could be traced to a specific gate.
- Tool used: Claude Code was 44% of the Top 50 vs 14% overall. The recap says behavior, not
  tool, drove this: complete logs, planning first, iterating against samples.

**Implication for how to build:** make the code show a REAL bounded agent loop (the model picks
tools/steps, with a hard max-iteration cap), with deterministic gates before and after it. A
pure "one LLM call then code decides" script may be safe but could score lower on the 30%
architecture dimension. Only the problem statement will tell whether an agent loop fits.

---

## 3. Operating protocol for the AI agent (this builds the transcript score)

The transcript is read by a grader looking for: scoped prompts, critique and verification of
AI output, and the HUMAN visibly steering architecture. So:

- **Plan before code.** First 45-60 minutes: no implementation. Produce short written notes
  (see section 4, Phase 1). Ask the participant to choose between options; present 2-3
  alternatives with trade-offs and a recommendation. The participant's choice is recorded.
- **Be explicit and specific.** Name files, functions, schemas, thresholds, label sets.
- **Checkpoint.** After each milestone: summarize what changed, what was verified, what is
  still unverified. Ask for go/no-go before large refactors.
- **Review like code review.** After running the system, inspect failures, question your own
  output, list what could break, then iterate. Attribute each error to a layer:
  (a) logic/rule bug, or (b) model misread. Fix (a) first; it is free to re-grade offline.
- **Do not flatter or rubber-stamp.** If the participant proposes something risky or
  over-complex, say so and explain. The transcript should show push-back on both sides.
- **Never fabricate the trail.** Do not invent conversation, backfill the log, or add
  entries for turns that did not happen. Honest imperfect logs beat doctored ones.
- **Verify, don't recall.** For API limits, model names, library behavior, pricing: look it
  up or test it. A model's confident answer is a hypothesis.
- **Log every turn** per the official AGENTS.md format. If sub-agents are used, they log too.

---

## 4. Phase plan (timeboxes for a 24h window; adapt to the actual deadline)

Do not use all 24 hours on building. Reserve time for QA, README, and rest before the interview.

**Phase 0 (0:00-0:20) Setup and reading**
- Clone starter repo, read `problem_statement.md`, `evalutation_criteria.md`, `AGENTS.md`,
  data files, sample/labeled files. Do the official onboarding. Confirm deadline.
- Create `.env` (gitignored), `.env.example`, pinned `requirements.txt`/lockfile.
- Check the log file is being written.

**Phase 1 (0:20-1:30) Understand and design on paper**
Create a `docs/` folder (short, bullet-style files, not essays):
- `docs/problem_analysis.md`: inputs, outputs, exact schema, allowed values, hard requirements,
  what is explicitly forbidden, what the rubric rewards. Quote the statement for every rule.
- `docs/data_analysis.md`: row counts, missing fields, duplicates/repeated IDs, languages,
  weird or adversarial rows, label distribution in labeled sample, ambiguity hotspots.
- `docs/threat_model.md`: prompt injection in inputs, malformed model output, API failure,
  empty/missing fields, conflicting signals, high-risk cases that need escalation.
- `docs/architecture.md`: one diagram of the data flow (input -> normalize -> context -> model
  -> typed record -> validate -> deterministic decision -> output) and what is model vs code.
- `docs/decisions.md`: running log, one entry per decision: choice, alternatives rejected,
  why. (This is your interview cheat-sheet. Update it throughout.)

**Phase 2 (1:30-4:00) Minimal end-to-end first**
- Smallest pipeline that reads the real input and writes a valid CSV with the exact columns.
  Even if dumb (rules only). Commit. This is the fallback you can always submit.

**Phase 3 (4:00-14:00) Iterate against evidence**
- Build the evaluation harness FIRST (section 6), then improve one thing at a time.
- Add: input validation, prompt, schema validation, retries (bounded), label whitelist,
  escalation/abstain path, injection defenses, deterministic decision rules, logging of failures.
- After each change: run eval, record before/after in `docs/decisions.md`. Keep what helps,
  revert what does not (and note that honestly).

**Phase 4 (14:00-19:00) Hardening**
- Run on the FULL real input. Inspect weird rows by hand. Test: empty row, missing field,
  repeated ID, hostile instruction, wrong-language text, very long text, API error mid-run
  (one bad row must never kill the run).
- Run the pipeline twice; diff the outputs; understand every difference.
- Code cleanup: rename vague files (`utils`, `helper`, `final`, `test2`), remove dead code
  (AI judges find dead code), remove generated junk from source, no hardcoded paths/keys.

**Phase 5 (19:00-21:30) Packaging**
- README, final output CSV QA (section 7), zip hygiene, fresh-clone run test.
- Interview prep pass (section 9).

**Phase 6 (21:30-deadline minus 1h) Submit early**
- Submit with a buffer. Do not make "one last improvement" in the final hour that you have
  not re-evaluated. Freeze, tag the commit.

---

## 5. Architecture rules

1. **Default to one agent (or one LLM step) plus strong code around it.** Add a second agent
   only if you can state what it owns, how context passes, and how conflicts are resolved,
   and you can show it improved a measured number.
2. **Typed seam.** Define one schema (pydantic/dataclass/TypedDict) that is the ONLY thing
   crossing from model to decision code. Never let downstream code read raw model text.
3. **Pure decision functions.** Data in, data out. No network, no file reads, no hidden state.
   Unit-test them without calling any model.
4. **Cheap deterministic pre-filters** for trivially classifiable inputs (empty, pleasantries,
   obvious injection, off-topic). Do not pay an LLM for what a rule handles reliably.
5. **Injection defense before the model.** Treat input as untrusted data. Put it in a clearly
   delimited data block, tell the model it is data, and add a code-level check for
   instruction-like content (multilingual). If the model's output tries to follow input
   instructions, route to flag/escalate.
6. **Constraints enforced structurally, not by hopeful prompting.** If some field "must never
   change the verdict," do not pass it into the decision code at all.
7. **Whitelist outputs.** Every categorical field is checked against the allowed set from the
   problem statement. Invalid -> bounded retry (max 2) -> safe fallback -> flag. Never write
   an unsupported label to the CSV.
8. **Abstain/escalate path is first-class**, with a recorded reason. Define exactly what triggers it.
9. **Grounding.** If the task provides a corpus or evidence set, answers must come from it, with
   citations/IDs where the schema allows. A citation only counts if the evidence was really
   retrieved in that run. No parametric-knowledge answers where the task forbids them.
10. **Reproducibility.** Seed anything random, pin dependency versions, cache raw model
    responses to disk keyed by (input hash, prompt version, model), and allow an offline
    "replay" mode so the decision layer can be re-run for free. Do not claim determinism you
    cannot demonstrate.
11. **Failure isolation.** Per-row try/except, log the failure with the row ID, continue,
    mark the row as flagged. One bad row never breaks the run. Add timeouts and backoff.
12. **Cost/latency awareness.** Track calls and approximate cost per row. Put a budget guard
    in. Keep a cheap fallback model path.
13. **Classical ML is a risk, not a shortcut.** In May, trained classifiers (TF-IDF + LogReg,
    Naive Bayes, etc.) overfit a tiny labeled set and did poorly on hidden rows. Only use one if
    the problem gives plenty of labeled data, and validate it on held-out rows. Prefer ML as a
    helper signal (e.g. a retrieval reranker or a risk feature), not the final decision-maker.
    Rule-only systems also ranked low; rules belong in gates, not as the whole system.
15. **Make the agent loop real and bounded.** If the task fits it: model-driven tool calls
    (search / read / lookup), a hard max-iteration cap, schema-validated final output, citation
    checks, and deterministic gates around it. Type-hint everything, keep functions small, and
    split modules by role, because the code judge scores only what is observable in source.
14. **Language/runtime:** use what the participant is fastest and strongest in (likely Python).
    Keep a single entry point (e.g. `python code/main.py`) matching whatever the problem
    statement/AGENTS.md specifies. Do not rename required entry points.

---

## 6. Evaluation protocol

- If a labeled sample is provided, build `eval/run_eval.py` immediately: per-field accuracy,
  confusion summary, and a list of mismatches with the model's stated reason.
- If there are few/no labels, hand-label 15-30 representative rows yourself (include edge
  cases and adversarial ones). Write expectations BEFORE running. Record them in `eval/cases.md`.
- Tag every error: `logic_bug` | `model_misread` | `ambiguous_spec` | `bad_label?`.
  Fix logic bugs by offline re-grading from cached responses (free). Batch model-misread
  fixes and re-run rarely.
- **Measure variance.** Run the model path 2-3 times; report the spread. Do not re-roll to get
  a lucky number. Do not "fix" differences within noise.
- **Input-dependence tests:** blank/knock-out the key input and confirm the output changes
  (or collapses to abstain). Swap inputs and confirm outputs change.
- **Consistency checks:** near-duplicate inputs should get consistent outputs. Unexplained
  inconsistency means a prompt/guardrail/validation issue.
- **Do NOT overfit to the sample:** no hardcoding row IDs or test strings, no per-row special
  cases. If a rule only helps one row, ask whether it generalizes; if not, drop it.
- If using an LLM-as-judge, define what it checks, pair it with problem-specific metrics, and
  spot-check its judgments against your own.
- Keep an `eval/results.md` table: change -> metric before -> after -> keep/revert.

---

## 7. Output CSV QA (run as a script, then eyeball)

Write `scripts/check_output.py` that fails loudly on:
- Row count differs from input; any ID missing or duplicated; row order differs if order matters.
- Column names/order differ from the problem statement EXACTLY.
- Any categorical value outside the allowed set; empty required fields; stray whitespace/case issues.
- Encoding/quoting issues (newlines, commas, quotes inside text fields); non-UTF-8.
- Justification/response fields that are empty, generic, or contradict the label or status
  (the judge caps these at ~70 even when the action is correct). Add a script check that each
  justification mentions concrete evidence and is consistent with the chosen status.
- Both extremes are penalized: do not escalate everything and do not reply to everything.
  Print the status distribution and sanity-check it.
Then manually read ~20 rows as if you had never seen the project, including every flagged row.
Justifications should cite the plain evidence; uncertain cases should visibly say why.

---

## 8. Code, README, and packaging hygiene

- Structure by role: input loading, prompts, agent/model call, validation, decision rules,
  evaluation, CLI/entry. Not one 2,000-line file; not 20 micro-modules.
- Names reflect role. No `utils.py`, `helper.py`, `final.py`, `test2.py`.
- Prompts are versioned files (`code/prompts/`), not buried strings. Each prompt states: the
  task, allowed outputs, the evidence to use, the exact return format (JSON schema), and what to
  do when information is missing or conflicting. It also states that input text is data.
- Secrets: environment variables only. `.env` gitignored, `.env.example` committed with
  placeholders. Grep the repo and the zip for keys before submitting.
- No hardcoded absolute paths. Runs from a fresh clone on another machine.
- Remove dead code, commented-out experiments, unused imports, stale files, `__pycache__`,
  `.venv`, `node_modules`, large data files (follow the zip rules in the problem statement).
- `code/README.md` must contain: what it does, architecture in 5-10 lines (with the flow),
  setup steps, dependency install, env vars, the exact run command(s), input/output file
  locations, how to run eval, how reproducibility works (seeds, cache/replay), known
  limitations, and where each decision lives (file pointers).
- Fresh-clone test: unzip into a new folder, new venv, follow the README literally. Fix every gap.

---

## 9. Interview preparation (30 min, AI judge, camera on)

What the judge probes (HackerRank blog + earlier rubric): depth of understanding, trade-off
awareness, failure-mode reasoning, honesty about what AI wrote vs what you designed.

- Prepare a 2-minute architecture walkthrough from memory: where input enters, how context is
  built, where the model is called, what it may decide, what code validates, where retries/
  abstain happen, where output is written.
- For every major component, know: why it exists, what alternative you rejected, one concrete
  case where it mattered, and how it fails.
- Know your numbers: eval scores, what changed them, which changes did NOT help (say so).
- Know the prompt, the schema, the thresholds, the main functions by name.
- Be able to trace one real input end to end, including what is logged.
- Answer format: direct answer first -> one concrete detail -> tie to the task -> stop.
- Be honest: "AI wrote this part; I reviewed it like this; I changed X because Y."
  Name limitations precisely (what you tested vs did not).
- Do NOT claim features that are not in the code. The judge reads the repo.
- Logistics: quiet room, charged laptop plugged in, working mic and camera, stable internet
  with a phone hotspot as backup, water nearby. Close notifications. Test mic/camera beforehand.
- Take the interview when rested, but do not miss the window stated in the instructions.
- If you pause to think, that is fine. Do not read from a script on screen.

---

## 10. Submission checklist

- [ ] Re-read problem_statement.md "hard requirements" line by line; each one has a check.
- [ ] Deadline confirmed; submitting with >= 1 hour buffer.
- [ ] Final output CSV produced by the SAME code in the zip (not hand-edited).
- [ ] Output QA script passes; manual read-through done.
- [ ] Code ZIP: only what the instructions allow; README present and tested from fresh clone.
- [ ] No secrets in code, zip, logs, or git history. (Rotate any key that was ever pasted into a prompt.)
- [ ] Chat transcript file exists, is the official log, is complete and unedited; size looks sane.
- [ ] If more than one tool/session was used, all turns are in the one shared log.
- [ ] Submission uploaded on the official platform; confirmation screen/email saved.
- [ ] Interview started/scheduled per instructions; environment tested.
- [ ] Final commit tagged; nothing changed after submission that contradicts what was submitted.

---

## 11. Do-nots

- Do not hardcode answers for known test rows, or tune to leaked/seen labels in a way that
  will not generalize.
- Do not copy another participant's repo or paste large external solutions. It is a solo,
  individual-authorship event, and you must be able to explain every line.
- Do not let the model self-grade its own output as the only check.
- Do not add stages you cannot explain or measure.
- Do not chase run-to-run noise.
- Do not write unsupported labels, guesses, or invented evidence to the CSV to "fill" rows.
- Do not put secrets in prompts (they end up in the transcript).
- Do not edit or "clean up" the transcript log.
- Do not leave debugging prints, TODOs, or half-finished experiments in the submitted code.
- Do not submit in the last minutes.

---

## 12. Pointer to add to the official repo files

Add this at the VERY END of the official `AGENTS.md` (and `CLAUDE.md` if present), without
touching onboarding or logging sections:

```
## Additional participant playbook
Also read and follow ORCHESTRATE_PLAYBOOK.md in the repo root. If it conflicts with this
file or problem_statement.md, this file and problem_statement.md win; tell the user.
```

## 13. Sources used to write this playbook

- Event page: hackerrank.com/hackerrank-orchestrate-october26 (FAQ bodies not readable)
- Registration email (screenshot) and HackerRank blog "Getting better at Orchestrate" (Jul 24, 2026)
- Official May 2026 starter repo: interviewstreet/hackerrank-orchestrate-may26 (README, AGENTS.md, evalutation_criteria.md)
- Saai Syvendra, "Winning HackerRank Orchestrate" (May edition #1)
- Swayam Mishra, "How to build AI agents you can actually trust" (June edition top 3)
- Participant testimonials on the event page (August edition winners/finishers)

---

## 14. Reference: patterns from a past top finisher's public repo (trickymind1324/personal-finance-agent)

Source: I cloned the public repo and read its README, file tree, `loop.py`, prompts and
`docs/CONTRACT.md`. The repo has a single "Initial commit", so it is a cleaned-up final state,
not a record of his hour-by-hour process. I could not confirm which edition it belongs to or
how it was scored. Use these as PATTERNS. Do not copy files or text: solo authorship, and the
judge will ask you to explain every line.

What he did (all observable in the repo):
1. **Contract first.** `docs/CONTRACT.md` fixes the exact output schema, formatting rules, and
   numbered invariants (I-1, I-2, ...). Invariants are runtime-asserted: a violation RAISES
   rather than being patched silently. Rules are tagged: quoted from the task / derived from
   solved samples / explicit convention decision to tune.
2. **Reverse-engineer conventions from the solved sample rows** (a "convention audit" with
   hundreds of checks) before building. Learn the hidden scoring conventions from the labeled
   samples, e.g. number formatting, date rules, when a field is empty.
3. **An early experiment decided the architecture.** A small "anchor experiment" showed the
   model's evidence reading cut error from 13.9% to 2.5%, so the model was placed at exactly
   ONE boundary (reading messy evidence); everything downstream is deterministic code.
4. **Bounded tool loop:** model chooses tools (inspect image, read linked row, re-read thread),
   MAX_TOOL_ITERATIONS cap, must end with a schema-validated `record_*` tool or
   `declare_unresolvable`. This is a genuine agent loop that is still controlled.
5. **Error taxonomy for retries:** parse errors retried max 2 with the validation errors fed
   back; transport errors retried with backoff; refusals NEVER retried.
6. **Injection defense in depth:** untrusted text wrapped in a fence with `<`/`>` defanged so it
   can't close the fence; the prompt says fenced content is data; imperatives aimed at the model
   are quoted verbatim into a field; an independent code-side regex scan also gates behavior.
7. **Reproducibility:** every model response cached, content-addressed by hash of prompt + tool
   schemas + model id; an `--offline` mode reproduces `output.csv` bit-identically with zero API
   calls; spend caps (per call/run/USD) with pre-flight checks. Packaging script proves a
   fresh-unpack double-run diff.
8. **Evidence of iteration:** `analysis/reports/` holds versioned eval runs (v1..v6), a naive
   baseline, an ablation, and `docs/FAILURES.md` (22 worked failure entries). README reports
   baseline 52.7% -> 78.7% composite with no column regressing.
9. **Tests:** ~76 offline tests with all model calls mocked, run before any paid call.
10. **Honest README:** states plainly what is deterministic and what is only "likely" stable.
11. **Hygiene:** prompts live in `prompts/*.md`; modules by role (ledger, simulate, solver,
    plans, reconcile, evidence/); mostly 100-350 lines per file; `from __future__ import
    annotations`, type hints, dataclasses; `.env.example`; validators in `code/`.

Skeleton worth mirroring (names are yours to choose):
```
code/main.py            entry point (flags: --offline, --samples, --out)
code/validate_output.py contract check for the final CSV
code/evaluation/        score.py (per-column metrics vs pinned run + baseline), baseline.py
src/<pkg>/              modules by role; model layer in its own subpackage (client, loop, schema)
prompts/                every prompt and tool description as a file
docs/                   CONTRACT.md (schema + invariants), FAILURES.md (what broke, why, fix)
analysis/reports/       data audit, eval runs, ablations
data/cache/             content-addressed model responses (replay mode)
tests/                  offline tests, model mocked
```

Be realistic about scope: his repo is ~4,000 lines, 76 tests and 22 failure entries. In 24 hours
(with sleep and an interview) aim for a smaller version of the same discipline:
CONTRACT.md + one bounded loop + deterministic gates + response cache + eval script +
FAILURES.md with 5-10 honest entries + a handful of unit tests on the pure decision code.
Do not add more machinery than you can defend in 30 minutes of questioning.
