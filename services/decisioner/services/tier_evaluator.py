"""
Deterministic Tier Evaluator for Stage 3 Decisioning.
Combines objective facts, sensitivity findings, Judgment consensus, and policy engine hits
into a final LaunchCandidate proposal with safety warnings, structured reasons, and status.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any
from launchgraph_core.contracts.decisioner import (
    LaunchTier,
    ConfidenceBand,
    JudgmentConsensus,
)
from services.decisioner.services.fact_extractor import ChangeFacts
from services.decisioner.services.sensitivity_detector import SensitivityFindings
from services.decisioner.services.policy_engine import PolicyEvaluationResult


@dataclass
class EvaluatedCandidateDecision:
    tier: LaunchTier
    confidence: ConfidenceBand
    score: int
    is_external_safe: bool
    status: str  # PENDING_REVIEW, SUPPRESSED, CONFIRMED
    safety_warnings: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    required_approvers: List[str] = field(default_factory=list)
    policy_hits: List[Dict[str, Any]] = field(default_factory=list)


class TierEvaluator:
    """
    Synthesizes facts, consensus judgment, and policy rules into the final proposed candidate.
    """

    @classmethod
    def evaluate_candidate(
        cls,
        facts: ChangeFacts,
        sensitivity: SensitivityFindings,
        consensus: JudgmentConsensus,
        policy_result: PolicyEvaluationResult
    ) -> EvaluatedCandidateDecision:
        # 1. Base Tier from consensus
        candidate_tier = consensus.consensus_tier

        # 2. Apply Policy Escalations / Overrides
        if policy_result.escalated_tier is not None:
            candidate_tier = policy_result.escalated_tier

        # 3. Hard Invariants for Infra / Revert
        if facts.is_infra_only or facts.is_revert:
            candidate_tier = LaunchTier.T0

        # 4. Status Evaluation
        if policy_result.suppress_launch or facts.is_revert:
            status = "SUPPRESSED"
        else:
            status = "PENDING_REVIEW"

        # 5. External Safety Invariant
        # An asset / candidate is NOT external-safe if it has blocking findings,
        # required domain sign-offs pending, is suppressed, or is internal-only (T0).
        is_external_safe = True
        if status == "SUPPRESSED":
            is_external_safe = False
        if candidate_tier == LaunchTier.T0:
            is_external_safe = False
        if policy_result.blocking_findings:
            is_external_safe = False
        if policy_result.required_approvers:
            is_external_safe = False
        if sensitivity.customer_nda_detected or sensitivity.security_flags:
            is_external_safe = False

        # 6. Safety Warnings Compilation
        warnings: List[str] = []
        if policy_result.suppress_reasons:
            warnings.extend(policy_result.suppress_reasons)
        if policy_result.blocking_findings:
            warnings.extend(policy_result.blocking_findings)
        if policy_result.required_approvers:
            approvers_str = ", ".join(policy_result.required_approvers)
            warnings.append(f"Mandatory domain sign-off required by: {approvers_str}")
        if sensitivity.summary_findings:
            warnings.extend(sensitivity.summary_findings)

        # 7. Structured Rationale Generation
        reasons: List[str] = [
            f"Consensus evaluation across k={consensus.k_samples} samples proposed Tier {consensus.consensus_tier.value} (Agreement: {int(consensus.agreement_score * 100)}%)."
        ]
        if policy_result.escalated_tier:
            reasons.append(f"Policy engine escalated tier to {policy_result.escalated_tier.value} based on enterprise rules.")
        if facts.is_infra_only:
            reasons.append("Restricted to Tier T0 because change is infrastructure/developer tooling only.")
        if facts.is_revert:
            reasons.append("Classified as Tier T0 and SUPPRESSED due to revert/rollback indicator.")
        if facts.is_breaking_change:
            reasons.append("Identified breaking change or API deprecation requiring developer notification.")
        if facts.has_customer_docs:
            reasons.append("Customer-facing documentation updates present in changeset.")

        return EvaluatedCandidateDecision(
            tier=candidate_tier,
            confidence=consensus.confidence,
            score=consensus.score,
            is_external_safe=is_external_safe,
            status=status,
            safety_warnings=warnings,
            reasons=reasons,
            required_approvers=policy_result.required_approvers,
            policy_hits=policy_result.triggered_rules
        )

