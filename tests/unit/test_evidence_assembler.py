"""
Unit tests for Stage 3 Evidence Pack Assembler.
"""

import uuid
from launchgraph_core.db.models.change_graph import ChangeEvent
from launchgraph_core.db.models.connection import SourceEvent
from services.decisioner.services.fact_extractor import ChangeFacts
from services.decisioner.services.sensitivity_detector import SensitivityFindings
from services.decisioner.services.evidence_assembler import EvidencePackAssembler


def test_evidence_pack_assembly_and_hash():
    change = ChangeEvent(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        anchor_ref="JIRA-100",
        title="Implement Multi-Tenant Row Level Security",
        description="Enforces tenant boundaries via workspace_id PostgreSQL RLS.",
        state="merged",
        availability="ga"
    )

    facts = ChangeFacts(
        changed_files_count=4,
        has_customer_docs=True,
        author_attribution="sec_team",
        ci_test_status="passed"
    )

    sensitivity = SensitivityFindings(
        compliance_flag=True,
        summary_findings=["Compliance standard referenced: SOC 2"]
    )

    source_event = SourceEvent(
        id=uuid.uuid4(),
        connection_id=uuid.uuid4(),
        source_type="GITHUB",
        external_id="PR-42",
        raw_payload={
            "pull_request": {
                "number": 42,
                "title": "RLS Policies",
                "state": "closed",
                "merged": True
            }
        }
    )

    pack = EvidencePackAssembler.assemble_pack(
        change_event=change,
        facts=facts,
        sensitivity=sensitivity,
        source_events=[source_event]
    )

    assert pack.workspace_id == str(change.workspace_id)
    assert pack.change_event_id == str(change.id)
    assert len(pack.chunks) >= 2
    assert pack.total_tokens <= 12000
    assert len(pack.context_hash) == 64  # SHA-256 hex string
    assert pack.chunks[0].chunk_id == "chk_facts_001"


def test_evidence_pack_truncation_under_12k_ceiling():
    change = ChangeEvent(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        anchor_ref="OVERFLOW-1",
        title="Massive Codebase Refactor",
        description="A" * 60000  # Enormous description (~15,000 tokens)
    )

    facts = ChangeFacts()
    sensitivity = SensitivityFindings()

    pack = EvidencePackAssembler.assemble_pack(
        change_event=change,
        facts=facts,
        sensitivity=sensitivity,
        source_events=[]
    )

    assert pack.total_tokens <= 12000
    assert any("[TRUNCATED DUE TO 12,000 TOKEN BOUNDING CEILING]" in c.content for c in pack.chunks)

