"""
Phase 1: Chunk Enrichment Module

This module handles the second LLM pass to extract metadata tags
from chunks, including STRIDE categories, keywords, and asset types.
"""

from .metadata_extractor import extract_chunk_metadata
from .synonym_expander import expand_keywords_with_synonyms, batch_expand_synonyms

__all__ = [
    'extract_chunk_metadata',
    'expand_keywords_with_synonyms',
    'batch_expand_synonyms'
]
