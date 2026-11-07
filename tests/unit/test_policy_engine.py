"""
Unit tests for Stage 3 Restrict-Only Policy Engine.
"""

from datetime import datetime, timezone, timedelta
from launchgraph_core.contracts.decisioner import LaunchTier
from services.decisioner.services.fact_extractor import ChangeFacts
from services.decisioner.services.sensitivity_detector import SensitivityFindings
from services.decisioner.services.policy_engine import PolicyEngine


def test_policy_engine_p_sec_requires_security_lead():
    facts = ChangeFacts()
    sensitivity = SensitivityFindings(security_flags=True)

    result = PolicyEngine.evaluate(facts, sensitivity, proposed_tier=LaunchTier.T2)

    assert "security_lead" in result.required_approvers
    assert any(hit["rule_code"] == "P-SEC" for hit in result.triggered_rules)


def test_policy_engine_p_cust_adds_blocking_finding():
    facts = ChangeFacts()
    sensitivity = SensitivityFindings(customer_nda_detected=True)

    result = PolicyEngine.evaluate(facts, sensitivity, proposed_tier=LaunchTier.T2)

    assert len(result.blocking_findings) > 0
    assert any("[P-CUST]" in f for f in result.blocking_findings)
    assert result.has_blocks_or_suppressions is True


def test_policy_engine_p_embargo_suppresses_launch():
    facts = ChangeFacts()
    future_date = datetime.now(timezone.utc) + timedelta(days=10)
    sensitivity = SensitivityFindings(is_embargoed=True, embargo_date=future_date)

    result = PolicyEngine.evaluate(facts, sensitivity, proposed_tier=LaunchTier.T1)

    assert result.suppress_launch is True
    assert any("[P-EMBARGO]" in r for r in result.suppress_reasons)


def test_policy_engine_p_depr_escalates_to_t2():
    facts = ChangeFacts(is_breaking_change=True)
    sensitivity = SensitivityFindings()

    result = PolicyEngine.evaluate(facts, sensitivity, proposed_tier=LaunchTier.T3)

    assert result.escalated_tier == LaunchTier.T2


def test_policy_engine_p_internal_restricts_to_t0():
    facts = ChangeFacts(is_infra_only=True)
    sensitivity = SensitivityFindings()

    result = PolicyEngine.evaluate(facts, sensitivity, proposed_tier=LaunchTier.T3)

    assert result.escalated_tier == LaunchTier.T0


def test_policy_engine_p_pricing_requires_gtm_vp():
    facts = ChangeFacts()
    sensitivity = SensitivityFindings(pricing_impact=True)

    result = PolicyEngine.evaluate(facts, sensitivity, proposed_tier=LaunchTier.T2)

    assert "gtm_vp" in result.required_approvers


def test_policy_engine_p_revert_suppresses():
    facts = ChangeFacts(is_revert=True)
    sensitivity = SensitivityFindings()

    result = PolicyEngine.evaluate(facts, sensitivity, proposed_tier=LaunchTier.T2)

    assert result.suppress_launch is True

