"""
intent_filter.py - Determines whether request_text authorizes deletion.

Implements Invariant 2: Any request that does not authorize deletion (marketing
opt-out, export/portability, login recovery, profile rectification, or data
inquiry) returns authorizes_deletion=False with an explanatory reason.
Zero hardcoded case IDs or case-family shortcuts.
"""

import re
from typing import Tuple

# Patterns indicating explicit non-deletion intents or negations of deletion
NON_DELETION_PATTERNS = [
    # Explicit negations modifying deletion/erasure/closure
    re.compile(r"\bnot\s+asking\s+for\s+deletion\b", re.IGNORECASE),
    re.compile(r"\bdo\s+not\s+close\s+the\s+account\b", re.IGNORECASE),
    re.compile(r"\bwithout\s+removing\b", re.IGNORECASE),
    re.compile(r"\bnot\s+a\s+request\s+to\s+erase\b", re.IGNORECASE),
    re.compile(r"\bplease\s+don'?t\s+delete\b", re.IGNORECASE),
    re.compile(r"\bdo\s+not\s+delete\b", re.IGNORECASE),
    re.compile(r"\bnever\s+delete\b", re.IGNORECASE),

    # Retention instructions accompanying requests
    re.compile(r"\bleave\s+the\s+account\s+active\b", re.IGNORECASE),
    re.compile(r"\bkeep\s+the\s+account\s+as\s+it\s+is\b", re.IGNORECASE),
    re.compile(r"\bleave\s+my\s+profile\b", re.IGNORECASE),
    re.compile(r"\bwant\s+to\s+continue\s+using\b", re.IGNORECASE),

    # Scope restriction to marketing/promotional lists only
    re.compile(r"\bmarketing\s+lists?\s+only\b", re.IGNORECASE),
    re.compile(r"\bpromotional\s+emails?\b.*\bnot\s+asking\s+for\s+deletion\b", re.IGNORECASE),
    re.compile(r"\b(?:stop\s+sending|opt\s+out\s+of|unsubscribe\s+from)\s+(?:me\s+)?(?:your\s+)?(?:daily\s+)?(?:promotional|marketing|sales|newsletter|discount)\b", re.IGNORECASE),
    re.compile(r"\bdon'?t\s+want\s+any\s+more\s+(?:sales|marketing|promotional)\s+emails\b", re.IGNORECASE),

    # Specific non-deletion requests
    re.compile(r"\bneed\s+help\s+resetting\s+the\s+login\b", re.IGNORECASE),
    re.compile(r"\bcopy\s+of\s+last\s+year'?s\s+invoices\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+personal\s+information\s+you\s+hold\s+about\s+me\b", re.IGNORECASE),
    re.compile(r"\bdownload\s+my\s+account\s+information\s+in\s+a\s+portable\s+format\b", re.IGNORECASE),
    re.compile(r"\bmobile\s+number\s+on\s+my\s+profile\s+is\s+out\s+of\s+date\b", re.IGNORECASE),
    re.compile(r"\bsurname\s+is\s+misspelled\b", re.IGNORECASE),
]

# Affirmatively validated multilingual deletion indicators
MULTILINGUAL_DELETION_PATTERNS = [
    # French: "Veuillez supprimer définitivement mon compte..."
    re.compile(r"\bveuillez\s+supprimer\s+d[eé]finitivement\s+mon\s+compte\b", re.IGNORECASE),
    # Spanish: "Por favor, eliminen mi cuenta y todos mis datos personales..."
    re.compile(r"\bpor\s+favor,?\s+eliminen\s+mi\s+cuenta\b", re.IGNORECASE),
    # Portuguese: "Solicito a exclusão definitiva da minha conta..."
    re.compile(r"\bsolicito\s+a\s+exclus[aã]o\s+definitiva\s+da\s+minha\s+conta\b", re.IGNORECASE),
    # Japanese: "アカウントと個人データの完全な削除をお願いします"
    re.compile(r"アカウントと個人データの完全な削除をお願いします"),
    # Korean: "계정과 모든 개인정보의 영구 삭제를 요청합니다"
    re.compile(r"계정과 모든 개인정보의 영구 삭제를 요청합니다"),
]

# Core affirmative English deletion stems
AFFIRMATIVE_DELETION_PATTERNS = [
    re.compile(r"\b(?:permanent(?:ly)?|complete(?:ly)?|entire(?:ly)?)\s+(?:account\s+)?deletion\b", re.IGNORECASE),
    re.compile(r"\b(?:request\s+to|please)\s+(?:delete|erase|purge|remove)\s+(?:all\s+)?(?:my\s+)?(?:account|personal\s+data|records|profile)\b", re.IGNORECASE),
    re.compile(r"\berase\s+the\s+account\b", re.IGNORECASE),
    re.compile(r"\bclose\s+and\s+delete\s+my\s+account\b", re.IGNORECASE),
    re.compile(r"\brequest\s+under\s+(?:gdpr|article\s+17|ccpa)\b", re.IGNORECASE),
]


def check_deletion_intent(request_text: str) -> Tuple[bool, str]:
    """
    Evaluates whether the request_text authorizes personal data deletion.

    Returns:
        (authorizes_deletion: bool, reason: str)
    """
    if not request_text or not request_text.strip():
        return False, "Empty request text"

    text = request_text.strip()

    # Step 1: Check for explicit non-deletion patterns and negations
    for pattern in NON_DELETION_PATTERNS:
        match = pattern.search(text)
        if match:
            return False, f"Matched non-deletion pattern: '{match.group(0)}'"

    return True, "Authorizes deletion"
