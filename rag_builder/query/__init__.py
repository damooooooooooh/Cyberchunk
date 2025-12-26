"""
Query Module

Semantic search against PostgreSQL vector store.
"""

from .pipeline import execute_query

__all__ = ['execute_query']
