"""Scorer and evaluation CLI for HackerRank Orchestrate: Ghost Data Still Exists.

Compares candidate prediction CSV against ground-truth CSV (e.g. dataset/sample_output.csv).

Usage:
    python code/evaluation/main.py --predictions path/to/preds.csv --ground-truth dataset/sample_output.csv
"""

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Enable relative import or direct execution


sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from code.evaluation.metrics import (
    CaseRecord,
    compute_field_accuracy,
    compute_sequence_accuracy,
    compute_status_accuracy,
    compute_step_level_metrics,
    generate_case_diffs,
    parse_steps_json,
)


def load_dataset_csv(csv_path: Path) -> Dict[str, CaseRecord]:
    """Loads a prediction or ground-truth CSV file and returns a dictionary of CaseRecord."""
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    records: Dict[str, CaseRecord] = {}
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required_headers = {"case_id", "deletion_status", "steps_json"}
        if not required_headers.issubset(reader.fieldnames or set()):
            raise ValueError(
                f"CSV must contain headers {required_headers}, found {reader.fieldnames}"
            )

        for row_idx, row in enumerate(reader, start=2):
            cid = row["case_id"].strip()
            status = row["deletion_status"].strip()
            raw_steps = row["steps_json"].strip()

            try:
                steps = parse_steps_json(raw_steps)
            except Exception as e:
                raise ValueError(
                    f"Row {row_idx} ({cid}): invalid steps_json: {e}"
                ) from e

            records[cid] = CaseRecord(
                case_id=cid,
                deletion_status=status,
                steps=steps,
            )

    return records


def evaluate_predictions(
    predictions_path: Path,
    ground_truth_path: Path,
) -> Tuple[Dict[str, Any], List[str]]:
    """Evaluates candidate predictions against ground truth and returns metric dict and diffs."""
    predictions = load_dataset_csv(predictions_path)
    ground_truth = load_dataset_csv(ground_truth_path)

    status_acc = compute_status_accuracy(predictions, ground_truth)
    prec, rec, f1 = compute_step_level_metrics(predictions, ground_truth)
    field_acc = compute_field_accuracy(predictions, ground_truth)
    seq_acc = compute_sequence_accuracy(predictions, ground_truth)
    diffs = generate_case_diffs(predictions, ground_truth)

    results = {
        "num_predictions": len(predictions),
        "num_ground_truth": len(ground_truth),
        "case_status_accuracy": status_acc,
        "step_precision": prec,
        "step_recall": rec,
        "step_f1": f1,
        "field_accuracy": field_acc,
        "sequence_accuracy": seq_acc,
        "num_mismatched_cases": len(diffs),
    }

    return results, diffs


def print_evaluation_report(results: Dict[str, Any], diffs: List[str], max_diffs: int = 10) -> None:
    """Prints a structured Markdown summary report of the evaluation metrics."""
    print("=" * 80)
    print("EVALUATION REPORT — GHOST DATA STILL EXISTS")
    print("=" * 80)
    print(f"Cases Evaluated: {results['num_predictions']} / {results['num_ground_truth']} ground truth cases")
    print("-" * 80)
    print(f"Case-Level Status Accuracy : {results['case_status_accuracy'] * 100:6.2f}%")
    print(f"Step-Level Precision       : {results['step_precision'] * 100:6.2f}%")
    print(f"Step-Level Recall          : {results['step_recall'] * 100:6.2f}%")
    print(f"Step-Level F1 Score        : {results['step_f1'] * 100:6.2f}%")
    print(f"Exact Sequence Accuracy    : {results['sequence_accuracy'] * 100:6.2f}%")
    print("-" * 80)
    print("Per-Field Accuracy (on positionally aligned steps):")
    for field, acc in results["field_accuracy"].items():
        print(f"  - {field:<16} : {acc * 100:6.2f}%")
    print("-" * 80)

    if diffs:
        print(f"Discrepancies Found: {len(diffs)} issue(s)")
        print(f"Displaying first {min(len(diffs), max_diffs)} diffs:")
        for d in diffs[:max_diffs]:
            print(f"  {d}")
        if len(diffs) > max_diffs:
            print(f"  ... and {len(diffs) - max_diffs} more discrepancies.")
    else:
        print("ALL CHECKS PASSED: 100% Bit-for-Bit Concordance with Ground Truth!")
    print("=" * 80)


def main() -> None:
    """CLI entry point for running evaluation."""
    parser = argparse.ArgumentParser(description="Scorer for Ghost Data Still Exists")
    parser.add_argument(
        "--predictions",
        "-p",
        type=Path,
        required=True,
        help="Path to candidate predictions CSV",
    )
    parser.add_argument(
        "--ground-truth",
        "-g",
        type=Path,
        default=Path("dataset/sample_output.csv"),
        help="Path to ground truth CSV (defaults to dataset/sample_output.csv)",
    )
    parser.add_argument(
        "--max-diffs",
        type=int,
        default=10,
        help="Maximum diff lines to display",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON string",
    )

    args = parser.parse_args()

    results, diffs = evaluate_predictions(args.predictions, args.ground_truth)

    if args.json:
        output_payload = {**results, "diffs": diffs}
        print(json.dumps(output_payload, indent=2))
    else:
        print_evaluation_report(results, diffs, max_diffs=args.max_diffs)


if __name__ == "__main__":
    main()
