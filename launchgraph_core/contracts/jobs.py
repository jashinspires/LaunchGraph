"""
B0.2 Job Contracts
Defines schemas, deduplication keys, and retry policies for all LaunchGraph background jobs.
"""

from enum import Enum
from typing import Dict, Any, Optional
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class JobType(str, Enum):
    NORMALIZE = "normalize"
    DECIDE = "decide"
    GENERATE_ASSET = "generate_asset"
    LINT = "lint"
    VERIFY = "verify"
    FINALIZE = "finalize"
    MEM0_UPDATE = "mem0_update"
    INDEX_RECORD = "index_record"
    NOTIFY = "notify"
    PURGE = "purge"
    RECONCILE = "reconcile"


class JobRetryPolicy(BaseModel):
    max_retries: int = Field(default=3, ge=0)
    initial_backoff_seconds: float = Field(default=1.0, ge=0.1)
    backoff_multiplier: float = Field(default=2.0, ge=1.0)
    timeout_seconds: int = Field(default=300, ge=1)


JOB_RETRY_POLICIES: Dict[JobType, JobRetryPolicy] = {
    JobType.NORMALIZE: JobRetryPolicy(max_retries=3, initial_backoff_seconds=2.0, timeout_seconds=60),
    JobType.DECIDE: JobRetryPolicy(max_retries=3, initial_backoff_seconds=5.0, timeout_seconds=120),
    JobType.GENERATE_ASSET: JobRetryPolicy(max_retries=2, initial_backoff_seconds=5.0, timeout_seconds=180),
    JobType.LINT: JobRetryPolicy(max_retries=1, initial_backoff_seconds=1.0, timeout_seconds=30),
    JobType.VERIFY: JobRetryPolicy(max_retries=2, initial_backoff_seconds=3.0, timeout_seconds=90),
    JobType.FINALIZE: JobRetryPolicy(max_retries=5, initial_backoff_seconds=1.0, timeout_seconds=60),
    JobType.MEM0_UPDATE: JobRetryPolicy(max_retries=3, initial_backoff_seconds=2.0, timeout_seconds=120),
    JobType.INDEX_RECORD: JobRetryPolicy(max_retries=3, initial_backoff_seconds=2.0, timeout_seconds=60),
    JobType.NOTIFY: JobRetryPolicy(max_retries=3, initial_backoff_seconds=1.0, timeout_seconds=30),
    JobType.PURGE: JobRetryPolicy(max_retries=2, initial_backoff_seconds=10.0, timeout_seconds=300),
    JobType.RECONCILE: JobRetryPolicy(max_retries=2, initial_backoff_seconds=10.0, timeout_seconds=300),
}


class JobEnvelope(BaseModel):
    """
    Standard job payload wrapper enqueued into the jobs coordinator.
    """
    workspace_id: UUID
    job_type: JobType
    deduplication_key: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    scheduled_at: Optional[datetime] = None
    retry_policy: Optional[JobRetryPolicy] = None

    @classmethod
    def create_dedupe_key(cls, job_type: JobType, entity_id: str, context: Optional[str] = None) -> str:
        """Constructs a deterministic deduplication key."""
        ctx_suffix = f":{context}" if context else ""
        return f"{job_type.value}:{entity_id}{ctx_suffix}"
