# 📋 HR Policy RAG System

> **Enterprise HR Policy Q&A — JWT RBAC ➜ Hybrid Vector+Keyword Retrieval ➜ GPT-4o Grounded Generation ➜ Cosmos DB Audit Trail**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Azure OpenAI](https://img.shields.io/badge/Azure_OpenAI-GPT--4o-0078D4?logo=microsoftazure&logoColor=white)](https://azure.microsoft.com/en-us/products/ai-services/openai-service)
[![Azure AI Search](https://img.shields.io/badge/Azure_AI_Search-Hybrid-0078D4?logo=microsoftazure&logoColor=white)](https://azure.microsoft.com/en-us/products/ai-services/ai-search)
[![Cosmos DB](https://img.shields.io/badge/Cosmos_DB-Audit_Trail-0078D4?logo=microsoftazure&logoColor=white)](https://azure.microsoft.com/en-us/products/cosmos-db)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An **enterprise-grade Retrieval-Augmented Generation (RAG) system** for HR policy Q&A. Employees ask natural-language questions about company policies; the system authenticates via **JWT with role-based clearance levels** (employee → manager → hr_admin), retrieves relevant policy chunks using **Azure AI Search hybrid vector+keyword search with RBAC filtering**, generates **grounded answers with source citations** via GPT-4o, and writes **every interaction to Cosmos DB** with 7-year retention for compliance audit.

From **"Prompt to Production"** by Maneesh Kumar.

---

## Table of Contents

| # | Section | Description |
|---|---------|-------------|
| 1 | [Architecture](#architecture) | System design, RAG pipeline, RBAC model |
| 2 | [How It Works — Annotated Walkthrough](#how-it-works--annotated-walkthrough) | Step-by-step request flow with annotations |
| 3 | [Design Decisions](#design-decisions) | Why hybrid search, JWT RBAC, Cosmos audit |
| 4 | [Data Contracts](#data-contracts) | Every Pydantic model, enum, dict structure |
| 5 | [Features](#features) | Comprehensive feature matrix |
| 6 | [Prerequisites](#prerequisites) | Platform-specific setup (macOS / Windows / Linux) |
| 7 | [Quick Start](#quick-start) | Clone → install → run in 3 minutes |
| 8 | [Indexing Pipeline](#indexing-pipeline) | Offline document chunking and indexing |
| 9 | [Project Structure](#project-structure) | File tree with module responsibilities |
| 10 | [Configuration Reference](#configuration-reference) | Every environment variable explained |
| 11 | [API Reference](#api-reference) | Endpoints with request/response schemas |
| 12 | [RBAC & Authentication](#rbac--authentication) | Clearance levels, JWT flow, mock users |
| 13 | [Testing](#testing) | Unit tests, mocking strategy |
| 14 | [Deployment](#deployment) | Docker, Azure Container Apps |
| 15 | [Troubleshooting](#troubleshooting) | Common issues and solutions |
| 16 | [Azure Production Mapping](#azure-production-mapping) | Local → cloud service mapping |
| 17 | [Production Checklist](#production-checklist) | Go-live readiness assessment |

---

## Architecture

### System Overview

```
  ┌─────────────────────────────────────────────────────────────────────────────────┐
  │                          OFFLINE: INDEXING PIPELINE                              │
  │                                                                                 │
  │   indexer/documents/                                                            │
  │   ├── benefits_guide.md         ┌─────────────────────┐   ┌─────────────────┐  │
  │   ├── code_of_conduct.md   ────►│  RecursiveChunker   │──►│ Azure OpenAI    │  │
  │   ├── expense_policy.md         │  (1000 chars/chunk)  │   │ Embeddings      │  │
  │   ├── parental_leave_policy.md  │  (200 char overlap)  │   │ text-embedding  │  │
  │   └── remote_work_policy.md     │  4-level splitting:  │   │ -3-large        │  │
  │                                 │  ¶¶ → ¶ → . → space │   │ (3072 dims)     │  │
  │                                 └─────────────────────┘   └────────┬────────┘  │
  │                                                                     │           │
  │                                                    ┌────────────────┴────────┐  │
  │                                                    │  Azure AI Search Index  │  │
  │                                                    │  "hr-policies"          │  │
  │                                                    │  ├─ title (searchable)  │  │
  │                                                    │  ├─ content (searchable)│  │
  │                                                    │  ├─ content_vector      │  │
  │                                                    │  │   (3072-dim HNSW)    │  │
  │                                                    │  ├─ clearance_level     │  │
  │                                                    │  │   (filterable int)   │  │
  │                                                    │  └─ semantic config     │  │
  │                                                    └─────────────────────────┘  │
  └─────────────────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────────────────┐
  │                          RUNTIME: RAG QUERY PIPELINE                            │
  │                                                                                 │
  │   Employee ─── POST /query ───► FastAPI (src/api/main.py)                      │
  │   {"question": "How many weeks of parental leave?"}                            │
  │   Authorization: Bearer <JWT>                                                   │
  │                │                                                                │
  │                ▼                                                                │
  │   ┌──────────────────────────────────────────────────────────────────────────┐  │
  │   │  Step 1: AUTHENTICATE & AUTHORIZE                                       │  │
  │   │  validate_token() → UserContext                                         │  │
  │   │                                                                          │  │
  │   │  JWT payload:                    UserContext output:                     │  │
  │   │  {"sub": "user-001",            {"user_id": "user-001",                │  │
  │   │   "role": "employee"}            "email": "alice@contoso.com",          │  │
  │   │                                  "role": "employee",                    │  │
  │   │                                  "department": "Engineering",           │  │
  │   │                                  "clearance_level": 1}                  │  │
  │   └──────────────────────────────────┬───────────────────────────────────────┘  │
  │                                      │                                          │
  │   ┌──────────────────────────────────▼───────────────────────────────────────┐  │
  │   │  Step 2: HYBRID RETRIEVAL with RBAC                                     │  │
  │   │  HybridRetriever.search()                                               │  │
  │   │                                                                          │  │
  │   │  1. Embed query → text-embedding-3-large → 3072-dim vector             │  │
  │   │  2. OData filter: "clearance_level le 1" (employee can't see L2/L3)    │  │
  │   │  3. Hybrid search: vector similarity + BM25 keyword + semantic ranking │  │
  │   │  4. Return top-5 SourceDocument results                                 │  │
  │   │                                                                          │  │
  │   │  ┌────────────────────────────────────────────────────────────────┐      │  │
  │   │  │  Azure AI Search Query:                                        │      │  │
  │   │  │  • search_text = "How many weeks of parental leave?"          │      │  │
  │   │  │  • vector_queries = [VectorizedQuery(vector=<3072>, k=5)]     │      │  │
  │   │  │  • filter = "clearance_level le 1"                            │      │  │
  │   │  │  • query_type = "semantic"                                     │      │  │
  │   │  │  • semantic_configuration_name = "default"                     │      │  │
  │   │  └────────────────────────────────────────────────────────────────┘      │  │
  │   └──────────────────────────────────┬───────────────────────────────────────┘  │
  │                                      │                                          │
  │   ┌──────────────────────────────────▼───────────────────────────────────────┐  │
  │   │  Step 3: GROUNDED GENERATION                                            │  │
  │   │  GroundedGenerator.generate()                                           │  │
  │   │                                                                          │  │
  │   │  System Prompt:                                                          │  │
  │   │  "You are an HR policy assistant for Contoso Corporation.               │  │
  │   │   Answer ONLY based on the provided HR policy documents.                │  │
  │   │   Always cite the specific policy document and section.                  │  │
  │   │   If the answer is not in the documents, say so clearly.                │  │
  │   │   Never fabricate policy information."                                   │  │
  │   │                                                                          │  │
  │   │  User Message:                                                           │  │
  │   │  "Question: How many weeks of parental leave?                           │  │
  │   │   [Document 1: Parental Leave Policy]                                    │  │
  │   │   Primary carer: 26 weeks paid leave at 100% salary...                  │  │
  │   │   [Document 2: Benefits Guide]                                           │  │
  │   │   Parental leave is part of the comprehensive benefits..."              │  │
  │   │                                                                          │  │
  │   │  → GPT-4o (temp=0.2, max_tokens=800)                                   │  │
  │   │  → Confidence: High (≥3 docs with score >0.8)                          │  │
  │   └──────────────────────────────────┬───────────────────────────────────────┘  │
  │                                      │                                          │
  │   ┌──────────────────────────────────▼───────────────────────────────────────┐  │
  │   │  Step 4: AUDIT LOGGING                                                  │  │
  │   │  AuditLogger.log_query() → Cosmos DB                                   │  │
  │   │                                                                          │  │
  │   │  Audit Record:                                                           │  │
  │   │  {"user_id": "user-001", "user_role": "employee",                      │  │
  │   │   "question": "How many weeks...", "answer": "According to...",         │  │
  │   │   "sources": ["Parental Leave Policy", "Benefits Guide"],              │  │
  │   │   "confidence": "High", "latency_ms": 1842.3,                         │  │
  │   │   "token_usage": {"total_tokens": 1200, "estimated_cost_usd": 0.012}, │  │
  │   │   "_partitionKey": "user-001", "ttl": 220752000}  ← 7-year retention  │  │
  │   └──────────────────────────────────┬───────────────────────────────────────┘  │
  │                                      │                                          │
  │                                      ▼                                          │
  │   Response: {"answer": "According to the Parental Leave Policy...",            │
  │              "sources": ["Parental Leave Policy", "Benefits Guide"],            │
  │              "confidence": "High", "query_id": "a1b2c3d4..."}                  │
  └─────────────────────────────────────────────────────────────────────────────────┘
```

### RBAC Clearance Filtering

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │                   DOCUMENT CLEARANCE LEVELS                        │
  │                                                                     │
  │   Level 1 (Employee)           Level 2 (Manager)    Level 3 (HR)   │
  │   ─────────────────           ─────────────────    ──────────────  │
  │   ✅ Benefits Guide            ✅ All Level 1       ✅ All L1 + L2  │
  │   ✅ Code of Conduct           ✅ Salary bands      ✅ Termination  │
  │   ✅ Expense Policy            ✅ Performance        procedures     │
  │   ✅ Remote Work Policy          review guides      ✅ Compensation │
  │   ✅ Parental Leave            ✅ Hiring budgets       structures   │
  │                                                     ✅ Legal docs   │
  │                                                                     │
  │   employee → clearance=1       manager → clearance=2               │
  │   "clearance_level le 1"      "clearance_level le 2"              │
  │                                                                     │
  │                                hr_admin → clearance=3              │
  │                                "clearance_level le 3" (sees all)   │
  └─────────────────────────────────────────────────────────────────────┘
```

---

## How It Works — Annotated Walkthrough

### Scenario 1: Employee Asks About Parental Leave

```
$ TOKEN=$(python -c "from src.auth import create_test_token; print(create_test_token('user-001', 'employee'))")

$ curl -s -X POST http://localhost:8000/query \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"question": "How many weeks of parental leave do I get?"}' | python -m json.tool
```

```json
{
    "answer": "According to the Parental Leave     // ← Grounded in retrieved documents
        Policy, Contoso Corporation offers:         // ← Citations to specific policy
                                                    //
        - **Primary carer**: 26 weeks paid leave    // ← Exact policy details
          at 100% salary                            //
        - **Secondary carer**: 4 weeks paid leave   // ← All from Document 1
        - **Adoption leave**: Mirrors maternity     //
          leave provisions                          //
                                                    //
        To apply, submit the parental leave         // ← Actionable guidance
        request form to HR at least 8 weeks         //
        before your expected start date.            //
                                                    //
        Source: Parental Leave Policy",             // ← Explicit source citation
    "sources": [                                    // ← Documents that were retrieved
        "Parental Leave Policy",                    //    and used for grounding
        "Benefits Guide"
    ],
    "confidence": "High",                           // ← ≥3 docs scored >0.8
    "query_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

**What happened behind the scenes:**
1. JWT token decoded → `user-001` with `clearance_level=1` (employee)
2. Query embedded via `text-embedding-3-large` → 3072-dimensional vector
3. Azure AI Search hybrid query with filter `clearance_level le 1`
4. Top-5 chunks retrieved (parental leave policy, benefits guide)
5. GPT-4o generated grounded answer citing specific policy sections
6. Confidence computed: "High" (3+ docs with relevance >0.8)
7. Audit record written to Cosmos DB with `_partitionKey=user-001`, TTL=7 years

### Scenario 2: Manager Sees More Documents

```
$ TOKEN_MGR=$(python -c "from src.auth import create_test_token; print(create_test_token('user-002', 'manager'))")

$ curl -s -X POST http://localhost:8000/query \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN_MGR" \
    -d '{"question": "What is the salary band for senior engineers?"}' | python -m json.tool
```

```json
{
    "answer": "According to the Compensation        // ← Manager can see Level 2 docs
        Guidelines, the salary band for Senior      //    that employees cannot access
        Software Engineers at Contoso is...",
    "sources": [
        "Compensation Guidelines",                  // ← Level 2 document
        "Benefits Guide"                            // ← Level 1 document
    ],
    "confidence": "Medium",
    "query_id": "..."
}
```

**Key difference**: The `clearance_level le 2` filter returned Level 2 compensation documents that an employee query would have **filtered out**.

### Scenario 3: No Auth Header (Dev Mode)

```
$ curl -s -X POST http://localhost:8000/query \
    -H "Content-Type: application/json" \
    -d '{"question": "What is the expense policy for travel?"}' | python -m json.tool
```

```json
{
    "answer": "Based on the Expense Policy,          // ← Uses dev user (employee)
        Contoso's travel expense guidelines are...",
    "sources": ["Expense Policy"],
    "confidence": "Medium",
    "query_id": "..."
}
```

**No `Authorization` header** → falls back to `MOCK_USERS["user-001"]` (employee, clearance=1). Logs warning: `no_auth_header_using_dev_user`.

### Scenario 4: Demo Script

```
$ python demo_e2e.py
```

```
=== HR Policy RAG - End-to-End Demo ===

JWT Token created (employee role)
  User ID: emp-001, Clearance: 1
  Manager: user-002, Clearance: 2
  HR Admin: user-003, Clearance: 3

Chunker: split HR policy into 2 chunks
  First chunk: # Parental Leave Policy

## Overview
Contoso offers comprehensive parental leave...

Policy documents available: 5 files
  - benefits_guide.md
  - code_of_conduct.md
  - expense_policy.md
  - parental_leave_policy.md
  - remote_work_policy.md

RBAC clearance levels:
  employee: clearance level 1
  manager: clearance level 2
  hr_admin: clearance level 3

=== HR Policy RAG: Auth, RBAC, and document chunking working ===
```

---

## Design Decisions

### Why Hybrid Search (Vector + Keyword + Semantic)?

| Search Mode | Strengths | Weaknesses | Example |
|-------------|-----------|------------|---------|
| **Keyword only (BM25)** | Exact match, fast | Misses synonyms, no semantic understanding | "maternity leave" won't find "parental leave" |
| **Vector only** | Semantic similarity, handles synonyms | Can miss exact terms, noisy for precise queries | Finds related docs but may miss exact policy name |
| **Hybrid (selected)** | Best of both — semantic understanding + exact matching | Slightly more compute | "parental leave" finds both exact matches AND semantically related benefits docs |
| **+ Semantic ranking** | Re-ranks results using transformer model | Additional latency (~100ms) | Prioritizes most relevant chunks within results |

**Key insight**: HR policy queries mix precise terms ("Section 4.2") with natural language ("how many vacation days"). Hybrid search handles both.

### Why JWT with Clearance Levels (Not Azure AD RBAC)?

| Approach | Pros | Cons | Verdict |
|----------|------|------|---------|
| **No auth** | Simplest | Anyone sees everything, no audit trail | ❌ Compliance violation |
| **Azure AD roles** | Enterprise SSO, automatic rotation | Requires Azure AD setup, complex for demo | ❌ Too heavy for this pattern |
| **JWT + clearance levels** | Self-contained, works anywhere, maps to document sensitivity | Manual token management | ✅ **Selected** — clear RBAC model |

**RBAC enforcement point**: The clearance filter is applied at the **search layer** (`clearance_level le N`), not at the application layer. This means:
- Even if the application logic has a bug, unauthorized documents are **never retrieved**
- Azure AI Search enforces the filter server-side before returning results

### Why Cosmos DB for Audit (Not SQL)?

| Store | Write Latency | 7-Year Retention | Partitioning | Cost at Scale |
|-------|:------------:|:-----------------:|:------------:|:------------:|
| **SQL Database** | ~10ms | Manual TTL | Table sharding | $$$ |
| **Blob Storage** | ~50ms | Lifecycle management | Container structure | $ |
| **Cosmos DB** | ~5ms | Built-in TTL | Automatic with partition key | $$ |

**Selected: Cosmos DB** because:
- **Built-in TTL**: `ttl: 220752000` (7 years) — automatic deletion, no cleanup job
- **Partition key**: `_partitionKey = user_id` — efficient per-user audit queries
- **Immutable writes**: Audit records are write-once, never updated
- **Global distribution**: Multi-region for compliance requirements

### Why Recursive Chunking (Not Fixed-Size)?

```
  Fixed-size chunking:                    Recursive chunking (selected):
  ─────────────────                       ───────────────────────────────
  Split at exactly 1000 chars             Split at paragraph boundaries first
  May break mid-sentence                  Then sentence boundaries
  Loses context boundaries                Then word boundaries
  Poor retrieval quality                  Preserves semantic coherence

  "...eligible for leave. [SPLIT]         "...eligible for leave."
   Employees who have completed..."        ───── chunk boundary ─────
                                           "Employees who have completed..."
```

**4-level separator hierarchy**: `\n\n` → `\n` → `. ` → ` ` (space). Each level only used when the previous separator produces chunks larger than `chunk_size`.

---

## Data Contracts

### Pydantic Models

```python
class QueryRequest(BaseModel):
    """API input — what the employee submits."""
    question: str = Field(..., min_length=5)                    # HR policy question
    session_id: Optional[str] = Field(default_factory=uuid4)    # Conversation tracking

class SourceDocument(BaseModel):
    """Retrieved document chunk from Azure AI Search."""
    title: str                    # e.g., "Parental Leave Policy"
    content_snippet: str          # First 300 chars of chunk
    relevance_score: float        # Azure AI Search score

class QueryResponse(BaseModel):
    """API output — grounded answer with citations."""
    answer: str                   # GPT-4o generated answer
    sources: List[str]            # Document titles used
    confidence: str               # "High" | "Medium" | "Low"
    query_id: str                 # Unique query identifier

class UserContext(BaseModel):
    """Authenticated user identity and permissions."""
    user_id: str                  # e.g., "user-001"
    email: str                    # e.g., "alice@contoso.com"
    role: str                     # "employee" | "manager" | "hr_admin"
    department: str               # e.g., "Engineering"
    clearance_level: int          # 1 (employee) | 2 (manager) | 3 (hr_admin)

class AuditRecord(BaseModel):
    """Immutable compliance record written to Cosmos DB."""
    id: str                       # UUID
    timestamp: datetime           # UTC ISO format
    user_id: str                  # Who asked
    user_role: str                # What role
    question: str                 # What was asked
    answer: str                   # What was answered
    sources: List[str]            # What documents were cited
    confidence: str               # How confident was the answer
    latency_ms: float             # How long it took
    token_usage: Dict[str, int]   # Token counts + estimated cost
```

### Indexer Data Structures

```python
@dataclass
class DocumentChunk:
    """Output of RecursiveChunker — input to indexer."""
    content: str                              # Chunk text with overlap
    source_file: str                          # e.g., "parental_leave_policy.md"
    title: str                                # e.g., "Parental Leave Policy"
    chunk_index: int                          # Position in document
    section_heading: Optional[str] = None     # Detected heading
    category: str = "hr_policy"               # Document category
    clearance_level: int = 1                  # RBAC clearance

# Azure AI Search index document (uploaded by indexer)
search_document = {
    "id": str,                                # UUID
    "title": str,                             # Document title
    "content": str,                           # Chunk text
    "source_file": str,                       # Filename
    "category": str,                          # "hr_policy"
    "clearance_level": int,                   # 1, 2, or 3
    "chunk_index": int,                       # Chunk position
    "content_vector": List[float],            # 3072-dim embedding
}

# Cosmos DB audit document (written by AuditLogger)
cosmos_document = {
    **audit_record_fields,                    # All AuditRecord fields
    "_partitionKey": str,                     # user_id for partitioning
    "ttl": 220752000,                         # 7 years in seconds
}
```

### Confidence Scoring Logic

```python
# GroundedGenerator._compute_confidence()
if no_docs_retrieved:
    confidence = "Low"
elif docs_with_score_above_0_8 >= 3:
    confidence = "High"
elif docs_retrieved >= 1:
    confidence = "Medium"
else:
    confidence = "Low"
```

---

## Features

| # | Feature | Description | Module |
|---|---------|-------------|--------|
| 1 | **Hybrid Vector+Keyword Search** | Combines semantic similarity with BM25 keyword matching | `src/retriever.py` |
| 2 | **Semantic Ranking** | Azure AI Search semantic reranking for result quality | `HybridRetriever` |
| 3 | **3072-dim Embeddings** | `text-embedding-3-large` for high-fidelity vector search | `HybridRetriever` |
| 4 | **RBAC Clearance Filtering** | OData filter `clearance_level le N` enforced at search layer | `HybridRetriever` |
| 5 | **Grounded Generation** | GPT-4o answers strictly from retrieved documents | `src/generator.py` |
| 6 | **Source Citations** | Every answer includes specific policy document references | `GroundedGenerator` |
| 7 | **Anti-Hallucination Prompt** | "Never fabricate policy information" in system prompt | `GroundedGenerator` |
| 8 | **Confidence Scoring** | High/Medium/Low based on retrieval quality | `GroundedGenerator` |
| 9 | **Token Usage Tracking** | Prompt, completion, total tokens + estimated USD cost | `GroundedGenerator` |
| 10 | **JWT Authentication** | HS256 JWT token validation with role extraction | `src/auth.py` |
| 11 | **3-Tier RBAC** | employee (L1) → manager (L2) → hr_admin (L3) | `src/auth.py` |
| 12 | **Mock Users** | 3 pre-configured test users for development | `src/auth.py` |
| 13 | **Dev Mode Fallback** | No auth header → employee dev user (with warning log) | `src/auth.py` |
| 14 | **Cosmos DB Audit Trail** | Immutable audit records for every query | `src/audit.py` |
| 15 | **7-Year Retention** | TTL-based automatic deletion after 7 years | `AuditLogger` |
| 16 | **User-Partitioned Audit** | `_partitionKey = user_id` for efficient per-user queries | `AuditLogger` |
| 17 | **Latency Tracking** | Millisecond-precision timing for every query | `src/api/main.py` |
| 18 | **Recursive Text Chunking** | 4-level separator hierarchy preserving semantic boundaries | `indexer/chunker.py` |
| 19 | **Chunk Overlap** | 200-char overlap between consecutive chunks | `RecursiveChunker` |
| 20 | **Min Chunk Filter** | Chunks < 50 chars are discarded (noise reduction) | `RecursiveChunker` |
| 21 | **HNSW Vector Index** | High-performance approximate nearest neighbor search | `indexer/index_documents.py` |
| 22 | **Semantic Search Config** | Title + content semantic fields for ranking | `index_documents.py` |
| 23 | **Batch Indexing** | Uploads chunks in batches of 100 | `index_documents.py` |
| 24 | **Clearance Auto-Detection** | `clearance_level: manager` in doc text → L2 | `index_documents.py` |
| 25 | **5 Policy Documents** | Benefits, conduct, expense, parental leave, remote work | `indexer/documents/` |
| 26 | **Pydantic Validation** | Input validation with min_length, Field constraints | `src/models.py` |
| 27 | **Pydantic Settings** | Environment-based config with `.env` file support | `src/config.py` |
| 28 | **LRU-Cached Settings** | Singleton settings instance via `@lru_cache` | `src/config.py` |
| 29 | **Structured JSON Logging** | structlog with ISO timestamps and JSON rendering | `src/api/main.py` |
| 30 | **Lifespan Management** | FastAPI lifespan context manager for component init | `src/api/main.py` |
| 31 | **Health Endpoint** | `GET /health` with service name and version | `src/api/main.py` |
| 32 | **Docker Support** | Multi-stage Python 3.11 slim image | `infra/Dockerfile` |
| 33 | **Azure Deploy Script** | ACR + Container Apps automated deployment | `infra/azure-deploy.sh` |
| 34 | **OpenAI Retry Logic** | `max_retries=3` on AsyncAzureOpenAI client | `GroundedGenerator` |
| 35 | **Graceful Error Handling** | Generation failure → "Contact HR directly" fallback | `GroundedGenerator` |

---

## Prerequisites

<details>
<summary><strong>macOS</strong></summary>

```bash
# Python 3.11+
brew install python@3.11

# Verify
python3 --version    # Python 3.11.x

# Optional: Azure CLI (for deployment)
brew install azure-cli

# Optional: Docker (for containerized deployment)
brew install --cask docker
```
</details>

<details>
<summary><strong>Windows</strong></summary>

```powershell
# Python 3.11+ from python.org or winget
winget install Python.Python.3.11

# Verify
python --version    # Python 3.11.x

# Optional: Azure CLI
winget install Microsoft.AzureCLI

# Optional: Docker Desktop
winget install Docker.DockerDesktop
```
</details>

<details>
<summary><strong>Linux (Ubuntu/Debian)</strong></summary>

```bash
# Python 3.11+
sudo apt update && sudo apt install python3.11 python3.11-venv python3-pip

# Verify
python3.11 --version    # Python 3.11.x

# Optional: Azure CLI
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Optional: Docker
sudo apt install docker.io docker-compose
```
</details>

### Azure Services Required

| Service | Purpose | Required for Local Dev? |
|---------|---------|------------------------|
| Azure OpenAI (GPT-4o) | Answer generation | ✅ Yes (for /query) |
| Azure OpenAI (text-embedding-3-large) | Vector embeddings | ✅ Yes (for indexing + search) |
| Azure AI Search | Hybrid retrieval | ✅ Yes (for /query) |
| Azure Cosmos DB | Audit logging | ❌ No (logs warning on failure) |
| Azure Container Apps | Production hosting | ❌ No (FastAPI local) |

---

## Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/maneeshkumar52/hr-policy-rag.git
cd hr-policy-rag

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate    # macOS/Linux
# .venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your Azure credentials:

```bash
AZURE_OPENAI_ENDPOINT=https://your-openai.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-large
AZURE_SEARCH_ENDPOINT=https://your-search.search.windows.net
AZURE_SEARCH_API_KEY=your-search-key
JWT_SECRET=change-me-in-production
```

### 3. Index HR Policy Documents

```bash
python -m indexer.index_documents
```

Expected output:
```
Index 'hr-policies' created/updated.
Indexed 47 chunks from indexer/documents
```

### 4. Run the Server

```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. Query HR Policies

```bash
# Create a test token
TOKEN=$(python -c "from src.auth import create_test_token; print(create_test_token('user-001', 'employee'))")

# Ask a question
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"question": "What is the remote work policy?"}'
```

### 6. Run the Demo Script

```bash
python demo_e2e.py
```

---

## Indexing Pipeline

### How Documents Are Indexed

```
  indexer/documents/*.md
         │
         ▼
  ┌──────────────────┐
  │ RecursiveChunker  │     Parameters:
  │                    │     • chunk_size: 1000 chars
  │  Separators:       │     • chunk_overlap: 200 chars
  │  1. \n\n (¶¶)     │     • min_chunk: 50 chars
  │  2. \n   (¶)       │
  │  3. ". " (sent)    │
  │  4. " "  (word)    │
  └────────┬───────────┘
           │
           ▼
  ┌──────────────────┐
  │ AzureOpenAI      │     text-embedding-3-large
  │ Embeddings       │     → 3072-dimensional vectors
  └────────┬───────────┘
           │
           ▼
  ┌──────────────────┐
  │ Azure AI Search  │     Index fields:
  │ Batch Upload     │     • id, title, content (searchable)
  │ (100 docs/batch) │     • content_vector (3072-dim HNSW)
  │                  │     • clearance_level (filterable)
  └──────────────────┘     • semantic config (title + content)
```

### Clearance Level Detection

Documents containing specific markers are assigned higher clearance levels:

```python
if "clearance_level: manager" in text:
    clearance_level = 2   # Manager-only policies
elif "clearance_level: hr_admin" in text:
    clearance_level = 3   # HR admin-only policies
else:
    clearance_level = 1   # Employee-visible (default)
```

### Azure AI Search Index Schema

| Field | Type | Searchable | Filterable | Vector |
|-------|------|:----------:|:----------:|:------:|
| `id` | String (key) | ❌ | ❌ | ❌ |
| `title` | String | ✅ | ❌ | ❌ |
| `content` | String | ✅ | ❌ | ❌ |
| `source_file` | String | ❌ | ❌ | ❌ |
| `category` | String | ❌ | ✅ | ❌ |
| `clearance_level` | Int32 | ❌ | ✅ | ❌ |
| `chunk_index` | Int32 | ❌ | ❌ | ❌ |
| `content_vector` | Collection(Single) | ✅ | ❌ | ✅ (3072-dim HNSW) |

---

## Project Structure

```
hr-policy-rag/
├── demo_e2e.py                          # End-to-end demo (auth + chunking)
├── requirements.txt                     # Python dependencies (16 packages)
├── .env.example                         # Environment variable template
├── src/                                 # Core application
│   ├── __init__.py
│   ├── config.py                        # Pydantic Settings — 16 env vars
│   ├── models.py                        # 5 Pydantic models, 1 dataclass
│   ├── retriever.py                     # Hybrid vector+keyword retriever
│   ├── generator.py                     # GPT-4o grounded response generator
│   ├── auth.py                          # JWT validation + RBAC clearance
│   ├── audit.py                         # Cosmos DB audit logger
│   └── api/
│       ├── __init__.py
│       └── main.py                      # FastAPI app, endpoints, logging
├── indexer/                             # Offline document processing
│   ├── chunker.py                       # Recursive text chunker
│   ├── index_documents.py              # Batch indexing to Azure AI Search
│   └── documents/                       # HR policy source documents
│       ├── benefits_guide.md
│       ├── code_of_conduct.md
│       ├── expense_policy.md
│       ├── parental_leave_policy.md
│       └── remote_work_policy.md
├── tests/                               # Test suite
│   ├── __init__.py
│   ├── test_auth.py                     # 5 JWT/RBAC tests
│   ├── test_e2e.py                      # 2 API integration tests
│   └── test_retriever.py               # 2 retriever tests with mocking
└── infra/                               # Deployment
    ├── Dockerfile                       # Python 3.11 slim image
    └── azure-deploy.sh                  # ACR + Container Apps script
```

### Module Responsibility Matrix

| Module | Responsibility | Dependencies | Lines |
|--------|---------------|-------------|-------|
| `src/api/main.py` | FastAPI app, `/query` endpoint, structured logging | All src modules | 110 |
| `src/config.py` | Environment config via Pydantic Settings | `pydantic_settings` | 33 |
| `src/models.py` | 5 Pydantic models — all data contracts | `pydantic` | 43 |
| `src/retriever.py` | Hybrid vector+keyword search with RBAC filter | `openai`, `azure-search` | 89 |
| `src/generator.py` | GPT-4o grounded generation with confidence | `openai`, `models` | 99 |
| `src/auth.py` | JWT decode, RBAC mapping, mock users | `python-jose` | 78 |
| `src/audit.py` | Cosmos DB audit logging with 7-year TTL | `azure-cosmos` | 37 |
| `indexer/chunker.py` | Recursive text chunking with overlap | None | 59 |
| `indexer/index_documents.py` | Embed + upload chunks to Azure AI Search | `openai`, `azure-search` | 92 |
| `demo_e2e.py` | End-to-end demo of auth, chunking, policies | `src/*`, `indexer/*` | 61 |

---

## Configuration Reference

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `AZURE_OPENAI_ENDPOINT` | `https://your-openai.openai.azure.com/` | ✅ | Azure OpenAI service endpoint |
| `AZURE_OPENAI_API_KEY` | `your-key` | ✅ | Azure OpenAI API key |
| `AZURE_OPENAI_API_VERSION` | `2024-02-01` | ❌ | OpenAI API version |
| `AZURE_OPENAI_DEPLOYMENT` | `gpt-4o` | ❌ | Chat completion model deployment |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | `text-embedding-3-large` | ❌ | Embedding model deployment |
| `AZURE_SEARCH_ENDPOINT` | `https://your-search.search.windows.net` | ✅ | Azure AI Search endpoint |
| `AZURE_SEARCH_API_KEY` | `your-search-key` | ✅ | Azure AI Search admin key |
| `AZURE_SEARCH_INDEX_NAME` | `hr-policies` | ❌ | Search index name |
| `COSMOS_ENDPOINT` | `https://your-cosmos.documents.azure.com:443/` | ❌ | Cosmos DB endpoint |
| `COSMOS_KEY` | `your-cosmos-key` | ❌ | Cosmos DB key |
| `COSMOS_DATABASE` | `hr-rag` | ❌ | Cosmos DB database name |
| `COSMOS_CONTAINER` | `audit-logs` | ❌ | Cosmos DB container name |
| `JWT_SECRET` | `dev-secret-change-in-production` | ✅ Prod | JWT signing secret |
| `JWT_ALGORITHM` | `HS256` | ❌ | JWT algorithm |
| `COMPANY_NAME` | `Contoso Corporation` | ❌ | Company name in prompts |
| `LOG_LEVEL` | `INFO` | ❌ | Logging level |

---

## API Reference

### `GET /health`

Health check endpoint.

**Response** `200 OK`:
```json
{"status": "healthy", "service": "hr-policy-rag", "version": "1.0.0"}
```

### `POST /query`

Submit an HR policy question. Requires JWT Bearer token.

**Headers**:
```
Authorization: Bearer <jwt_token>
Content-Type: application/json
```

**Request Body**:
```json
{
    "question": "How many weeks of parental leave do I get?",  // Required, min 5 chars
    "session_id": "optional-session-uuid"                       // Optional, auto-generated
}
```

**Response** `200 OK`:
```json
{
    "answer": "According to the Parental Leave Policy...",
    "sources": ["Parental Leave Policy", "Benefits Guide"],
    "confidence": "High",
    "query_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

**Error Responses**:
| Code | Cause |
|------|-------|
| `401` | Missing, invalid, or expired JWT token |
| `422` | Question shorter than 5 characters |
| `500` | Internal processing error |

---

## RBAC & Authentication

### Clearance Levels

| Role | Clearance | Document Access | Example User |
|------|:---------:|----------------|-------------|
| `employee` | 1 | General policies only | `alice@contoso.com` (user-001) |
| `manager` | 2 | General + management policies | `bob@contoso.com` (user-002) |
| `hr_admin` | 3 | All policies including HR-confidential | `carol@contoso.com` (user-003) |

### JWT Token Flow

```
  1. Client creates/receives JWT:
     {"sub": "user-001", "role": "employee"}
     Signed with HS256 + JWT_SECRET

  2. Client sends:
     Authorization: Bearer eyJhbGciOiJIUzI1NiI...

  3. validate_token() decodes:
     ├─ Verify HS256 signature
     ├─ Extract sub → user_id
     ├─ Lookup in MOCK_USERS (if exists)
     └─ Or create UserContext from JWT claims

  4. UserContext used for:
     ├─ RBAC filter: "clearance_level le {N}"
     ├─ Audit record: user_id, user_role
     └─ Logging: user identification
```

### Mock Users (Development)

| User ID | Email | Role | Clearance |
|---------|-------|------|:---------:|
| `user-001` | alice@contoso.com | employee | 1 |
| `user-002` | bob@contoso.com | manager | 2 |
| `user-003` | carol@contoso.com | hr_admin | 3 |

### Creating Test Tokens

```python
from src.auth import create_test_token

# Employee token
token = create_test_token("user-001", "employee")

# Manager token
token = create_test_token("user-002", "manager")

# HR admin token
token = create_test_token("user-003", "hr_admin")
```

---

## Testing

### Run Tests

```bash
pytest tests/ -v
```

### Test Coverage

| Test File | Tests | What It Verifies |
|-----------|:-----:|-----------------|
| `test_auth.py` | 5 | JWT creation, validation, RBAC levels, invalid token rejection, dev fallback |
| `test_e2e.py` | 2 | Health endpoint, query validation (min 5 chars) |
| `test_retriever.py` | 2 | Search result parsing, embedding failure graceful handling |

### Mocking Strategy

```python
# External services are mocked at the boundary:
with patch("src.retriever.AsyncAzureOpenAI"),     # Mock embeddings
     patch("src.retriever.SearchClient"),           # Mock Azure AI Search
     patch("src.generator.AsyncAzureOpenAI"),       # Mock GPT-4o
     patch("src.audit.CosmosClient", create=True):  # Mock Cosmos DB
```

---

## Deployment

### Docker

```bash
cd infra
docker build -t hr-policy-rag .
docker run -p 8000:8000 --env-file ../.env hr-policy-rag
```

### Azure Container Apps

```bash
chmod +x infra/azure-deploy.sh
./infra/azure-deploy.sh
```

The script:
1. Creates resource group `rg-hr-rag` in `uksouth`
2. Creates Azure Container Registry
3. Builds and pushes Docker image
4. Creates Container Apps environment
5. Deploys with external ingress, 1-5 replicas, port 8000

---

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| `401 Invalid or expired token` | JWT signature mismatch | Ensure `JWT_SECRET` matches between token creation and validation |
| `422 Unprocessable Entity` | Question < 5 characters | Provide at least 5 characters in question |
| Empty sources in response | Azure AI Search not indexed | Run `python -m indexer.index_documents` first |
| "Contact HR directly" fallback | Azure OpenAI API failure | Check `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_API_KEY` |
| Confidence always "Low" | No relevant documents found | Re-index documents, verify search index exists |
| `audit_write_failed` in logs | Cosmos DB not configured | Set `COSMOS_ENDPOINT` and `COSMOS_KEY` (non-blocking) |
| `embedding_failed` in logs | Wrong embedding deployment name | Verify `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` |
| Manager can't see L2 docs | Documents not marked with clearance | Add `clearance_level: manager` to document text |
| Search returns no results | Index empty or wrong index name | Check `AZURE_SEARCH_INDEX_NAME` matches indexed index |
| `no_auth_header_using_dev_user` warning | No Authorization header sent | Expected in dev; use JWT in production |

---

## Azure Production Mapping

| Local Component | Azure Production Service | Purpose |
|----------------|-------------------------|---------|
| `uvicorn src.api.main:app` | Azure Container Apps | Serverless container hosting |
| `AsyncAzureOpenAI` (chat) | Azure OpenAI Service (GPT-4o) | Answer generation |
| `AsyncAzureOpenAI` (embed) | Azure OpenAI (text-embedding-3-large) | Vector embeddings |
| `SearchClient` | Azure AI Search (semantic) | Hybrid retrieval + RBAC |
| `CosmosClient` | Azure Cosmos DB (NoSQL) | Audit trail (7-year TTL) |
| `JWT_SECRET` env var | Azure Key Vault | Secrets management |
| `structlog` JSON output | Application Insights + Log Analytics | Observability |
| `Dockerfile` | Azure Container Registry | Image storage |
| `azure-deploy.sh` | Azure CLI | Infrastructure provisioning |
| — | Azure Monitor Alerts | SLA monitoring |
| — | Azure AD (Entra ID) | Production JWT issuer |

---

## Production Checklist

### Security

| # | Item | Status | Notes |
|---|------|--------|-------|
| 1 | Replace `JWT_SECRET` with Key Vault reference | ⬜ | `@Microsoft.KeyVault(SecretUri=...)` |
| 2 | Replace `AZURE_OPENAI_API_KEY` with Managed Identity | ⬜ | `DefaultAzureCredential` |
| 3 | Replace `AZURE_SEARCH_API_KEY` with Managed Identity | ⬜ | `DefaultAzureCredential` |
| 4 | Replace `COSMOS_KEY` with Managed Identity | ⬜ | `DefaultAzureCredential` |
| 5 | Remove `allow_origins=["*"]` CORS | ⬜ | Restrict to known frontends |
| 6 | Replace mock users with Azure AD/Entra ID | ⬜ | Real JWT issuer validation |
| 7 | Add rate limiting on `/query` | ⬜ | Azure API Management or WAF |
| 8 | Validate question text for prompt injection | ⬜ | Input sanitization layer |

### Reliability

| # | Item | Status | Notes |
|---|------|--------|-------|
| 9 | Add circuit breaker for Azure OpenAI | ⬜ | `tenacity` with exponential backoff |
| 10 | Set embedding timeout (currently default) | ⬜ | 30s timeout for embeddings |
| 11 | Add health checks for Azure AI Search | ⬜ | Verify index exists on startup |
| 12 | Handle Cosmos DB write failures with retry | ⬜ | Currently fire-and-forget |
| 13 | Container Apps auto-scaling: 1-5 replicas | ✅ | Set in `azure-deploy.sh` |

### Observability

| # | Item | Status | Notes |
|---|------|--------|-------|
| 14 | Dashboard: query volume, avg latency, confidence distribution | ⬜ | Azure Monitor Workbook |
| 15 | Alert: latency > 5s (P95) | ⬜ | Indicates OpenAI slowdown |
| 16 | Alert: confidence "Low" rate > 20% | ⬜ | Indicates retrieval quality issues |
| 17 | Alert: audit write failures > 0 | ⬜ | Cosmos DB connectivity |
| 18 | Token usage cost tracking dashboard | ⬜ | From `estimated_cost_usd` in audit |

---

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| **Runtime** | Python | 3.11+ |
| **Web Framework** | FastAPI | 0.111.0 |
| **ASGI Server** | Uvicorn | 0.30.0 |
| **LLM** | Azure OpenAI (GPT-4o) | API 2024-02-01 |
| **Embeddings** | Azure OpenAI (text-embedding-3-large) | 3072 dims |
| **Search** | Azure AI Search | 11.4.0 |
| **Audit Store** | Azure Cosmos DB | 4.7.0 |
| **Identity** | Azure Identity | 1.16.0 |
| **Auth** | python-jose (JWT) | 3.3.0 |
| **Validation** | Pydantic | 2.7.0 |
| **Configuration** | pydantic-settings | 2.3.0 |
| **Logging** | structlog | 24.2.0 |
| **HTTP Client** | httpx | 0.27.0 |
| **Templates** | Jinja2 | 3.1.4 |
| **Testing** | pytest + pytest-asyncio | 8.2.0 / 0.23.0 |
| **Container** | Docker (Python 3.11 slim) | — |
| **Hosting** | Azure Container Apps | — |

---

## License

MIT — see [LICENSE](LICENSE) for details.

---

<div align="center">

**Built by [Maneesh Kumar](https://github.com/maneeshkumar52)**

*Prompt to Production*

*Enterprise HR policy Q&A with RBAC clearance filtering, grounded generation, and compliance-grade audit logging.*

</div>