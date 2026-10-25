"""
step_sorter.py - Deterministic 4-tuple step sorter and consecutive step re-indexer.

Implements Contract Section 4:
sort_key = (phase_rank, operation_rank, system_id ASC, resource_id ASC)
Followed by consecutive 1-indexed numbering.
"""

from typing import Any, Dict, List

PHASE_RANK = {
    "FINDING": 0,
    "REMEDIATION": 1,
    "VERIFICATION": 2,
}

OPERATION_RANK = {
    # FINDING
    "REPORT_REMAINING_RECORD": 0,
    "REPORT_EXPOSED_PII": 1,
    "REPORT_ACTIVE_DATA_FLOW": 2,
    "REPORT_RESTORE_RISK": 3,
    # REMEDIATION
    "DISABLE_DATA_FLOW": 0,
    "BLOCK_RESTORE": 1,
    "DELETE_RECORD": 2,
    "REDACT_RECORD": 3,
    "ANONYMIZE_RECORD": 4,
    # VERIFICATION
    "VERIFY_RECORD_ABSENT": 0,
    "VERIFY_RECORD_PRESENT": 1,
    "VERIFY_RECORD_REDACTED": 2,
    "VERIFY_RECORD_ANONYMIZED": 3,
    "VERIFY_DATA_FLOW_DISABLED": 4,
    "VERIFY_RESTORE_BLOCKED": 5,
}


def sort_and_number_steps(steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Sorts steps deterministically by (phase_rank, operation_rank, system_id, resource_id)
    and assigns consecutive 1-indexed step_no values.
    """
    def step_key(s: Dict[str, Any]):
        p_rank = PHASE_RANK.get(s["phase"], 99)
        op_rank = OPERATION_RANK.get(s["operation"], 99)
        sys_id = s.get("system_id", "")
        res_id = s.get("resource_id", "")
        return (p_rank, op_rank, sys_id, res_id)

    sorted_steps = sorted(steps, key=step_key)

    numbered_steps = []
    for idx, s in enumerate(sorted_steps, start=1):
        clean_step = {
            "step_no": idx,
            "phase": s["phase"],
            "system_id": s["system_id"],
            "resource_id": s["resource_id"],
            "operation": s["operation"],
            "state": s["state"],
            "evidence_id": s.get("evidence_id", ""),
        }
        numbered_steps.append(clean_step)

    return numbered_steps
