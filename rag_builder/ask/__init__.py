"""
Ask Module

Full RAG flow with query analysis, retrieval, and LLM generation.
"""

from .pipeline import execute_rag, analyze_query

__all__ = ['execute_rag', 'analyze_query']
