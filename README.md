# HR Policy RAG System

**Project 1, Chapter 20 — Prompt to Production by Maneesh Kumar**

An enterprise-grade Retrieval-Augmented Generation (RAG) system for querying HR policies using
Azure OpenAI, Azure AI Search, and Cosmos DB, with JWT-based RBAC and full audit logging.

---

## Architecture

```
Employee/Manager
      │
      ▼ HTTPS + Bearer JWT
┌─────────────────────────────┐
│   FastAPI (src/api/main.py) │
│   - /health                 │
│   - /query (POST)           │
└──────┬──────────────────────┘
       │
       ├──► Auth (src/auth.py)
       │    JWT decode → UserContext + clearance_level
       │
       ├──► Retriever (src/retriever.py)
       │    Azure OpenAI embeddings → Azure AI Search
       │    Hybrid (vector + keyword) with RBAC filter
       │
       ├──► Generator (src/generator.py)
       │    GPT-4o grounded generation from retrieved docs
       │    Confidence scoring
       │
       └──► Audit (src/audit.py)
            Cosmos DB — immutable audit log (7-year TTL)
```

**Azure Services Used:**

| Service               | Purpose                               |
|-----------------------|---------------------------------------|
| Azure OpenAI (GPT-4o) | Answer generation                     |
| Azure OpenAI Embeddings | text-embedding-3-large (3072-dim)  |
| Azure AI Search       | Hybrid vector + keyword retrieval     |
| Azure Cosmos DB       | Compliance audit logging              |
| Azure Container Apps  | Serverless hosting                    |
| Azure Container Registry | Docker image storage              |

---

## Prerequisites

- Python 3.11+
- Azure subscription with the following resources provisioned:
  - Azure OpenAI resource (GPT-4o + text-embedding-3-large deployments)
  - Azure AI Search (Standard tier recommended for semantic search)
  - Azure Cosmos DB (serverless)
- Azure CLI installed (for deployment)

---

## Local Development Setup

### 1. Clone and install dependencies

```bash
git clone <repo-url>
cd hr-policy-rag
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
# Edit .env with your Azure resource endpoints and keys
```

### 3. Index HR documents into Azure AI Search

```bash
python -m indexer.index_documents
```

This will:
- Create (or update) the `hr-policies` search index with vector search and semantic configuration
- Chunk and embed all 5 HR policy documents from `indexer/documents/`
- Upload all document chunks to Azure AI Search

### 4. Run the API server

```bash
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`.
Interactive docs: `http://localhost:8000/docs`

---

## API Usage

### Get a development JWT token

The system includes a helper to generate test tokens for the three mock users:

```python
from src.auth import create_test_token

# employee (clearance level 1)
token_employee = create_test_token("user-001")

# manager (clearance level 2)
token_manager = create_test_token("user-002")

# hr_admin (clearance level 3)
token_admin = create_test_token("user-003")

print(token_employee)
```

Or generate one inline:

```bash
python -c "from src.auth import create_test_token; print(create_test_token('user-001'))"
```

### Health check

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "hr-policy-rag",
  "version": "1.0.0"
}
```

### Query HR policies

```bash
TOKEN=$(python -c "from src.auth import create_test_token; print(create_test_token('user-001'))")

curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"question": "How many weeks of maternity leave am I entitled to?"}'
```

Expected response:
```json
{
  "answer": "According to the Parental Leave Policy (HR-PL-001), you are entitled to up to 52 weeks of maternity leave. This is divided into Ordinary Maternity Leave (OML) covering the first 26 weeks, and Additional Maternity Leave (AML) covering the remaining 26 weeks. Contoso enhances Statutory Maternity Pay to full pay for the first 16 weeks.",
  "sources": [
    "Parental Leave Policy"
  ],
  "confidence": "High",
  "query_id": "a3f2c1e8-7b4d-4e2a-9f1c-2d8b3e4f5a6c"
}
```

### Example queries by role

```bash
# Employee: general policy question
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the meal allowance for business travel?"}'

# Employee: remote work
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "Can I work from Spain for two weeks?"}'

# Employee: benefits
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "Does the company match my pension contributions?"}'
```

---

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pip install pytest-cov
pytest tests/ -v --cov=src --cov-report=term-missing

# Run specific test file
pytest tests/test_auth.py -v
```

---

## Azure Deployment

### Prerequisites

```bash
az login
az extension add --name containerapp
```

### Deploy using the provided script

```bash
chmod +x infra/azure-deploy.sh
./infra/azure-deploy.sh
```

This script will:
1. Create a resource group `rg-hr-rag` in UK South
2. Build and push the Docker image to Azure Container Registry
3. Create an Azure Container Apps environment
4. Deploy the app with auto-scaling (1–5 replicas)

### Set environment variables in Container Apps

After deployment, set your secrets:

```bash
az containerapp secret set \
  --name hr-policy-rag \
  --resource-group rg-hr-rag \
  --secrets \
    azure-openai-key=<your-key> \
    azure-search-key=<your-key> \
    cosmos-key=<your-key> \
    jwt-secret=<your-secret>

az containerapp update \
  --name hr-policy-rag \
  --resource-group rg-hr-rag \
  --set-env-vars \
    AZURE_OPENAI_API_KEY=secretref:azure-openai-key \
    AZURE_SEARCH_API_KEY=secretref:azure-search-key \
    COSMOS_KEY=secretref:cosmos-key \
    JWT_SECRET=secretref:jwt-secret
```

---

## Cost Breakdown (Estimated Monthly)

| Resource                     | SKU/Tier         | Estimated Cost (USD) |
|------------------------------|------------------|----------------------|
| Azure OpenAI (GPT-4o)        | Pay-as-you-go    | ~$30 (500 queries/day) |
| Azure OpenAI Embeddings      | Pay-as-you-go    | ~$5                  |
| Azure AI Search              | Standard S1      | ~$250                |
| Azure Cosmos DB              | Serverless       | ~$5                  |
| Azure Container Apps         | Consumption plan | ~$20                 |
| Azure Container Registry     | Basic            | ~$5                  |
| **Total**                    |                  | **~$315/month**      |

*Costs vary by usage. Search tier can be reduced to Basic for development (~$75/month).*

---

## Project Structure

```
hr-policy-rag/
├── src/
│   ├── api/main.py          # FastAPI app, /health and /query endpoints
│   ├── auth.py              # JWT validation, RBAC, mock user store
│   ├── retriever.py         # Azure AI Search hybrid retrieval
│   ├── generator.py         # GPT-4o grounded response generation
│   ├── audit.py             # Cosmos DB compliance audit logger
│   ├── config.py            # pydantic-settings configuration
│   └── models.py            # Pydantic request/response models
├── indexer/
│   ├── index_documents.py   # Batch indexing pipeline
│   ├── chunker.py           # Recursive text chunker
│   └── documents/           # HR policy source documents (Markdown)
├── tests/
│   ├── test_auth.py         # JWT and RBAC unit tests
│   ├── test_retriever.py    # Retriever unit tests (mocked)
│   └── test_e2e.py          # End-to-end API tests
├── infra/
│   ├── Dockerfile           # Container image definition
│   └── azure-deploy.sh      # One-command Azure deployment
├── .env.example             # Environment variable template
└── requirements.txt         # Python dependencies
```

---

## Security Considerations

- JWT tokens are validated on every request; tokens expire per the configured algorithm
- RBAC clearance levels (1=employee, 2=manager, 3=hr_admin) are enforced at retrieval time via Azure AI Search filters
- All queries and responses are written to Cosmos DB audit log with 7-year TTL for compliance
- The `.env` file is excluded from version control; never commit real credentials
- VPN should be enforced for production Container Apps using VNET integration

---

## Book Reference

This project is **Project 1 from Chapter 20** of:

> **Prompt to Production** by Maneesh Kumar
> Building production-grade AI systems with Azure OpenAI and the Azure ecosystem.

The system demonstrates the following Chapter 20 concepts:
- Hybrid RAG architecture (vector + keyword search)
- Role-Based Access Control (RBAC) in RAG pipelines
- Grounded generation with confidence scoring
- Compliance-grade audit logging
- Enterprise deployment with Azure Container Apps
