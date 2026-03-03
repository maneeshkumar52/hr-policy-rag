"""Grounded response generation for HR queries."""
import time
import structlog
from typing import List, Tuple, Dict
from openai import AsyncAzureOpenAI
from src.config import get_settings
from src.models import SourceDocument, UserContext

logger = structlog.get_logger(__name__)

SYSTEM_PROMPT_TEMPLATE = """You are an HR policy assistant for {company_name}.
Answer questions ONLY based on the provided HR policy documents.
Always cite the specific policy document and section when referencing information.
If the answer is not in the provided documents, say so clearly.
Never fabricate policy information or make assumptions about policies not in the documents.
Be concise, helpful, and professional."""


class GroundedGenerator:
    """Generates grounded responses from retrieved HR documents."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = AsyncAzureOpenAI(
            azure_endpoint=self.settings.azure_openai_endpoint,
            api_key=self.settings.azure_openai_api_key,
            api_version=self.settings.azure_openai_api_version,
            max_retries=3,
        )

    def _compute_confidence(self, docs: List[SourceDocument]) -> str:
        """Determine confidence level based on retrieved documents."""
        if not docs:
            return "Low"
        high_score_docs = [d for d in docs if d.relevance_score > 0.8]
        if len(high_score_docs) >= 3:
            return "High"
        elif len(docs) >= 1:
            return "Medium"
        return "Low"

    async def generate(
        self,
        question: str,
        retrieved_docs: List[SourceDocument],
        user_context: UserContext,
    ) -> Tuple[str, str, Dict]:
        """
        Generate a grounded answer from retrieved documents.

        Args:
            question: The user's HR question.
            retrieved_docs: Documents from retrieval.
            user_context: Authenticated user context.

        Returns:
            Tuple of (answer, confidence_level, token_usage).
        """
        start = time.time()

        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(company_name=self.settings.company_name)

        # Build context from retrieved docs
        context_text = ""
        for i, doc in enumerate(retrieved_docs, 1):
            context_text += f"\n[Document {i}: {doc.title}]\n{doc.content_snippet}\n"

        if not context_text:
            context_text = "No relevant policy documents were found."

        user_message = f"""Question: {question}

Relevant HR Policy Documents:
{context_text}

Please provide a clear, accurate answer based solely on the above documents. Cite your sources."""

        try:
            response = await self.client.chat.completions.create(
                model=self.settings.azure_openai_deployment,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.2,
                max_tokens=800,
            )

            answer = response.choices[0].message.content or ""
            usage = {}
            if response.usage:
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                    "estimated_cost_usd": round(response.usage.total_tokens * 0.00001, 4),
                }

            confidence = self._compute_confidence(retrieved_docs)
            latency = (time.time() - start) * 1000
            logger.info("generation_complete", confidence=confidence, latency_ms=round(latency, 2))
            return answer, confidence, usage

        except Exception as exc:
            logger.error("generation_failed", error=str(exc))
            return "I'm unable to answer this question right now. Please contact HR directly.", "Low", {}
