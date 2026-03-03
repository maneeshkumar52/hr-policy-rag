"""End-to-end tests for the HR RAG API."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from src.auth import create_test_token


def test_health_endpoint():
    """Test health check returns 200."""
    with patch("src.retriever.AsyncAzureOpenAI"), \
         patch("src.retriever.SearchClient"), \
         patch("src.generator.AsyncAzureOpenAI"), \
         patch("src.audit.CosmosClient", create=True):
        from src.api.main import app
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


def test_query_requires_valid_question():
    """Test that short questions are rejected."""
    with patch("src.retriever.AsyncAzureOpenAI"), \
         patch("src.retriever.SearchClient"), \
         patch("src.generator.AsyncAzureOpenAI"):
        from src.api.main import app
        client = TestClient(app)
        token = create_test_token("user-001")
        response = client.post("/query", json={"question": "hi"}, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 422
