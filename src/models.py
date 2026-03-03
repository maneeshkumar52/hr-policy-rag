"""Pydantic models for the HR RAG system."""
from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
import uuid


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=5, description="HR policy question")
    session_id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))


class SourceDocument(BaseModel):
    title: str
    content_snippet: str
    relevance_score: float


class QueryResponse(BaseModel):
    answer: str
    sources: List[str]
    confidence: str = Field(..., description="High, Medium, or Low")
    query_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class UserContext(BaseModel):
    user_id: str
    email: str
    role: str
    department: str
    clearance_level: int = Field(default=1, ge=1, le=3)


class AuditRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    user_id: str
    user_role: str
    question: str
    answer: str
    sources: List[str]
    confidence: str
    latency_ms: float
    token_usage: Dict[str, int] = Field(default_factory=dict)
