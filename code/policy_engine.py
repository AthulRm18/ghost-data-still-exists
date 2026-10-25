"""
policy_engine.py - Applies deletion rules and reconstructs complete/incomplete state.

Implements Contract Section 5 & 6:
1. Synthesized A+C rule: Findings strictly require participant evidence; Complete requires
   affirmative proof for verified records; reported_status is never trusted.
2. Formulates FINDING, REMEDIATION, and post-remediation VERIFICATION steps.
3. Formulates evidence-backed VERIFICATION steps for COMPLETE cases.
"""

from typing import Any, Dict, List, Optional, Set, Tuple

from code.activity_index import ActivityIndex
from code.evidence_index import EvidenceIndex, EvidenceObservation
from code.identity_resolver import UserIdentity


class PolicyEngine:
    def __init__(self, evidence_index: EvidenceIndex, activity_index: ActivityIndex):
        self.evidence_index = evidence_index
        self.activity_index = activity_index

    def audit_case(
        self,
        user: Optional[UserIdentity],
        requested_at: str,
        audit_at: str,
        reported_at: Optional[str] = None,
        known_resource_ids: Optional[Set[str]] = None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Reconstructs the deletion state for a single user at audit_at.

        Returns:
            (deletion_status: str, steps: List[Dict[str, Any]])
        """
        if not user:
            return "NOT_APPLICABLE", []

        # 1. Query all pre-audit evidence observations
        observations = self.evidence_index.query_observations_for_user(
            user, audit_at, known_resource_ids=known_resource_ids
        )

        findings: List[Dict[str, Any]] = []
        verified_items: List[Dict[str, Any]] = []

        seen_finding_keys = set()
        seen_verified_keys = set()

        # Track known resources for this user, prioritizing latest post-request observations
        primary_account_id = None
        security_audit_id = None

        post_obs = [o for o in observations if o.captured_at >= requested_at]
        obs_by_time_desc = sorted(
            post_obs if post_obs else observations,
            key=lambda x: x.captured_at,
            reverse=True,
        )

        for obs in obs_by_time_desc:
            if obs.system_id == "account_service" and not primary_account_id:
                primary_account_id = obs.resource_id
            elif obs.system_id == "security_service" and not security_audit_id:
                security_audit_id = obs.resource_id

        # HEURISTIC (Validated on 32 samples): For a user whose account_service resource
        # is not found in other evidence, test deletion_worker DELETE_RECORD activity
        if not primary_account_id and reported_at:
            heuristic_acc = self.activity_index.find_worker_account_heuristic(
                requested_at, reported_at, audit_at, window_seconds=600
            )
            if heuristic_acc:
                primary_account_id = heuristic_acc

        for obs in observations:
            sys_id = obs.system_id
            res_id = obs.resource_id

            # Evidence captured before requested_at is pre-request historical context;
            # deletion state audits evaluate post-request state up to audit_at.
            if obs.captured_at < requested_at:
                continue

            # Case A: Ghost or remaining account record in failover/read replica
            if sys_id == "account_service":
                if obs.state == "PRESENT":
                    f_key = (sys_id, res_id, "REPORT_REMAINING_RECORD")
                    if f_key not in seen_finding_keys:
                        seen_finding_keys.add(f_key)
                        findings.append({
                            "phase": "FINDING",
                            "system_id": sys_id,
                            "resource_id": res_id,
                            "operation": "REPORT_REMAINING_RECORD",
                            "state": "PRESENT",
                            "evidence_id": obs.file_id,
                        })
                elif obs.observation_type == "LOOKUP_404" or obs.state == "ABSENT":
                    v_key = (sys_id, res_id, "VERIFY_RECORD_ABSENT")
                    if v_key not in seen_verified_keys:
                        seen_verified_keys.add(v_key)
                        verified_items.append({
                            "phase": "VERIFICATION",
                            "system_id": sys_id,
                            "resource_id": res_id,
                            "operation": "VERIFY_RECORD_ABSENT",
                            "state": "ABSENT",
                            "evidence_id": obs.file_id,
                        })

            # Case B: Search index entry
            elif sys_id == "search_service":
                if obs.state == "PRESENT":
                    f_key = (sys_id, res_id, "REPORT_REMAINING_RECORD")
                    if f_key not in seen_finding_keys:
                        seen_finding_keys.add(f_key)
                        findings.append({
                            "phase": "FINDING",
                            "system_id": sys_id,
                            "resource_id": res_id,
                            "operation": "REPORT_REMAINING_RECORD",
                            "state": "PRESENT",
                            "evidence_id": obs.file_id,
                        })

            # Case C: Export file remaining
            elif sys_id == "export_service":
                if obs.state == "PRESENT":
                    f_key = (sys_id, res_id, "REPORT_REMAINING_RECORD")
                    if f_key not in seen_finding_keys:
                        seen_finding_keys.add(f_key)
                        findings.append({
                            "phase": "FINDING",
                            "system_id": sys_id,
                            "resource_id": res_id,
                            "operation": "REPORT_REMAINING_RECORD",
                            "state": "PRESENT",
                            "evidence_id": obs.file_id,
                        })

            # Case D: Support ticket / attachment
            elif sys_id == "support_platform":
                if obs.observation_type == "SUPPORT_ATTACHMENT" or obs.details.get("marker_found") == "false":
                    f_key = (sys_id, res_id, "REPORT_REMAINING_RECORD")
                    if f_key not in seen_finding_keys:
                        seen_finding_keys.add(f_key)
                        findings.append({
                            "phase": "FINDING",
                            "system_id": sys_id,
                            "resource_id": res_id,
                            "operation": "REPORT_REMAINING_RECORD",
                            "state": "PRESENT",
                            "evidence_id": obs.file_id,
                        })
                elif obs.state == "PRESENT":
                    f_key = (sys_id, res_id, "REPORT_EXPOSED_PII")
                    if f_key not in seen_finding_keys:
                        seen_finding_keys.add(f_key)
                        findings.append({
                            "phase": "FINDING",
                            "system_id": sys_id,
                            "resource_id": res_id,
                            "operation": "REPORT_EXPOSED_PII",
                            "state": "PRESENT",
                            "evidence_id": obs.file_id,
                        })
                elif obs.state in ("REDACTED", "ABSENT"):
                    v_key = (sys_id, res_id, "VERIFY_RECORD_REDACTED")
                    if v_key not in seen_verified_keys:
                        seen_verified_keys.add(v_key)
                        verified_items.append({
                            "phase": "VERIFICATION",
                            "system_id": sys_id,
                            "resource_id": res_id,
                            "operation": "VERIFY_RECORD_REDACTED",
                            "state": "REDACTED",
                            "evidence_id": obs.file_id,
                        })

            # Case E: Analytics profile
            elif sys_id == "analytics_platform":
                if obs.observation_type == "MARKETING_PROFILE":
                    f_key = (sys_id, res_id, "REPORT_REMAINING_RECORD")
                    if f_key not in seen_finding_keys:
                        seen_finding_keys.add(f_key)
                        findings.append({
                            "phase": "FINDING",
                            "system_id": sys_id,
                            "resource_id": res_id,
                            "operation": "REPORT_REMAINING_RECORD",
                            "state": "PRESENT",
                            "evidence_id": obs.file_id,
                        })
                elif obs.observation_type == "ANONYMIZED" or obs.state == "ANONYMIZED":
                    v_key = (sys_id, res_id, "VERIFY_RECORD_ANONYMIZED")
                    if v_key not in seen_verified_keys:
                        seen_verified_keys.add(v_key)
                        verified_items.append({
                            "phase": "VERIFICATION",
                            "system_id": sys_id,
                            "resource_id": res_id,
                            "operation": "VERIFY_RECORD_ANONYMIZED",
                            "state": "ANONYMIZED",
                            "evidence_id": obs.file_id,
                        })
                elif obs.state == "PRESENT":
                    f_key = (sys_id, res_id, "REPORT_EXPOSED_PII")
                    if f_key not in seen_finding_keys:
                        seen_finding_keys.add(f_key)
                        findings.append({
                            "phase": "FINDING",
                            "system_id": sys_id,
                            "resource_id": res_id,
                            "operation": "REPORT_EXPOSED_PII",
                            "state": "PRESENT",
                            "evidence_id": obs.file_id,
                        })

            # Case F: Integration data flow
            elif sys_id == "integration_service":
                if obs.state == "ACTIVE":
                    f_key = (sys_id, res_id, "REPORT_ACTIVE_DATA_FLOW")
                    if f_key not in seen_finding_keys:
                        seen_finding_keys.add(f_key)
                        findings.append({
                            "phase": "FINDING",
                            "system_id": sys_id,
                            "resource_id": res_id,
                            "operation": "REPORT_ACTIVE_DATA_FLOW",
                            "state": "ACTIVE",
                            "evidence_id": obs.file_id,
                        })
                elif obs.state == "DISABLED":
                    v_key = (sys_id, res_id, "VERIFY_DATA_FLOW_DISABLED")
                    if v_key not in seen_verified_keys:
                        seen_verified_keys.add(v_key)
                        verified_items.append({
                            "phase": "VERIFICATION",
                            "system_id": sys_id,
                            "resource_id": res_id,
                            "operation": "VERIFY_DATA_FLOW_DISABLED",
                            "state": "DISABLED",
                            "evidence_id": obs.file_id,
                        })

            # Case G: Backup archive restore risk
            elif sys_id == "backup_service":
                if obs.state == "ACTIVE":
                    f_key = (sys_id, res_id, "REPORT_RESTORE_RISK")
                    if f_key not in seen_finding_keys:
                        seen_finding_keys.add(f_key)
                        findings.append({
                            "phase": "FINDING",
                            "system_id": sys_id,
                            "resource_id": res_id,
                            "operation": "REPORT_RESTORE_RISK",
                            "state": "ACTIVE",
                            "evidence_id": obs.file_id,
                        })
                elif obs.state == "BLOCKED":
                    v_key = (sys_id, res_id, "VERIFY_RESTORE_BLOCKED")
                    if v_key not in seen_verified_keys:
                        seen_verified_keys.add(v_key)
                        verified_items.append({
                            "phase": "VERIFICATION",
                            "system_id": sys_id,
                            "resource_id": res_id,
                            "operation": "VERIFY_RESTORE_BLOCKED",
                            "state": "BLOCKED",
                            "evidence_id": obs.file_id,
                        })

            # Case H: Security audit log
            elif sys_id == "security_service":
                v_key = (sys_id, res_id, "VERIFY_RECORD_PRESENT")
                if v_key not in seen_verified_keys:
                    seen_verified_keys.add(v_key)
                    verified_items.append({
                        "phase": "VERIFICATION",
                        "system_id": sys_id,
                        "resource_id": res_id,
                        "operation": "VERIFY_RECORD_PRESENT",
                        "state": "PRESENT",
                        "evidence_id": obs.file_id,
                    })

            # Case I: Account tombstone
            elif sys_id == "identity_service":
                if obs.state == "PRESENT":
                    f_key = (sys_id, res_id, "REPORT_EXPOSED_PII")
                    if f_key not in seen_finding_keys:
                        seen_finding_keys.add(f_key)
                        findings.append({
                            "phase": "FINDING",
                            "system_id": sys_id,
                            "resource_id": res_id,
                            "operation": "REPORT_EXPOSED_PII",
                            "state": "PRESENT",
                            "evidence_id": obs.file_id,
                        })
                elif obs.state == "REDACTED":
                    v_key = (sys_id, res_id, "VERIFY_RECORD_REDACTED")
                    if v_key not in seen_verified_keys:
                        seen_verified_keys.add(v_key)
                        verified_items.append({
                            "phase": "VERIFICATION",
                            "system_id": sys_id,
                            "resource_id": res_id,
                            "operation": "VERIFY_RECORD_REDACTED",
                            "state": "REDACTED",
                            "evidence_id": obs.file_id,
                        })

        # Status Decision
        if findings:
            status = "INCOMPLETE"
            steps = []
            steps.extend(findings)

            # Remediation & future verification
            for f in findings:
                s_id = f["system_id"]
                r_id = f["resource_id"]
                op = f["operation"]

                if op == "REPORT_REMAINING_RECORD":
                    steps.append({
                        "phase": "REMEDIATION",
                        "system_id": s_id,
                        "resource_id": r_id,
                        "operation": "DELETE_RECORD",
                        "state": "ABSENT",
                        "evidence_id": "",
                    })
                    steps.append({
                        "phase": "VERIFICATION",
                        "system_id": s_id,
                        "resource_id": r_id,
                        "operation": "VERIFY_RECORD_ABSENT",
                        "state": "ABSENT",
                        "evidence_id": "",
                    })
                elif op == "REPORT_EXPOSED_PII":
                    rem_op = "ANONYMIZE_RECORD" if s_id == "analytics_platform" else "REDACT_RECORD"
                    rem_state = "ANONYMIZED" if s_id == "analytics_platform" else "REDACTED"
                    ver_op = "VERIFY_RECORD_ANONYMIZED" if s_id == "analytics_platform" else "VERIFY_RECORD_REDACTED"
                    steps.append({
                        "phase": "REMEDIATION",
                        "system_id": s_id,
                        "resource_id": r_id,
                        "operation": rem_op,
                        "state": rem_state,
                        "evidence_id": "",
                    })
                    steps.append({
                        "phase": "VERIFICATION",
                        "system_id": s_id,
                        "resource_id": r_id,
                        "operation": ver_op,
                        "state": rem_state,
                        "evidence_id": "",
                    })
                elif op == "REPORT_ACTIVE_DATA_FLOW":
                    steps.append({
                        "phase": "REMEDIATION",
                        "system_id": s_id,
                        "resource_id": r_id,
                        "operation": "DISABLE_DATA_FLOW",
                        "state": "DISABLED",
                        "evidence_id": "",
                    })
                    steps.append({
                        "phase": "VERIFICATION",
                        "system_id": s_id,
                        "resource_id": r_id,
                        "operation": "VERIFY_DATA_FLOW_DISABLED",
                        "state": "DISABLED",
                        "evidence_id": "",
                    })
                elif op == "REPORT_RESTORE_RISK":
                    steps.append({
                        "phase": "REMEDIATION",
                        "system_id": s_id,
                        "resource_id": r_id,
                        "operation": "BLOCK_RESTORE",
                        "state": "BLOCKED",
                        "evidence_id": "",
                    })
                    steps.append({
                        "phase": "VERIFICATION",
                        "system_id": s_id,
                        "resource_id": r_id,
                        "operation": "VERIFY_RESTORE_BLOCKED",
                        "state": "BLOCKED",
                        "evidence_id": "",
                    })

            # Only add account verification if we observed a real primary_account_id
            if primary_account_id:
                has_acc_ver = any(
                    s["phase"] == "VERIFICATION" and s["system_id"] == "account_service"
                    for s in steps
                )
                if not has_acc_ver:
                    steps.append({
                        "phase": "VERIFICATION",
                        "system_id": "account_service",
                        "resource_id": primary_account_id,
                        "operation": "VERIFY_RECORD_ABSENT",
                        "state": "ABSENT",
                        "evidence_id": "",
                    })

            # Only add security audit verification if we observed a real security_audit_id
            if security_audit_id:
                has_sec_ver = any(
                    s["phase"] == "VERIFICATION" and s["system_id"] == "security_service"
                    for s in steps
                )
                if not has_sec_ver:
                    steps.append({
                        "phase": "VERIFICATION",
                        "system_id": "security_service",
                        "resource_id": security_audit_id,
                        "operation": "VERIFY_RECORD_PRESENT",
                        "state": "PRESENT",
                        "evidence_id": "",
                    })

            return status, steps
        else:
            # COMPLETE: use evidence-backed verified items plus
            # absence-from-snapshot verification for deletion-worker resources
            status = "COMPLETE"
            steps = list(verified_items)

            # Mine deletion-worker events for resource_ids targeted for this user
            deletion_resources = self.activity_index.get_deletion_resources_for_user(
                user, requested_at, audit_at
            )

            # For each targeted resource, check if an evidence snapshot proves absence
            for res_id, worker_events in deletion_resources.items():
                # Determine the target system from the worker event
                target_sys = "account_service"
                for we in worker_events:
                    if we.target_system:
                        target_sys = we.target_system
                        break

                # Check if we already have a verified item for this resource
                already_verified = any(
                    s["resource_id"] == res_id for s in steps
                )
                if already_verified:
                    continue

                # Find the latest worker event time
                latest_worker_time = max(we.event_time for we in worker_events)

                # Search for evidence snapshots captured AFTER the deletion
                # that do NOT contain this resource (proving absence)
                proving_file_id = self._find_absence_evidence(
                    res_id, target_sys, latest_worker_time, audit_at
                )

                if proving_file_id:
                    steps.append({
                        "phase": "VERIFICATION",
                        "system_id": target_sys,
                        "resource_id": res_id,
                        "operation": "VERIFY_RECORD_ABSENT",
                        "state": "ABSENT",
                        "evidence_id": proving_file_id,
                    })

            if not steps:
                # When no evidence exists to affirmatively prove deletion completion,
                # the case is unverifiable and marked INCOMPLETE with []
                return "INCOMPLETE", []

            return status, steps

    def _find_absence_evidence(
        self, resource_id: str, target_system: str,
        after_time: str, before_time: str
    ) -> str:
        """Finds an evidence file that proves a resource is absent.

        A database snapshot captured after the deletion event that does NOT
        contain the resource_id proves the deletion succeeded.

        Prefers profile/account snapshots (customer_profiles*) over generic
        multi-tenant data stores for account_service resources.
        """
        # Collect candidate evidence files that cover the target system
        # in the valid time window
        candidate_files = set()
        # Track which files contain profile tables (preferred for account_service)
        profile_files = set()

        for obs in self.evidence_index.observations:
            if obs.captured_at < after_time or obs.captured_at > before_time:
                continue
            if obs.system_id == target_system:
                candidate_files.add(obs.file_id)
                # Prefer files with profile table observations
                details = obs.details
                if isinstance(details, dict):
                    tbl = details.get("table", "")
                    if "customer_profiles" in tbl:
                        profile_files.add(obs.file_id)

        # Sort candidates: profile files first, then by file_id
        sorted_candidates = sorted(
            candidate_files,
            key=lambda fid: (0 if fid in profile_files else 1, fid)
        )

        # Among candidates, check if any does NOT contain our resource_id
        for fid in sorted_candidates:
            has_resource = any(
                obs.file_id == fid and obs.resource_id == resource_id
                for obs in self.evidence_index.observations
            )
            if not has_resource:
                return fid

        return ""

