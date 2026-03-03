"""Azure AI Search hybrid retrieval with RBAC filtering."""
import structlog
from typing import List, Optional
from openai import AsyncAzureOpenAI
from azure.search.documents.aio import SearchClient
from azure.search.documents.models import VectorizedQuery
from azure.core.credentials import AzureKeyCredential
from src.config import get_settings
from src.models import SourceDocument, UserContext

logger = structlog.get_logger(__name__)


class HybridRetriever:
    """Performs hybrid vector+keyword search with RBAC filtering."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.openai_client = AsyncAzureOpenAI(
            azure_endpoint=self.settings.azure_openai_endpoint,
            api_key=self.settings.azure_openai_api_key,
            api_version=self.settings.azure_openai_api_version,
        )
        self.search_client = SearchClient(
            endpoint=self.settings.azure_search_endpoint,
            index_name=self.settings.azure_search_index_name,
            credential=AzureKeyCredential(self.settings.azure_search_api_key),
        )

    async def _get_embedding(self, text: str) -> List[float]:
        """Generate text embedding."""
        try:
            response = await self.openai_client.embeddings.create(
                input=text,
                model=self.settings.azure_openai_embedding_deployment,
            )
            return response.data[0].embedding
        except Exception as exc:
            logger.error("embedding_failed", error=str(exc))
            return []

    async def search(self, query: str, user_context: UserContext, top_k: int = 5) -> List[SourceDocument]:
        """
        Perform hybrid search with RBAC clearance filtering.

        Args:
            query: Search query text.
            user_context: Authenticated user with clearance level.
            top_k: Number of results to return.

        Returns:
            List of relevant documents the user is authorized to see.
        """
        logger.info("search_started", query=query[:80], clearance=user_context.clearance_level)

        try:
            embedding = await self._get_embedding(query)
            clearance_filter = f"clearance_level le {user_context.clearance_level}"

            search_kwargs = {
                "search_text": query,
                "top": top_k,
                "filter": clearance_filter,
                "select": ["title", "content", "source_file"],
                "query_type": "semantic",
                "semantic_configuration_name": "default",
            }

            if embedding:
                vector_query = VectorizedQuery(
                    vector=embedding,
                    k_nearest_neighbors=top_k,
                    fields="content_vector",
                )
                search_kwargs["vector_queries"] = [vector_query]

            results = []
            async with self.search_client as client:
                async for doc in await client.search(**search_kwargs):
                    results.append(SourceDocument(
                        title=doc.get("title", "HR Policy"),
                        content_snippet=doc.get("content", "")[:300],
                        relevance_score=doc.get("@search.score", 0.0),
                    ))

            logger.info("search_complete", results=len(results))
            return results

        except Exception as exc:
            logger.error("search_failed", error=str(exc))
            return []
