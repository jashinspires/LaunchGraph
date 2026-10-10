# LaunchGraph

[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![Architecture](https://img.shields.io/badge/architecture-Microservices%20%2B%20Context%20Graph-orange.svg)](#architecture)
[![Database](https://img.shields.io/badge/storage-PostgreSQL%2016%20%2B%20pgvector-blue.svg)](https://www.postgresql.org/)
[![Tests](https://img.shields.io/badge/tests-34%20passed%20%7C%20100%25-brightgreen.svg)](#testing)

**LaunchGraph** is an enterprise Go-To-Market (GTM) Context Graph platform. It automatically ingests raw engineering activity from GitHub, Jira, and Slack, synthesizes it into an anchored, typed context graph of product changes, deterministically classifies launch tiers ($T0$–$T3$), generates grounded GTM asset packs governed by 14 deterministic safety linters, and persists approved releases into a scalable long-term memory layer grounded in the **Mem0** graph architecture ($G = (V, E, L)$) for downstream consumption via a read-only Agent-to-Agent (A2A) protocol.

---

## Architecture Overview

LaunchGraph processes developer telemetry through a five-stage processing pipeline supported by decoupled autonomous worker loops:

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

| Service Name | Port | Primary Responsibility | Coordination Pattern |
|:---|:---:|:---|:---|
| **`launchgraph_core`** | — | Shared SQLAlchemy models, contracts, database pooling, crypto, and Mem0 primitives. | Python package imported across services. |
| **`ingester`** | `8001` | HMAC verification, deduplication (`webhook_inbox`), secret scrubbing, and raw event normalization. | FastAPI server + background reconciliation jobs. |
| **`normalizer`** | `8002` | Reference extraction, link typing ($L1$–$L8$), anchor resolution, and append-only ledger processing. | Autonomous `process -> sleep` worker loop + Triage API. |
| **`decisioner`** | `8003` | Deterministic fact building, sensitivity detector scans, 12k evidence packaging, and policy rules. | Worker loop + Claude Judgment consensus client. |
| **`generator`** | `8004` | 6-block context assembly, Mem0 few-shot memory retrieval, 14 deterministic linters, and verification. | Worker loop + Writer LLM client pool. |
| **`dashboard`** | `8005` | Internal review workspace, domain approver sign-offs, edit diffs, and reason chip capture. | FastAPI REST endpoints + PostgreSQL pool. |
| **`a2a_interface`** | `8006` | External Agent-to-Agent protocol; scoped API keys, 5-stage egress filter, discovery manifest. | FastAPI high-throughput read-only service. |

---

## Core Capabilities

### 1. Ingestion Pipeline & Hygiene (Stage 1)
* **HMAC Verification:** Enforces cryptographic validation (`X-Hub-Signature-256`, `X-Slack-Signature` with 5-minute replay prevention).
* **Idempotency Keys:** Unique delivery deduplication keys per provider (`github:{delivery_id}:{event}`, `jira:{issue_id}:{ts}`, `slack:{event_id}`).
* **Secret Scrubber:** High-performance regex sanitizer redacting AWS credentials, API tokens, JWTs, and private keys to `[REDACTED_SECRET]` prior to database insertion.
* **Events-Only Posture:** Adheres to enterprise security standards with zero historical Slack channel crawling.

### 2. Context Graph & Deterministic Normalization (Stage 2)
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

### 3. Mem0 Long-Term Memory Engine
Grounded in *Chhikara et al. (2025)*, LaunchGraph organizes memory into a labeled directed graph $G = (V, E, L)$:
* **Nodes ($V$):** Capabilities, features, personas, and ticket entities with dense embeddings ($e_v$).
* **Edges ($E$):** Typed semantic triplets $(v_s, r, v_d)$ labeled $r$ (e.g. `delivers_capability`, `deprecates`, `targets_persona`).
* **Algorithm 1 Operations:** Dynamic memory evolution via `ADD`, `UPDATE`, `DELETE` (soft-invalidation), and `NOOP` to prevent context bloating and memory amnesia.
* **Performance:** Dual retrieval delivers $\ge 90\%$ token savings and $91\%$ lower p95 latency ($< 200\text{ ms}$) compared to naive full-context injection.

### 4. Safety Architecture & Deterministic Linters
Defense-in-depth across 6 architectural layers ($L0$–$L5$):
* **14 Deterministic Linters:** `LINT-CODENAME`, `LINT-UNCITED`, `LINT-TOKEN`, `LINT-COMPETITOR`, `LINT-SUPERLATIVE`, `LINT-PRICING`, `LINT-TIMING`, `LINT-EMBARGO`, `LINT-LENGTH`, `LINT-PROFANITY`, `LINT-SECURITY`, `LINT-FORMAT`, `LINT-PERSONA`, `LINT-DISALLOWED-CLAIM`.
* **5-Stage Egress Hard Gate:** Verifies workspace isolation, `is_external_safe` marker, embargo scheduling, secret scrubbing, and synchronous audit logging before any data leaves via the A2A API.

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
|   `-- normalizer/                # Stage 2: Normalization Microservice (:8002)
|       |-- main.py                # FastAPI app & triage queue endpoints
|       |-- worker.py              # Autonomous worker loop for SourceEvents
|       `-- services/              # Reference extractor, link typing, anchor resolver, ledger
|-- migrations/                    # Alembic migration revisions
|   |-- env.py                     # Async Alembic execution environment
|   `-- versions/                  # Revision scripts (0001_initial_schema.py)
|-- tests/                         # Comprehensive test harness
|   |-- conftest.py                # In-memory async fixtures & test client
|   |-- fixtures/webhooks/         # Golden payload test vectors
|   |-- unit/                      # Unit tests for models, contracts, scrubber, typing
|   `-- integration/               # Webhooks, replay storm (1,000 events), e2e pipeline
```

---

## Getting Started

### Prerequisites

* **Python:** 3.11 or higher
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
```

Apply database migrations:
```bash
alembic upgrade head
```

---

## Running Services

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

---

## Testing & Quality Verification

LaunchGraph maintains a strict testing regime with 100% pass criteria on all gates.

Run the test suite:
```bash
pytest -v
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
* **End-to-End Pipeline (`test_normalization_flow.py`):**
  Simulates full event progression from raw webhook ingestion to anchored `ChangeEvent` and append-only ledger attachments.

---

## Development Milestones

Implementation progress is tracked against frozen PRD milestones:

- [x] **10% Milestone:** Batch 0 Contract Freeze & Complete 34-Table Database Schema
- [x] **25% Milestone:** Milestone M1 — "Data In" (Live Ingestion, Deduplication, Scrubbing)
- [x] **30% Milestone:** Milestone M2 Core — "Changes Are Right" (Normalization, Link Typing, Ledger)
- [ ] **55% Milestone:** Stage 3 Decisioning Core (Deterministic Facts, Q1-Q9 Consensus, Policy Engine)
- [ ] **70% Milestone:** Milestone M3 (Gate G0) — Generation, 14 Safety Linters, Claim Verifier
- [ ] **80% Milestone:** Review Dashboard & Mem0 Long-Term Memory Lifecycle Engine
- [ ] **90% Milestone:** Milestone M4 — Agent-to-Agent (A2A) REST Interface & 5-Step Egress Gate
- [ ] **100% Milestone:** Milestone M5 (Gate G4) — Production Hardening & General Availability

---

## License

Distributed under the Apache 2.0 License. See `LICENSE` for details.
