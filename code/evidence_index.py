"""
evidence_index.py - In-memory pre-indexer for all 94 evidence files.

Parses and indexes:
1. 24 SQL database snapshots (table rows with user identifiers and resource IDs).
2. 26 Structured and semi-structured log files (trace-correlated events).
3. 29 Record files (JSON snapshots and handover text).
4. 15 Unstructured artifacts (cached structured extractions of 11 PNGs and 4 PDFs).

All queries are strictly bounded by: captured_at <= audit_at.
"""

import csv
import json
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from code.identity_resolver import UserIdentity


# System mapping for SQL tables
TABLE_TO_SYSTEM = {
    "customer_profiles": "account_service",
    "customer_profiles_primary": "account_service",
    "customer_profiles_failover_replica": "account_service",
    "customer_data_primary": "_multi_tenant",  # uses origin_system + collection_name
    "customer_data_failover_replica": "_multi_tenant",
    "customer_data_read_replica": "_multi_tenant",
    "customer_data_replica_ap_south": "_multi_tenant",
    "customer_data_replica_eu_west": "_multi_tenant",
    "customer_data_reporting_replica": "_multi_tenant",
    "customer_search_documents": "search_service",
    "search_documents_primary": "search_service",
    "support_records": "support_platform",
    "customer_analytics_profiles": "analytics_platform",
    "security_audit_records": "security_service",
    "connector_subscriptions": "integration_service",
    "backup_restore_entries": "backup_service",
    "customer_exports": "export_service",
}

# Mapping from origin_system in customer_data_* tables to canonical system_id
ORIGIN_TO_SYSTEM = {
    "account_service": "account_service",
    "analytics_platform": "analytics_platform",
    "backup_service": "backup_service",
    "backup_restore_service": "backup_service",
    "export_service": "export_service",
    "identity_service": "identity_service",
    "integration_service": "integration_service",
    "legal_service": "security_service",
    "search_service": "search_service",
    "security_service": "security_service",
    "support_platform": "support_platform",
    "support_storage_service": "support_platform",
    "privacy_treatment_service": "security_service",
}

SERVICE_MAP = {
    "support_replica": "support_platform",
    "support_platform": "support_platform",
    "search_index_service": "search_service",
    "search_service": "search_service",
    "account_service": "account_service",
    "analytics_platform": "analytics_platform",
    "backup_service": "backup_service",
    "backup_restore_service": "backup_service",
    "export_service": "export_service",
    "identity_service": "identity_service",
    "integration_service": "integration_service",
    "security_service": "security_service",
    "legal_service": "security_service",
    "attachment_preview": "support_platform",
    "support_storage_service": "support_platform",
}


@dataclass
class EvidenceObservation:
    file_id: str
    file_path: str
    captured_at: str
    system_id: str
    resource_id: str
    observation_type: str  # RECORD_FOUND, LOOKUP_404, LOOKUP_HIT, FLOW_ACTIVE, FLOW_DISABLED, RESTORE_ACTIVE, RESTORE_BLOCKED, AUDIT_RETAINED, ANONYMIZED
    state: str  # PRESENT, ABSENT, ACTIVE, DISABLED, BLOCKED, REDACTED, ANONYMIZED
    details: Dict[str, Any] = field(default_factory=dict)
    matched_identifier: str = ""


class EvidenceIndex:
    def __init__(self, dataset_dir: Path, cache_dir: Path):
        self.dataset_dir = dataset_dir
        self.cache_dir = cache_dir
        self.evidence_files: Dict[str, Dict[str, str]] = {}
        self.observations: List[EvidenceObservation] = []
        self._load_manifest()
        self._load_unstructured_cache()
        self._load_records()
        self._load_sql_snapshots()
        self._load_logs()
        self._load_pdf_documents()
        self.export_files_data = self._index_export_files()
        self.user_all_accounts: Dict[str, str] = {}
        self.user_all_audit_records: Dict[str, str] = {}
        self._index_user_resources()

    def _index_export_files(self) -> Dict[str, Any]:
        export_files_data = {}
        for ef in self.evidence_files.values():
            if "service_resource_export" in ef["file_path"]:
                fid = ef["file_id"]
                fpath = self.dataset_dir / ef["file_path"]
                if not fpath.exists():
                    continue
                try:
                    with open(fpath, mode="r", encoding="utf-8") as f:
                        c = json.load(f)
                    se = c.get("service_exports", {})
                    raw_acc_404 = [
                        a for a in se.get("account_service", {}).get("profile_lookups", [])
                        if a.get("status_code") == 404
                    ]
                    raw_acc_404.sort(key=lambda x: x.get("observed_at", ""))
                    acc_404 = [a["resource_id"] for a in raw_acc_404]
                    acc_obs_times = {a["resource_id"]: a.get("observed_at", "") for a in raw_acc_404}

                    raw_an_anon = [
                        a for a in se.get("analytics_platform", {}).get("profiles", [])
                        if not a.get("email") and not a.get("customer_reference")
                    ]
                    raw_an_anon.sort(key=lambda x: x.get("observed_at", ""))
                    an_anon = [a["resource_id"] for a in raw_an_anon]
                    an_obs_times = {a["resource_id"]: a.get("observed_at", "") for a in raw_an_anon}

                    sec_users = [
                        s["subject_reference"]
                        for s in se.get("security_service", {}).get("audit_records", [])
                        if s.get("subject_reference")
                    ]
                    export_files_data[fid] = {
                        "file_id": fid,
                        "captured_at": ef["captured_at"],
                        "acc_404": acc_404,
                        "acc_obs_times": acc_obs_times,
                        "an_anon": an_anon,
                        "an_obs_times": an_obs_times,
                        "sec_users": set(sec_users),
                    }
                except Exception:
                    pass
        return export_files_data

    def _index_user_resources(self) -> None:
        for obs in self.observations:
            ident = obs.matched_identifier.strip().lower()
            if not ident:
                continue
            if obs.system_id == "account_service" and obs.resource_id:
                if ident not in self.user_all_accounts:
                    self.user_all_accounts[ident] = obs.resource_id
            elif obs.system_id == "security_service" and obs.resource_id:
                if ident not in self.user_all_audit_records:
                    self.user_all_audit_records[ident] = obs.resource_id

        for obs in self.observations:
            if obs.system_id == "security_service" and obs.resource_id and isinstance(obs.details, dict):
                sub_ref = obs.details.get("subject_reference") or obs.details.get("subject_ref")
                if sub_ref and sub_ref.lower().startswith("user_"):
                    self.user_all_audit_records[sub_ref.lower()] = obs.resource_id

    def _load_manifest(self) -> None:
        manifest_path = self.dataset_dir / "evidence_files.csv"
        with open(manifest_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.evidence_files[row["file_id"]] = row

    def _load_unstructured_cache(self) -> None:
        cache_path = self.cache_dir / "unstructured_evidence.json"
        if not cache_path.exists():
            return
        with open(cache_path, mode="r", encoding="utf-8") as f:
            data = json.load(f)

        # 1. Images
        for fid, info in data.get("images", {}).items():
            meta = self.evidence_files.get(fid, {})
            captured_at = meta.get("captured_at", info.get("captured_at", ""))
            fpath = meta.get("file_path", info.get("file_path", ""))

            # Single resource image
            if "resource_id" in info:
                sys_id = info.get("system_id", "account_service")
                res_id = info["resource_id"]
                state = info.get("state", "PRESENT")
                obs_type = "RECORD_FOUND"
                if state == "REDACTED":
                    obs_type = "TOMBSTONE_REDACTED"
                self.observations.append(
                    EvidenceObservation(
                        file_id=fid,
                        file_path=fpath,
                        captured_at=captured_at,
                        system_id=sys_id,
                        resource_id=res_id,
                        observation_type=obs_type,
                        state=state,
                        details=info,
                        matched_identifier=info.get("email") or info.get("user_id") or "",
                    )
                )

            # Flows
            for flow in info.get("flows", []):
                self.observations.append(
                    EvidenceObservation(
                        file_id=fid,
                        file_path=fpath,
                        captured_at=captured_at,
                        system_id="integration_service",
                        resource_id=flow["resource_id"],
                        observation_type="FLOW_ACTIVE",
                        state=flow.get("state", "ACTIVE"),
                        details=flow,
                        matched_identifier=flow.get("email", ""),
                    )
                )

            # Exports
            for exp in info.get("exports", []):
                self.observations.append(
                    EvidenceObservation(
                        file_id=fid,
                        file_path=fpath,
                        captured_at=captured_at,
                        system_id="export_service",
                        resource_id=exp["resource_id"],
                        observation_type="RECORD_FOUND",
                        state=exp.get("state", "PRESENT"),
                        details=exp,
                        matched_identifier=exp.get("email", ""),
                    )
                )

            # Backups
            for bkp in info.get("backups", []):
                self.observations.append(
                    EvidenceObservation(
                        file_id=fid,
                        file_path=fpath,
                        captured_at=captured_at,
                        system_id="backup_service",
                        resource_id=bkp["resource_id"],
                        observation_type="RESTORE_ACTIVE",
                        state=bkp.get("state", "ACTIVE"),
                        details=bkp,
                        matched_identifier=bkp.get("email", ""),
                    )
                )

        # 2. Documents (PDFs)
        for fid, info in data.get("documents", {}).items():
            meta = self.evidence_files.get(fid, {})
            captured_at = meta.get("captured_at", info.get("captured_at", ""))
            fpath = meta.get("file_path", info.get("file_path", ""))

            # Support attachment
            if info.get("attachment_only") and "resource_id" in info:
                self.observations.append(
                    EvidenceObservation(
                        file_id=fid,
                        file_path=fpath,
                        captured_at=captured_at,
                        system_id=info.get("system_id", "support_platform"),
                        resource_id=info["resource_id"],
                        observation_type="SUPPORT_ATTACHMENT",
                        state="PRESENT",
                        details=info,
                        matched_identifier=info.get("email") or info.get("user_id") or "",
                    )
                )
            # Security retention
            elif info.get("retain_until") and "resource_id" in info:
                self.observations.append(
                    EvidenceObservation(
                        file_id=fid,
                        file_path=fpath,
                        captured_at=captured_at,
                        system_id="security_service",
                        resource_id=info["resource_id"],
                        observation_type="AUDIT_RETAINED",
                        state="PRESENT",
                        details=info,
                        matched_identifier=info.get("user_id", ""),
                    )
                )

    def _load_pdf_documents(self) -> None:
        try:
            import fitz
            for fid, ef in self.evidence_files.items():
                if not ef["file_path"].endswith(".pdf"):
                    continue
                pdf_path = self.dataset_dir / ef["file_path"]
                if not pdf_path.exists():
                    continue
                doc = fitz.open(pdf_path)
                full_text = "\n".join(page.get_text() for page in doc)
                captured_at = ef["captured_at"]

                # Extract support resources
                for sm in re.finditer(r"\b(support_\d+)\b", full_text, flags=re.IGNORECASE):
                    res_id = sm.group(1).lower()
                    emails = re.findall(r"[\w\.-]+@[\w\.-]+\.\w+", full_text)
                    uids = re.findall(r"\b(user_\d+)\b", full_text, flags=re.IGNORECASE)
                    for ident in set(emails + uids):
                        self.observations.append(
                            EvidenceObservation(
                                file_id=fid,
                                file_path=ef["file_path"],
                                captured_at=captured_at,
                                system_id="support_platform",
                                resource_id=res_id,
                                observation_type="SUPPORT_ATTACHMENT",
                                state="PRESENT",
                                details={"text_snippet": full_text[:300]},
                                matched_identifier=str(ident),
                            )
                        )

                # Extract security audit records
                for am in re.finditer(r"\b(audit_record_\d+)\b", full_text, flags=re.IGNORECASE):
                    res_id = am.group(1).lower()
                    emails = re.findall(r"[\w\.-]+@[\w\.-]+\.\w+", full_text)
                    uids = re.findall(r"\b(user_\d+)\b", full_text, flags=re.IGNORECASE)
                    for ident in set(emails + uids):
                        self.observations.append(
                            EvidenceObservation(
                                file_id=fid,
                                file_path=ef["file_path"],
                                captured_at=captured_at,
                                system_id="security_service",
                                resource_id=res_id,
                                observation_type="AUDIT_RETAINED",
                                state="PRESENT",
                                details={"text_snippet": full_text[:300]},
                                matched_identifier=str(ident),
                            )
                        )

                # Extract statement exports (e.g. statement NST-2026-0718-1842 -> export_1842)
                for em in re.finditer(r"statement\s+NST-\d+-(\d+)", full_text, flags=re.IGNORECASE):
                    res_id = f"export_{em.group(1)}"
                    emails = re.findall(r"[\w\.-]+@[\w\.-]+\.\w+", full_text)
                    uids = re.findall(r"\b(user_\d+)\b", full_text, flags=re.IGNORECASE)
                    for ident in set(emails + uids):
                        self.observations.append(
                            EvidenceObservation(
                                file_id=fid,
                                file_path=ef["file_path"],
                                captured_at=captured_at,
                                system_id="export_service",
                                resource_id=res_id,
                                observation_type="RECORD_FOUND",
                                state="PRESENT",
                                details={"text_snippet": full_text[:300]},
                                matched_identifier=str(ident),
                            )
                        )
        except Exception:
            pass

    def _load_records(self) -> None:
        rec_dir = self.dataset_dir / "evidence" / "records"
        for ef in self.evidence_files.values():
            if not ef["file_path"].startswith("evidence/records/"):
                continue
            fid = ef["file_id"]
            captured_at = ef["captured_at"]
            fpath = self.dataset_dir / ef["file_path"]
            if not fpath.exists():
                continue

            # Handover text file
            if fpath.suffix == ".txt":
                with open(fpath, mode="r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("- "):
                            parts = [p.strip() for p in line[2:].split("|")]
                            if len(parts) >= 6:
                                ts, sys_id, res_id, rtype, status, ident = parts[:6]
                                state = "PRESENT"
                                obs_type = "RECORD_FOUND"

                                if rtype == "SUPPORT_ATTACHMENT":
                                    obs_type = "SUPPORT_ATTACHMENT"
                                elif rtype == "MARKETING_PROFILE":
                                    obs_type = "MARKETING_PROFILE"
                                elif rtype == "SECURITY_AUDIT_LOG":
                                    obs_type = "AUDIT_RETAINED"

                                if status == "NOT_FOUND":
                                    state = "ABSENT"
                                    obs_type = "LOOKUP_404"
                                elif status == "ANONYMIZED":
                                    state = "ANONYMIZED"
                                    obs_type = "ANONYMIZED"
                                elif status == "ACTIVE":
                                    state = "ACTIVE"
                                    obs_type = "FLOW_ACTIVE" if sys_id == "integration_service" else "RESTORE_ACTIVE"
                                elif status == "DISABLED":
                                    state = "DISABLED"
                                    obs_type = "FLOW_DISABLED"
                                elif status == "BLOCKED":
                                    state = "BLOCKED"
                                    obs_type = "RESTORE_BLOCKED"

                                self.observations.append(
                                    EvidenceObservation(
                                        file_id=fid,
                                        file_path=ef["file_path"],
                                        captured_at=captured_at,
                                        system_id=sys_id,
                                        resource_id=res_id,
                                        observation_type=obs_type,
                                        state=state,
                                        details={"raw": line},
                                        matched_identifier=ident,
                                    )
                                )
                continue


            # JSON files
            if fpath.suffix == ".json":
                try:
                    with open(fpath, mode="r", encoding="utf-8") as f:
                        content = json.load(f)
                except Exception:
                    continue

                # Service resource exports
                if "service_exports" in content:
                    se = content["service_exports"]
                    root_ident = (
                        content.get("email")
                        or content.get("customer_reference")
                        or content.get("user_id")
                        or content.get("subject_reference")
                        or ""
                    )
                    for sys_id, cat_dict in se.items():
                        sys_ident = (
                            cat_dict.get("email")
                            or cat_dict.get("customer_reference")
                            or cat_dict.get("user_id")
                            or cat_dict.get("subject_reference")
                            or root_ident
                        ) if isinstance(cat_dict, dict) else root_ident
                        for cat_name, item_list in cat_dict.items():
                            if not isinstance(item_list, list):
                                continue
                            for item_idx, item in enumerate(item_list):
                                if not isinstance(item, dict):
                                    continue

                                ancestor_path = f"service_exports.{sys_id}.{cat_name}[{item_idx}]"
                                item["json_path"] = ancestor_path

                                # Search index queries
                                if sys_id == "search_service" and cat_name == "index_queries":
                                    query = item.get("query", "")
                                    hits = item.get("hits") or {}
                                    total = hits.get("total", 0)
                                    docs = hits.get("documents") or []
                                    item_res_id = item.get("resource_id", "")
                                    if total > 0 and docs:
                                        for doc_idx, doc in enumerate(docs):
                                            doc["json_path"] = f"{ancestor_path}.hits.documents[{doc_idx}]"
                                            d_res = doc.get("resource_id") or item_res_id
                                            d_ident = doc.get("email") or doc.get("customer_reference") or sys_ident or query
                                            self.observations.append(
                                                EvidenceObservation(
                                                    file_id=fid,
                                                    file_path=ef["file_path"],
                                                    captured_at=captured_at,
                                                    system_id="search_service",
                                                    resource_id=d_res,
                                                    observation_type="RECORD_FOUND",
                                                    state="PRESENT",
                                                    details=doc,
                                                    matched_identifier=str(d_ident),
                                                )
                                            )
                                    continue

                                res_id = item.get("resource_id") or item.get("connector_id") or item.get("backup_id") or item.get("export_id")
                                if not res_id:
                                    continue

                                state = "PRESENT"
                                obs_type = "RECORD_FOUND"
                                ident = (
                                    item.get("email")
                                    or item.get("customer_reference")
                                    or item.get("user_id")
                                    or item.get("customer_email")
                                    or item.get("subject_reference")
                                    or sys_ident
                                    or ""
                                )

                                # Check profile lookups
                                if "status_code" in item:
                                    sc = item["status_code"]
                                    prof = item.get("profile") or {}
                                    ident = prof.get("email") or prof.get("customer_reference") or ident
                                    if sc == 404:
                                        state = "ABSENT"
                                        obs_type = "LOOKUP_404"
                                    else:
                                        state = "PRESENT"
                                        obs_type = "LOOKUP_HIT"

                                # Check connectors
                                elif sys_id == "integration_service" or "enabled" in item or "is_enabled" in item:
                                    is_en = item.get("enabled") if "enabled" in item else item.get("is_enabled")
                                    state = "ACTIVE" if is_en in (True, 1, "true", "1") else "DISABLED"
                                    obs_type = "FLOW_ACTIVE" if state == "ACTIVE" else "FLOW_DISABLED"

                                # Check restore entries
                                elif sys_id == "backup_service" or "restore_allowed" in item or "is_restorable" in item:
                                    is_rest = item.get("restore_allowed") if "restore_allowed" in item else item.get("is_restorable")
                                    state = "ACTIVE" if is_rest in (True, 1, "true", "1") else "BLOCKED"
                                    obs_type = "RESTORE_ACTIVE" if state == "ACTIVE" else "RESTORE_BLOCKED"

                                # Check analytics
                                elif sys_id == "analytics_platform":
                                    has_ident = item.get("email") or item.get("phone") or item.get("customer_reference") or item.get("email_hash")
                                    if not has_ident:
                                        state = "ANONYMIZED"
                                        obs_type = "ANONYMIZED"
                                    else:
                                        state = "PRESENT"
                                        obs_type = "PII_EXPOSED"

                                # Check support tickets
                                elif sys_id == "support_platform":
                                    has_pii = item.get("requester_email") or item.get("requester_name") or item.get("requester_phone")
                                    ident = item.get("customer_reference") or item.get("requester_email") or ident
                                    if not has_pii:
                                        state = "REDACTED"
                                        obs_type = "RECORD_REDACTED"
                                    else:
                                        state = "PRESENT"
                                        obs_type = "PII_EXPOSED"

                                # Check security audit
                                elif sys_id == "security_service":
                                    state = "PRESENT"
                                    obs_type = "AUDIT_RETAINED"

                                self.observations.append(
                                    EvidenceObservation(
                                        file_id=fid,
                                        file_path=ef["file_path"],
                                        captured_at=captured_at,
                                        system_id=sys_id,
                                        resource_id=res_id,
                                        observation_type=obs_type,
                                        state=state,
                                        details=item,
                                        matched_identifier=str(ident),
                                    )
                                )

                # Top-level records array (e.g. export jobs, analytics reports, connector configs, security ledger)
                if "records" in content:
                    root_ident = (
                        content.get("email")
                        or content.get("customer_reference")
                        or content.get("user_id")
                        or content.get("subject_reference")
                        or content.get("owner_email")
                        or ""
                    )
                    coll = content.get("collection", "") or content.get("source", "") or content.get("origin", "")
                    sys_id = "account_service"
                    if "analytics" in coll or "analytics" in fpath.name:
                        sys_id = "analytics_platform"
                    elif "export" in coll or "export" in fpath.name:
                        sys_id = "export_service"
                    elif "connector" in coll or "connector" in fpath.name:
                        sys_id = "integration_service"
                    elif "security" in coll or "security" in fpath.name:
                        sys_id = "security_service"

                    for rec_idx, rec in enumerate(content["records"]):
                        if not isinstance(rec, dict):
                            continue
                        rec["json_path"] = f"records[{rec_idx}]"
                        res_id = rec.get("resource_id") or rec.get("export_id") or rec.get("connector_id") or rec.get("backup_id")
                        if not res_id:
                            continue
                        ident = (
                            rec.get("email")
                            or rec.get("owner_email")
                            or rec.get("customer_email")
                            or rec.get("user_id")
                            or rec.get("customer_reference")
                            or rec.get("subject_reference")
                            or root_ident
                            or ""
                        )

                        state = "PRESENT"
                        obs_type = "RECORD_FOUND"

                        if sys_id == "analytics_platform":
                            if not rec.get("email") and not rec.get("phone") and not rec.get("user_id"):
                                state = "ANONYMIZED"
                                obs_type = "ANONYMIZED"
                        elif sys_id == "integration_service":
                            is_en = rec.get("is_enabled") or rec.get("enabled")
                            state = "ACTIVE" if is_en in (1, "1", True, "true") else "DISABLED"
                            obs_type = "FLOW_ACTIVE" if state == "ACTIVE" else "FLOW_DISABLED"
                        elif sys_id == "security_service":
                            obs_type = "AUDIT_RETAINED"

                        self.observations.append(
                            EvidenceObservation(
                                file_id=fid,
                                file_path=ef["file_path"],
                                captured_at=captured_at,
                                system_id=sys_id,
                                resource_id=res_id,
                                observation_type=obs_type,
                                state=state,
                                details=rec,
                                matched_identifier=str(ident),
                            )
                        )

                # Snapshot bundles
                if "snapshots" in content:
                    bundle_ident = (
                        content.get("email")
                        or content.get("customer_reference")
                        or content.get("user_id")
                        or content.get("subject_reference")
                        or ""
                    )
                    for snap_idx, snap in enumerate(content["snapshots"]):
                        snap_ident = (
                            snap.get("email")
                            or snap.get("customer_reference")
                            or snap.get("user_id")
                            or snap.get("subject_reference")
                            or bundle_ident
                            or ""
                        )
                        raw_store = snap.get("data_store", "account_service")
                        coll = snap.get("collection", "")
                        sys_id = raw_store
                        if raw_store in ("legal_service", "privacy_treatment_service"):
                            sys_id = "security_service"
                        elif raw_store == "backup_restore_service":
                            sys_id = "backup_service"
                        elif raw_store == "support_storage_service":
                            sys_id = "support_platform"

                        for rec_idx, rec in enumerate(snap.get("records", [])):
                            if not isinstance(rec, dict):
                                continue
                            rec["json_path"] = f"snapshots[{snap_idx}].records[{rec_idx}]"
                            res_id = rec.get("resource_id") or rec.get("order_reference") or rec.get("ticket_id")
                            if not res_id:
                                continue

                            ident = (
                                rec.get("subject_reference")
                                or rec.get("customer_reference")
                                or rec.get("user_id")
                                or rec.get("email")
                                or rec.get("owner_email")
                                or rec.get("uploaded_by")
                                or rec.get("subject_selector")
                                or rec.get("lookup_value")
                                or (rec.get("document", {}).get("email") if isinstance(rec.get("document"), dict) else "")
                                or (rec.get("document", {}).get("customer_reference") if isinstance(rec.get("document"), dict) else "")
                                or snap_ident
                                or ""
                            )

                            state = "PRESENT"
                            obs_type = "RECORD_FOUND"

                            if coll == "deleted_customer_references":
                                sys_id = "identity_service"
                                has_pii = rec.get("name") or rec.get("email") or rec.get("phone") or rec.get("email_hash")
                                if not has_pii:
                                    state = "REDACTED"
                                    obs_type = "RECORD_REDACTED"
                                else:
                                    state = "PRESENT"
                                    obs_type = "PII_EXPOSED"
                            elif coll == "connector_configurations":
                                sys_id = "integration_service"
                                is_en = rec.get("enabled") if "enabled" in rec else rec.get("is_enabled")
                                state = "ACTIVE" if is_en in (True, 1, "true", "1") else "DISABLED"
                                obs_type = "FLOW_ACTIVE" if state == "ACTIVE" else "FLOW_DISABLED"
                            elif coll == "backup_catalog":
                                sys_id = "backup_service"
                                is_rest = rec.get("restore_allowed") if "restore_allowed" in rec else rec.get("is_restorable")
                                state = "ACTIVE" if is_rest in (True, 1, "true", "1") else "BLOCKED"
                                obs_type = "RESTORE_ACTIVE" if state == "ACTIVE" else "RESTORE_BLOCKED"
                            elif coll == "customer_analytics_reports":
                                sys_id = "analytics_platform"
                                has_ident = rec.get("email") or rec.get("phone") or rec.get("user_id") or rec.get("customer_reference")
                                if not has_ident:
                                    state = "ANONYMIZED"
                                    obs_type = "ANONYMIZED"
                                else:
                                    state = "PRESENT"
                                    obs_type = "PII_EXPOSED"
                            elif coll in ("security_audit_events", "retained_order_records") or sys_id == "security_service":
                                sys_id = "security_service"
                                state = "PRESENT"
                                obs_type = "AUDIT_RETAINED"
                            elif coll == "ticket_attachments":
                                sys_id = "support_platform"
                                state = "PRESENT"
                                obs_type = "SUPPORT_ATTACHMENT"
                            elif coll == "support_conversations":
                                sys_id = "support_platform"
                                state = "PRESENT"
                                obs_type = "PII_EXPOSED"
                            elif coll == "operational_record_history":
                                sys_id = rec.get("system", sys_id)
                                res_id = rec.get("resource_id", res_id)
                                ident = rec.get("lookup_value", ident)
                                if rec.get("result") == "FOUND":
                                    state = "PRESENT"
                                    obs_type = "RECORD_FOUND"
                                elif rec.get("result") == "NOT_FOUND":
                                    state = "ABSENT"
                                    obs_type = "LOOKUP_404"

                            self.observations.append(
                                EvidenceObservation(
                                    file_id=fid,
                                    file_path=ef["file_path"],
                                    captured_at=captured_at,
                                    system_id=sys_id,
                                    resource_id=res_id,
                                    observation_type=obs_type,
                                    state=state,
                                    details=rec,
                                    matched_identifier=str(ident),
                                )
                            )

    def _load_sql_snapshots(self) -> None:
        sql_dir = self.dataset_dir / "evidence" / "databases"
        for ef in self.evidence_files.values():
            if not ef["file_path"].startswith("evidence/databases/"):
                continue
            fid = ef["file_id"]
            captured_at = ef["captured_at"]
            fpath = self.dataset_dir / ef["file_path"]
            if not fpath.exists():
                continue

            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")
                db = sqlite3.connect(":memory:")
                db.executescript(content)
                tables = [
                    r[0]
                    for r in db.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                ]

                for tbl in tables:
                    tbl_sys = TABLE_TO_SYSTEM.get(tbl, "account_service")
                    is_multi_tenant = (tbl_sys == "_multi_tenant")
                    col_info = db.execute(f"PRAGMA table_info({tbl})").fetchall()
                    cols = [c[1] for c in col_info]
                    rows = db.execute(f"SELECT * FROM {tbl}").fetchall()

                    for row in rows:
                        row_dict = dict(zip(cols, row))
                        res_id = (
                            row_dict.get("resource_id")
                            or row_dict.get("backup_id")
                            or row_dict.get("connector_id")
                            or row_dict.get("export_id")
                            or (str(row[0]) if row else "")
                        )
                        if not res_id:
                            continue

                        # Parse record_json first so we can use its fields
                        rec_json = {}
                        if "record_json" in row_dict and row_dict["record_json"]:
                            try:
                                rec_json = json.loads(row_dict["record_json"])
                            except Exception:
                                pass

                        # For multi-tenant tables, resolve resource_id from record_json
                        if is_multi_tenant and rec_json.get("resource_id"):
                            res_id = rec_json["resource_id"]

                        # Extract identifier from direct columns first, then record_json
                        ident = (
                            row_dict.get("email")
                            or row_dict.get("requester_email")
                            or row_dict.get("customer_email")
                            or row_dict.get("user_id")
                            or row_dict.get("customer_reference")
                            or row_dict.get("subject_reference")
                            or row_dict.get("phone")
                            or row_dict.get("customer_phone")
                            or row_dict.get("requester_phone")
                            or row_dict.get("requester_name")
                            or row_dict.get("full_name")
                            or row_dict.get("name")
                            or row_dict.get("email_hash")
                            or ""
                        )

                        if not ident and rec_json:
                            ident = (
                                rec_json.get("subject_reference")
                                or rec_json.get("requester_email")
                                or rec_json.get("email")
                                or rec_json.get("customer_reference")
                                or rec_json.get("user_id")
                                or rec_json.get("owner_email")
                                or rec_json.get("phone")
                                or rec_json.get("customer_phone")
                                or rec_json.get("email_hash")
                                or rec_json.get("subject_selector")
                                or rec_json.get("uploaded_by")
                                or rec_json.get("full_name")
                                or rec_json.get("name")
                                or ""
                            )

                        # Determine system_id and observation semantics
                        if is_multi_tenant:
                            # Use origin_system and collection_name from the row
                            origin = row_dict.get("origin_system", "")
                            coll = row_dict.get("collection_name", "")
                            sys_id = ORIGIN_TO_SYSTEM.get(origin, origin or "account_service")
                            state, obs_type = self._classify_multi_tenant_row(
                                sys_id, coll, rec_json, ident
                            )
                        else:
                            sys_id = tbl_sys
                            state = "PRESENT"
                            obs_type = "RECORD_FOUND"

                            if tbl == "connector_subscriptions":
                                is_en = row_dict.get("enabled") or row_dict.get("is_enabled")
                                state = "ACTIVE" if is_en in (1, "1", True, "true") else "DISABLED"
                                obs_type = "FLOW_ACTIVE" if state == "ACTIVE" else "FLOW_DISABLED"
                            elif tbl == "backup_restore_entries":
                                is_rest = row_dict.get("restore_allowed") or row_dict.get("is_restorable")
                                state = "ACTIVE" if is_rest in (1, "1", True, "true") else "BLOCKED"
                                obs_type = "RESTORE_ACTIVE" if state == "ACTIVE" else "RESTORE_BLOCKED"
                            elif tbl == "security_audit_records":
                                obs_type = "AUDIT_RETAINED"
                            elif tbl == "customer_analytics_profiles":
                                if not row_dict.get("email") and not row_dict.get("phone"):
                                    state = "ANONYMIZED"
                                    obs_type = "ANONYMIZED"

                        self.observations.append(
                            EvidenceObservation(
                                file_id=fid,
                                file_path=ef["file_path"],
                                captured_at=captured_at,
                                system_id=sys_id,
                                resource_id=res_id,
                                observation_type=obs_type,
                                state=state,
                                details={"table": tbl, "row": row_dict, "json": rec_json},
                                matched_identifier=str(ident),
                            )
                        )

                        # If row contains a distinct primary account_id reference, index it for account_service
                        acc_col = row_dict.get("account_id") or row_dict.get("source_resource_id")
                        if acc_col and str(acc_col).startswith("account_") and str(acc_col) != res_id:
                            self.observations.append(
                                EvidenceObservation(
                                    file_id=fid,
                                    file_path=ef["file_path"],
                                    captured_at=captured_at,
                                    system_id="account_service",
                                    resource_id=str(acc_col),
                                    observation_type="SOURCE_RESOURCE_REF",
                                    state="REFERENCE",
                                    details={"table": tbl, "row": row_dict, "linked_from": res_id},
                                    matched_identifier=str(ident),
                                )
                            )
                db.close()

            except Exception as e:
                pass

    def _classify_multi_tenant_row(
        self, sys_id: str, collection_name: str, rec_json: Dict, ident: str
    ) -> Tuple[str, str]:
        """Classifies a row from a customer_data_* multi-tenant table.

        Uses the collection_name to determine the correct observation type and state,
        matching the semantics in _load_records for JSON snapshot bundles.
        """
        state = "PRESENT"
        obs_type = "RECORD_FOUND"

        if collection_name == "security_audit_events":
            state = "PRESENT"
            obs_type = "AUDIT_RETAINED"
        elif collection_name == "retained_order_records":
            state = "PRESENT"
            obs_type = "AUDIT_RETAINED"
        elif collection_name == "deleted_customer_references":
            has_pii = (
                rec_json.get("name")
                or rec_json.get("email")
                or rec_json.get("phone")
                or rec_json.get("email_hash")
            )
            if not has_pii:
                state = "REDACTED"
                obs_type = "RECORD_REDACTED"
            else:
                state = "PRESENT"
                obs_type = "PII_EXPOSED"
        elif collection_name == "connector_configurations":
            is_en = rec_json.get("enabled")
            if is_en is None:
                is_en = rec_json.get("is_enabled")
            state = "ACTIVE" if is_en in (True, 1, "true", "1") else "DISABLED"
            obs_type = "FLOW_ACTIVE" if state == "ACTIVE" else "FLOW_DISABLED"
        elif collection_name == "backup_catalog":
            is_rest = rec_json.get("restore_allowed")
            if is_rest is None:
                is_rest = rec_json.get("is_restorable")
            state = "ACTIVE" if is_rest in (True, 1, "true", "1") else "BLOCKED"
            obs_type = "RESTORE_ACTIVE" if state == "ACTIVE" else "RESTORE_BLOCKED"
        elif collection_name == "customer_analytics_reports":
            has_ident = (
                rec_json.get("email")
                or rec_json.get("phone")
                or rec_json.get("user_id")
                or rec_json.get("customer_reference")
            )
            if not has_ident:
                state = "ANONYMIZED"
                obs_type = "ANONYMIZED"
            else:
                state = "PRESENT"
                obs_type = "PII_EXPOSED"
        elif collection_name == "customer_export_jobs":
            state = "PRESENT"
            obs_type = "RECORD_FOUND"
        elif collection_name == "customer_search_documents":
            # Check if document contains user data
            doc = rec_json.get("document", {})
            if isinstance(doc, dict) and (doc.get("email") or doc.get("customer_reference")):
                state = "PRESENT"
                obs_type = "RECORD_FOUND"
            else:
                state = "PRESENT"
                obs_type = "RECORD_FOUND"
        elif collection_name == "support_conversations":
            state = "PRESENT"
            obs_type = "PII_EXPOSED"
        elif collection_name == "ticket_attachments":
            state = "PRESENT"
            obs_type = "SUPPORT_ATTACHMENT"
        elif collection_name == "customer_profiles":
            state = "PRESENT"
            obs_type = "RECORD_FOUND"

        return state, obs_type


    def _load_logs(self) -> None:
        log_dir = self.dataset_dir / "evidence" / "logs"
        for ef in self.evidence_files.values():
            if not ef["file_path"].startswith("evidence/logs/"):
                continue
            fid = ef["file_id"]
            captured_at = ef["captured_at"]
            fpath = self.dataset_dir / ef["file_path"]
            if not fpath.exists():
                continue

            try:
                lines = fpath.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                continue

            # Group by trace_id if present
            traces: Dict[str, List[Dict[str, str]]] = {}
            untraced_lines: List[Dict[str, str]] = []

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                fields: Dict[str, str] = {}
                # JSON log
                if "{" in line and "}" in line:
                    try:
                        j_start = line.index("{")
                        j_end = line.rindex("}") + 1
                        fields = json.loads(line[j_start:j_end])
                    except Exception:
                        pass

                # Extract trace ID: check explicit trace pattern tr-\d+, requestId, or trace_id
                trace_match = re.search(r'\b(tr-\d+)\b', line)
                trace = trace_match.group(1) if trace_match else ""

                clean_line = line.replace('\\"', '"')
                # Key-value extraction
                for part in re.findall(r'(\w+)=(?:"([^"]*)"|([^\s"]+))', clean_line):
                    k = part[0]
                    v = part[1] if part[1] else part[2]
                    fields[k] = v

                if not trace:
                    trace = fields.get("trace_id") or fields.get("requestId")

                # If service not in key-value, extract from syslog or pipe format
                if not fields.get("service") and not fields.get("function"):
                    pipe_parts = [p.strip() for p in line.split("|")]
                    if len(pipe_parts) >= 5:
                        fields["service"] = pipe_parts[2]
                        fields["event"] = pipe_parts[4]
                    else:
                        syslog_m = re.search(r'\s([a-z_]+)\s+(tr-\d+)\s', line)
                        if syslog_m:
                            fields["service"] = syslog_m.group(1)

                if trace:
                    if trace not in traces:
                        traces[trace] = []
                    traces[trace].append(fields)
                else:
                    untraced_lines.append(fields)

            # Process trace groups
            for trace_id, events in traces.items():
                trace_ident = ""
                trace_res_id = ""
                trace_sys_id = ""
                trace_status = ""
                trace_details: Dict[str, Any] = {}

                for ev in events:
                    trace_details.update(ev)
                    for k in (
                        "lookup_key",
                        "owner_key",
                        "subject_key",
                        "subject_ref",
                        "subject_reference",
                        "customer_email",
                        "email",
                        "correlation_key",
                        "user_id",
                        "customer_reference",
                        "requester_email",
                    ):
                        val = ev.get(k)
                        if val and val != "null":
                            trace_ident = val

                    if ev.get("resource_id"):
                        trace_res_id = ev["resource_id"]
                    if ev.get("service") or ev.get("function"):
                        raw_srv = ev.get("service") or ev.get("function")
                        trace_sys_id = SERVICE_MAP.get(raw_srv, raw_srv)

                if trace_res_id:
                    state = "PRESENT"
                    obs_type = "RECORD_FOUND"

                    # 404 profile lookup
                    if trace_details.get("http_status") == "404" or trace_details.get("rows") == "0":
                        state = "ABSENT"
                        obs_type = "LOOKUP_404"
                    # Enabled connector
                    elif trace_details.get("enabled") == "true":
                        state = "ACTIVE"
                        obs_type = "FLOW_ACTIVE"
                    elif trace_details.get("enabled") == "false":
                        state = "DISABLED"
                        obs_type = "FLOW_DISABLED"
                    # Restore allowed
                    elif trace_details.get("restore_allowed") == "false" or trace_details.get("deletion_block") == "true":
                        state = "BLOCKED"
                        obs_type = "RESTORE_BLOCKED"
                    elif trace_details.get("restore_allowed") == "true" or trace_details.get("eligible") == "true":
                        state = "ACTIVE"
                        obs_type = "RESTORE_ACTIVE"
                    # Marketing contact lookup
                    elif trace_details.get("event") == "contact_lookup_completed" and (
                        trace_details.get("email_opt_in") == "true" or trace_details.get("opt_in") == "true"
                    ):
                        state = "PRESENT"
                        obs_type = "MARKETING_PROFILE"
                    # Audit log retained
                    elif trace_sys_id == "security_service" and (
                        trace_details.get("rows") == "1" or trace_details.get("retention_until")
                    ):
                        state = "PRESENT"
                        obs_type = "AUDIT_RETAINED"
                    # Anonymized analytics
                    elif trace_sys_id == "analytics_platform" and not trace_details.get("email") and not trace_details.get("phone"):
                        state = "ANONYMIZED"
                        obs_type = "ANONYMIZED"

                    self.observations.append(
                        EvidenceObservation(
                            file_id=fid,
                            file_path=ef["file_path"],
                            captured_at=captured_at,
                            system_id=trace_sys_id or "account_service",
                            resource_id=trace_res_id,
                            observation_type=obs_type,
                            state=state,
                            details=trace_details,
                            matched_identifier=str(trace_ident),
                        )
                    )

            # Untraced lines
            for ev in untraced_lines:
                res_id = ev.get("resource_id") or ev.get("connector_id") or ev.get("backup_id") or ev.get("export_id")
                ident = (
                    ev.get("subject_reference")
                    or ev.get("subject_ref")
                    or ev.get("lookup_key")
                    or ev.get("email")
                    or ev.get("customer_reference")
                    or ev.get("user_id")
                    or ""
                )
                raw_srv = ev.get("system") or ev.get("service") or "account_service"
                srv = SERVICE_MAP.get(raw_srv, raw_srv)

                res_val = str(ev.get("result", "")).upper()
                if res_val == "NOT_FOUND":
                    state = "ABSENT"
                    obs_type = "LOOKUP_404"
                elif res_val == "ACTIVE":
                    state = "ACTIVE"
                    obs_type = "FLOW_ACTIVE" if srv == "integration_service" else "RESTORE_ACTIVE"
                elif res_val == "DISABLED":
                    state = "DISABLED"
                    obs_type = "FLOW_DISABLED"
                elif res_val == "BLOCKED":
                    state = "BLOCKED"
                    obs_type = "RESTORE_BLOCKED"
                elif res_val == "IDENTIFIABLE":
                    state = "PRESENT"
                    obs_type = "PII_EXPOSED"
                elif res_val == "REDACTED":
                    state = "REDACTED"
                    obs_type = "RECORD_REDACTED"
                elif res_val == "FOUND":
                    state = "PRESENT"
                    obs_type = "AUDIT_RETAINED" if srv == "security_service" else "RECORD_FOUND"
                else:
                    state = "PRESENT"
                    obs_type = "RECORD_FOUND"

                if res_id:
                    self.observations.append(
                        EvidenceObservation(
                            file_id=fid,
                            file_path=ef["file_path"],
                            captured_at=captured_at,
                            system_id=srv,
                            resource_id=res_id,
                            observation_type=obs_type,
                            state=state,
                            details=ev,
                            matched_identifier=str(ident),
                        )
                    )

    def query_observations_for_user(
        self, user: UserIdentity, audit_at: str, known_resource_ids: Optional[Set[str]] = None
    ) -> List[EvidenceObservation]:
        """
        Finds all evidence observations matching this user with captured_at <= audit_at.
        """
        matched = []
        for obs in self.observations:
            if obs.captured_at > audit_at:
                continue

            # Match by known resource ID (e.g. from deletion workflow or anonymized records)
            if known_resource_ids and obs.resource_id in known_resource_ids:
                matched.append(obs)
                continue

            # Check if identifier matches user
            ident = obs.matched_identifier.strip().lower()
            is_match = False
            if ident:
                if ident == user.user_id.lower():
                    is_match = True
                elif ident in user.all_emails:
                    is_match = True
                elif ident in user.all_phones:
                    is_match = True
                elif ident in user.all_email_hashes:
                    is_match = True
                elif user.matches_string(ident):
                    is_match = True

            # If not matched by direct identifier, check details
            if not is_match and obs.details:
                if user.matches_string(str(obs.details)):
                    is_match = True

            if is_match:
                matched.append(obs)

        return matched
