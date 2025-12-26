"""
Database Module

PostgreSQL operations for CyberChunk.
"""

from .connection import get_db_connection
from .operations import (
    insert_chunk,
    insert_document,
    get_chunks_without_embeddings,
    update_chunk_embedding,
    search_chunks,
    insert_llm_interaction
)

__all__ = [
    'get_db_connection',
    'insert_chunk',
    'insert_document',
    'get_chunks_without_embeddings',
    'update_chunk_embedding',
    'search_chunks',
    'insert_llm_interaction'
]
