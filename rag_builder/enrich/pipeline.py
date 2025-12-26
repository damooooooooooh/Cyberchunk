"""
Pipeline for re-enriching existing chunks in database.

Adds synonyms and updates tags without re-ingesting documents.
"""

import json
from typing import Optional
from rag_builder.database import get_db_connection
from rag_builder.enrich.synonym_expander import expand_keywords_with_synonyms
from rag_builder.enrich.metadata_extractor import extract_chunk_metadata


def re_enrich_chunks(
    config: dict,
    llm_client,
    dataset_id: Optional[str] = None,
    batch_size: int = 50,
    regenerate_embeddings: bool = False,
    update_stride: bool = False
) -> dict:
    """
    Re-enrich tags for existing chunks without re-ingesting.

    Process:
    1. Fetch existing chunks from database
    2. Call LLM to enhance tags (add synonyms)
    3. Optionally re-extract all metadata (including tags.stride)
    4. Update chunks in database
    5. Optionally mark embeddings for regeneration

    Args:
        config: Configuration dict
        llm_client: LLM client for enrichment
        dataset_id: Optional dataset filter (e.g., 'owasp_top10')
        batch_size: Number of chunks to process per batch
        regenerate_embeddings: Whether to clear embeddings for regeneration
        update_stride: Whether to re-extract all metadata (including STRIDE tags)

    Returns:
        dict with stats: {
            'total_chunks': int,
            'enhanced_count': int,
            'failed_count': int
        }
    """
    conn = get_db_connection(config)

    # Fetch chunks to enrich
    print("Fetching chunks from database...")
    chunks = _fetch_chunks(conn, dataset_id)
    print(f"  ✓ Found {len(chunks)} chunks to enrich\n")

    if not chunks:
        print("No chunks to enrich.")
        conn.close()
        return {'total_chunks': 0, 'enhanced_count': 0, 'failed_count': 0}

    # Process in batches
    total_batches = (len(chunks) + batch_size - 1) // batch_size
    enhanced_count = 0
    failed_count = 0

    for batch_num in range(total_batches):
        start_idx = batch_num * batch_size
        end_idx = min(start_idx + batch_size, len(chunks))
        batch = chunks[start_idx:end_idx]

        print(f"Processing batch {batch_num + 1}/{total_batches} ({len(batch)} chunks)...")

        for chunk_id, text, tags in batch:
            try:
                # Parse current tags
                current_tags = json.loads(tags) if isinstance(tags, str) else tags
                current_keywords = current_tags.get('keywords', [])

                # Enhance keywords with synonyms
                if current_keywords:
                    enhanced_keywords = expand_keywords_with_synonyms(
                        text,
                        current_keywords,
                        llm_client,
                        max_keywords=20
                    )
                    current_tags['keywords'] = enhanced_keywords
                else:
                    print(f"  ⚠ Chunk {chunk_id} has no keywords, skipping synonym expansion")

                # Optionally re-run full metadata extraction
                if update_stride:
                    metadata = extract_chunk_metadata(text, llm_client)

                    # Update tags with new metadata (including tags.stride)
                    current_tags['stride'] = metadata.get('stride_categories', [])
                    current_tags['keywords'] = metadata.get('keywords', current_tags.get('keywords', []))
                    current_tags['topics'] = metadata.get('topics', [])
                    current_tags['taxonomy'] = metadata.get('taxonomy_tags', [])
                    current_tags['asset_types'] = metadata.get('asset_types', [])
                    current_tags['technologies'] = metadata.get('technologies', [])
                    current_tags['security_controls'] = metadata.get('security_controls', [])

                # Save to database
                _update_chunk_tags(conn, chunk_id, current_tags)

                enhanced_count += 1

            except Exception as e:
                print(f"  ✗ Failed to enhance chunk {chunk_id}: {e}")
                failed_count += 1
                continue

        print(f"  ✓ Enhanced {len(batch)} chunks\n")

    # Optionally clear embeddings for regeneration
    if regenerate_embeddings:
        print("Clearing embeddings for regeneration...")
        _clear_embeddings(conn, dataset_id)
        print("  ✓ Embeddings cleared")
        print("  Run: python -m rag_builder.cli embed --provider ollama --batch-size 50\n")

    conn.close()

    return {
        'total_chunks': len(chunks),
        'enhanced_count': enhanced_count,
        'failed_count': failed_count
    }


def _fetch_chunks(conn, dataset_id: Optional[str] = None):
    """Fetch chunks from database."""
    cursor = conn.cursor()

    if dataset_id:
        # Filter by dataset_id via documents table
        query = """
            SELECT c.chunk_id, c.text, c.tags
            FROM chunks c
            JOIN documents d ON c.doc_id = d.doc_id
            WHERE c.tags IS NOT NULL
              AND d.dataset_id = %s
        """
        params = [dataset_id]
    else:
        # No filter - get all chunks
        query = """
            SELECT chunk_id, text, tags
            FROM chunks
            WHERE tags IS NOT NULL
        """
        params = []

    cursor.execute(query, tuple(params) if params else ())
    chunks = cursor.fetchall()
    cursor.close()

    return chunks


def _update_chunk_tags(conn, chunk_id, tags: dict):
    """Update chunk tags in database."""
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE chunks
        SET tags = %s::jsonb,
            updated_at = CURRENT_TIMESTAMP
        WHERE chunk_id = %s
    """, (json.dumps(tags), str(chunk_id)))

    conn.commit()
    cursor.close()


def _clear_embeddings(conn, dataset_id: Optional[str] = None):
    """Clear embeddings to force regeneration."""
    cursor = conn.cursor()

    if dataset_id:
        # Filter by dataset_id via documents table
        query = """
            UPDATE chunks c
            SET embedding = NULL,
                embedding_model = NULL,
                embedding_generated_at = NULL
            FROM documents d
            WHERE c.doc_id = d.doc_id
              AND d.dataset_id = %s
        """
        params = [dataset_id]
    else:
        # Clear all embeddings
        query = """
            UPDATE chunks
            SET embedding = NULL,
                embedding_model = NULL,
                embedding_generated_at = NULL
        """
        params = []

    cursor.execute(query, tuple(params) if params else ())
    conn.commit()
    cursor.close()
