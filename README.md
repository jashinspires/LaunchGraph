# LaunchGraph

[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![Architecture](https://img.shields.io/badge/architecture-Microservices%20%2B%20Context%20Graph-orange.svg)](#architecture)
[![Database](https://img.shields.io/badge/storage-PostgreSQL%2016%20%2B%20pgvector-blue.svg)](https://www.postgresql.org/)
[![Tests](https://img.shields.io/badge/tests-61%20passed%20%7C%20100%25-brightgreen.svg)](#testing)
[![Milestone](https://img.shields.io/badge/milestone-55%25%20Completed%20(Wave%203A%20%2F%20Stage%201--3%20Live)-brightgreen.svg)](#development-milestones)

**LaunchGraph** is an enterprise Go-To-Market (GTM) Context Graph platform. It automatically ingests raw engineering activity from GitHub, Jira, and Slack, synthesizes it into an anchored, typed context graph of product changes, deterministically classifies launch tiers ($T0$–$T3$), generates grounded GTM asset packs governed by 14 deterministic safety linters, and persists approved releases into a scalable long-term memory layer grounded in the **Mem0** graph architecture ($G = (V, E, L)$) for downstream consumption via a read-only Agent-to-Agent (A2A) protocol.

---

## Architecture Overview

LaunchGraph processes developer telemetry through a sequential multi-stage processing pipeline supported by decoupled autonomous worker loops:

![LaunchGraph System Context](docs/images/system_context.png)

```
+---------------------------------------------------------------------------------------------------+
|                                     LaunchGraph V1 Architecture                                   |
+---------------------------------------------------------------------------------------------------+
|                                                                                                   |
|  [ GitHub Webhooks ]     [ Jira Cloud Webhooks ]     [ Slack Events API ]                         |
|           |                        |                         |                                    |
|           +------------------------+-------------------------+                                    |
|                                    |                                                              |
|                                    v                                                              |
|                     +-----------------------------+                                               |
|                     | Stage 1: Ingestion (:8001)  |  HMAC Verification, Deduplication             |
|                     |      (Webhook Inbox)        |  Secret & Credential Scrubber                 |
|                     +-----------------------------+                                               |
|                                    |                                                              |
|                                    v                                                              |
|                     +-----------------------------+                                               |
|                     | Stage 2: Normalization (:8002) Ref Extraction, Link Typing (L1-L8)          |
|                     |     (Context Graph Ledger)  |  Anchor Resolution & Availability Tracker     |
|                     +-----------------------------+                                               |
|                                    |                                                              |
|                                    v                                                              |
|                     +-----------------------------+                                               |
|                     | Stage 3: Decisioning (:8003)|  Deterministic Facts, 12k Token Bounder       |
|                     |      (Tier Proposals)       |  Consensus Sampling (k=3), Policy Engine      |
|                     +-----------------------------+                                               |
|                                    |                                                              |
|                                    v                                                              |
|                     +-----------------------------+                                               |
|                     | Stage 4: Generation (:8004) |  6-Block Context + Mem0 Few-Shot Injection    |
|                     |      (GTM Asset Packs)      |  14 Deterministic Linters & Claim Verifier    |
|                     +-----------------------------+                                               |
|                                    |                                                              |
|                                    v                                                              |
|                     +-----------------------------+                                               |
|                     | Stage 5: Review & Memory    |  Human Multi-Party Approvals & Audit Trail    |
|                     |      (Mem0 Long-Term)       |  Algorithm 1 Graph Memory (ADD/UPDATE/DELETE) |
|                     +-----------------------------+                                               |
|                                    |                                                              |
|                                    v                                                              |
|                     +-----------------------------+                                               |
|                     | Stage 6: A2A Egress (:8006) |  5-Stage Egress Gate (Zero-Leak Security)     |
|                     |   (Agent-to-Agent REST API) |  Dual Graph & Semantic Triplet Search (<200ms)|
|                     +-----------------------------+                                               |
|                                                                                                   |
+---------------------------------------------------------------------------------------------------+
```

### Microservice Topology

| Service Name | Port | Status | Primary Responsibility | Coordination Pattern |
|:---|:---:|:---:|:---|:---|
| **`launchgraph_core`** | — | **Live** | Shared SQLAlchemy models (34 tables), contracts, database pooling, crypto, and Mem0 primitives. | Python package imported across services. |
| **`ingester`** | `8001` | **Live** | HMAC verification, deduplication (`webhook_inbox`), secret scrubbing, and raw event normalization. | FastAPI server + background reconciliation jobs. |
| **`normalizer`** | `8002` | **Live** | Reference extraction, link typing ($L1$–$L8$), anchor resolution, and append-only ledger processing. | Autonomous `process -> sleep` worker loop + Triage API. |
| **`decisioner`** | `8003` | **Live** | Deterministic fact extraction, sensitivity detector scans, 12k evidence packaging, $k=3$ consensus, and policy engine. | Autonomous worker loop + Claude Opus Judgment consensus client. |
| **`generator`** | `8004` | Planned | 6-block context assembly, Mem0 few-shot memory retrieval, 14 deterministic linters, and claim verification. | Worker loop + Writer LLM client pool. |
| **`dashboard`** | `8005` | Planned | Internal review workspace, domain approver sign-offs, edit diffs, and reason chip capture. | FastAPI REST endpoints + PostgreSQL pool. |
| **`a2a_interface`** | `8006` | Planned | External Agent-to-Agent protocol; scoped API keys, 5-stage egress filter, discovery manifest. | FastAPI high-throughput read-only service. |

---

## Pipeline Stages & Capabilities

### Stage 1: Ingestion Pipeline & Hygiene (Port 8001)

![Stage 1 Ingestion Pipeline](docs/images/pipeline_stage1_ingestion.png)

* **HMAC Cryptographic Verification:** Enforces tamper-proof validation on all inbound webhooks (`X-Hub-Signature-256`, `X-Slack-Signature` with 5-minute replay attack prevention).
* **Deterministic Idempotency Keys:** Unique delivery deduplication keys per provider (`github:{delivery_id}:{event}`, `jira:{issue_id}:{ts}`, `slack:{event_id}`).
* **Zero-Leak Secret Scrubber:** High-performance compiled regex sanitizer redacting AWS credentials, API tokens, JWTs, and private keys to `[REDACTED_SECRET]` before database insertion.
* **Events-Only Posture:** Adheres to enterprise security standards with zero historical Slack channel crawling.

### Stage 2: Context Graph & Deterministic Normalization (Port 8002)

![Stage 2 Normalization & Graph Ledger](docs/images/pipeline_stage2_normalization.png)

* **Reference Extractor:** Compiled extraction for Jira keys (`[A-Z][A-Z0-9]+-[0-9]+`), GitHub PR numbers (`#\d+`), commit SHAs, and URLs.
* **Deterministic Link Typing ($L1$–$L8$):**
  * $L1$ (`implements`): PR title/branch directly implements a ticket.
  * $L2$ (`mentions`): Informal reference in discussions.
  * $L3$ (`fixes`): Explicit defect closure keywords.
  * $L4$ (`reverts`): Git revert commits or rollback markers.
  * $L5$ (`contains`): Release versions and Epics.
  * $L6$ (`relates_to`), $L7$ (`duplicate_of`), $L8$ (`blocks`).
* **Anchor Resolution:** Authoritative hierarchy: Jira Epic $\to$ Jira Issue $\to$ GitHub PR $\to$ Promoted Slack Thread.
* **Append-Only Ledger (`change_membership`):** All attachments are auditable and immutable. Soft-unlinking requires mandatory rationale; destructive deletes are prohibited.
* **Deterministic Suggestion Formula:**
  $$\text{Score} = 0.35 \times S_{\text{person}} + 0.20 \times S_{\text{time}} + 0.25 \times S_{\text{path}} + 0.20 \times S_{\text{text}}$$

### Stage 3: Decisioning Engine & Consensus Sampling (Port 8003)

![Stage 3 Decisioning Engine](docs/images/pipeline_stage3_decisioning.png)

The Decisioning Engine transforms raw context graph changes into authoritative launch tier proposals ($T0$–$T3$) through a strict multi-tier pipeline:

1. **Deterministic Fact Extraction (`FactExtractor`):** Evaluates quantitative metrics without LLM non-determinism:
   - Lines of code modified, commit counts, author metadata.
   - Customer-facing documentation touched (`docs/`, `*.md`, `guides/`).
   - Breaking change indicators (`BREAKING CHANGE`, semantic major version bumps).
   - Infrastructure-only flags (`.github/`, `ci/`, `terraform/`, `Dockerfile`).
2. **Sensitivity Detector (`SensitivityDetector`):** Scans payloads against strict compliance patterns:
   - Security vulnerabilities and CVE references (`CVE-\d{4}-\d{4,7}`).
   - Customer Confidential / NDA / PII flags.
   - Regulatory standards (SOC2, HIPAA, GDPR, PCI-DSS).
   - Pricing, tier changes, and subscription shift keywords.
   - Embargo dates (`EMBARGO: YYYY-MM-DD`).
3. **Evidence Pack Assembly (`EvidenceAssembler`):** Compiles evidence into a structured markdown pack strictly bounded to a **12,000-token ceiling** with SHA-256 context hash verification to prevent prompt injection and context overflow.
4. **Claude Opus Judgment Client (`JudgmentClient`):** Evaluates structured, frozen questions $Q1$–$Q9$:
   - $Q1$: User-facing change?
   - $Q2$: Novel capability vs routine fix?
   - $Q3$: Target persona (Developer, Ops, Admin, End-User)?
   - $Q4$: Action required by customers?
   - $Q5$: Risk level (low, med, high)?
   - $Q6$: Rollback / revert flag?
   - $Q7$: Deprecation included?
   - $Q8$: Security / vulnerability fix?
   - $Q9$: Pricing / packaging shift?
5. **Consensus Sampling Engine (`ConsensusEngine`):** Executes $k=3$ runs at temperatures $t \in [0.0, 0.3, 0.7]$:
   - Computes raw question agreement score ($\ge 85\%$ threshold).
   - Assigns confidence bands: `high` ($\ge 90\%$), `medium` ($75\%\text{--}89\%$), `low` ($< 75\%$).
6. **Policy Engine (`PolicyEngine`):** Enforces 11 restrict-only deterministic safety rules:
   - $P\text{-SEC}$: Security CVEs downgraded to internal / unannounced.
   - $P\text{-CUST}$: Customer-specific work stripped from general release.
   - $P\text{-EMBARGO}$: Explicit hold applied until specified date.
   - $P\text{-COMPL}$: Regulatory audits flagged for mandatory legal review.
   - $P\text{-DEPR}$: Deprecations require migration guidance flag.
   - $P\text{-INTERNAL}$: Infra/CI/test-only changes auto-classified as $T0$.
   - $P\text{-PRICING}$: Pricing adjustments flagged for executive review.
   - $P\text{-REVERT}$: Rollback events require hotfix classification.
   - $P\text{-EXPERIMENTAL}$: Alpha/Beta flags routed to limited audiences.
   - $P\text{-MAJOR-TIER}$: Breaking public API changes force Tier 1 ($T1$) review.
   - $P\text{-EXTERNAL-TRUST}$: Prevents external publication if consensus confidence is low.
7. **Tier Evaluator (`TierEvaluator`):** Proposes launch tier ($T0$: No GTM, $T1$: Major Launch, $T2$: Minor Feature, $T3$: Patch/Docs), determines `is_external_safe`, and records human-readable reason chips.

---

## Safety Architecture & Long-Term Memory

### Defense-in-Depth Safety Architecture

![Defense-in-Depth Safety Architecture](docs/images/safety_architecture.png)

LaunchGraph deploys multi-layer verification across 6 safety boundaries ($L0$–$L5$):
* **14 Deterministic Linters:** `LINT-CODENAME`, `LINT-UNCITED`, `LINT-TOKEN`, `LINT-COMPETITOR`, `LINT-SUPERLATIVE`, `LINT-PRICING`, `LINT-TIMING`, `LINT-EMBARGO`, `LINT-LENGTH`, `LINT-PROFANITY`, `LINT-SECURITY`, `LINT-FORMAT`, `LINT-PERSONA`, `LINT-DISALLOWED-CLAIM`.
* **5-Stage Egress Hard Gate:** Verifies workspace isolation, `is_external_safe` marker, embargo scheduling, secret scrubbing, and synchronous audit logging before any data leaves via the A2A API.

### Mem0 Long-Term Memory Engine

![Mem0 Long-Term Memory Engine](docs/images/mem0_memory_engine.png)

Grounded in *Chhikara et al. (2025)*, LaunchGraph organizes memory into a labeled directed graph $G = (V, E, L)$:
* **Nodes ($V$):** Capabilities, features, personas, and ticket entities with dense embeddings ($e_v$).
* **Edges ($E$):** Typed semantic triplets $(v_s, r, v_d)$ labeled $r$ (e.g. `delivers_capability`, `deprecates`, `targets_persona`).
* **Algorithm 1 Operations:** Dynamic memory evolution via `ADD`, `UPDATE`, `DELETE` (soft-invalidation), and `NOOP` to prevent context bloating and memory amnesia.
* **Performance:** Dual retrieval delivers $\ge 90\%$ token savings and $91\%$ lower p95 latency ($< 200\text{ ms}$) compared to naive full-context injection.

### Candidate Lifecycle State Machine

![Candidate Lifecycle State Machine](docs/images/lifecycle_state_machine.png)

Every release candidate moves deterministically through explicit state transitions:
`DETECTED` $\to$ `EVIDENCE_PACKED` $\to$ `DECIDED` $\to$ `ASSETS_GENERATED` $\to$ `APPROVED` $\to$ `MEM0_INDEXED` $\to$ `EGRESS_READY`.

---

## Directory Layout

```
LaunchGraph/
|-- alembic.ini                    # Alembic migration configuration
|-- pyproject.toml                 # Package specifications & build config
|-- requirements.txt               # Dependencies
|-- launchgraph_core/              # Shared Core Library (Batch 0)
|   |-- config.py                  # Pydantic BaseSettings environment configuration
|   |-- db/                        # Database engine, sessionmaker, and models
|   |   |-- base.py                # DeclarativeBase, UUIDMixin, TimestampMixin
|   |   |-- session.py             # Async connection pool & session scope
|   |   `-- models/                # 34 normalized tables across 4 domains
|   |       |-- workspace.py       # Domain 1: Workspaces, Brands, Users, Identities
|   |       |-- brand_profile.py   # Domain 1: BrandProfiles, AudienceSegments
|   |       |-- connection.py      # Domain 2: Connections, WebhookInbox, SourceEvents
|   |       |-- change_graph.py    # Domain 2: ChangeEvents, ChangeMembership, Suggestions
|   |       |-- candidates.py      # Domain 3: LaunchCandidates, DecisionRuns
|   |       |-- gtm_pack.py        # Domain 3: GtmPacks, GtmAssets, LintFindings, Approvals
|   |       |-- launch_record.py   # Domain 3: LaunchRecords (Mem0 snapshot & vector)
|   |       |-- platform.py        # Domain 4: ApiKeys, Jobs, AuditLogs, EgressFilters
|   |       `-- mem0_graph.py      # Mem0: EntityNodes, RelationEdges, MemoryOps
|   |-- contracts/                 # Frozen Pydantic v2 schemas
|   |   |-- jobs.py                # Job envelope, dedupe keys, retry policies
|   |   |-- ingress.py             # GitHub, Jira, and Slack payload schemas
|   |   |-- decisioner.py          # Evidence pack (12k ceiling), Q1-Q9, Policy DSL
|   |   |-- generator.py           # 9 asset schemas, 14 deterministic lint findings
|   |   |-- mem0.py                # Candidate facts, operations, relation triplets
|   |   `-- a2a.py                 # A2A bundle, pack, brand, check, and discovery
|   |-- security/                  # Security primitives
|   |   |-- scrubber.py            # High-performance compiled regex secret scrubber
|   |   `-- crypto.py              # HMAC verifiers, SHA-256 API key generator
|   `-- workers/                   # Worker coordination
|       `-- base.py                # PostgreSQL SKIP LOCKED job claimer & worker loop
|-- services/
|   |-- ingester/                  # Stage 1: Ingestion Microservice (:8001)
|   |   |-- main.py                # FastAPI application
|   |   |-- routes/                # GitHub, Jira, and Slack webhook receivers
|   |   `-- services/              # Event processor & reconciler
|   |-- normalizer/                # Stage 2: Normalization Microservice (:8002)
|   |   |-- main.py                # FastAPI app & triage queue endpoints
|   |   |-- worker.py              # Autonomous worker loop for SourceEvents
|   |   `-- services/              # Reference extractor, link typing, anchor resolver, ledger
|   `-- decisioner/                # Stage 3: Decisioning Microservice (:8003)
|       |-- main.py                # FastAPI service & trigger endpoints
|       |-- worker.py              # Autonomous worker loop (ChangeEvent -> Candidate -> DecisionRun)
|       |-- config.py              # Port 8003 settings & consensus defaults
|       `-- services/              # Core decisioning pipeline components
|           |-- fact_extractor.py  # Deterministic facts (code diff, docs, breaking flags)
|           |-- sensitivity_detector.py # CVE, PII/NDA, compliance, pricing, embargo scan
|           |-- evidence_assembler.py   # 12,000-token ceiling bounded pack assembly
|           |-- judgment_client.py      # Frozen Q1-Q9 Claude Opus & offline evaluation
|           |-- consensus.py            # k=3 temperature sampling (t=0.0, 0.3, 0.7)
|           |-- policy_engine.py        # 11 deterministic restrict-only policy rules
|           `-- tier_evaluator.py       # T0-T3 tier classification & reason chips
|-- scripts/                       # Operational scripts & database tools
|   |-- init_db.py                 # Workspace initialization & connection seeding
|   |-- inspect_tables.py          # Database verification & record counter
|   |-- run_decisioner.py          # CLI runner for the Stage 3 Decisioning worker
|   |-- simulate_event.py          # Inbound webhook simulation test tool
|   |-- github_sync.py             # Live GitHub polling synchronizer
|   |-- jira_sync.py               # Live Jira ticket synchronizer
|   `-- slack_listener.py          # Real-time Slack Socket Mode event listener
|-- migrations/                    # Alembic migration revisions
|   |-- env.py                     # Async Alembic execution environment
|   `-- versions/                  # Revision scripts (0001_initial_schema.py)
|-- tests/                         # Comprehensive test harness (61 tests, 100% pass)
|   |-- conftest.py                # In-memory async fixtures & HTTPX test clients
|   |-- fixtures/webhooks/         # Golden payload test vectors
|   |-- unit/                      # 41 unit tests for models, contracts, scrubber, Stage 3
|   `-- integration/               # 20 integration tests: webhooks, replay storm, e2e pipelines
`-- docs/
    `-- images/                    # Clean architectural diagrams & charts
```

---

## Getting Started

### Prerequisites

* **Python:** 3.11, 3.12, or 3.13
* **PostgreSQL:** 16+ (with `pgvector` extension enabled)
* **Package Manager:** `pip` or `uv`

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/jashinspires/LaunchGraph.git
   cd LaunchGraph
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Database Setup & Migrations

Configure your PostgreSQL connection in `.env`:
```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/launchgraph
SECRET_KEY=your-secure-32-character-secret-key
GITHUB_WEBHOOK_SECRET=your-github-webhook-secret
SLACK_SIGNING_SECRET=your-slack-signing-secret
JIRA_WEBHOOK_SECRET=your-jira-webhook-secret
ANTHROPIC_API_KEY=your-optional-claude-api-key
```

Apply database migrations:
```bash
alembic upgrade head
```

Initialize your default workspace and seed connections:
```bash
python scripts/init_db.py
```

---

## Running Services

LaunchGraph microservices run independently or concurrently:

### Ingestion Service (Port 8001)
Receives inbound GitHub, Jira, and Slack webhooks:
```bash
uvicorn services.ingester.main:app --host 0.0.0.0 --port 8001 --reload
```

### Normalizer Service (Port 8002)
Runs the context graph normalization engine and serves triage queues:
```bash
uvicorn services.normalizer.main:app --host 0.0.0.0 --port 8002 --reload
```

### Decisioner Service (Port 8003)
Runs the Stage 3 decisioning API and consensus engine:
```bash
uvicorn services.decisioner.main:app --host 0.0.0.0 --port 8003 --reload
```

### Background Decisioner Worker Loop
Run the autonomous decisioner worker against your live database:
```bash
python scripts/run_decisioner.py
```

### Inspect Database State
View live record counts across all 34 tables:
```bash
python scripts/inspect_tables.py
```

---

## Testing & Quality Verification

LaunchGraph enforces a zero-regression policy. The entire test suite executes in **< 6 seconds** with **100% pass rate**:

```bash
pytest -v
```

```
============================== test session starts ==============================
collected 61 items

tests/unit/test_crypto.py ............                                    [ 19%]
tests/unit/test_evidence_assembler.py ....                                [ 26%]
tests/unit/test_fact_extractor.py ...                                     [ 31%]
tests/unit/test_judgment_and_consensus.py ....                            [ 37%]
tests/unit/test_link_typing.py ........                                   [ 50%]
tests/unit/test_models.py ..                                              [ 54%]
tests/unit/test_policy_engine.py ...                                      [ 59%]
tests/unit/test_scrubber.py .....                                         [ 67%]
tests/unit/test_sensitivity_detector.py ....                              [ 73%]
tests/unit/test_tier_evaluator.py ....                                    [ 80%]
tests/integration/test_decisioner_api.py ..                               [ 83%]
tests/integration/test_decisioner_pipeline.py ..                          [ 86%]
tests/integration/test_normalization_flow.py ...                          [ 91%]
tests/integration/test_replay_storm.py ..                                 [ 95%]
tests/integration/test_webhooks.py ...                                    [100%]

======================== 61 passed, 1 warning in 5.90s ========================
```

### Key Verification Milestones Included

* **Replay Storm Test (`test_replay_storm.py`):**
  Processes 1,000 duplicate and out-of-order webhook events verifying zero duplicate `source_events` are created.
* **Secret Scrubbing Precision (`test_scrubber.py`):**
  Ensures 100% redaction of AWS keys, GitHub tokens, Slack tokens, private keys, and JWTs.
* **HMAC Signature Verifiers (`test_crypto.py`):**
  Validates cryptographic integrity and Slack 5-minute replay attack windows.
* **Deterministic Link Typing (`test_link_typing.py`):**
  Verifies $L1$–$L8$ priority classification across pull requests, commits, and tickets.
* **Evidence Pack 12,000-Token Hard Ceiling (`test_evidence_assembler.py`):**
  Verifies strict markdown budget truncation and SHA-256 context hashing.
* **Consensus Sampling ($k=3$) & Agreement (`test_judgment_and_consensus.py`):**
  Verifies $k=3$ temperature sampling agreement calculations ($\ge 85\%$) and confidence grading.
* **Policy Engine 11 Restrict Rules (`test_policy_engine.py`):**
  Validates strict restrict-only policy application ($P\text{-SEC}$, $P\text{-CUST}$, $P\text{-EMBARGO}$, $P\text{-PRICING}$, etc.).
* **End-to-End Decisioner Pipeline (`test_decisioner_pipeline.py`):**
  Simulates full flow from `ChangeEvent` $\to$ `LaunchCandidate` $\to$ `DecisionRun` with consensus and audit trail.

---

## Development Milestones

![Milestone Progress](docs/images/milestone_progress.png)

Implementation progress is tracked against frozen PRD milestones:

- [x] **10% Milestone:** Batch 0 Contract Freeze & Complete 34-Table Database Schema
- [x] **25% Milestone:** Milestone M1 — "Data In" (Live Ingestion, Deduplication, Scrubbing)
- [x] **40% Milestone:** Milestone M2 — "Changes Are Right" (Normalization, Link Typing, Ledger)
- [x] **55% Milestone:** Wave 3A — Stage 3 Decisioning Engine (Deterministic Facts, Q1–Q9 Consensus, Policy Engine, Tier Evaluation)
- [ ] **70% Milestone:** Wave 3B / Milestone M3 (Gate G0) — Generation, 14 Safety Linters, Claim Verifier
- [ ] **80% Milestone:** Wave 4A — Review Dashboard & Mem0 Long-Term Memory Lifecycle Engine
- [ ] **90% Milestone:** Wave 4B / Milestone M4 — Agent-to-Agent (A2A) REST Interface & 5-Step Egress Gate
- [ ] **100% Milestone:** Wave 5 / Milestone M5 (Gate G4) — Production Hardening & General Availability

---

## License

Distributed under the Apache 2.0 License. See `LICENSE` for details.
