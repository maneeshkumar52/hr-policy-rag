"""Batch indexing pipeline for HR documents into Azure AI Search."""
import uuid
from pathlib import Path
from openai import AzureOpenAI
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex, SimpleField, SearchableField, SearchField,
    SearchFieldDataType, VectorSearch, HnswAlgorithmConfiguration,
    VectorSearchProfile, SemanticConfiguration, SemanticSearch,
    SemanticPrioritizedFields, SemanticField,
)
from azure.core.credentials import AzureKeyCredential
import sys
import os
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.config import get_settings


def create_index(index_client: SearchIndexClient, index_name: str) -> None:
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SearchableField(name="title", type=SearchFieldDataType.String),
        SearchableField(name="content", type=SearchFieldDataType.String),
        SimpleField(name="source_file", type=SearchFieldDataType.String),
        SimpleField(name="category", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="clearance_level", type=SearchFieldDataType.Int32, filterable=True),
        SimpleField(name="chunk_index", type=SearchFieldDataType.Int32),
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=3072,
            vector_search_profile_name="myHnswProfile",
        ),
    ]
    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="myHnsw")],
        profiles=[VectorSearchProfile(name="myHnswProfile", algorithm_configuration_name="myHnsw")],
    )
    semantic_config = SemanticConfiguration(
        name="default",
        prioritized_fields=SemanticPrioritizedFields(
            title_field=SemanticField(field_name="title"),
            content_fields=[SemanticField(field_name="content")],
        ),
    )
    index = SearchIndex(
        name=index_name,
        fields=fields,
        vector_search=vector_search,
        semantic_search=SemanticSearch(configurations=[semantic_config]),
    )
    index_client.create_or_update_index(index)
    print(f"Index '{index_name}' created/updated.")


def main():
    settings = get_settings()
    credential = AzureKeyCredential(settings.azure_search_api_key)
    index_client = SearchIndexClient(endpoint=settings.azure_search_endpoint, credential=credential)
    search_client = SearchClient(endpoint=settings.azure_search_endpoint, index_name=settings.azure_search_index_name, credential=credential)
    openai_client = AzureOpenAI(azure_endpoint=settings.azure_openai_endpoint, api_key=settings.azure_openai_api_key, api_version=settings.azure_openai_api_version)

    create_index(index_client, settings.azure_search_index_name)

    from indexer.chunker import RecursiveChunker
    chunker = RecursiveChunker(chunk_size=1000, chunk_overlap=200)

    docs_dir = Path(__file__).parent / "documents"
    all_docs = []
    for md_file in docs_dir.glob("*.md"):
        text = md_file.read_text(encoding="utf-8")
        title = md_file.stem.replace("_", " ").title()
        # Parse clearance_level from file comment
        clearance_level = 1
        if "clearance_level: manager" in text:
            clearance_level = 2
        elif "clearance_level: hr_admin" in text:
            clearance_level = 3
        chunks = chunker.chunk(text, md_file.name, title, clearance_level)
        for chunk in chunks:
            embedding = openai_client.embeddings.create(input=chunk.content, model=settings.azure_openai_embedding_deployment).data[0].embedding
            all_docs.append({
                "id": str(uuid.uuid4()),
                "title": chunk.title,
                "content": chunk.content,
                "source_file": chunk.source_file,
                "category": "hr_policy",
                "clearance_level": chunk.clearance_level,
                "chunk_index": chunk.chunk_index,
                "content_vector": embedding,
            })

    if all_docs:
        for i in range(0, len(all_docs), 100):
            search_client.upload_documents(all_docs[i:i+100])
        print(f"Indexed {len(all_docs)} chunks from {docs_dir}")


if __name__ == "__main__":
    main()
