"""Evaluation metrics for HackerRank Orchestrate: Ghost Data Still Exists.

Provides pure functions for:
- Case-level deletion_status accuracy
- Step-level precision, recall, and F1 on (phase, system_id, resource_id, operation, state, evidence_id)
- Per-field accuracy across step attributes
- Exact sequence accuracy
- Per-case diff generation for debugging mismatches
"""

import json
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass(frozen=True)
class Step:
    """Represents a single audit/remediation/verification step."""
    step_no: int
    phase: str
    system_id: str
    resource_id: str
    operation: str
    state: str
    evidence_id: str

    def to_tuple_without_step_no(self) -> Tuple[str, str, str, str, str, str]:
        """Returns the 6-tuple identifying the step content independent of sequence number."""
        return (
            self.phase,
            self.system_id,
            self.resource_id,
            self.operation,
            self.state,
            self.evidence_id,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Returns the step as a dictionary matching the JSON schema."""
        return {
            "step_no": self.step_no,
            "phase": self.phase,
            "system_id": self.system_id,
            "resource_id": self.resource_id,
            "operation": self.operation,
            "state": self.state,
            "evidence_id": self.evidence_id,
        }


@dataclass
class CaseRecord:
    """Represents one evaluation case prediction or ground truth row."""
    case_id: str
    deletion_status: str
    steps: List[Step]


def parse_step(raw_step: Dict[str, Any]) -> Step:
    """Parses a dictionary into a typed Step object."""
    return Step(
        step_no=int(raw_step.get("step_no", 0)),
        phase=str(raw_step.get("phase", "")),
        system_id=str(raw_step.get("system_id", "")),
        resource_id=str(raw_step.get("resource_id", "")),
        operation=str(raw_step.get("operation", "")),
        state=str(raw_step.get("state", "")),
        evidence_id=str(raw_step.get("evidence_id", "")),
    )


def parse_steps_json(steps_json_str: str) -> List[Step]:
    """Parses a JSON string array of steps into a list of Step objects."""
    if not steps_json_str or not steps_json_str.strip():
        return []
    data = json.loads(steps_json_str)
    if not isinstance(data, list):
        raise ValueError(f"Expected JSON list of steps, got {type(data)}")
    return [parse_step(item) for item in data]


def compute_status_accuracy(
    predictions: Dict[str, CaseRecord],
    ground_truth: Dict[str, CaseRecord],
) -> float:
    """Computes case-level status accuracy (percentage of matching deletion_status)."""
    if not ground_truth:
        return 0.0

    common_cases = set(predictions.keys()) & set(ground_truth.keys())
    if not common_cases:
        return 0.0

    correct = sum(
        1 for cid in common_cases
        if predictions[cid].deletion_status == ground_truth[cid].deletion_status
    )
    return correct / len(ground_truth)


def compute_step_level_metrics(
    predictions: Dict[str, CaseRecord],
    ground_truth: Dict[str, CaseRecord],
) -> Tuple[float, float, float]:
    """Computes step-level precision, recall, and F1 on the 6-tuple:

    (phase, system_id, resource_id, operation, state, evidence_id).
    Returns (precision, recall, f1).
    """
    total_tp = 0
    total_pred = 0
    total_gt = 0

    all_cases = set(ground_truth.keys()) | set(predictions.keys())
    for cid in all_cases:
        pred_record = predictions.get(cid)
        gt_record = ground_truth.get(cid)

        pred_steps = pred_record.steps if pred_record else []
        gt_steps = gt_record.steps if gt_record else []

        pred_counts = Counter(s.to_tuple_without_step_no() for s in pred_steps)
        gt_counts = Counter(s.to_tuple_without_step_no() for s in gt_steps)

        overlap = sum((pred_counts & gt_counts).values())
        total_tp += overlap
        total_pred += len(pred_steps)
        total_gt += len(gt_steps)

    if total_pred == 0 and total_gt == 0:
        return (1.0, 1.0, 1.0)

    precision = total_tp / total_pred if total_pred > 0 else 0.0
    recall = total_tp / total_gt if total_gt > 0 else 0.0
    f1 = (
        (2 * precision * recall) / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    return (precision, recall, f1)


def compute_field_accuracy(
    predictions: Dict[str, CaseRecord],
    ground_truth: Dict[str, CaseRecord],
) -> Dict[str, float]:
    """Computes per-field accuracy across step attributes for positionally aligned steps."""
    fields = ["phase", "system_id", "resource_id", "operation", "state", "evidence_id"]
    correct_by_field = {f: 0 for f in fields}
    total_step_slots = 0

    for cid, gt_record in ground_truth.items():
        pred_record = predictions.get(cid)
        pred_steps = pred_record.steps if pred_record else []
        gt_steps = gt_record.steps

        num_slots = max(len(pred_steps), len(gt_steps))
        total_step_slots += num_slots

        for idx in range(num_slots):
            has_pred = idx < len(pred_steps)
            has_gt = idx < len(gt_steps)

            if has_pred and has_gt:
                p_step = pred_steps[idx]
                g_step = gt_steps[idx]
                for f in fields:
                    if getattr(p_step, f) == getattr(g_step, f):
                        correct_by_field[f] += 1
            # If slot exists in only one, fields count as incorrect (0 added)

    if total_step_slots == 0:
        return {f: 1.0 for f in fields}

    return {f: correct_by_field[f] / total_step_slots for f in fields}


def compute_sequence_accuracy(
    predictions: Dict[str, CaseRecord],
    ground_truth: Dict[str, CaseRecord],
) -> float:
    """Computes exact sequence accuracy: fraction of cases where status and

    entire ordered steps list match identically.
    """
    if not ground_truth:
        return 0.0

    matches = 0
    for cid, gt_record in ground_truth.items():
        pred_record = predictions.get(cid)
        if not pred_record:
            continue

        if pred_record.deletion_status != gt_record.deletion_status:
            continue

        if len(pred_record.steps) != len(gt_record.steps):
            continue

        # Check every step in exact order
        all_steps_match = True
        for p_step, g_step in zip(pred_record.steps, gt_record.steps):
            if p_step != g_step:
                all_steps_match = False
                break

        if all_steps_match:
            matches += 1

    return matches / len(ground_truth)


def generate_case_diffs(
    predictions: Dict[str, CaseRecord],
    ground_truth: Dict[str, CaseRecord],
) -> List[str]:
    """Produces detailed diff strings for every case with a discrepancy."""
    diffs = []
    all_cids = sorted(set(ground_truth.keys()) | set(predictions.keys()))

    for cid in all_cids:
        pred = predictions.get(cid)
        gt = ground_truth.get(cid)

        if not pred:
            diffs.append(f"[{cid}] MISSING in predictions.")
            continue
        if not gt:
            diffs.append(f"[{cid}] EXTRA case not in ground truth.")
            continue

        case_discrepancies = []
        if pred.deletion_status != gt.deletion_status:
            case_discrepancies.append(
                f"  Status: predicted '{pred.deletion_status}' != GT '{gt.deletion_status}'"
            )

        if len(pred.steps) != len(gt.steps):
            case_discrepancies.append(
                f"  Step count: predicted {len(pred.steps)} != GT {len(gt.steps)}"
            )

        max_len = max(len(pred.steps), len(gt.steps))
        for idx in range(max_len):
            if idx >= len(pred.steps):
                case_discrepancies.append(f"  Step #{idx+1}: MISSING in prediction (GT: {gt.steps[idx].to_dict()})")
            elif idx >= len(gt.steps):
                case_discrepancies.append(f"  Step #{idx+1}: EXTRA in prediction ({pred.steps[idx].to_dict()})")
            elif pred.steps[idx] != gt.steps[idx]:
                p = pred.steps[idx]
                g = gt.steps[idx]
                diff_fields = [
                    f"{field}: pred '{getattr(p, field)}' != gt '{getattr(g, field)}'"
                    for field in ["step_no", "phase", "system_id", "resource_id", "operation", "state", "evidence_id"]
                    if getattr(p, field) != getattr(g, field)
                ]
                case_discrepancies.append(f"  Step #{idx+1} mismatch: " + ", ".join(diff_fields))

        if case_discrepancies:
            diffs.append(f"[{cid}] MISMATCH:")
            diffs.extend(case_discrepancies)

    return diffs
