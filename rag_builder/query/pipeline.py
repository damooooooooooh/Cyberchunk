"""
Query pipeline for semantic search.

Handles embedding generation and vector search against PostgreSQL.
"""

from typing import List, Dict, Any, Optional
from rag_builder.embeddings import get_embedding_provider
from rag_builder.database import get_db_connection, search_chunks


def execute_query(
    query_text: str,
    config: dict,
    embed_provider: str = "ollama",
    embed_model: Optional[str] = None,
    limit: int = 10,
    chunk_type: Optional[str] = None,
    asset_types: Optional[List[str]] = None,
    taxonomy: Optional[List[str]] = None,
    version: Optional[str] = None,
    include_inactive: bool = False
) -> List[Dict[str, Any]]:
    """
    Execute semantic search query.

    Args:
        query_text: User's search query
        config: Configuration dict
        embed_provider: Embedding provider (ollama, openai, bedrock)
        embed_model: Optional model override
        limit: Number of results
        chunk_type: Filter by chunk type
        asset_types: Filter by asset types
        taxonomy: Filter by taxonomy
        version: Filter by version
        include_inactive: Include inactive datasets

    Returns:
        List of search results with similarity scores
    """
    # Get embedding provider
    provider = get_embedding_provider(
        provider=embed_provider,
        model=embed_model
    )

    # Generate query embedding
    query_embeddings = provider.embed_batch([query_text])
    query_embedding = query_embeddings[0]

    # Connect to database and search
    conn = get_db_connection(config)
    results = search_chunks(
        conn,
        query_embedding=query_embedding,
        limit=limit,
        chunk_type=chunk_type,
        asset_types=asset_types,
        taxonomy=taxonomy,
        version=version,
        only_active=not include_inactive
    )
    conn.close()

    return results
