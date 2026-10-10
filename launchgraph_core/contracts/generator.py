"""
B0.6-B0.8 Asset & Lint Contracts
Defines schemas for 9 GTM asset types and the 14 deterministic safety linters.
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


# ============================================================================
# 14 Deterministic Linters
# ============================================================================

class LintSeverity(str, Enum):
    BLOCKER = "BLOCKER"
    WARNING = "WARNING"


class LintRuleCode(str, Enum):
    LINT_CODENAME = "LINT-CODENAME"
    LINT_UNCITED = "LINT-UNCITED"
    LINT_TOKEN = "LINT-TOKEN"
    LINT_COMPETITOR = "LINT-COMPETITOR"
    LINT_SUPERLATIVE = "LINT-SUPERLATIVE"
    LINT_PRICING = "LINT-PRICING"
    LINT_TIMING = "LINT-TIMING"
    LINT_EMBARGO = "LINT-EMBARGO"
    LINT_LENGTH = "LINT-LENGTH"
    LINT_PROFANITY = "LINT-PROFANITY"
    LINT_SECURITY = "LINT-SECURITY"
    LINT_FORMAT = "LINT-FORMAT"
    LINT_PERSONA = "LINT-PERSONA"
    LINT_DISALLOWED_CLAIM = "LINT-DISALLOWED-CLAIM"


class LintFindingReport(BaseModel):
    rule_code: LintRuleCode
    severity: LintSeverity
    message: str
    snippet: Optional[str] = None
    character_offset: Optional[int] = None
    is_overridden: bool = False
    override_reason: Optional[str] = None


# ============================================================================
# 9 Asset Types & Character Boundaries
# ============================================================================

class AssetType(str, Enum):
    CHANGELOG = "CHANGELOG"
    EMAIL = "EMAIL"
    LINKEDIN = "LINKEDIN"
    SALES_SNIPPET = "SALES_SNIPPET"
    SUPPORT_FAQ = "SUPPORT_FAQ"
    INTERNAL_BRIEF = "INTERNAL_BRIEF"
    PRODUCT_BLOG = "PRODUCT_BLOG"
    RELEASE_NOTE = "RELEASE_NOTE"
    X_THREAD = "X_THREAD"


class AssetBoundary(BaseModel):
    min_length: int
    max_length: int
    requires_subject: bool = False
    is_external: bool = True


ASSET_BOUNDARIES: Dict[AssetType, AssetBoundary] = {
    AssetType.CHANGELOG: AssetBoundary(min_length=50, max_length=1200, is_external=True),
    AssetType.EMAIL: AssetBoundary(min_length=200, max_length=3000, requires_subject=True, is_external=True),
    AssetType.LINKEDIN: AssetBoundary(min_length=150, max_length=2000, is_external=True),
    AssetType.SALES_SNIPPET: AssetBoundary(min_length=100, max_length=1500, is_external=False),
    AssetType.SUPPORT_FAQ: AssetBoundary(min_length=200, max_length=4000, is_external=False),
    AssetType.INTERNAL_BRIEF: AssetBoundary(min_length=200, max_length=5000, is_external=False),
    AssetType.PRODUCT_BLOG: AssetBoundary(min_length=500, max_length=8000, is_external=True),
    AssetType.RELEASE_NOTE: AssetBoundary(min_length=100, max_length=2000, is_external=True),
    AssetType.X_THREAD: AssetBoundary(min_length=100, max_length=1500, is_external=True),
}


class AssetDraftOutput(BaseModel):
    asset_type: AssetType
    content: str
    structured_data: Dict[str, Any] = Field(default_factory=dict)
    citations: List[str] = Field(default_factory=list)
    findings: List[LintFindingReport] = Field(default_factory=list)
    is_blocked: bool = False

    def validate_bounds(self) -> None:
        boundary = ASSET_BOUNDARIES.get(self.asset_type)
        if not boundary:
            return
        length = len(self.content)
        if length > boundary.max_length:
            self.findings.append(
                LintFindingReport(
                    rule_code=LintRuleCode.LINT_LENGTH,
                    severity=LintSeverity.BLOCKER,
                    message=f"Content length {length} exceeds maximum {boundary.max_length} characters.",
                    snippet=self.content[-50:]
                )
            )
            self.is_blocked = True
