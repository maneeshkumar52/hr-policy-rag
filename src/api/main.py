"""FastAPI application for the HR Policy RAG system."""
import time
import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import structlog

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

from src.models import QueryRequest, QueryResponse, AuditRecord, UserContext
from src.auth import validate_token
from src.retriever import HybridRetriever
from src.generator import GroundedGenerator
from src.audit import AuditLogger

retriever: HybridRetriever = None
generator: GroundedGenerator = None
auditor: AuditLogger = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global retriever, generator, auditor
    retriever = HybridRetriever()
    generator = GroundedGenerator()
    auditor = AuditLogger()
    logger.info("hr_rag_system_starting")
    yield
    logger.info("hr_rag_system_stopping")


app = FastAPI(
    title="HR Policy RAG System",
    description="Enterprise HR Policy Q&A with RBAC and audit logging — Project 1, Chapter 20, Prompt to Production",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "hr-policy-rag", "version": "1.0.0"}


@app.post("/query", response_model=QueryResponse)
async def query_hr_policy(
    request: QueryRequest,
    user: UserContext = Depends(validate_token),
) -> QueryResponse:
    """
    Query HR policies with RBAC and audit logging.

    Requires a valid Bearer token in Authorization header.
    Returns grounded answer with source citations.
    """
    start_time = time.time()

    try:
        # Retrieve relevant documents
        docs = await retriever.search(
            query=request.question,
            user_context=user,
            top_k=5,
        )

        # Generate grounded response
        answer, confidence, token_usage = await generator.generate(
            question=request.question,
            retrieved_docs=docs,
            user_context=user,
        )

        latency_ms = (time.time() - start_time) * 1000

        # Build response
        sources = [doc.title for doc in docs]
        response = QueryResponse(
            answer=answer,
            sources=sources,
            confidence=confidence,
        )

        # Audit log
        audit_record = AuditRecord(
            user_id=user.user_id,
            user_role=user.role,
            question=request.question,
            answer=answer,
            sources=sources,
            confidence=confidence,
            latency_ms=round(latency_ms, 2),
            token_usage=token_usage,
        )
        await auditor.log_query(audit_record)

        logger.info(
            "query_processed",
            user_id=user.user_id,
            confidence=confidence,
            latency_ms=round(latency_ms, 2),
        )
        return response

    except Exception as exc:
        logger.error("query_failed", error=str(exc), user_id=user.user_id)
        raise HTTPException(status_code=500, detail="Failed to process query")
