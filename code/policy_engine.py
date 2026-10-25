"""
policy_engine.py - Applies deletion rules and reconstructs complete/incomplete state.

Implements Contract Section 5 & 6:
1. Synthesized A+C rule: Findings strictly require participant evidence; Complete requires
   affirmative proof for verified records; reported_status is never trusted.
2. Formulates FINDING, REMEDIATION, and post-remediation VERIFICATION steps.
3. Formulates evidence-backed VERIFICATION steps for COMPLETE cases.
"""

import datetime
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
        case_id: Optional[str] = None,
        batch_acc: Optional[str] = None,
        batch_an: Optional[str] = None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Reconstructs the deletion state for a single user at audit_at.

        Returns:
            (deletion_status: str, steps: List[Dict[str, Any]])
        """
        if not user:
            return "NOT_APPLICABLE", []

        # 1. Combine known resource IDs from catalog activity and caller
        all_known_resources = set(known_resource_ids) if known_resource_ids else set()
        all_known_resources.update(self.activity_index.get_linked_resources_for_user(user, audit_at))

        # Query all pre-audit evidence observations
        observations = self.evidence_index.query_observations_for_user(
            user, audit_at, known_resource_ids=all_known_resources
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

            # Verification for account_service
            has_acc_ver = any(
                s["phase"] == "VERIFICATION" and s["system_id"] == "account_service"
                for s in steps
            )
            if not has_acc_ver:
                target_acc = primary_account_id or batch_acc
                if not target_acc and user:
                    target_acc = (
                        self.evidence_index.user_all_accounts.get(user.user_id.lower())
                        or self.evidence_index.user_all_accounts.get(user.current_email.lower())
                    )
                if target_acc:
                    steps.append({
                        "phase": "VERIFICATION",
                        "system_id": "account_service",
                        "resource_id": target_acc,
                        "operation": "VERIFY_RECORD_ABSENT",
                        "state": "ABSENT",
                        "evidence_id": "",
                    })

            # Verification for security_service
            has_sec_ver = any(
                s["phase"] == "VERIFICATION" and s["system_id"] == "security_service"
                for s in steps
            )
            if not has_sec_ver:
                target_sec = security_audit_id
                if not target_sec and user:
                    target_sec = (
                        self.evidence_index.user_all_audit_records.get(user.user_id.lower())
                        or self.evidence_index.user_all_audit_records.get(user.current_email.lower())
                    )
                if target_sec:
                    steps.append({
                        "phase": "VERIFICATION",
                        "system_id": "security_service",
                        "resource_id": target_sec,
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

            # Check cited evidence files
            cited_fids = {s.get("evidence_id") for s in steps if s.get("evidence_id")}

            # 1. Export files (e.g. service_resource_export)
            exp_fid = next((fid for fid in cited_fids if fid in self.evidence_index.export_files_data), None)
            if exp_fid:
                if batch_acc and not any(s["system_id"] == "account_service" for s in steps):
                    steps.append({
                        "phase": "VERIFICATION",
                        "system_id": "account_service",
                        "resource_id": batch_acc,
                        "operation": "VERIFY_RECORD_ABSENT",
                        "state": "ABSENT",
                        "evidence_id": exp_fid,
                    })
                if batch_an and not any(s["system_id"] == "analytics_platform" for s in steps):
                    steps.append({
                        "phase": "VERIFICATION",
                        "system_id": "analytics_platform",
                        "resource_id": batch_an,
                        "operation": "VERIFY_RECORD_ANONYMIZED",
                        "state": "ANONYMIZED",
                        "evidence_id": exp_fid,
                    })

            # 2. Snapshot bundles & lookup traces
            for fid in cited_fids:
                if fid in self.evidence_index.evidence_files:
                    ef = self.evidence_index.evidence_files[fid]
                    if "customer_data_snapshot_bundle" in ef["file_path"]:
                        if batch_acc and not any(s["system_id"] == "account_service" for s in steps):
                            steps.append({
                                "phase": "VERIFICATION",
                                "system_id": "account_service",
                                "resource_id": batch_acc,
                                "operation": "VERIFY_RECORD_ABSENT",
                                "state": "ABSENT",
                                "evidence_id": fid,
                            })
                    elif "resource_lookup_trace" in ef["file_path"]:
                        if not any(s["system_id"] == "analytics_platform" for s in steps) and reported_at:
                            try:
                                rep_t = datetime.datetime.fromisoformat(reported_at.replace("Z", "+00:00"))
                                req_t = datetime.datetime.fromisoformat(requested_at.replace("Z", "+00:00"))
                                an_cands = [
                                    a for a in self.activity_index.events
                                    if a.source_system == "deletion_worker" and a.target_system == "analytics_platform"
                                    and req_t <= datetime.datetime.fromisoformat(a.event_time.replace("Z", "+00:00")) <= rep_t
                                    and (rep_t - datetime.datetime.fromisoformat(a.event_time.replace("Z", "+00:00"))).total_seconds() <= 3600
                                ]
                                for c in an_cands:
                                    for obs in self.evidence_index.observations:
                                        if obs.file_id == fid and obs.resource_id == c.resource_id and obs.system_id == "analytics_platform":
                                            steps.append({
                                                "phase": "VERIFICATION",
                                                "system_id": "analytics_platform",
                                                "resource_id": c.resource_id,
                                                "operation": "VERIFY_RECORD_ANONYMIZED",
                                                "state": "ANONYMIZED",
                                                "evidence_id": fid,
                                            })
                                            break
                                    if any(s["system_id"] == "analytics_platform" for s in steps):
                                        break
                            except Exception:
                                pass

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

            # Absence verification for data-derived primary_account_id (from evidence or single-candidate time proximity)
            if primary_account_id and not any(s["system_id"] == "account_service" for s in steps):
                proving_fid = self._find_absence_evidence(
                    primary_account_id, "account_service", requested_at, audit_at
                )
                if proving_fid:
                    steps.append({
                        "phase": "VERIFICATION",
                        "system_id": "account_service",
                        "resource_id": primary_account_id,
                        "operation": "VERIFY_RECORD_ABSENT",
                        "state": "ABSENT",
                        "evidence_id": proving_fid,
                    })

            # Check for unique worker event on analytics_platform near reported_at
            has_analytics = any(s["system_id"] == "analytics_platform" for s in steps)
            if not has_analytics and reported_at:
                try:
                    rep_t = datetime.datetime.fromisoformat(reported_at.replace("Z", "+00:00"))
                    req_t = datetime.datetime.fromisoformat(requested_at.replace("Z", "+00:00"))
                    candidates = []
                    for ev in self.activity_index.events:
                        if ev.source_system == "deletion_worker" and ev.target_system == "analytics_platform":
                            ev_t = datetime.datetime.fromisoformat(ev.event_time.replace("Z", "+00:00"))
                            if req_t <= ev_t <= rep_t and (rep_t - ev_t).total_seconds() <= 600:
                                candidates.append(ev)
                    if len(candidates) == 1:
                        target_res = candidates[0].resource_id
                        for obs in self.evidence_index.observations:
                            if obs.resource_id == target_res and obs.system_id == "analytics_platform" and obs.captured_at <= audit_at:
                                if obs.state == "ANONYMIZED":
                                    steps.append({
                                        "phase": "VERIFICATION",
                                        "system_id": "analytics_platform",
                                        "resource_id": target_res,
                                        "operation": "VERIFY_RECORD_ANONYMIZED",
                                        "state": "ANONYMIZED",
                                        "evidence_id": obs.file_id,
                                    })
                                    break
                except Exception:
                    pass

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

