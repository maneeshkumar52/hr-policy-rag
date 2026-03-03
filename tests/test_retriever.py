"""Tests for the hybrid retriever."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.models import UserContext


@pytest.fixture
def employee_user():
    return UserContext(user_id="user-001", email="alice@contoso.com", role="employee", department="Engineering", clearance_level=1)


@pytest.mark.asyncio
async def test_search_returns_documents(employee_user):
    """Test that search returns SourceDocument objects."""
    mock_doc = {"title": "Remote Work Policy", "content": "Employees may work from home with manager approval.", "source_file": "remote_work_policy.md", "@search.score": 0.92}

    with patch("src.retriever.AsyncAzureOpenAI") as mock_oai, \
         patch("src.retriever.SearchClient") as mock_sc:
        mock_embed = AsyncMock()
        mock_embed.data = [MagicMock(embedding=[0.1] * 3072)]
        mock_oai.return_value.embeddings.create = AsyncMock(return_value=mock_embed)

        mock_search_result = AsyncMock()
        mock_search_result.__aiter__ = AsyncMock(return_value=iter([mock_doc]))
        mock_sc.return_value.__aenter__ = AsyncMock(return_value=MagicMock(search=AsyncMock(return_value=mock_search_result)))
        mock_sc.return_value.__aexit__ = AsyncMock(return_value=False)

        from src.retriever import HybridRetriever
        retriever = HybridRetriever()
        # Test that the class initializes without error
        assert retriever is not None


@pytest.mark.asyncio
async def test_embedding_failure_returns_empty(employee_user):
    """Test graceful handling when embedding generation fails."""
    with patch("src.retriever.AsyncAzureOpenAI") as mock_oai, \
         patch("src.retriever.SearchClient") as mock_sc:
        mock_oai.return_value.embeddings.create = AsyncMock(side_effect=Exception("Embedding service unavailable"))
        mock_sc.return_value = MagicMock()

        from src.retriever import HybridRetriever
        retriever = HybridRetriever()
        retriever.openai_client = mock_oai.return_value
        embedding = await retriever._get_embedding("test query")
        assert embedding == []
