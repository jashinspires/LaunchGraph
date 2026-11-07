"""
Unit tests for Stage 3 Deterministic Tier Evaluator.
"""

from launchgraph_core.contracts.decisioner import (
    LaunchTier,
    ConfidenceBand,
    JudgmentConsensus,
)
from services.decisioner.services.fact_extractor import ChangeFacts
from services.decisioner.services.sensitivity_detector import SensitivityFindings
from services.decisioner.services.policy_engine import PolicyEvaluationResult
from services.decisioner.services.tier_evaluator import TierEvaluator


def test_tier_evaluator_clean_t1():
    facts = ChangeFacts(changed_files_count=15, has_customer_docs=True)
    sensitivity = SensitivityFindings()
    consensus = JudgmentConsensus(
        consensus_tier=LaunchTier.T1,
        confidence=ConfidenceBand.HIGH,
        score=95
    )
    policy_res = PolicyEvaluationResult(
        required_approvers=["product_lead"]  # P-MAJOR-TIER
    )

    decision = TierEvaluator.evaluate_candidate(
        facts=facts,
        sensitivity=sensitivity,
        consensus=consensus,
        policy_result=policy_res
    )

    assert decision.tier == LaunchTier.T1
    assert decision.status == "PENDING_REVIEW"
    # Not external safe until product_lead sign-off
    assert decision.is_external_safe is False
    assert any("product_lead" in w for w in decision.safety_warnings)


def test_tier_evaluator_suppressed_revert():
    facts = ChangeFacts(is_revert=True)
    sensitivity = SensitivityFindings()
    consensus = JudgmentConsensus(
        consensus_tier=LaunchTier.T2,
        confidence=ConfidenceBand.MEDIUM,
        score=40
    )
    policy_res = PolicyEvaluationResult(suppress_launch=True)

    decision = TierEvaluator.evaluate_candidate(
        facts=facts,
        sensitivity=sensitivity,
        consensus=consensus,
        policy_result=policy_res
    )

    assert decision.tier == LaunchTier.T0
    assert decision.status == "SUPPRESSED"
    assert decision.is_external_safe is False


def test_tier_evaluator_clean_t3():
    facts = ChangeFacts(changed_files_count=1)
    sensitivity = SensitivityFindings()
    consensus = JudgmentConsensus(
        consensus_tier=LaunchTier.T3,
        confidence=ConfidenceBand.HIGH,
        score=45
    )
    policy_res = PolicyEvaluationResult()

    decision = TierEvaluator.evaluate_candidate(
        facts=facts,
        sensitivity=sensitivity,
        consensus=consensus,
        policy_result=policy_res
    )

    assert decision.tier == LaunchTier.T3
    assert decision.status == "PENDING_REVIEW"
    assert decision.is_external_safe is True
    assert len(decision.safety_warnings) == 0

