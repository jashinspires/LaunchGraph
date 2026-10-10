"""
Unit tests for Frozen Pydantic v2 Contracts.
"""

import uuid
import pytest
from launchgraph_core.contracts.jobs import JobEnvelope, JobType, JOB_RETRY_POLICIES
from launchgraph_core.contracts.decisioner import (
    EvidencePack,
    EvidenceChunk,
    LaunchTier,
    ConfidenceBand,
    DEFAULT_POLICY_RULES,
)
from launchgraph_core.contracts.generator import (
    AssetType,
    AssetDraftOutput,
    LintRuleCode,
    LintSeverity,
    ASSET_BOUNDARIES,
)
from launchgraph_core.contracts.mem0 import CandidateFact, ExtractedMemoryPack, Mem0OperationAction


def test_job_contract_dedupe_key():
    entity_id = "PROJ-1024"
    dedupe_key = JobEnvelope.create_dedupe_key(JobType.NORMALIZE, entity_id, "v1")
    assert dedupe_key == "normalize:PROJ-1024:v1"
    assert JobType.NORMALIZE in JOB_RETRY_POLICIES
    assert JOB_RETRY_POLICIES[JobType.NORMALIZE].max_retries == 3


def test_evidence_pack_12k_token_bounding():
    pack = EvidencePack(
        workspace_id=str(uuid.uuid4()),
        change_event_id=str(uuid.uuid4()),
        context_hash="abc123hash"
    )

    chunk1 = EvidenceChunk(
        chunk_id="chunk-1",
        source_ref="PR-100",
        content="Initial implementation details",
        token_count=5000
    )
    assert pack.add_chunk(chunk1) is True
    assert pack.total_tokens == 5000

    chunk2 = EvidenceChunk(
        chunk_id="chunk-2",
        source_ref="JIRA-50",
        content="Customer bug ticket details",
        token_count=6000
    )
    assert pack.add_chunk(chunk2) is True
    assert pack.total_tokens == 11000

    # Exceeds 12k ceiling (11,000 + 2,000 > 12,000) -> must reject
    chunk3 = EvidenceChunk(
        chunk_id="chunk-3",
        source_ref="JIRA-99",
        content="Overflowing chunk",
        token_count=2000
    )
    assert pack.add_chunk(chunk3) is False
    assert pack.total_tokens == 11000


def test_asset_character_boundary_validation():
    # Changelog max is 1200 characters
    changelog_draft = AssetDraftOutput(
        asset_type=AssetType.CHANGELOG,
        content="A" * 1500
    )
    changelog_draft.validate_bounds()
    assert changelog_draft.is_blocked is True
    assert any(f.rule_code == LintRuleCode.LINT_LENGTH for f in changelog_draft.findings)


def test_mem0_contract_candidate_fact():
    fact = CandidateFact(
        entity_type="FEATURE",
        name="Zero-Knowledge Identity Verification",
        attributes={"standard": "OIDC4VP"},
        information_content_score=0.95
    )
    assert fact.name == "Zero-Knowledge Identity Verification"
    assert fact.attributes["standard"] == "OIDC4VP"


def test_policy_dsl_rules_catalog():
    assert len(DEFAULT_POLICY_RULES) >= 11
    rule_codes = {r.code for r in DEFAULT_POLICY_RULES}
    assert "P-SEC" in rule_codes
    assert "P-CUST" in rule_codes
    assert "P-EMBARGO" in rule_codes
    assert "P-COMPL" in rule_codes
    assert "P-DEPR" in rule_codes
    assert "P-INTERNAL" in rule_codes
