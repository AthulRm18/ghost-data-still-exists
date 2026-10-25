"""
test_custom_cases.py - Executable unit tests for the three custom evaluation cases.

Uses the real domain vocabulary:
- system_id: account_service, security_service, search_service, support_platform, etc.
- resource_id: account_005, audit_record_2016, search_8911, etc.
- evidence_id: evidence_54, evidence_05, evidence_94, etc.
"""

import json
import unittest
from pathlib import Path

from code.evidence_index import EvidenceObservation
from code.identity_resolver import UserIdentity
from code.intent_filter import check_deletion_intent
from code.policy_engine import PolicyEngine
from code.step_sorter import sort_and_number_steps


class MockEvidenceIndex:
    def __init__(self, observations, evidence_files=None):
        self.obs = observations
        self.evidence_files = evidence_files or {}
        self.export_files_data = {}
        self.user_all_accounts = {}
        self.user_all_audit_records = {}

    def query_observations_for_user(self, user, audit_at, known_resource_ids=None):
        return [o for o in self.obs if o.captured_at <= audit_at]


class MockActivityIndex:
    def __init__(self, events=None, deletion_resources=None):
        self.events = events or []
        self.deletion_resources = deletion_resources or {}

    def get_deletion_resources_for_user(self, user, requested_at, audit_at):
        return self.deletion_resources

    def get_linked_resources_for_user(self, user, audit_at):
        return set()

    def find_worker_account_heuristic(self, requested_at, reported_at, audit_at, window_seconds=600):
        return None


class TestCustomEvaluationCases(unittest.TestCase):
    """
    Validates edge cases specified in evaluation_report.md:
    1. custom_01_marketing_optout: Communication preference vs deletion intent
    2. custom_02_replica_sync_recreation: Ghost record in replica snapshot
    3. custom_03_legal_hold_retention: Preserving retained security audit log
    """

    def test_custom_01_marketing_optout(self):
        """Case 1: User requests marketing communication opt-out, not deletion."""
        request_text = (
            "Please stop sending me your daily promotional discounts and marketing offers. "
            "I don't want any more sales emails."
        )
        is_deletion, reason = check_deletion_intent(request_text)
        self.assertFalse(is_deletion, "Marketing opt-out should not be classified as deletion")
        self.assertIn("promotional", reason.lower())

    def test_custom_02_replica_sync_recreation(self):
        """Case 2: Replica snapshot evidence_05 retains remaining search record."""
        user = UserIdentity(
            user_id="user_771",
            current_name="Elena Rostova",
            current_email="e.rostova@example.com",
            current_phone="+1-555-0199",
            current_email_hash="hash_771",
        )
        requested_at = "2026-09-01T10:00:00Z"
        audit_at = "2026-09-22T10:00:00Z"

        # Evidence observation from replica database evidence_05 showing search record still present
        obs = [
            EvidenceObservation(
                file_id="evidence_05",
                file_path="evidence/databases/customer_data_read_replica_20260921.sql",
                captured_at="2026-09-21T08:00:00Z",
                system_id="search_service",
                resource_id="search_8911",
                observation_type="SEARCH_RECORD",
                state="PRESENT",
            )
        ]
        engine = PolicyEngine(MockEvidenceIndex(obs), MockActivityIndex())
        status, raw_steps = engine.audit_case(user, requested_at, audit_at)
        ordered_steps = sort_and_number_steps(raw_steps)

        self.assertEqual(status, "INCOMPLETE")
        # Step 1: Finding
        self.assertEqual(ordered_steps[0]["phase"], "FINDING")
        self.assertEqual(ordered_steps[0]["system_id"], "search_service")
        self.assertEqual(ordered_steps[0]["resource_id"], "search_8911")
        self.assertEqual(ordered_steps[0]["operation"], "REPORT_REMAINING_RECORD")
        self.assertEqual(ordered_steps[0]["state"], "PRESENT")
        self.assertEqual(ordered_steps[0]["evidence_id"], "evidence_05")

        # Step 2: Remediation
        self.assertEqual(ordered_steps[1]["phase"], "REMEDIATION")
        self.assertEqual(ordered_steps[1]["system_id"], "search_service")
        self.assertEqual(ordered_steps[1]["operation"], "DELETE_RECORD")
        self.assertEqual(ordered_steps[1]["state"], "ABSENT")
        self.assertEqual(ordered_steps[1]["evidence_id"], "")

        # Verification step must include search_service absent
        self.assertTrue(any(
            s["phase"] == "VERIFICATION" and s["system_id"] == "search_service" and s["operation"] == "VERIFY_RECORD_ABSENT"
            for s in ordered_steps
        ))

    def test_custom_03_legal_hold_retention(self):
        """Case 3: Deletion completed while preserving statutory security audit record."""
        user = UserIdentity(
            user_id="user_889",
            current_name="Carlos Silva",
            current_email="csilva@example.com",
            current_phone="+1-555-0889",
            current_email_hash="hash_889",
        )
        requested_at = "2026-09-10T12:00:00Z"
        audit_at = "2026-09-27T12:00:00Z"

        # Evidence shows account is absent and security audit log is verified PRESENT in evidence_94
        obs = [
            EvidenceObservation(
                file_id="evidence_94",
                file_path="evidence/logs/resource_lookup_trace_20260926_103856.log",
                captured_at="2026-09-26T10:38:56Z",
                system_id="account_service",
                resource_id="account_889",
                observation_type="LOOKUP_404",
                state="ABSENT",
            ),
            EvidenceObservation(
                file_id="evidence_94",
                file_path="evidence/logs/resource_lookup_trace_20260926_103856.log",
                captured_at="2026-09-26T10:38:56Z",
                system_id="security_service",
                resource_id="audit_record_2016",
                observation_type="SECURITY_AUDIT_LOG",
                state="PRESENT",
            ),
        ]
        engine = PolicyEngine(MockEvidenceIndex(obs), MockActivityIndex())
        status, raw_steps = engine.audit_case(user, requested_at, audit_at)
        ordered_steps = sort_and_number_steps(raw_steps)

        self.assertEqual(status, "COMPLETE")
        # Must verify account_service absent
        self.assertTrue(any(
            s["system_id"] == "account_service" and s["operation"] == "VERIFY_RECORD_ABSENT" and s["evidence_id"] == "evidence_94"
            for s in ordered_steps
        ))
        # Must verify security audit record retained present
        self.assertTrue(any(
            s["system_id"] == "security_service" and s["resource_id"] == "audit_record_2016" and
            s["operation"] == "VERIFY_RECORD_PRESENT" and s["evidence_id"] == "evidence_94"
            for s in ordered_steps
        ))


if __name__ == "__main__":
    unittest.main()
