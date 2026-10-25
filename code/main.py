"""
main.py - End-to-end pipeline CLI for Ghost Data Still Exists deletion audit agent.

Supports:
  --mode samples : Audits 32 public sample cases and validates against sample_output.csv
  --mode full    : Audits all 518 evaluation cases from dataset/deletion_requests.csv
                   and writes final output.csv to the repository root.
"""

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from code.activity_index import ActivityIndex
from code.evidence_index import EvidenceIndex
from code.identity_resolver import IdentityResolver
from code.intent_filter import check_deletion_intent
from code.policy_engine import PolicyEngine
from code.step_sorter import sort_and_number_steps


def build_pipeline(dataset_dir: Path, cache_dir: Path):
    """Initializes and returns the audit pipeline components."""
    print("Initializing IdentityResolver...")
    resolver = IdentityResolver(
        dataset_dir / "user_identities.csv", dataset_dir / "user_audit_log.csv"
    )

    print("Indexing evidence files...")
    evidence_index = EvidenceIndex(dataset_dir, cache_dir)

    print("Indexing global system activity...")
    activity_index = ActivityIndex(dataset_dir / "system_activity.csv")

    print("Initializing PolicyEngine...")
    policy_engine = PolicyEngine(evidence_index, activity_index)

    return resolver, evidence_index, activity_index, policy_engine


def extract_worker_known_resources(
    activity_index: ActivityIndex,
    requested_at: str,
    reported_at: str,
    user_id: str,
) -> Set[str]:
    """
    Extracts candidate resources targeted by deletion_worker for this case window.
    """
    known_res = set()
    worker_events = [
        ev for ev in activity_index.events
        if ev.source_system == "deletion_worker" and requested_at <= ev.event_time <= reported_at
    ]

    for ev in worker_events:
        if ev.resource_id:
            known_res.add(ev.resource_id)

    return known_res


def process_case(
    req: Dict[str, str],
    resolver: IdentityResolver,
    activity_index: ActivityIndex,
    policy_engine: PolicyEngine,
) -> Dict[str, Any]:
    """Processes a single deletion request and returns output row dictionary."""
    cid = req["case_id"].strip()
    email = req["email"].strip()
    req_at = req["requested_at"].strip()
    rep_at = req.get("reported_at", "").strip()
    audit_at = req["audit_at"].strip()
    text = req.get("request_text", "").strip()

    # 1. Authorize deletion intent
    is_deletion, reason = check_deletion_intent(text)
    if not is_deletion:
        return {
            "case_id": cid,
            "deletion_status": "NOT_APPLICABLE",
            "steps_json": "[]",
        }

    # 2. Resolve current and historical identifiers
    user = resolver.resolve_by_email(email)
    if not user:
        return {
            "case_id": cid,
            "deletion_status": "NOT_APPLICABLE",
            "steps_json": "[]",
        }

    # 3. Evaluate deletion policy and evidence
    status, raw_steps = policy_engine.audit_case(
        user=user,
        requested_at=req_at,
        audit_at=audit_at,
        reported_at=rep_at,
    )

    # 5. Deterministically sort and consecutively number steps
    ordered_steps = sort_and_number_steps(raw_steps)
    steps_json = json.dumps(ordered_steps, separators=(",", ":"))

    return {
        "case_id": cid,
        "deletion_status": status,
        "steps_json": steps_json,
    }


def run_pipeline(
    mode: str,
    output_path: Path,
    dataset_dir: Path,
    cache_dir: Path,
    evaluate: bool = False,
):
    """Executes the pipeline for the given mode and writes output CSV."""
    resolver, evidence_index, activity_index, policy_engine = build_pipeline(
        dataset_dir, cache_dir
    )

    if mode == "samples":
        input_csv = dataset_dir / "sample_deletion_requests.csv"
    else:
        input_csv = dataset_dir / "deletion_requests.csv"

    print(f"Reading requests from {input_csv}...")
    with open(input_csv, mode="r", encoding="utf-8") as f:
        requests = list(csv.DictReader(f))

    print(f"Processing {len(requests)} cases in '{mode}' mode...")
    rows = []
    for i, req in enumerate(requests, 1):
        row = process_case(req, resolver, activity_index, policy_engine)
        rows.append(row)
        if i % 50 == 0 or i == len(requests):
            print(f"  Processed {i}/{len(requests)} cases...")

    # Sort strictly by case_id
    rows.sort(key=lambda r: r["case_id"])

    # Write output CSV
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["case_id", "deletion_status", "steps_json"]
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Successfully wrote {len(rows)} cases to {output_path}")

    # If samples mode and evaluate flag is on, evaluate against ground truth
    if mode == "samples" and evaluate:
        gt_path = dataset_dir / "sample_output.csv"
        if gt_path.exists():
            print("\nRunning evaluation on sample predictions...")
            from code.evaluation.main import evaluate_predictions, print_evaluation_report

            results, diffs = evaluate_predictions(output_path, gt_path)
            print_evaluation_report(results, diffs, max_diffs=10)


def main():
    parser = argparse.ArgumentParser(
        description="Ghost Data Still Exists - Deletion Audit Pipeline"
    )
    parser.add_argument(
        "--mode",
        choices=["samples", "full"],
        default="samples",
        help="Run mode: 'samples' for 32 public cases, 'full' for 518 evaluation cases.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output CSV path. Defaults to root output.csv for full mode, scratch/sample_predictions.csv for samples.",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=REPO_ROOT / "dataset",
        help="Path to dataset directory.",
    )
    parser.add_argument(
        "--cache",
        type=Path,
        default=REPO_ROOT / "code" / "cache",
        help="Path to code/cache directory.",
    )
    parser.add_argument(
        "--evaluate",
        action="store_true",
        default=True,
        help="Run evaluation against sample_output.csv when mode is samples.",
    )

    args = parser.parse_args()

    if args.output is None:
        if args.mode == "full":
            args.output = REPO_ROOT / "output.csv"
        else:
            args.output = REPO_ROOT / "scratch" / "sample_predictions.csv"

    run_pipeline(
        mode=args.mode,
        output_path=args.output,
        dataset_dir=args.dataset,
        cache_dir=args.cache,
        evaluate=args.evaluate,
    )


if __name__ == "__main__":
    main()
