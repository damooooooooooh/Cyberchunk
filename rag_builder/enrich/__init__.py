"""
Phase 1: Chunk Enrichment Module

This module handles the second LLM pass to extract metadata tags
from chunks, including STRIDE categories, keywords, and asset types.
"""

from .metadata_extractor import extract_chunk_metadata

__all__ = ['extract_chunk_metadata']
