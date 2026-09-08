"""Two-Stage RBAC Security Gatekeeper for OP-05.

Audits candidate passages retrieved globally across the corpus to decide if the
requester is permitted to access the governing policy.
"""
from __future__ import annotations

from typing import List, Optional, Tuple
from src.indexer import Passage, ROLE_RANK


class SecurityGatekeeper:
    @staticmethod
    def is_permitted(doc_role: str, user_role: str) -> bool:
        """True if user_role clearance is >= doc_role."""
        return ROLE_RANK.get(user_role, 0) >= ROLE_RANK.get(doc_role, 0)

    @classmethod
    def audit_retrieval(
        cls,
        hits: List[Tuple[Passage, float]],
        user_role: str,
        min_score_threshold: float = 12.0
    ) -> Tuple[bool, Optional[Passage]]:
        """Audit candidate retrieval hits.

        Returns:
            (is_allowed: bool, blocking_passage: Optional[Passage])
            If is_allowed is False, the user lacks permission for the top governing document.
        """
        if not hits:
            return True, None

        top_passage, top_score = hits[0]

        # If the highest-scoring governing document exceeds user role clearance:
        if top_score >= min_score_threshold and not cls.is_permitted(top_passage.role, user_role):
            # Check if there is another permitted passage with practically identical top score (> 0.99)
            permitted_hits = [p for p, s in hits if cls.is_permitted(p.role, user_role) and s >= top_score * 0.99]
            if not permitted_hits:
                return False, top_passage

        # Also check if the top 3 hits are predominantly restricted
        top3 = hits[:3]
        restricted_count = sum(1 for p, s in top3 if s >= min_score_threshold and not cls.is_permitted(p.role, user_role))
        if restricted_count >= 2 and not cls.is_permitted(top_passage.role, user_role):
            return False, top_passage

        return True, None
