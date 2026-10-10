"""
B0.5 Mem0 Memory Layer Contracts
Grounded in Chhikara et al. (2025): Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory.
Defines candidate facts (Omega), operations (ADD, UPDATE, DELETE, NOOP), and triplets (v_s, r, v_d).
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class Mem0OperationAction(str, Enum):
    ADD = "ADD"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    NOOP = "NOOP"


class CandidateFact(BaseModel):
    """
    Extracted candidate factual statement omega_i from a finalized launch.
    """
    entity_type: str  # FEATURE, TICKET, EPIC, PERSONA, CLAIM
    name: str
    attributes: Dict[str, Any] = Field(default_factory=dict)
    information_content_score: float = Field(default=1.0, ge=0.0)
    embedding: Optional[List[float]] = None


class ExtractedMemoryPack(BaseModel):
    """
    Complete extraction set Omega = {omega_1, ..., omega_n} yielded from an approved launch pack.
    """
    workspace_id: UUID
    launch_record_id: UUID
    candidate_facts: List[CandidateFact] = Field(default_factory=list)
    extraction_model: str = "claude-opus-5"


class RelationshipTriplet(BaseModel):
    """
    Directed labeled edge (v_s, r, v_d) in the Mem0 graph representation G = (V, E, L).
    """
    source_name: str
    target_name: str
    relation_type: str  # implements, deprecates, targets_persona, delivers_capability
    weight: float = 1.0
    attributes: Dict[str, Any] = Field(default_factory=dict)


class Mem0OperationDecision(BaseModel):
    """
    Classifier decision output for Mem0 Algorithm 1.
    """
    action: Mem0OperationAction
    target_entity_id: Optional[UUID] = None
    target_name: Optional[str] = None
    reasoning: str
    updated_attributes: Optional[Dict[str, Any]] = None
