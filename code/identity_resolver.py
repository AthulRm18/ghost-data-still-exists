"""
identity_resolver.py - Resolves current and historical user identifiers.

Reconstructs the full identity profile for any user from user_identities.csv
and user_audit_log.csv:
- Current and historical emails (normalized to lowercase)
- SHA-256 hashes of all lowercase emails
- Current and historical phone numbers
- Current and historical names
- Stable user_id and customer reference variants
"""

import csv
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Dict, List, Optional, Set


def compute_email_hash(email: str) -> str:
    """Computes SHA-256 hex digest of the normalized lowercase email."""
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


@dataclass
class UserIdentity:
    user_id: str
    current_name: str
    current_email: str
    current_phone: str
    current_email_hash: str
    all_names: Set[str] = field(default_factory=set)
    all_emails: Set[str] = field(default_factory=set)
    all_email_hashes: Set[str] = field(default_factory=set)
    all_phones: Set[str] = field(default_factory=set)
    customer_references: Set[str] = field(default_factory=set)
    audit_ids: Set[str] = field(default_factory=set)

    def matches_string(self, text: str) -> bool:
        """Checks if text contains any direct identifier for this user."""
        if not text:
            return False
        lower_text = text.lower()
        if re.search(r'\b' + re.escape(self.user_id.lower()) + r'\b', lower_text):
            return True
        for email in self.all_emails:
            if email in lower_text:
                return True
        for h in self.all_email_hashes:
            if h in lower_text:
                return True
        for phone in self.all_phones:
            if phone in text or phone.replace(" ", "") in text.replace(" ", ""):
                return True
        for name in self.all_names:
            if len(name) > 3 and re.search(r'\b' + re.escape(name.lower()) + r'\b', lower_text):
                return True
        for ref in self.customer_references:
            if re.search(r'\b' + re.escape(ref.lower()) + r'\b', lower_text):
                return True
        return False


class IdentityResolver:
    def __init__(self, identities_csv: Path, audit_log_csv: Path):
        self.identities_csv = identities_csv
        self.audit_log_csv = audit_log_csv
        self.users_by_id: Dict[str, UserIdentity] = {}
        self.email_to_user_id: Dict[str, str] = {}
        self.hash_to_user_id: Dict[str, str] = {}
        self._load_data()

    def _load_data(self) -> None:
        # 1. Load current snapshot
        with open(self.identities_csv, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                uid = row["user_id"].strip()
                name = row["name"].strip()
                email = row["email"].strip().lower()
                phone = row["phone"].strip()
                email_h = row["email_hash"].strip().lower()

                # Derive potential customer reference variations
                refs = {uid}
                # e.g., user_05 -> CUST-05, CUST_05, CUST-005 if relevant
                num_part = uid.replace("user_", "")
                if num_part.isdigit():
                    refs.add(f"CUST-{num_part}")
                    refs.add(f"CUST_{num_part}")

                identity = UserIdentity(
                    user_id=uid,
                    current_name=name,
                    current_email=email,
                    current_phone=phone,
                    current_email_hash=email_h,
                    all_names={name},
                    all_emails={email},
                    all_email_hashes={email_h, compute_email_hash(email)},
                    all_phones={phone},
                    customer_references=refs,
                )
                self.users_by_id[uid] = identity
                self.email_to_user_id[email] = uid
                self.hash_to_user_id[email_h] = uid

        # 2. Enrich with historical changes from user_audit_log.csv
        with open(self.audit_log_csv, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                uid = row["user_id"].strip()
                if uid not in self.users_by_id:
                    continue
                user = self.users_by_id[uid]
                audit_id = row["audit_id"].strip()
                user.audit_ids.add(audit_id)
                field_name = row["field_name"].strip()
                old_val = row["old_value"].strip()
                new_val = row["new_value"].strip()

                if field_name == "email":
                    if old_val:
                        old_email = old_val.lower()
                        user.all_emails.add(old_email)
                        old_hash = compute_email_hash(old_email)
                        user.all_email_hashes.add(old_hash)
                        self.email_to_user_id[old_email] = uid
                        self.hash_to_user_id[old_hash] = uid
                    if new_val:
                        new_email = new_val.lower()
                        user.all_emails.add(new_email)
                        new_hash = compute_email_hash(new_email)
                        user.all_email_hashes.add(new_hash)
                        self.email_to_user_id[new_email] = uid
                        self.hash_to_user_id[new_hash] = uid
                elif field_name == "phone":
                    if old_val:
                        user.all_phones.add(old_val)
                    if new_val:
                        user.all_phones.add(new_val)
                elif field_name == "name":
                    if old_val:
                        user.all_names.add(old_val)
                    if new_val:
                        user.all_names.add(new_val)

    def resolve_by_email(self, email: str) -> Optional[UserIdentity]:
        """Resolves current or historical email (case-insensitive) to UserIdentity."""
        norm_email = email.strip().lower()
        uid = self.email_to_user_id.get(norm_email)
        if uid:
            return self.users_by_id.get(uid)
        # Fallback by email hash
        email_h = compute_email_hash(norm_email)
        uid = self.hash_to_user_id.get(email_h)
        if uid:
            return self.users_by_id.get(uid)
        return None

    def resolve_by_user_id(self, user_id: str) -> Optional[UserIdentity]:
        """Resolves user_id (e.g. 'user_01') to UserIdentity."""
        return self.users_by_id.get(user_id.strip())
