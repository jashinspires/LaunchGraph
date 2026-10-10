"""
Complete model registry for LaunchGraph V1.
Registers all 34 database entities across Domain 1-4 and Mem0 memory graph.
"""

from launchgraph_core.db.base import Base

# Domain 1: Identity & Brand
from launchgraph_core.db.models.workspace import Workspace, Brand, AppUser, PersonIdentity
from launchgraph_core.db.models.brand_profile import BrandProfile, AudienceSegment

# Domain 2: Ingestion & Graph
from launchgraph_core.db.models.connection import Connection, WebhookInbox, SourceEvent
from launchgraph_core.db.models.change_graph import ChangeEvent, ChangeMembership, LinkSuggestion, ChangeRelation

# Domain 3: Candidates, Packs & Governance
from launchgraph_core.db.models.candidates import LaunchCandidate, DecisionRun
from launchgraph_core.db.models.gtm_pack import GtmPack, GtmAsset, AssetRevision, LintFinding, ApprovalEvent
from launchgraph_core.db.models.launch_record import LaunchRecord

# Domain 4: Platform & Security
from launchgraph_core.db.models.platform import (
    ApiKey,
    LlmCallLog,
    Job,
    AuditLog,
    A2ARequestLog,
    EgressFilter,
    PolicyRule,
    TriageQueue,
    RateLimit
)

# Mem0 Long-Term Memory
from launchgraph_core.db.models.mem0_graph import (
    Mem0EntityNode,
    Mem0RelationEdge,
    Mem0MemoryOperation,
    BrandProfileEvolution
)

__all__ = [
    "Base",
    # Domain 1
    "Workspace",
    "Brand",
    "AppUser",
    "PersonIdentity",
    "BrandProfile",
    "AudienceSegment",
    # Domain 2
    "Connection",
    "WebhookInbox",
    "SourceEvent",
    "ChangeEvent",
    "ChangeMembership",
    "LinkSuggestion",
    "ChangeRelation",
    # Domain 3
    "LaunchCandidate",
    "DecisionRun",
    "GtmPack",
    "GtmAsset",
    "AssetRevision",
    "LintFinding",
    "ApprovalEvent",
    "LaunchRecord",
    # Domain 4
    "ApiKey",
    "LlmCallLog",
    "Job",
    "AuditLog",
    "A2ARequestLog",
    "EgressFilter",
    "PolicyRule",
    "TriageQueue",
    "RateLimit",
    # Mem0
    "Mem0EntityNode",
    "Mem0RelationEdge",
    "Mem0MemoryOperation",
    "BrandProfileEvolution",
]
