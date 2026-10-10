"""
Unit tests for Deterministic Link Typing Engine (L1-L8).
"""

from services.normalizer.services.link_typing import LinkTypingEngine, LinkType


def test_link_typing_implements():
    # Title starting with Jira key
    link = LinkTypingEngine.determine_link_type(title="PROJ-1024: Add OAuth support")
    assert link == LinkType.L1_IMPLEMENTS

    # Branch name containing Jira key
    link_branch = LinkTypingEngine.determine_link_type(
        title="Add OAuth support",
        branch_name="feature/PROJ-1024-oauth"
    )
    assert link_branch == LinkType.L1_IMPLEMENTS


def test_link_typing_fixes():
    link = LinkTypingEngine.determine_link_type(
        title="Fix authentication bug",
        body="This PR resolves PROJ-999 and fixes #42."
    )
    assert link == LinkType.L3_FIXES


def test_link_typing_reverts():
    link = LinkTypingEngine.determine_link_type(
        title='Revert "PROJ-1024: Add OAuth support"',
        body="Reverting due to unexpected latency spike."
    )
    assert link == LinkType.L4_REVERTS


def test_link_typing_jira_explicit_types():
    assert LinkTypingEngine.determine_link_type(title="Issue", jira_link_type="Blocks") == LinkType.L8_BLOCKS
    assert LinkTypingEngine.determine_link_type(title="Issue", jira_link_type="Duplicate") == LinkType.L7_DUPLICATE_OF
    assert LinkTypingEngine.determine_link_type(title="Issue", jira_link_type="Relates") == LinkType.L6_RELATES_TO
    assert LinkTypingEngine.determine_link_type(title="Issue", jira_link_type="Epic-Child") == LinkType.L5_CONTAINS


def test_link_typing_default_mentions():
    link = LinkTypingEngine.determine_link_type(
        title="General refactor",
        body="Note: similar to how PROJ-10 handled database pooling."
    )
    assert link == LinkType.L2_MENTIONS
