"""
Evidence Pack Assembler for Stage 3 Decisioning.
Compiles deterministic facts, ticket details, PR diff summaries, and discussion contexts
into an auditable, strictly bounded EvidencePack (capped at 12,000 tokens) with SHA-256 context hash.
"""

import hashlib
import json
from typing import List, Dict, Any, Optional
from launchgraph_core.contracts.decisioner import EvidencePack, EvidenceChunk
from launchgraph_core.db.models.change_graph import ChangeEvent, ChangeMembership
from launchgraph_core.db.models.connection import SourceEvent
from services.decisioner.services.fact_extractor import ChangeFacts
from services.decisioner.services.sensitivity_detector import SensitivityFindings


class EvidencePackAssembler:
    """
    Assembles evidence chunks from ChangeEvent and linked SourceEvents,
    strictly enforcing the 12,000 token ceiling and generating a cryptographic context hash.
    """

    MAX_TOKENS = 12000

    @staticmethod
    def estimate_token_count(text: str) -> int:
        """Heuristic token estimator (1 token ~= 4 characters in English)."""
        if not text:
            return 1
        return max(1, len(text) // 4 + 1)

    @classmethod
    def assemble_pack(
        cls,
        change_event: ChangeEvent,
        facts: ChangeFacts,
        sensitivity: SensitivityFindings,
        source_events: List[SourceEvent],
        memberships: Optional[List[ChangeMembership]] = None
    ) -> EvidencePack:
        workspace_id_str = str(change_event.workspace_id)
        change_event_id_str = str(change_event.id)

        # Temporary holder for calculating hash
        all_chunk_texts: List[str] = []

        # Initialize pack with temporary hash
        pack = EvidencePack(
            workspace_id=workspace_id_str,
            change_event_id=change_event_id_str,
            chunks=[],
            total_tokens=0,
            context_hash=""
        )

        # 1. Chunk: Deterministic Fact Sheet & Sensitivity
        fact_content = (
            f"=== DETERMINISTIC FACT SHEET ===\n"
            f"Anchor Reference: {change_event.anchor_ref}\n"
            f"Title: {change_event.title}\n"
            f"Lifecycle State: {change_event.state} | Availability: {facts.availability}\n"
            f"Changed Files Count: {facts.changed_files_count} | Commits Count: {facts.total_commits_count}\n"
            f"Customer Docs Present: {facts.has_customer_docs}\n"
            f"Breaking Change: {facts.is_breaking_change}\n"
            f"Infrastructure Only: {facts.is_infra_only}\n"
            f"Revert Detected: {facts.is_revert}\n"
            f"Authors: {facts.author_attribution}\n"
            f"CI Status: {facts.ci_test_status}\n"
            f"Ticket Priority: {facts.ticket_priority}\n"
            f"\n=== SENSITIVITY SCAN RESULTS ===\n"
            f"Security Flags: {sensitivity.security_flags}\n"
            f"Customer NDA Detected: {sensitivity.customer_nda_detected}\n"
            f"Compliance Flag: {sensitivity.compliance_flag}\n"
            f"Pricing Impact: {sensitivity.pricing_impact}\n"
            f"Is Embargoed: {sensitivity.is_embargoed}\n"
        )
        if sensitivity.summary_findings:
            fact_content += "Findings: " + "; ".join(sensitivity.summary_findings) + "\n"

        cls._add_bounded_chunk(
            pack=pack,
            chunk_id="chk_facts_001",
            source_ref=change_event.anchor_ref,
            trust_label="INTERNAL",
            content=fact_content,
            all_texts=all_chunk_texts
        )

        # 2. Chunk: Primary Change Event Description
        if change_event.description:
            desc_content = f"=== PRIMARY ANCHOR CONTEXT ===\n{change_event.description}"
            cls._add_bounded_chunk(
                pack=pack,
                chunk_id="chk_anchor_002",
                source_ref=change_event.anchor_ref,
                trust_label="INTERNAL",
                content=desc_content,
                all_texts=all_chunk_texts
            )

        # 3. Chunks: Linked Source Events (GitHub PRs, Jira Issues, Slack Messages)
        for idx, event in enumerate(source_events, start=3):
            payload = event.raw_payload or {}
            source_ref = event.external_id
            trust_label = event.trust_label or "INTERNAL"

            content_lines = [f"=== SOURCE EVENT ({event.source_type} - {source_ref}) ==="]

            if event.source_type == "GITHUB":
                pr = payload.get("pull_request")
                if pr:
                    content_lines.append(f"PR #{pr.get('number')}: {pr.get('title')}")
                    content_lines.append(f"State: {pr.get('state')} | Merged: {pr.get('merged')}")
                    if pr.get("body"):
                        content_lines.append(f"Description:\n{pr.get('body')}")
                elif "commits" in payload:
                    content_lines.append(f"Push commits count: {len(payload['commits'])}")
                    for c in payload["commits"][:5]:
                        content_lines.append(f"- {c.get('id', '')[:7]}: {c.get('message', '').strip()}")

            elif event.source_type == "JIRA":
                issue = payload.get("issue", {})
                fields = issue.get("fields", {})
                content_lines.append(f"Key: {issue.get('key')} | Summary: {fields.get('summary')}")
                content_lines.append(f"Status: {fields.get('status', {}).get('name')}")
                content_lines.append(f"Issue Type: {fields.get('issuetype', {}).get('name')}")
                desc = fields.get("description")
                if desc:
                    content_lines.append(f"Description:\n{desc}")

            elif event.source_type == "SLACK":
                slack_ev = payload.get("event", {})
                content_lines.append(f"Channel: {slack_ev.get('channel')}")
                content_lines.append(f"Message Text:\n{slack_ev.get('text')}")

            content_str = "\n".join(content_lines)
            chunk_id = f"chk_source_{idx:03d}"
            added = cls._add_bounded_chunk(
                pack=pack,
                chunk_id=chunk_id,
                source_ref=source_ref,
                trust_label=trust_label,
                content=content_str,
                all_texts=all_chunk_texts
            )
            if not added:
                # Stop adding more source events once 12k ceiling is reached
                break

        # Calculate cryptographic hash of assembled context
        combined_context = "\n---\n".join(all_chunk_texts)
        pack.context_hash = hashlib.sha256(combined_context.encode("utf-8")).hexdigest()

        return pack

    @classmethod
    def _add_bounded_chunk(
        cls,
        pack: EvidencePack,
        chunk_id: str,
        source_ref: str,
        trust_label: str,
        content: str,
        all_texts: List[str]
    ) -> bool:
        tokens = cls.estimate_token_count(content)
        remaining = cls.MAX_TOKENS - pack.total_tokens

        if remaining <= 10:
            return False

        if tokens > remaining:
            # Truncate content to fit in remaining token budget
            suffix = "\n... [TRUNCATED DUE TO 12,000 TOKEN BOUNDING CEILING]"
            suffix_tokens = cls.estimate_token_count(suffix)
            budget_for_body = max(10, remaining - suffix_tokens - 5)
            content = content[:budget_for_body * 4] + suffix
            tokens = min(remaining, cls.estimate_token_count(content))

        chunk = EvidenceChunk(
            chunk_id=chunk_id,
            source_ref=source_ref,
            trust_label=trust_label,
            content=content,
            token_count=tokens
        )

        if pack.add_chunk(chunk):
            all_texts.append(content)
            return True
        return False
