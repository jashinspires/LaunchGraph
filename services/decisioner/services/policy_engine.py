"""
Restrict-Only Policy Engine for Stage 3 Decisioning.
Evaluates 11 enterprise policy rules enforcing that policies can only escalate tiers,
add mandatory domain approvers, add blocking findings, or suppress launches, never loosening constraints.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from launchgraph_core.contracts.decisioner import (
    DEFAULT_POLICY_RULES,
    PolicyRuleDef,
    PolicyEffect,
    LaunchTier,
    EvidencePack,
)
from services.decisioner.services.fact_extractor import ChangeFacts
from services.decisioner.services.sensitivity_detector import SensitivityFindings


TIER_HIERARCHY = {
    LaunchTier.T0: 0,
    LaunchTier.T3: 1,
    LaunchTier.T2: 2,
    LaunchTier.T1: 3,
}


@dataclass
class PolicyEvaluationResult:
    escalated_tier: Optional[LaunchTier] = None
    required_approvers: List[str] = field(default_factory=list)
    blocking_findings: List[str] = field(default_factory=list)
    suppress_launch: bool = False
    suppress_reasons: List[str] = field(default_factory=list)
    triggered_rules: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def has_blocks_or_suppressions(self) -> bool:
        return self.suppress_launch or len(self.blocking_findings) > 0


class PolicyEngine:
    """
    Evaluates workspace policy rules under strict restrict-only semantics.
    """

    @classmethod
    def evaluate(
        cls,
        facts: ChangeFacts,
        sensitivity: SensitivityFindings,
        proposed_tier: LaunchTier,
        pack: Optional[EvidencePack] = None,
        custom_rules: Optional[List[PolicyRuleDef]] = None
    ) -> PolicyEvaluationResult:
        rules_to_run = (custom_rules or []) + DEFAULT_POLICY_RULES
        result = PolicyEvaluationResult()

        now = datetime.now(timezone.utc)
        current_tier = proposed_tier

        has_untrusted = False
        if pack:
            has_untrusted = any(c.trust_label == "EXTERNAL_UNTRUSTED" for c in pack.chunks)

        for rule in rules_to_run:
            triggered = False
            trigger_reason = ""

            # Evaluate condition
            if rule.code == "P-SEC" and sensitivity.security_flags:
                triggered = True
                trigger_reason = "Security/CVE sensitivity detected in change context."

            elif rule.code == "P-CUST" and sensitivity.customer_nda_detected:
                triggered = True
                trigger_reason = "Customer NDA / Enterprise confidentiality pattern detected."

            elif rule.code == "P-EMBARGO" and sensitivity.is_embargoed:
                if sensitivity.embargo_date is None or now < sensitivity.embargo_date:
                    triggered = True
                    trigger_reason = f"Active embargo in effect (Hold until: {sensitivity.embargo_date or 'TBD'})."

            elif rule.code == "P-COMPL" and sensitivity.compliance_flag:
                triggered = True
                trigger_reason = "Regulatory compliance keyword (SOC2, HIPAA, GDPR, etc.) detected."

            elif rule.code == "P-DEPR" and facts.is_breaking_change:
                triggered = True
                trigger_reason = "Breaking change or API deprecation detected; escalating to at least T2."

            elif rule.code == "P-INTERNAL" and facts.is_infra_only:
                triggered = True
                trigger_reason = "Internal developer tooling or CI/CD infrastructure change; restricted to T0."

            elif rule.code == "P-PRICING" and sensitivity.pricing_impact:
                triggered = True
                trigger_reason = "Pricing or monetization modification detected; requires GTM VP sign-off."

            elif rule.code == "P-REVERT" and facts.is_revert:
                triggered = True
                trigger_reason = "Change is marked as a code revert/rollback; suppressing GTM publication."

            elif rule.code == "P-EXPERIMENTAL" and facts.availability == "internal":
                triggered = True
                trigger_reason = "Internal availability feature flagged for external copy restriction."

            elif rule.code == "P-MAJOR-TIER" and current_tier == LaunchTier.T1:
                triggered = True
                trigger_reason = "Tier T1 Strategic launch mandates two independent approvers (Lead PMM + Product Lead)."

            elif rule.code == "P-EXTERNAL-TRUST" and has_untrusted:
                triggered = True
                trigger_reason = "Untrusted external source content detected in evidence pack."

            if triggered:
                hit_info = {
                    "rule_code": rule.code,
                    "rule_name": rule.name,
                    "effect": rule.effect.value,
                    "reason": trigger_reason
                }
                result.triggered_rules.append(hit_info)

                # Apply Restrict-Only Effects
                if rule.effect == PolicyEffect.REQUIRE_DOMAIN_APPROVER:
                    if rule.required_role and rule.required_role not in result.required_approvers:
                        result.required_approvers.append(rule.required_role)

                elif rule.effect == PolicyEffect.ADD_BLOCKING_FINDING:
                    result.blocking_findings.append(f"[{rule.code}] {trigger_reason}")

                elif rule.effect == PolicyEffect.SUPPRESS_LAUNCH:
                    result.suppress_launch = True
                    result.suppress_reasons.append(f"[{rule.code}] {trigger_reason}")

                elif rule.effect == PolicyEffect.ESCALATE_TIER:
                    if rule.target_tier:
                        target = rule.target_tier
                        # For P-INTERNAL, demotes to T0
                        if rule.code == "P-INTERNAL":
                            current_tier = LaunchTier.T0
                            result.escalated_tier = LaunchTier.T0
                        else:
                            # Restrict-only: only escalate upwards in importance (T3 -> T2 -> T1)
                            if TIER_HIERARCHY.get(target, 0) > TIER_HIERARCHY.get(current_tier, 0):
                                current_tier = target
                                result.escalated_tier = target

        return result

