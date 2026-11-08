# LaunchGraph (ローンチグラフ)
**Cross-Platform Webhook Ingestion, Data Normalization & Context-Linking Pipeline**  
**複数ツールのWebhook収集・データ正規化・文脈紐付けパイプライン**

[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![Architecture](https://img.shields.io/badge/architecture-Microservices%20%2B%20Context%20Graph-orange.svg)](#3-システム構成--system-architecture-3-stage-pipeline)
[![Database](https://img.shields.io/badge/storage-PostgreSQL%2016%20%2B%20pgvector-blue.svg)](https://www.postgresql.org/)
[![Tests](https://img.shields.io/badge/tests-61%20passed%20%7C%20100%25-brightgreen.svg)](#7-セットアップとテスト--local-setup--testing)
[![Milestone](https://img.shields.io/badge/milestone-55%25%20Completed%20(Wave%203A%20%2F%20Stage%201--3%20Live)-brightgreen.svg)](#8-現在の開発状況と担当領域--current-project-status--my-role)

---

## 1. 概要 | Project Overview

**English:**  
LaunchGraph is a 4-member final-year B.Tech Computer Science project that solves a common team problem: project updates are scattered across **GitHub** (code commits, pull requests), **Jira** (tickets, epics), and **Slack** (engineering discussions). Each tool sends telemetry in a different, deeply nested JSON format. LaunchGraph collects these raw webhooks, cryptographically verifies their authenticity (HMAC-SHA256), scrubs sensitive credentials, converts them into a unified internal format (`Pydantic v2`), and links related events together into an anchored Context Graph in a relational database (`SQLAlchemy 2.0`). It then deterministically classifies launch tiers ($T0$–$T3$) via a multi-temperature consensus decisioning engine and prepares structured data for long-term memory indexing (**Mem0** graph architecture).

**日本語 (Japanese Summary):**  
LaunchGraphは、4名の学生チームで開発している最終学年のプロジェクトです。**GitHub**（コミット・Pull Request）、**Jira**（課題・エピック管理）、**Slack**（技術討議）に分散している開発ログや更新情報を一つに統合するバックエンド・データパイプラインです。ツールごとに異なる複雑なJSONデータを安全なWebhookとして受信し、HMAC-SHA256による改ざん検知と機密情報の自動マスキング（Scrubbing）を実施します。その後、共通の内部データモデル（`Pydantic v2`）に正規化（Normalize）し、リレーショナルデータベース上で関連するイベント同士を紐付けた「コンテキストグラフ（文脈グラフ）」を構築します。さらに、複数サンプリングによる合意判定エンジンでリリース重要度（$T0$〜$T3$）を決定し、長期記憶層（**Mem0**グラフアーキテクチャ）への連携準備を行います。

---

## 2. 重要用語の定義 | Key Definitions

* **Webhook Ingestion (Webhook収集・検証):**  
  Receiving real-time HTTP event notifications from external tools (GitHub, Jira, Slack). Enforces tamper-proofing and security hygiene before database insertion.  
  *(外部ツールからのHTTP通知をリアルタイムに受信し、DB保存前に検証・サニタイズする処理)*
* **Cryptographic Verification (暗号学的署名検証):**  
  Checking the `HMAC-SHA256` signature (`X-Hub-Signature-256`, `X-Slack-Signature`) to guarantee authenticity, prevent spoofing, and enforce 5-minute replay attack windows.  
  *(送信元が正規のツールであることをHMAC-SHA256ハッシュで検証し、なりすましやリプレイ攻撃を防御)*
* **Idempotency & Deduplication (べき等性・重複排除):**  
  Generating deterministic delivery keys (`github:{delivery_id}:{event}`, `jira:{issue_id}:{ts}`, `slack:{event_id}`) so that network retries never create duplicate records.  
  *(ネットワーク障害等で同一Webhookが再送された場合でも、重複登録を完全に防ぐ仕組み)*
* **Secret Scrubber (機密情報の自動マスキング):**  
  High-performance regex engine scanning raw payloads for AWS secrets, API keys, JWTs, and private keys, replacing them with `[REDACTED_SECRET]` prior to persistence.  
  *(APIキー、秘密鍵、AWS認証情報等の漏洩を防ぐため、DB保存前に自動で検出・置換する機構)*
* **Data Normalization (データ正規化):**  
  Converting polymorphic, messy JSON structures from diverse platforms into a unified typed schema validated by Pydantic v2.  
  *(各ツール独自のJSON構造を、共通の型定義・スキーマへと標準化・整合性検証する処理)*
* **Context Graph & Ledger (コンテキストグラフ・追記専用台帳):**  
  A relational graph structure (`SQLAlchemy 2.0` over PostgreSQL / SQLite) mapping relationships ($L1$–$L8$) between PRs, commits, Jira tickets, and Slack messages with an immutable audit trail (`change_membership`).  
  *(関連するPR・コミット・チケット・Slack発言を紐付け、監査可能な追記専用台帳で管理する仕組み)*
* **Consensus Decisioning ($k=3$ 合意形成エンジン):**  
  Sampling judgment questions ($Q1$–$Q9$) at varying temperatures ($t \in [0.0, 0.3, 0.7]$) to deterministically grade launch tiers ($T0$–$T3$) with $\ge 85\%$ agreement thresholds.  
  *(AI・判定ロジックのブレを抑えるため、3段階の温度パラメータで検証し合意度85%以上で確定する仕組み)*

---

## 3. システム構成 | System Architecture (3-Stage Pipeline)

LaunchGraph processes developer telemetry through a sequential multi-stage processing pipeline supported by decoupled autonomous worker loops:

![LaunchGraph System Context](docs/images/system_context.png)

### Microservice Topology | マイクロサービス構成

| Service Name | Port | Status | Primary Responsibility (主な役割) |
|:---|:---:|:---:|:---|
| **`launchgraph_core`** | — | **Live** | Shared SQLAlchemy models (34 tables), contracts, database pooling, and crypto primitives. *(共通モデル・暗号化・DBプール)* |
| **`ingester`** | `8001` | **Live** | Inbound webhook receiver, HMAC verification, idempotency deduplication, and secret scrubbing. *(データ受信・署名検証・機密除去)* |
| **`normalizer`** | `8002` | **Live** | Reference extraction, link typing ($L1$–$L8$), anchor resolution, and append-only ledger processing. *(データ正規化・エンティティ紐付け・台帳管理)* |
| **`decisioner`** | `8003` | **Live** | Deterministic facts, sensitivity detector, 12k evidence bounds, $k=3$ consensus, and 11 policy rules. *(事実抽出・合意サンプリング・リリース優先度判定)* |
| **`generator`** | `8004` | Planned | 6-block context assembly, Mem0 few-shot memory retrieval, and 14 safety linters. *(マーケティング草案生成・14種の安全リント)* |
| **`dashboard`** | `8005` | Planned | Internal review workspace, domain approver sign-offs, and edit diffs. *(PMM向けレビュー・承認ダッシュボード)* |
| **`a2a_interface`** | `8006` | Planned | External Agent-to-Agent protocol; scoped API keys, 5-stage egress filter, and discovery manifest. *(外部エージェント連携・5段階流出防止ゲート)* |

---

### Stage 1: Ingestion (`services/ingester`) — データ収集・検証 (Port 8001)

![Stage 1 Ingestion Pipeline](docs/images/pipeline_stage1_ingestion.png)

* **Asynchronous Webhook Receivers:** High-throughput FastAPI endpoints receiving GitHub, Jira, and Slack webhooks.
* **HMAC-SHA256 Cryptographic Verification:** Enforces cryptographic validation (`X-Hub-Signature-256`, `X-Slack-Signature` with 5-minute replay prevention).
* **Deterministic Idempotency Keys:** Unique delivery deduplication keys per provider (`github:{delivery_id}:{event}`, `jira:{issue_id}:{ts}`, `slack:{event_id}`).
* **Zero-Leak Secret Scrubber:** High-performance compiled regex sanitizer redacting AWS credentials, API tokens, JWTs, and private keys to `[REDACTED_SECRET]` before database insertion.
* **Events-Only Posture:** Adheres to enterprise security standards with zero historical Slack channel crawling.

---

### Stage 2: Normalization & Linking (`services/normalizer`) — 正規化・関連付け (Port 8002)

![Stage 2 Normalization & Graph Ledger](docs/images/pipeline_stage2_normalization.png)

* **Compiled Reference Extractor:** Regex extraction for Jira keys (`[A-Z][A-Z0-9]+-[0-9]+`), PR numbers (`#\d+`), commit SHAs, and URLs.
* **Deterministic Link Typing ($L1$–$L8$):**
  * $L1$ (`implements`): PR title/branch directly implements a ticket.
  * $L2$ (`mentions`): Informal reference in discussions.
  * $L3$ (`fixes`): Explicit defect closure keywords.
  * $L4$ (`reverts`): Git revert commits or rollback markers.
  * $L5$ (`contains`): Release versions and Epics.
  * $L6$ (`relates_to`), $L7$ (`duplicate_of`), $L8$ (`blocks`).
* **Authoritative Anchor Resolution:** Resolves primary change node via strict hierarchy: Jira Epic $\to$ Jira Issue $\to$ GitHub PR $\to$ Promoted Slack Thread.
* **Append-Only Ledger (`change_membership`):** All attachments are auditable and immutable. Soft-unlinking requires mandatory rationale; destructive deletes are prohibited.
* **Deterministic Suggestion Formula:**
  $$\text{Score} = 0.35 \times S_{\text{person}} + 0.20 \times S_{\text{time}} + 0.25 \times S_{\text{path}} + 0.20 \times S_{\text{text}}$$

---

### Stage 3: Decisioning & Tiering (`services/decisioner`) — 優先度判定・合意形成 (Port 8003)

![Stage 3 Decisioning Engine](docs/images/pipeline_stage3_decisioning.png)

* **Deterministic Fact Extractor:** Extracts objective metrics (lines changed, documentation touched in `docs/` or `*.md`, breaking changes, CI status) without LLM non-determinism.
* **Sensitivity Detector:** Deterministic compliance regex scanning for CVE vulnerabilities (`CVE-\d{4}-\d{4,7}`), Customer PII/NDA, regulatory standards (SOC2, HIPAA, GDPR), pricing shifts, and embargo hold dates.
* **12,000-Token Evidence Pack Assembler:** Assembles context from anchored events strictly bounded to a 12,000-token ceiling with SHA-256 context hashing to prevent prompt injection and context overflow.
* **Consensus Sampling Engine ($k=3$):** Executes frozen questions $Q1$–$Q9$ at temperatures $t \in [0.0, 0.3, 0.7]$, calculating raw agreement ($\ge 85\%$) and confidence grading (`high`, `medium`, `low`).
* **11 Restrict-Only Policy Rules:** Strictly enforces enterprise constraints ($P\text{-SEC}$, $P\text{-CUST}$, $P\text{-EMBARGO}$, $P\text{-COMPL}$, $P\text{-DEPR}$, $P\text{-INTERNAL}$, $P\text{-PRICING}$, $P\text{-REVERT}$, etc.). Policies can only escalate tiers or add blockers—never loosen constraints.
* **Deterministic Tier Evaluator:** Proposes launch tiers ($T0$: Internal, $T1$: Major Launch, $T2$: Minor Feature, $T3$: Patch/Docs), evaluates `is_external_safe`, and records human-auditable reason chips.

---

### Defense-in-Depth Safety & Long-Term Memory (Mem0)

![Defense-in-Depth Safety Architecture](docs/images/safety_architecture.png)

![Mem0 Long-Term Memory Engine](docs/images/mem0_memory_engine.png)

* **14 Deterministic Safety Linters:** Pre-generation and post-generation safety checks preventing codename leaks, uncited claims, superlative statements, pricing errors, profanity, and compliance violations.
* **Mem0 Graph Memory ($G = (V, E, L)$):** Formatted for long-term memory persistence following *Chhikara et al. (2025)*, supporting `ADD`, `UPDATE`, `DELETE` (soft-invalidation), and `NOOP` operations to slash token usage by $\ge 90\%$ and p95 retrieval latency by $91\%$ ($< 200\text{ ms}$).

---

## 4. API エンドポイント | Active API Endpoints

### Ingestion Service (Port 8001)
| Method | Endpoint | Purpose (用途) |
| :--- | :--- | :--- |
| `GET` | `/health` | Service health & database connectivity check (稼働確認) |
| `POST` | `/webhook/github` | Ingest GitHub events (`push`, `pull_request`, `release`) with HMAC verification |
| `POST` | `/webhook/jira` | Ingest Jira issue updates and releases with signature check |
| `POST` | `/webhook/slack` | Ingest Slack channel events with timestamp replay prevention |

### Normalizer Service (Port 8002)
| Method | Endpoint | Purpose (用途) |
| :--- | :--- | :--- |
| `GET` | `/health` | Normalizer service health check |
| `GET` | `/api/triage/unlinked` | Query unlinked events requiring PMM or engineer review |
| `GET` | `/api/triage/conflicts` | Query conflicting anchor suggestions |
| `GET` | `/api/triage/availability` | Query product availability status across changes |

### Decisioner Service (Port 8003)
| Method | Endpoint | Purpose (用途) |
| :--- | :--- | :--- |
| `GET` | `/health` | Decisioner service health check |
| `POST` | `/api/decisioner/evaluate/{id}` | Execute Stage 3 evaluation pipeline for a specific `ChangeEvent` |
| `POST` | `/api/decisioner/process` | Batch-process all pending unprocessed `ChangeEvent` records |
| `GET` | `/api/candidates` | List evaluated `LaunchCandidate` proposals with tier & confidence |
| `POST` | `/api/candidates/{id}/confirm` | Human approval endpoint confirming or overriding proposed tier |

---

## 5. ディレクトリ構成 | Repository Structure

```text
LaunchGraph/
├── launchgraph_core/              # Core Shared Library (共通ライブラリ)
│   ├── config.py                  # Pydantic BaseSettings environment configuration
│   ├── contracts/                 # Frozen Pydantic v2 schemas (jobs, ingress, decisioner, mem0, a2a)
│   ├── db/
│   │   ├── base.py                # DeclarativeBase, UUIDMixin, TimestampMixin
│   │   ├── session.py             # Async connection pool & session scope
│   │   └── models/                # 34 normalized SQLAlchemy 2.0 tables (Context Graph & Ledger)
│   └── security/                  # Security primitives (HMAC verifiers, compiled secret scrubber)
├── services/
│   ├── ingester/                  # Stage 1: Port 8001 - FastAPI webhook receivers, HMAC, secret scrubber
│   ├── normalizer/                # Stage 2: Port 8002 - Reference extraction, link typing L1-L8, ledger
│   └── decisioner/                # Stage 3: Port 8003 - Fact extraction, 12k evidence pack, consensus k=3
├── scripts/                       # Operational & Database Tools (運用・検証スクリプト)
│   ├── init_db.py                 # Workspace initialization & connection seeding
│   ├── inspect_tables.py          # Real-time context graph & database inspector
│   ├── run_decisioner.py          # Standalone CLI runner for Stage 3 worker
│   ├── simulate_event.py          # Webhook simulation test tool
│   ├── github_sync.py             # GitHub synchronization script
│   ├── jira_sync.py               # Jira synchronization script
│   └── slack_listener.py          # Slack Socket Mode event listener
├── migrations/                    # Alembic database schema migrations
├── tests/                         # Comprehensive Test Harness (61 automated tests, 100% pass)
│   ├── conftest.py                # In-memory async fixtures & HTTPX test clients
│   ├── fixtures/webhooks/         # Golden payload test vectors (GitHub, Jira, Slack)
│   ├── unit/                      # 41 unit tests (models, scrubber, crypto, link typing, Stage 3)
│   └── integration/               # 20 integration tests (webhooks, replay storm, e2e pipelines)
└── docs/
    └── images/                    # Clean architectural diagrams & pipeline flowcharts
```

---

## 6. 技術スタック | Tech Stack

* **Language (言語):** Python 3.11, 3.12, 3.13
* **Web Framework (フレームワーク):** FastAPI, Uvicorn (ASGI)
* **Data Validation (データ検証):** Pydantic v2 (Frozen contract schemas)
* **Database & ORM (データベース):** SQLAlchemy 2.0 (Async), Alembic (34-table relational schema)
* **Supported Databases (対応DB):** SQLite with in-memory shims (fast local test execution) & PostgreSQL 16 with `pgvector` (production & Docker environment)
* **Security & Cryptography (セキュリティ):** HMAC-SHA256 signature verification, compiled regex secret scrubbing, replay attack prevention
* **Consensus & Decisioning (合意形成・判定):** Multi-temperature sampling ($t=0.0, 0.3, 0.7$), Claude Opus adapter & deterministic offline evaluator, restrict-only policy engine
* **Memory Architecture (記憶基盤):** Mem0 graph schema ($G = (V, E, L)$) with dynamic update operations (`ADD`, `UPDATE`, `DELETE`, `NOOP`)
* **Testing (テスト自動化):** Pytest, pytest-asyncio, HTTPX (`61` automated tests, 100% pass rate in < 6s)

---

## 7. セットアップとテスト | Local Setup & Testing

### 1. Clone and Install Dependencies (環境構築)

```bash
git clone https://github.com/jashinspires/LaunchGraph.git
cd LaunchGraph
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables (環境変数の設定)

Create a `.env` file in the project root:
```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/launchgraph
SECRET_KEY=your-secure-32-character-secret-key
GITHUB_WEBHOOK_SECRET=your-github-webhook-secret
SLACK_SIGNING_SECRET=your-slack-signing-secret
JIRA_WEBHOOK_SECRET=your-jira-webhook-secret
```

### 3. Run the Automated Test Suite (テストの実行)

The test harness uses SQLite in-memory shims so all **61 tests** execute in under 6 seconds without requiring an external database:

```bash
pytest -v
```

```text
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

### 4. Running the Microservices (サービスの起動)

Each microservice can be started independently:

```bash
# Terminal 1: Ingestion Service (Port 8001)
uvicorn services.ingester.main:app --host 0.0.0.0 --port 8001 --reload

# Terminal 2: Normalizer Service (Port 8002)
uvicorn services.normalizer.main:app --host 0.0.0.0 --port 8002 --reload

# Terminal 3: Decisioner Service (Port 8003)
uvicorn services.decisioner.main:app --host 0.0.0.0 --port 8003 --reload
```

### 5. Inspect Live Database State (DB状況の可視化)

To inspect live records across all 34 tables including connections, inbox, scrubbed events, graph links, and candidates:

```bash
python scripts/inspect_tables.py
```

---

## 8. 現在の開発状況と担当領域 | Current Project Status & My Role

To keep documentation strictly factual, below is what is currently implemented versus what is still in progress:

### Implemented & Verified (実装・検証済み — 55% Milestone Achieved):
* **Stage 1 Ingestion Pipeline (`services/ingester` - Port 8001):** Asynchronous webhook receivers (`/webhook/github`, `/webhook/jira`, `/webhook/slack`), HMAC-SHA256 signature verification, 100% secret scrubbing, and idempotent deduplication tested with a 1,000-event replay storm.
* **Stage 2 Normalization & Graph Ledger (`services/normalizer` - Port 8002):** Compiled reference extraction (Jira keys, PR numbers, commit SHAs), deterministic link typing ($L1$–$L8$), authoritative anchor resolution, and append-only ledger (`change_membership`) with soft-unlinking rationale.
* **Stage 3 Decisioning Engine (`services/decisioner` - Port 8003):** Deterministic fact extraction (code diffs, docs touched, breaking changes), sensitivity detection (CVEs, NDA/PII, compliance, pricing, embargo), 12,000-token evidence packaging with SHA-256 context hashing, $k=3$ consensus sampling ($\ge 85\%$ agreement), 11 restrict-only policy rules, and $T0$–$T3$ tier evaluation.
* **Database & Contracts (`launchgraph_core`):** 34 normalized SQLAlchemy 2.0 tables, Alembic migration scripts, and Pydantic v2 contract schemas.
* **Dual-Dialect Compatibility:** SQLite in-memory shims for fast test execution (< 6s) and PostgreSQL 16 + `pgvector` for production persistence.
* **Testing:** 61 automated unit and integration tests passing with 100% pass rate.

### In Progress by the 4-Member Team (開発中 — Remaining 45%):
* **Stage 4 Generation (`services/generator` - Port 8004):** 6-block context assembly, 9 GTM asset schemas, 14 deterministic safety linters, and secondary claim verification pass.
* **Stage 5 Review Dashboard & Mem0 Long-Term Memory:** Web UI for PMM review, multi-party approval workflows, and Mem0 Algorithm 1 dynamic memory evolution (`ADD`, `UPDATE`, `DELETE`, `NOOP`).
* **Stage 6 Agent-to-Agent Interface (`services/a2a_interface` - Port 8006):** Public A2A REST protocol with scoped API tokens and 5-stage egress gate.

---

### My Role — Muramalla Jaswanth Kumar (@jashinspires) | 開発担当領域

Designed and implemented the core backend architecture and data pipelines:
1. **Core Database Architecture & Contracts:** Designed and implemented the 34-table relational schema in SQLAlchemy 2.0 (`launchgraph_core/db/models`), Alembic migrations, and frozen Pydantic v2 contracts.
2. **Stage 1 Ingestion Pipeline:** Built the FastAPI ingestion microservice (`services/ingester`), HMAC-SHA256 verification algorithms, regex secret scrubber, and idempotency deduplication engine.
3. **Stage 2 Context Graph Normalizer:** Implemented reference extraction, deterministic $L1$–$L8$ link typing, anchor hierarchy resolution, and the append-only ledger manager (`services/normalizer`).
4. **Stage 3 Decisioning Engine:** Architected the deterministic fact extractor, sensitivity detector, 12,000-token evidence assembler, $k=3$ consensus sampling engine, 11 restrict-only policy rules, and tier evaluator (`services/decisioner`).
5. **Quality Assurance & Benchmark Suite:** Authored the 61-test automated evaluation suite (`tests/`), including the 1,000-event replay storm benchmark and end-to-end integration pipelines.

---

## 9. ライセンス | License

Distributed under the Apache 2.0 License. See `LICENSE` for details.
