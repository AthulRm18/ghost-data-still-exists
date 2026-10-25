import sys
from pathlib import Path

# Ensure repo root is prioritized on sys.path over built-in 'code' module
repo_root = str(Path(__file__).resolve().parent.parent.parent)
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)


import unittest
from code.evaluation.metrics import (

    CaseRecord,
    Step,
    compute_field_accuracy,
    compute_sequence_accuracy,
    compute_status_accuracy,
    compute_step_level_metrics,
    generate_case_diffs,
    parse_step,
    parse_steps_json,
)


class TestEvaluationMetrics(unittest.TestCase):
    def setUp(self):
        self.step_a1 = Step(
            step_no=1,
            phase="FINDING",
            system_id="account_service",
            resource_id="account_005",
            operation="REPORT_REMAINING_RECORD",
            state="PRESENT",
            evidence_id="evidence_54",
        )
        self.step_a2 = Step(
            step_no=2,
            phase="REMEDIATION",
            system_id="account_service",
            resource_id="account_005",
            operation="DELETE_RECORD",
            state="ABSENT",
            evidence_id="",
        )
        self.step_a3 = Step(
            step_no=3,
            phase="VERIFICATION",
            system_id="account_service",
            resource_id="account_005",
            operation="VERIFY_RECORD_ABSENT",
            state="ABSENT",
            evidence_id="",
        )

        self.gt = {
            "case_01": CaseRecord(
                case_id="case_01",
                deletion_status="COMPLETE",
                steps=[self.step_a3],
            ),
            "case_02": CaseRecord(
                case_id="case_02",
                deletion_status="INCOMPLETE",
                steps=[self.step_a1, self.step_a2],
            ),
            "case_03": CaseRecord(
                case_id="case_03",
                deletion_status="NOT_APPLICABLE",
                steps=[],
            ),
        }

    def test_parse_steps_json(self):
        raw = '[{"step_no": 1, "phase": "FINDING", "system_id": "account_service", "resource_id": "account_005", "operation": "REPORT_REMAINING_RECORD", "state": "PRESENT", "evidence_id": "evidence_54"}]'
        steps = parse_steps_json(raw)
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0], self.step_a1)

        empty_steps = parse_steps_json("[]")
        self.assertEqual(empty_steps, [])

    def test_status_accuracy_perfect(self):
        pred = {
            "case_01": CaseRecord("case_01", "COMPLETE", [self.step_a3]),
            "case_02": CaseRecord("case_02", "INCOMPLETE", [self.step_a1, self.step_a2]),
            "case_03": CaseRecord("case_03", "NOT_APPLICABLE", []),
        }
        acc = compute_status_accuracy(pred, self.gt)
        self.assertAlmostEqual(acc, 1.0)

    def test_status_accuracy_partial(self):
        pred = {
            "case_01": CaseRecord("case_01", "INCOMPLETE", [self.step_a3]),  # wrong
            "case_02": CaseRecord("case_02", "INCOMPLETE", [self.step_a1, self.step_a2]),
            "case_03": CaseRecord("case_03", "NOT_APPLICABLE", []),
        }
        acc = compute_status_accuracy(pred, self.gt)
        self.assertAlmostEqual(acc, 2 / 3)

    def test_step_level_metrics_perfect(self):
        pred = {
            "case_01": CaseRecord("case_01", "COMPLETE", [self.step_a3]),
            "case_02": CaseRecord("case_02", "INCOMPLETE", [self.step_a1, self.step_a2]),
            "case_03": CaseRecord("case_03", "NOT_APPLICABLE", []),
        }
        p, r, f1 = compute_step_level_metrics(pred, self.gt)
        self.assertAlmostEqual(p, 1.0)
        self.assertAlmostEqual(r, 1.0)
        self.assertAlmostEqual(f1, 1.0)

    def test_step_level_metrics_drop_on_missing_and_extra(self):
        # Case 02: missing step_a2, added an extra step_a3
        pred = {
            "case_01": CaseRecord("case_01", "COMPLETE", [self.step_a3]),
            "case_02": CaseRecord("case_02", "INCOMPLETE", [self.step_a1, self.step_a3]),
            "case_03": CaseRecord("case_03", "NOT_APPLICABLE", []),
        }
        p, r, f1 = compute_step_level_metrics(pred, self.gt)
        # Total GT steps = 3 (case_01: 1, case_02: 2)
        # Total Pred steps = 3 (case_01: 1, case_02: 2)
        # Matches: case_01 step_a3 (1), case_02 step_a1 (1). Total TP = 2.
        # Precision = 2/3, Recall = 2/3, F1 = 2/3
        self.assertAlmostEqual(p, 2 / 3)
        self.assertAlmostEqual(r, 2 / 3)
        self.assertAlmostEqual(f1, 2 / 3)

    def test_sequence_accuracy(self):
        # Exact match
        pred = {
            "case_01": CaseRecord("case_01", "COMPLETE", [self.step_a3]),
            "case_02": CaseRecord("case_02", "INCOMPLETE", [self.step_a1, self.step_a2]),
            "case_03": CaseRecord("case_03", "NOT_APPLICABLE", []),
        }
        self.assertAlmostEqual(compute_sequence_accuracy(pred, self.gt), 1.0)

        # Inverted step order in case_02
        pred_shuffled = {
            "case_01": CaseRecord("case_01", "COMPLETE", [self.step_a3]),
            "case_02": CaseRecord("case_02", "INCOMPLETE", [self.step_a2, self.step_a1]),  # swapped!
            "case_03": CaseRecord("case_03", "NOT_APPLICABLE", []),
        }
        # case_02 sequence fails -> 2 / 3
        self.assertAlmostEqual(compute_sequence_accuracy(pred_shuffled, self.gt), 2 / 3)

    def test_field_accuracy(self):
        # Mutate one field (operation) on step_a1 in case_02
        mutated_step = Step(
            step_no=1,
            phase="FINDING",
            system_id="account_service",
            resource_id="account_005",
            operation="REPORT_EXPOSED_PII",  # mutated
            state="PRESENT",
            evidence_id="evidence_54",
        )
        pred = {
            "case_01": CaseRecord("case_01", "COMPLETE", [self.step_a3]),
            "case_02": CaseRecord("case_02", "INCOMPLETE", [mutated_step, self.step_a2]),
            "case_03": CaseRecord("case_03", "NOT_APPLICABLE", []),
        }
        field_acc = compute_field_accuracy(pred, self.gt)
        self.assertAlmostEqual(field_acc["phase"], 1.0)
        self.assertAlmostEqual(field_acc["system_id"], 1.0)
        self.assertAlmostEqual(field_acc["resource_id"], 1.0)
        self.assertAlmostEqual(field_acc["state"], 1.0)
        self.assertAlmostEqual(field_acc["evidence_id"], 1.0)
        # 3 total slots: 2 matched, 1 mismatched -> 2/3
        self.assertAlmostEqual(field_acc["operation"], 2 / 3)

    def test_generate_case_diffs(self):
        pred = {
            "case_01": CaseRecord("case_01", "COMPLETE", [self.step_a3]),
            "case_02": CaseRecord("case_02", "INCOMPLETE", [self.step_a1]),  # missing step_a2
            "case_03": CaseRecord("case_03", "COMPLETE", []),  # wrong status
        }
        diffs = generate_case_diffs(pred, self.gt)
        self.assertTrue(any("case_02" in d for d in diffs))
        self.assertTrue(any("MISSING" in d for d in diffs))
        self.assertTrue(any("case_03" in d for d in diffs))
        self.assertTrue(any("Status: predicted 'COMPLETE' != GT 'NOT_APPLICABLE'" in d for d in diffs))

    def test_ground_truth_sample_step_count_matches_file(self):
        """Fails if the scorer's ground-truth step count differs from the total in sample_output.csv."""
        import csv
        import json
        from code.evaluation.main import load_dataset_csv

        gt_file = Path(repo_root) / "dataset" / "sample_output.csv"
        self.assertTrue(gt_file.exists(), f"Ground truth file missing: {gt_file}")

        # Count directly from raw CSV
        with open(gt_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            raw_total_steps = sum(len(json.loads(row["steps_json"])) for row in reader)

        # Count parsed by evaluation loader / scorer
        loaded_gt = load_dataset_csv(gt_file)
        scorer_total_steps = sum(len(rec.steps) for rec in loaded_gt.values())

        self.assertEqual(
            scorer_total_steps,
            raw_total_steps,
            f"Scorer step count ({scorer_total_steps}) != raw file step count ({raw_total_steps})",
        )
        self.assertEqual(scorer_total_steps, 193)


if __name__ == "__main__":
    unittest.main()

