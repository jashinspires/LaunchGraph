"""
A2A Protocol & Egress Contracts
Defines schemas for the Agent-to-Agent REST API and 5-step egress filter.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class A2ABrandResponse(BaseModel):
    workspace_name: str
    voice_tone: str
    tone_rules: List[str]
    allowed_claims: List[str]
    product_summary: str


class A2ALaunchSummary(BaseModel):
    id: UUID
    change_ref: str
    tier: str
    published_at: datetime
    summary: str
    assets: Dict[str, Any]


class A2ABundleResponse(BaseModel):
    items: List[A2ALaunchSummary]
    next_cursor: Optional[str] = None
    has_more: bool = False


class A2APackDetailResponse(BaseModel):
    id: UUID
    change_ref: str
    tier: str
    published_at: datetime
    summary: str
    assets: Dict[str, Any]
    citations: List[Dict[str, Any]]
    is_external_safe: bool = True


class A2ASimilarSearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)
    tier: Optional[str] = None


class A2ASimilarSearchResponse(BaseModel):
    results: List[Dict[str, Any]]
    search_latency_ms: int


class A2ARetractionItem(BaseModel):
    launch_record_id: UUID
    retracted_at: datetime
    reason: str


class A2ARetractionFeedResponse(BaseModel):
    retractions: List[A2ARetractionItem]


class A2ACheckDraftRequest(BaseModel):
    asset_type: str
    content: str


class A2ACheckDraftResponse(BaseModel):
    is_compliant: bool
    violations: List[Dict[str, Any]] = Field(default_factory=list)


class A2ADiscoveryManifest(BaseModel):
    name: str = "LaunchGraph GTM Context Graph"
    version: str = "1.0.0"
    description: str = "Enterprise GTM context graph platform and long-term memory layer"
    capabilities: List[str] = Field(
        default_factory=lambda: [
            "brand_guidance",
            "launch_records",
            "mem0_similarity_search",
            "retraction_stream",
            "copy_compliance_check"
        ]
    )
    endpoints: Dict[str, str] = Field(
        default_factory=lambda: {
            "brand": "/v1/brand",
            "bundle": "/v1/bundle",
            "pack": "/v1/pack/{id}",
            "similar": "/v1/similar",
            "retractions": "/v1/retractions",
            "check": "/v1/check"
        }
    )
