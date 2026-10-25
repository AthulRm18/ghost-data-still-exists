"""
Unit tests for intent_filter.py and identity_resolver.py
"""

import unittest
from pathlib import Path

from code.identity_resolver import IdentityResolver, compute_email_hash
from code.intent_filter import check_deletion_intent


class TestIntentFilter(unittest.TestCase):
    def test_explicit_non_deletion_cases(self):
        non_deletion_samples = [
            "The mobile number on my profile is out of date. Please replace it with the new one and leave the account active.",
            "Please stop the promotional emails. I still need the account and my order history, so I am not asking for deletion.",
            "I'd like to download my account information in a portable format. Please keep the account as it is.",
            "I can't access my profile and need help resetting the login. Do not close the account.",
            "My surname is misspelled on the account. Can you correct it without removing any of my records?",
            "Please remove me from marketing lists only. I still want receipts and service messages for this account.",
            "Can you tell me what personal information you hold about me? This is an information request, not a request to erase it.",
            "I need a copy of last year's invoices for my records. Please leave my profile and purchase history in place.",
            "Please change the email address used for this account. I want to continue using the service.",
            "Could you send me a copy of the information held on my account? I still use it, so please don't delete or change anything.",
        ]
        for text in non_deletion_samples:
            authorized, reason = check_deletion_intent(text)
            self.assertFalse(authorized, f"Expected non-deletion for: {text} (got {reason})")

    def test_affirmative_deletion_cases(self):
        affirmative_samples = [
            "Please treat this message as a request for permanent account deletion.",
            "I would like to submit a request to delete this account and its personal data under GDPR.",
            "Please erase the account linked to this email address and all associated records.",
            "Veuillez supprimer définitivement mon compte et l'ensemble de mes données personnelles.",
            "Por favor, eliminen mi cuenta y todos mis datos personales asociados a esta dirección.",
            "Solicito a exclusão definitiva da minha conta e de todos os dados pessoais.",
            "アカウントと個人データの完全な削除をお願いします。",
            "계정과 모든 개인정보의 영구 삭제를 요청합니다.",
        ]
        for text in affirmative_samples:
            authorized, reason = check_deletion_intent(text)
            self.assertTrue(authorized, f"Expected deletion for: {text} (got {reason})")


class TestIdentityResolver(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        repo_root = Path(__file__).resolve().parent.parent.parent
        identities_csv = repo_root / "dataset" / "user_identities.csv"
        audit_log_csv = repo_root / "dataset" / "user_audit_log.csv"
        cls.resolver = IdentityResolver(identities_csv, audit_log_csv)

    def test_current_email_resolution(self):
        user = self.resolver.resolve_by_email("amina.elmasri@gmail.com")
        self.assertIsNotNone(user)
        self.assertEqual(user.user_id, "user_01")
        self.assertEqual(user.current_name, "Amina El-Masri")

    def test_case_insensitive_resolution(self):
        user = self.resolver.resolve_by_email("AMINA.ELMASRI@GMAIL.COM")
        self.assertIsNotNone(user)
        self.assertEqual(user.user_id, "user_01")

    def test_historical_email_resolution(self):
        # Find a user with historical email update in audit log
        # In audit log, user_485, user_505, etc. have phone, let's test lookup on an email change
        for uid, user in self.resolver.users_by_id.items():
            if len(user.all_emails) > 1:
                emails = list(user.all_emails)
                # Test resolving both emails
                u1 = self.resolver.resolve_by_email(emails[0])
                u2 = self.resolver.resolve_by_email(emails[1])
                self.assertEqual(u1.user_id, uid)
                self.assertEqual(u2.user_id, uid)
                break

    def test_compute_email_hash(self):
        h = compute_email_hash("amina.elmasri@gmail.com")
        self.assertEqual(h, "d4e1f59abcf9a1e0cfdc7c27ad6c07ed4ff88b326a16ed5eed5ec6bc31618c93")


if __name__ == "__main__":
    unittest.main()
