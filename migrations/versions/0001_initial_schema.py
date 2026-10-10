"""Initial schema baseline with 34 tables

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-10-10 18:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Optional: enable pgvector extension in PostgreSQL
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    op.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")

    # Domain 1: Workspaces & Brands
    op.create_table(
        'workspaces',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('slug', sa.String(64), unique=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('tier', sa.String(32), server_default='pilot', nullable=False),
        sa.Column('settings', postgresql.JSONB(), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'brands',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('is_default', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'app_users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('role', sa.String(32), server_default='reviewer', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'person_identities',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('canonical_name', sa.String(255), nullable=False),
        sa.Column('canonical_email', sa.String(255), nullable=True),
        sa.Column('github_username', sa.String(128), nullable=True),
        sa.Column('jira_account_id', sa.String(128), nullable=True),
        sa.Column('slack_user_id', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'brand_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('brand_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('brands.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('product_summary', sa.Text(), nullable=False),
        sa.Column('voice_tone', sa.String(128), nullable=False),
        sa.Column('tone_rules', postgresql.JSONB(), server_default='[]', nullable=False),
        sa.Column('allowed_claims', postgresql.JSONB(), server_default='[]', nullable=False),
        sa.Column('disallowed_claims', postgresql.JSONB(), server_default='[]', nullable=False),
        sa.Column('codenames', postgresql.JSONB(), server_default='[]', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'audience_segments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('pain_points', postgresql.JSONB(), server_default='[]', nullable=False),
        sa.Column('desired_outcomes', postgresql.JSONB(), server_default='[]', nullable=False),
        sa.Column('objections', postgresql.JSONB(), server_default='[]', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    # Domain 2: Ingestion & Context Graph
    op.create_table(
        'connections',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_type', sa.String(32), nullable=False),
        sa.Column('status', sa.String(32), server_default='ACTIVE', nullable=False),
        sa.Column('credentials', sa.LargeBinary(), nullable=False),
        sa.Column('config', postgresql.JSONB(), server_default='{}', nullable=False),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'webhook_inbox',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('connection_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('connections.id', ondelete='CASCADE'), nullable=False),
        sa.Column('idempotency_key', sa.String(255), nullable=False),
        sa.Column('event_type', sa.String(128), nullable=False),
        sa.Column('payload', postgresql.JSONB(), nullable=False),
        sa.Column('status', sa.String(32), server_default='pending', nullable=False),
        sa.Column('retry_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('connection_id', 'idempotency_key', name='uq_webhook_inbox_dedupe'),
    )

    op.create_table(
        'source_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('connection_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('connections.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_type', sa.String(32), nullable=False),
        sa.Column('external_id', sa.String(255), nullable=False),
        sa.Column('trust_label', sa.String(32), server_default='INTERNAL', nullable=False),
        sa.Column('raw_payload', postgresql.JSONB(), nullable=False),
        sa.Column('is_processed', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'change_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('anchor_ref', sa.String(255), nullable=False),
        sa.Column('title', sa.String(512), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('state', sa.String(32), server_default='discovered', nullable=False),
        sa.Column('availability', sa.String(32), server_default='unknown', nullable=False),
        sa.Column('last_activity_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_processed', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'change_membership',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('change_event_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('change_events.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_event_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('source_events.id', ondelete='SET NULL'), nullable=True),
        sa.Column('ref_type', sa.String(32), nullable=False),
        sa.Column('ref_key', sa.String(255), nullable=False),
        sa.Column('link_type', sa.String(32), nullable=False),
        sa.Column('role', sa.String(32), nullable=False),
        sa.Column('attached_by', sa.String(64), server_default='system', nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('unlinked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('unlinked_by', sa.String(64), nullable=True),
        sa.Column('unlink_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'link_suggestions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('change_event_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('change_events.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_event_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('source_events.id', ondelete='CASCADE'), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('feature_breakdown', postgresql.JSONB(), server_default='{}', nullable=False),
        sa.Column('status', sa.String(32), server_default='pending', nullable=False),
        sa.Column('reviewed_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('app_users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'change_relations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_change_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('change_events.id', ondelete='CASCADE'), nullable=False),
        sa.Column('target_change_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('change_events.id', ondelete='CASCADE'), nullable=False),
        sa.Column('relation_type', sa.String(32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    # Domain 3: Candidates, Packs & Governance
    op.create_table(
        'launch_candidates',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('change_event_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('change_events.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('tier', sa.String(16), nullable=False),
        sa.Column('confirmed_tier', sa.String(16), nullable=True),
        sa.Column('confidence', sa.String(16), server_default='medium', nullable=False),
        sa.Column('score', sa.Integer(), server_default='50', nullable=False),
        sa.Column('reasons', postgresql.JSONB(), server_default='[]', nullable=False),
        sa.Column('is_external_safe', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('safety_warnings', postgresql.JSONB(), server_default='[]', nullable=False),
        sa.Column('status', sa.String(32), server_default='PENDING_REVIEW', nullable=False),
        sa.Column('is_processed', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'decision_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('launch_candidate_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('launch_candidates.id', ondelete='CASCADE'), nullable=False),
        sa.Column('model_name', sa.String(64), nullable=False),
        sa.Column('k_samples', sa.Integer(), server_default='3', nullable=False),
        sa.Column('evidence_pack_tokens', sa.Integer(), nullable=False),
        sa.Column('evidence_pack_hash', sa.String(64), nullable=False),
        sa.Column('raw_answers', postgresql.JSONB(), server_default='{}', nullable=False),
        sa.Column('policy_hits', postgresql.JSONB(), server_default='[]', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'gtm_packs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('launch_candidate_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('launch_candidates.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('status', sa.String(32), server_default='DRAFT', nullable=False),
        sa.Column('version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finalized_at', sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        'gtm_assets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('gtm_pack_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('gtm_packs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('asset_type', sa.String(32), nullable=False),
        sa.Column('audience_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('audience_segments.id', ondelete='SET NULL'), nullable=True),
        sa.Column('content_draft', sa.Text(), nullable=False),
        sa.Column('content_final', sa.Text(), nullable=True),
        sa.Column('structured_data', postgresql.JSONB(), server_default='{}', nullable=False),
        sa.Column('citations', postgresql.JSONB(), server_default='[]', nullable=False),
        sa.Column('status', sa.String(32), server_default='DRAFT', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'asset_revisions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('gtm_asset_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('gtm_assets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('revision_number', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('author_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('app_users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'lint_findings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('gtm_asset_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('gtm_assets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('rule_code', sa.String(64), nullable=False),
        sa.Column('severity', sa.String(16), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('snippet', sa.String(255), nullable=True),
        sa.Column('is_overridden', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('override_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'approval_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('gtm_asset_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('gtm_assets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('app_users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('action', sa.String(32), nullable=False),
        sa.Column('reason_chips', postgresql.JSONB(), server_default='[]', nullable=False),
        sa.Column('edit_diff', postgresql.JSONB(), nullable=True),
        sa.Column('comments', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    # Use raw SQL or JSON fallback for vector type in migration definition
    op.create_table(
        'launch_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('gtm_pack_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('gtm_packs.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('change_event_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('change_events.id', ondelete='CASCADE'), nullable=False),
        sa.Column('final_tier', sa.String(16), nullable=False),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('assets_snapshot', postgresql.JSONB(), server_default='{}', nullable=False),
        sa.Column('embedding', postgresql.JSONB(), nullable=True),
        sa.Column('mem0_entities', postgresql.JSONB(), server_default='[]', nullable=False),
        sa.Column('mem0_relations', postgresql.JSONB(), server_default='[]', nullable=False),
        sa.Column('is_retracted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('retracted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('retraction_reason', sa.Text(), nullable=True),
    )

    # Domain 4: Platform & Security
    op.create_table(
        'api_keys',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('key_prefix', sa.String(16), nullable=False),
        sa.Column('key_hash', sa.String(64), unique=True, nullable=False),
        sa.Column('scopes', postgresql.JSONB(), server_default='[]', nullable=False),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'llm_call_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('service_name', sa.String(32), nullable=False),
        sa.Column('model', sa.String(64), nullable=False),
        sa.Column('prompt_tokens', sa.Integer(), nullable=False),
        sa.Column('completion_tokens', sa.Integer(), nullable=False),
        sa.Column('cost_usd', sa.Numeric(10, 6), server_default='0', nullable=False),
        sa.Column('latency_ms', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('job_type', sa.String(64), nullable=False),
        sa.Column('deduplication_key', sa.String(255), nullable=False),
        sa.Column('payload', postgresql.JSONB(), server_default='{}', nullable=False),
        sa.Column('status', sa.String(32), server_default='pending', nullable=False),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('locked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('locked_by', sa.String(64), nullable=True),
        sa.Column('retry_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('max_retries', sa.Integer(), server_default='3', nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('workspace_id', 'deduplication_key', name='uq_jobs_dedupe'),
    )

    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('app_users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('action', sa.String(64), nullable=False),
        sa.Column('entity_type', sa.String(64), nullable=False),
        sa.Column('entity_id', sa.String(64), nullable=False),
        sa.Column('metadata_json', postgresql.JSONB(), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'a2a_request_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('api_key_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('api_keys.id', ondelete='SET NULL'), nullable=True),
        sa.Column('endpoint', sa.String(255), nullable=False),
        sa.Column('status_code', sa.Integer(), nullable=False),
        sa.Column('latency_ms', sa.Integer(), nullable=False),
        sa.Column('ip_address', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'egress_filters',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('filter_name', sa.String(64), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('config', postgresql.JSONB(), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'policy_rules',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('rule_code', sa.String(64), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('effect', sa.String(32), server_default='ESCALATE_TIER', nullable=False),
        sa.Column('condition_expr', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'triage_queues',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('queue_type', sa.String(32), nullable=False),
        sa.Column('item_ref', sa.String(255), nullable=False),
        sa.Column('priority', sa.Integer(), server_default='1', nullable=False),
        sa.Column('status', sa.String(32), server_default='open', nullable=False),
        sa.Column('assigned_to', postgresql.UUID(as_uuid=True), sa.ForeignKey('app_users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'rate_limits',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('key_prefix', sa.String(64), nullable=False),
        sa.Column('window_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('request_count', sa.Integer(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    # Mem0 Long-Term Memory
    op.create_table(
        'mem0_entity_nodes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('entity_type', sa.String(64), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('attributes', postgresql.JSONB(), server_default='{}', nullable=False),
        sa.Column('embedding', postgresql.JSONB(), nullable=True),
        sa.Column('information_score', sa.Float(), server_default='1.0', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('invalidated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('invalidation_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'mem0_relation_edges',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_node_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('mem0_entity_nodes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('target_node_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('mem0_entity_nodes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('relation_type', sa.String(64), nullable=False),
        sa.Column('weight', sa.Float(), server_default='1.0', nullable=False),
        sa.Column('attributes', postgresql.JSONB(), server_default='{}', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'mem0_memory_operations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('launch_record_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('launch_records.id', ondelete='CASCADE'), nullable=False),
        sa.Column('operation_type', sa.String(16), nullable=False),
        sa.Column('candidate_fact', postgresql.JSONB(), nullable=False),
        sa.Column('target_node_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('mem0_entity_nodes.id', ondelete='SET NULL'), nullable=True),
        sa.Column('reasoning', sa.Text(), nullable=True),
        sa.Column('executed_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'brand_profile_evolutions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('suggested_rules', postgresql.JSONB(), server_default='[]', nullable=False),
        sa.Column('source_approval_events', postgresql.JSONB(), server_default='[]', nullable=False),
        sa.Column('status', sa.String(32), server_default='pending', nullable=False),
        sa.Column('reviewed_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('app_users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_table('brand_profile_evolutions')
    op.drop_table('mem0_memory_operations')
    op.drop_table('mem0_relation_edges')
    op.drop_table('mem0_entity_nodes')
    op.drop_table('rate_limits')
    op.drop_table('triage_queues')
    op.drop_table('policy_rules')
    op.drop_table('egress_filters')
    op.drop_table('a2a_request_logs')
    op.drop_table('audit_logs')
    op.drop_table('jobs')
    op.drop_table('llm_call_logs')
    op.drop_table('api_keys')
    op.drop_table('launch_records')
    op.drop_table('approval_events')
    op.drop_table('lint_findings')
    op.drop_table('asset_revisions')
    op.drop_table('gtm_assets')
    op.drop_table('gtm_packs')
    op.drop_table('decision_runs')
    op.drop_table('launch_candidates')
    op.drop_table('change_relations')
    op.drop_table('link_suggestions')
    op.drop_table('change_membership')
    op.drop_table('change_events')
    op.drop_table('source_events')
    op.drop_table('webhook_inbox')
    op.drop_table('connections')
    op.drop_table('audience_segments')
    op.drop_table('brand_profiles')
    op.drop_table('person_identities')
    op.drop_table('app_users')
    op.drop_table('brands')
    op.drop_table('workspaces')
