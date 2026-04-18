# HR Policy RAG

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

HR policy RAG assistant for grounded employee policy answers with retrieval auditability, JWT authentication, and HIPAA-style governance controls — powered by Azure OpenAI, Azure AI Search, and Cosmos DB.

## Architecture

```
HR Policy Documents
        │
        ▼
┌──────────────────────────┐
│  Indexer Pipeline        │
│  chunker.py → embeddings │──► Azure AI Search (vector index)
└──────────────────────────┘

Employee Query
        │
        ▼
┌───────────────────────────────────────┐
│  FastAPI Service (:8000)              │
│                                       │
│  Auth (JWT) ──► validate_user()       │
│       │                               │
│  Retriever ──► Azure AI Search        │──► Hybrid vector + keyword search
│       │                               │
│  Generator ──► Azure OpenAI (GPT-4o)  │──► Grounded answer with citations
│       │                               │
│  AuditLogger ──► Cosmos DB            │──► Full query audit trail
└───────────────────────────────────────┘
```

## Key Features

- **Grounded Policy Answers** — RAG pipeline retrieves relevant policy chunks before generating answers, ensuring responses are backed by actual documents
- **JWT Authentication** — Token-based auth with role validation for employee access control
- **Audit Logging** — Every query, retrieved context, and generated answer is logged to Cosmos DB for compliance
- **Hybrid Search** — Combines vector similarity and keyword matching via Azure AI Search
- **Policy Chunking** — Smart document chunking with metadata preservation for accurate retrieval
- **Multi-Tenant Ready** — Cosmos DB partitioning supports multi-organization deployments

## Step-by-Step Flow

### Step 1: Policy Ingestion
Run `indexer/index_documents.py` to chunk HR policy documents from `indexer/documents/` using `chunker.py`, embed them, and index in Azure AI Search.

### Step 2: Employee Authenticates
Employee sends a JWT token. `auth.py` validates the token and extracts user context (employee_id, role, department).

### Step 3: Query Submission
Employee submits a policy question via the API.

### Step 4: Retrieval
`Retriever` performs hybrid search against Azure AI Search, returning the most relevant policy chunks with relevance scores.

### Step 5: Answer Generation
`Generator` sends the retrieved context + query to GPT-4o with a system prompt that enforces grounded answers with citations.

### Step 6: Audit Trail
`AuditLogger` writes the full interaction (query, retrieved chunks, generated answer, user context) to Cosmos DB.

## Repository Structure

```
hr-policy-rag/
├── src/
│   ├── api/                     # API route definitions
│   ├── retriever.py             # Azure AI Search hybrid retrieval
│   ├── generator.py             # GPT-4o grounded answer generation
│   ├── auth.py                  # JWT authentication
│   ├── audit.py                 # Cosmos DB audit logging
│   ├── models.py                # Pydantic models
│   └── config.py                # Environment settings
├── indexer/
│   ├── index_documents.py       # Document indexing pipeline
│   ├── chunker.py               # Policy document chunker
│   └── documents/               # Sample HR policy documents
├── tests/
│   ├── test_auth.py
│   ├── test_retriever.py
│   └── test_e2e.py
├── infra/
│   ├── Dockerfile
│   └── azure-deploy.sh
├── demo_e2e.py
├── requirements.txt
└── .env.example
```

## Quick Start

```bash
git clone https://github.com/maneeshkumar52/hr-policy-rag.git
cd hr-policy-rag
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Configure Azure + JWT credentials
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

## Configuration

| Variable | Description |
|----------|-------------|
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint |
| `AZURE_OPENAI_DEPLOYMENT` | Model deployment (gpt-4o) |
| `AZURE_SEARCH_ENDPOINT` | Azure AI Search endpoint |
| `AZURE_SEARCH_INDEX_NAME` | Index name (hr-policies) |
| `COSMOS_ENDPOINT` | Cosmos DB endpoint for audit logs |
| `COSMOS_DATABASE` | Database name (hr-rag) |
| `JWT_SECRET` | JWT signing secret |

## Testing

```bash
pytest -q
python demo_e2e.py
```

## License

MIT
