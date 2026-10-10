"""
B0.4 Judgment & Policy Contracts
Defines schemas for deterministic facts, evidence packaging (12,000 token bounding),
questions Q1-Q9, consensus scoring, and the Restrict-Only Policy DSL.
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ConfidenceBand(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class LaunchTier(str, Enum):
    T0 = "T0"  # Internal only / No external GTM
    T1 = "T1"  # Major strategic launch
    T2 = "T2"  # Notable feature
    T3 = "T3"  # Minor changelog entry


class EvidenceChunk(BaseModel):
    chunk_id: str
    source_ref: str
    trust_label: str = "INTERNAL"  # INTERNAL or EXTERNAL_UNTRUSTED
    content: str
    token_count: int


class EvidencePack(BaseModel):
    workspace_id: str
    change_event_id: str
    chunks: List[EvidenceChunk] = Field(default_factory=list)
    total_tokens: int = Field(default=0, le=12000)  # Hard 12,000 token ceiling
    context_hash: str  # SHA-256 hash of assembled context

    def add_chunk(self, chunk: EvidenceChunk) -> bool:
        """Adds a chunk strictly respecting the 12,000 token limit."""
        if self.total_tokens + chunk.token_count > 12000:
            return False
        self.chunks.append(chunk)
        self.total_tokens += chunk.token_count
        return True


class QuestionAnswer(BaseModel):
    question_id: str  # Q1 through Q9
    question_text: str
    answer: Any
    confidence: ConfidenceBand
    citations: List[str] = Field(default_factory=list)
    rationale: str


class JudgmentConsensus(BaseModel):
    k_samples: int = 3
    consensus_tier: LaunchTier
    confidence: ConfidenceBand
    score: int = Field(ge=1, le=100)
    answers: List[QuestionAnswer] = Field(default_factory=list)
    raw_samples: List[Dict[str, Any]] = Field(default_factory=list)
    agreement_score: float = Field(default=1.0, ge=0.0, le=1.0)


# ============================================================================
# Restrict-Only Policy DSL
# ============================================================================

class PolicyEffect(str, Enum):
    ESCALATE_TIER = "ESCALATE_TIER"
    REQUIRE_DOMAIN_APPROVER = "REQUIRE_DOMAIN_APPROVER"
    ADD_BLOCKING_FINDING = "ADD_BLOCKING_FINDING"
    SUPPRESS_LAUNCH = "SUPPRESS_LAUNCH"


class PolicyRuleDef(BaseModel):
    code: str  # P-SEC, P-CUST, etc.
    name: str
    description: str
    effect: PolicyEffect
    condition: str
    target_tier: Optional[LaunchTier] = None
    required_role: Optional[str] = None


DEFAULT_POLICY_RULES: List[PolicyRuleDef] = [
    PolicyRuleDef(
        code="P-SEC",
        name="Security/CVE Remediation Gate",
        description="Changes touching security vulnerabilities must be reviewed by Security Lead.",
        effect=PolicyEffect.REQUIRE_DOMAIN_APPROVER,
        condition="facts.security_flags == true",
        required_role="security_lead"
    ),
    PolicyRuleDef(
        code="P-CUST",
        name="Customer NDA / PII Embargo",
        description="Changes referencing private enterprise customer names must not leak externally.",
        effect=PolicyEffect.ADD_BLOCKING_FINDING,
        condition="facts.customer_nda_detected == true"
    ),
    PolicyRuleDef(
        code="P-EMBARGO",
        name="Marketing Embargo Date Gate",
        description="Embargoed product features cannot be published before scheduled date.",
        effect=PolicyEffect.SUPPRESS_LAUNCH,
        condition="facts.is_embargoed == true and now() < facts.embargo_date"
    ),
    PolicyRuleDef(
        code="P-COMPL",
        name="Regulatory Compliance Audit",
        description="Changes affecting SOC2, HIPAA, or financial controls require Legal sign-off.",
        effect=PolicyEffect.REQUIRE_DOMAIN_APPROVER,
        condition="facts.compliance_flag == true",
        required_role="compliance_officer"
    ),
    PolicyRuleDef(
        code="P-DEPR",
        name="API Deprecation Escalation",
        description="Breaking API changes or endpoint deprecations must be elevated to at least T2.",
        effect=PolicyEffect.ESCALATE_TIER,
        condition="facts.is_breaking_change == true",
        target_tier=LaunchTier.T2
    ),
    PolicyRuleDef(
        code="P-INTERNAL",
        name="Internal Infrastructure Demotion",
        description="CI/CD, developer tooling, and refactors are restricted to T0.",
        effect=PolicyEffect.ESCALATE_TIER,
        condition="facts.is_infra_only == true",
        target_tier=LaunchTier.T0
    ),
    PolicyRuleDef(
        code="P-PRICING",
        name="Pricing & Monetization Shift",
        description="Monetization alterations require GTM VP sign-off.",
        effect=PolicyEffect.REQUIRE_DOMAIN_APPROVER,
        condition="facts.pricing_impact == true",
        required_role="gtm_vp"
    ),
    PolicyRuleDef(
        code="P-REVERT",
        name="Revert Invalidation",
        description="Reverted commits automatically suppress pending launch drafts.",
        effect=PolicyEffect.SUPPRESS_LAUNCH,
        condition="facts.is_revert == true"
    ),
    PolicyRuleDef(
        code="P-EXPERIMENTAL",
        name="Experimental Flag Restriction",
        description="Features marked experimental require explicit PMM override for external copy.",
        effect=PolicyEffect.ADD_BLOCKING_FINDING,
        condition="facts.availability == 'internal' and target_asset.is_external == true"
    ),
    PolicyRuleDef(
        code="P-MAJOR-TIER",
        name="T1 Dual Approval Requirement",
        description="Strategic launches require two independent human approvals.",
        effect=PolicyEffect.REQUIRE_DOMAIN_APPROVER,
        condition="candidate.tier == 'T1'",
        required_role="product_lead"
    ),
    PolicyRuleDef(
        code="P-EXTERNAL-TRUST",
        name="Untrusted External Content Filter",
        description="Source events from untrusted origins cannot be cited in public claims.",
        effect=PolicyEffect.ADD_BLOCKING_FINDING,
        condition="evidence.has_untrusted_source == true"
    ),
]
