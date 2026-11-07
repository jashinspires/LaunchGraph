"""
Unit tests for Stage 3 Deterministic Fact Extractor.
"""

import uuid
from launchgraph_core.db.models.change_graph import ChangeEvent
from launchgraph_core.db.models.connection import SourceEvent
from services.decisioner.services.fact_extractor import DeterministicFactExtractor


def test_fact_extractor_basic_pr():
    change = ChangeEvent(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        anchor_ref="PR-101",
        title="feat: Add OAuth2 PKCE login support",
        description="Implements PKCE RFC 7636 flow for single-page applications.",
        availability="beta"
    )

    src_event = SourceEvent(
        id=uuid.uuid4(),
        connection_id=uuid.uuid4(),
        source_type="GITHUB",
        external_id="PR-101",
        raw_payload={
            "pull_request": {
                "number": 101,
                "title": "feat: Add OAuth2 PKCE login support",
                "body": "Implements PKCE RFC 7636 flow.",
                "user": {"login": "alice_dev"},
                "changed_files": [
                    "auth/pkce.py",
                    "auth/token.py",
                    "docs/auth_guide.md"
                ]
            },
            "commits": [
                {
                    "id": "c0ffee1",
                    "message": "Add PKCE challenge validator",
                    "author": {"name": "alice_dev"},
                    "modified": ["auth/pkce.py"]
                }
            ]
        }
    )

    facts = DeterministicFactExtractor.extract_facts(change, [src_event])

    assert facts.changed_files_count == 3
    assert facts.has_customer_docs is True
    assert facts.is_infra_only is False
    assert facts.is_breaking_change is False
    assert facts.is_revert is False
    assert "alice_dev" in facts.author_attribution
    assert facts.availability == "beta"


def test_fact_extractor_breaking_change():
    change = ChangeEvent(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        anchor_ref="JIRA-202",
        title="BREAKING CHANGE: Deprecate v1 telemetry endpoints",
        description="Removes legacy v1 endpoint paths in favor of v2.",
        availability="ga"
    )

    facts = DeterministicFactExtractor.extract_facts(change, [])
    assert facts.is_breaking_change is True


def test_fact_extractor_infra_only():
    change = ChangeEvent(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        anchor_ref="PR-404",
        title="chore: update CI matrix for python 3.13",
        description="Upgrades GitHub actions workflow files.",
        availability="internal"
    )

    src_event = SourceEvent(
        id=uuid.uuid4(),
        connection_id=uuid.uuid4(),
        source_type="GITHUB",
        external_id="PR-404",
        raw_payload={
            "commits": [
                {
                    "id": "abc1234",
                    "message": "Update CI runners",
                    "added": [".github/workflows/ci.yml", ".github/workflows/deploy.yml"]
                }
            ]
        }
    )

    facts = DeterministicFactExtractor.extract_facts(change, [src_event])
    assert facts.is_infra_only is True
    assert facts.has_customer_docs is False


def test_fact_extractor_revert():
    change = ChangeEvent(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        anchor_ref="PR-505",
        title="Revert 'feat: experimental streaming cache'",
        description="Rolls back commit due to memory leak."
    )

    facts = DeterministicFactExtractor.extract_facts(change, [])
    assert facts.is_revert is True

