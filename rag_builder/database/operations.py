"""
Database Operations

CRUD operations for chunks, documents, embeddings, and LLM interactions.
"""
import json
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from uuid import UUID


def insert_document(
    conn,
    doc_id: UUID,
    dataset_id: str,
    source_uri: str,
    publisher: str,
    version: str,
    source_file_path: str = None,
    source_file_hash: str = None,
    edition: str = None,
    metadata: Dict = None
) -> UUID:
    """
    Insert a document into the database.

    Returns:
        doc_id (UUID)
    """
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO documents (
            doc_id, dataset_id, source_uri, source_file_path,
            source_file_hash, publisher, edition, version,
            metadata, ingested_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
        ON CONFLICT (doc_id) DO UPDATE SET
            source_uri = EXCLUDED.source_uri,
            metadata = EXCLUDED.metadata,
            updated_at = CURRENT_TIMESTAMP
        RETURNING doc_id
    """, (
        str(doc_id),
        dataset_id,
        source_uri,
        source_file_path,
        source_file_hash,
        publisher,
        edition,
        version,
        json.dumps(metadata or {}),
        datetime.now(timezone.utc)
    ))

    result = cursor.fetchone()[0]
    conn.commit()
    cursor.close()

    return UUID(result)


def insert_chunk(
    conn,
    chunk_id: UUID,
    doc_id: UUID,
    chunk_type: str,
    text: str,
    canonical_id: str = None,
    title: str = None,
    section_id: UUID = None,
    section_path: List[str] = None,
    tags: Dict = None,
    source_uri: str = None,
    source_locator: str = None,
    source_file_path: str = None,
    source_file_hash: str = None,
    ingestion_id: str = None,
    publisher: str = None,
    edition: str = None,
    version: str = None,
    metadata: Dict = None
) -> UUID:
    """
    Insert a chunk into the database.

    Returns:
        chunk_id (UUID)
    """
    cursor = conn.cursor()

    # Default tags structure
    default_tags = {
        "keywords": [],
        "topics": [],
        "taxonomy": [],
        "stride": [],
        "asset_types": [],
        "technologies": [],
        "security_controls": []
    }

    if tags:
        default_tags.update(tags)

    cursor.execute("""
        INSERT INTO chunks (
            chunk_id, doc_id, section_id, chunk_type, canonical_id, title, text,
            section_path, tags, source_uri, source_locator,
            source_file_path, source_file_hash, ingestion_id,
            publisher, edition, version, metadata, ingested_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
        ON CONFLICT (chunk_id) DO UPDATE SET
            tags = EXCLUDED.tags,
            text = EXCLUDED.text,
            metadata = EXCLUDED.metadata,
            section_id = EXCLUDED.section_id,
            section_path = EXCLUDED.section_path,
            updated_at = CURRENT_TIMESTAMP
        RETURNING chunk_id
    """, (
        str(chunk_id),
        str(doc_id),
        str(section_id) if section_id else None,
        chunk_type,
        canonical_id,
        title,
        text,
        section_path if section_path else [],
        json.dumps(default_tags),
        source_uri,
        source_locator,
        source_file_path,
        source_file_hash,
        ingestion_id,
        publisher,
        edition,
        version,
        json.dumps(metadata or {}),
        datetime.now(timezone.utc)
    ))

    result = cursor.fetchone()[0]
    conn.commit()
    cursor.close()

    return UUID(result)


def get_chunks_without_embeddings(
    conn,
    limit: int = None,
    dataset_id: str = None
) -> List[Tuple[UUID, str]]:
    """
    Get chunks that don't have embeddings yet.

    Returns:
        List of (chunk_id, text) tuples
    """
    cursor = conn.cursor()

    query = """
        SELECT c.chunk_id, c.text
        FROM chunks c
        WHERE c.embedding IS NULL
    """

    params = []

    if dataset_id:
        query += " AND c.publisher = %s"
        params.append(dataset_id)

    if limit:
        query += " LIMIT %s"
        params.append(limit)

    cursor.execute(query, params)
    results = cursor.fetchall()
    cursor.close()

    return [(UUID(row[0]), row[1]) for row in results]


def update_chunk_embedding(
    conn,
    chunk_id: UUID,
    embedding: List[float],
    embedding_model: str
):
    """
    Update a chunk with its embedding vector.

    Args:
        conn: Database connection
        chunk_id: Chunk UUID
        embedding: Embedding vector (list of floats)
        embedding_model: Model name used to generate embedding
    """
    cursor = conn.cursor()

    # Convert embedding to PostgreSQL vector format
    embedding_str = "[" + ",".join(map(str, embedding)) + "]"

    cursor.execute("""
        UPDATE chunks
        SET embedding = %s::vector,
            embedding_model = %s,
            embedding_generated_at = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE chunk_id = %s
    """, (
        embedding_str,
        embedding_model,
        datetime.now(timezone.utc),
        str(chunk_id)
    ))

    conn.commit()
    cursor.close()


def search_chunks(
    conn,
    query_embedding: List[float],
    limit: int = 10,
    chunk_type: str = None,
    asset_types: List[str] = None,
    taxonomy: List[str] = None,
    version: str = None,
    only_active: bool = True
) -> List[Dict[str, Any]]:
    """
    Semantic search for chunks using vector similarity.

    Args:
        conn: Database connection
        query_embedding: Query embedding vector
        limit: Number of results to return
        chunk_type: Filter by chunk type (e.g., "mitigation")
        asset_types: Filter by asset types (e.g., ["API", "Web"])
        taxonomy: Filter by taxonomy (e.g., ["CWE-79", "CWE-89"])
        version: Filter by specific version (e.g., "2025")
        only_active: Only return chunks from active datasets (default: True)

    Returns:
        List of chunks with similarity scores
    """
    cursor = conn.cursor()

    # Build query with dataset join for version filtering
    query = """
        SELECT
            c.chunk_id,
            c.title,
            c.text,
            c.canonical_id,
            c.chunk_type,
            c.tags,
            c.source_uri,
            c.version,
            c.publisher,
            1 - (c.embedding <=> %s::vector) as similarity
        FROM chunks c
        JOIN documents d ON c.doc_id = d.doc_id
        JOIN datasets ds ON d.dataset_id = ds.dataset_id
        WHERE c.embedding IS NOT NULL
    """

    params = ["[" + ",".join(map(str, query_embedding)) + "]"]

    # Filter by active datasets (default)
    if only_active:
        query += " AND ds.active = true"

    # Filter by specific version
    if version:
        query += " AND c.version = %s"
        params.append(version)

    if chunk_type:
        query += " AND c.chunk_type = %s"
        params.append(chunk_type)

    if asset_types:
        query += " AND c.tags->'asset_types' ?| %s"
        params.append(asset_types)

    if taxonomy:
        query += " AND c.tags->'taxonomy' ?| %s"
        params.append(taxonomy)

    query += " ORDER BY c.embedding <=> %s::vector LIMIT %s"
    params.append(params[0])  # Same embedding for ordering
    params.append(limit)

    # Debug: Print the query and params
    print(f"\n[DEBUG] search_chunks SQL:")
    print(f"  Query: {query}")
    print(f"  Params: chunk_type={chunk_type}, asset_types={asset_types}, taxonomy={taxonomy}, version={version}, limit={limit}")
    print(f"  only_active={only_active}\n")

    cursor.execute(query, params)

    results = []
    for row in cursor.fetchall():
        results.append({
            "chunk_id": str(row[0]),
            "title": row[1],
            "text": row[2],
            "canonical_id": row[3],
            "chunk_type": row[4],
            "tags": row[5],
            "source_uri": row[6],
            "version": row[7],
            "publisher": row[8],
            "similarity": float(row[9])
        })

    cursor.close()
    return results


def insert_llm_interaction(
    conn,
    doc_id: UUID,
    llm_provider: str,
    llm_model: str,
    prompt: str,
    response: Dict[str, Any],
    operation: str = "ingest",
    prompt_template: str = None,
    tokens_used: int = None,
    cost_usd: float = None,
    duration_ms: int = None,
    status: str = "success",
    error_message: str = None
) -> UUID:
    """
    Log an LLM interaction for audit trail.

    Args:
        conn: Database connection
        doc_id: Document UUID
        llm_provider: Provider name (e.g., "openai", "anthropic")
        llm_model: Model name (e.g., "gpt-4o-mini")
        prompt: Full prompt sent to LLM
        response: Full JSON response from LLM
        operation: Operation type ("ingest", "enrich", "validate")
        prompt_template: Template used (optional)
        tokens_used: Total tokens consumed
        cost_usd: Estimated cost in USD
        duration_ms: Request duration in milliseconds
        status: "success", "failure", or "partial"
        error_message: Error details if failed

    Returns:
        interaction_id (UUID)
    """
    cursor = conn.cursor()

    # Calculate hashes for deduplication/verification
    prompt_hash = hashlib.sha256(prompt.encode('utf-8')).hexdigest()
    response_str = json.dumps(response, sort_keys=True)
    response_hash = hashlib.sha256(response_str.encode('utf-8')).hexdigest()

    cursor.execute("""
        INSERT INTO llm_interactions (
            doc_id, llm_provider, llm_model,
            prompt, prompt_template, prompt_hash,
            response, response_hash,
            operation, tokens_used, cost_usd, duration_ms,
            status, error_message, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING interaction_id
    """, (
        str(doc_id),
        llm_provider,
        llm_model,
        prompt,
        prompt_template,
        prompt_hash,
        json.dumps(response),
        response_hash,
        operation,
        tokens_used,
        cost_usd,
        duration_ms,
        status,
        error_message,
        datetime.now(timezone.utc)
    ))

    interaction_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()

    return UUID(interaction_id)
