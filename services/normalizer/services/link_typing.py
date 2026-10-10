"""
Deterministic Link Typing Engine (L1-L8).
Categorizes relationships between source events and changes with high precision.
"""

import re
from enum import Enum
from typing import Optional

CLOSING_KEYWORDS_PATTERN = re.compile(
    r"(?i)\b(fix|fixes|fixed|close|closes|closed|resolve|resolves|resolved)\s+(?:#\d+|[A-Z][A-Z0-9]+-\d+)"
)
REVERT_PATTERN = re.compile(
    r"(?i)\b(revert|reverting|reverted)\b|\bRevert\s+\"[^\"]+\""
)


class LinkType(str, Enum):
    L1_IMPLEMENTS = "implements"
    L2_MENTIONS = "mentions"
    L3_FIXES = "fixes"
    L4_REVERTS = "reverts"
    L5_CONTAINS = "contains"
    L6_RELATES_TO = "relates_to"
    L7_DUPLICATE_OF = "duplicate_of"
    L8_BLOCKS = "blocks"


class LinkTypingEngine:
    """
    Evaluates context, syntax, and keywords to assign deterministic relationship types.
    """

    @classmethod
    def determine_link_type(
        cls,
        title: str,
        body: Optional[str] = None,
        branch_name: Optional[str] = None,
        jira_link_type: Optional[str] = None,
        is_revert: bool = False
    ) -> LinkType:
        """
        Applies deterministic priority cascade:
        1. Explicit revert syntax -> L4 (reverts)
        2. Explicit Jira relation (blocks, duplicate, relates) -> L8, L7, L6
        3. Closing keywords in text -> L3 (fixes)
        4. PR title or branch name ticket match -> L1 (implements)
        5. Epics / Release versions -> L5 (contains)
        6. Default informal citation -> L2 (mentions)
        """
        combined_text = f"{title or ''} {body or ''}"

        # 1. Revert check
        if is_revert or REVERT_PATTERN.search(title or ""):
            return LinkType.L4_REVERTS

        # 2. Jira link types
        if jira_link_type:
            j_lower = jira_link_type.lower()
            if "block" in j_lower:
                return LinkType.L8_BLOCKS
            if "duplicate" in j_lower:
                return LinkType.L7_DUPLICATE_OF
            if "relate" in j_lower:
                return LinkType.L6_RELATES_TO
            if "contain" in j_lower or "epic" in j_lower:
                return LinkType.L5_CONTAINS

        # 3. PR branch / title implements check (L1: PR directly implements an issue)
        if branch_name and re.search(r"[A-Z][A-Z0-9]+-[0-9]+", branch_name):
            return LinkType.L1_IMPLEMENTS
        if title and re.search(r"^[A-Z][A-Z0-9]+-[0-9]+", title.strip()):
            return LinkType.L1_IMPLEMENTS

        # 4. Closing keyword check (L3: fixes)
        if CLOSING_KEYWORDS_PATTERN.search(combined_text):
            return LinkType.L3_FIXES

        # 5. Default
        return LinkType.L2_MENTIONS
