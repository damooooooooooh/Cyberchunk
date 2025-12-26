"""
Migration Script: JSONL → PostgreSQL

Migrates existing chunks from JSONL files to PostgreSQL database.
Preserves all metadata, tags, and enrichment data.
"""
import os
import sys
import json
import uuid
import psycopg2
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_builder.store.jsonl_writer import read_records_from_jsonl
from rag_builder.chunk.schema import ChunkRecord, DocumentRecord


def get_db_connection():
    """Get PostgreSQL connection using environment variables or defaults"""
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
        database=os.getenv("POSTGRES_DB", "cyberchunk")
    )


def migrate_documents(conn, documents: List[DocumentRecord], dataset_id: str, version: str, publisher: str):
    """Migrate DocumentRecords to PostgreSQL"""
    cursor = conn.cursor()

    print(f"\nMigrating {len(documents)} documents...")

    # Ensure dataset exists
    cursor.execute("""
        INSERT INTO datasets (dataset_id, version, publisher, created_at)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (dataset_id, version) DO NOTHING
    """, (dataset_id, version, publisher, datetime.now(timezone.utc)))

    migrated_count = 0
    for doc in documents:
        try:
            # Convert metadata to JSONB
            metadata = {
                "title": doc.title,
                "fetched_at": doc.fetched_at.isoformat() if doc.fetched_at else None,
                "fetched_by": doc.fetched_by,
                "content_type": doc.content_type,
            }

            cursor.execute("""
                INSERT INTO documents (
                    doc_id, dataset_id, source_uri, source_file_path,
                    source_file_hash, content_hash, ingested_at,
                    publisher, edition, version, metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (doc_id) DO UPDATE SET
                    source_uri = EXCLUDED.source_uri,
                    metadata = EXCLUDED.metadata
            """, (
                str(doc.doc_id),
                dataset_id,
                doc.source_uri,
                None,  # source_file_path (will be added via source preservation)
                None,  # source_file_hash
                None,  # content_hash
                datetime.now(timezone.utc),
                publisher,
                doc.edition,
                doc.version,
                json.dumps(metadata)
            ))
            migrated_count += 1
        except Exception as e:
            print(f"  ✗ Failed to migrate document {doc.doc_id}: {e}")
            continue

    conn.commit()
    print(f"  ✓ Migrated {migrated_count}/{len(documents)} documents")
    cursor.close()


def migrate_chunks(conn, chunks: List[ChunkRecord], dataset_id: str, version: str, publisher: str):
    """Migrate ChunkRecords to PostgreSQL"""
    cursor = conn.cursor()

    print(f"\nMigrating {len(chunks)} chunks...")

    migrated_count = 0
    for chunk in chunks:
        try:
            # Build tags JSONB from chunk fields
            tags = {
                "keywords": chunk.keywords or [],
                "topics": chunk.topics or [],
                "taxonomy": chunk.taxonomy or [],
                "stride": chunk.stride or [],
                "asset_types": chunk.asset_types or [],
                "technologies": chunk.technologies or [],
                "security_controls": chunk.security_controls or []
            }

            # Insert chunk
            cursor.execute("""
                INSERT INTO chunks (
                    chunk_id, doc_id, chunk_type, canonical_id, title, text,
                    tags, source_uri, source_locator,
                    publisher, edition, version, ingested_at, metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (chunk_id) DO UPDATE SET
                    tags = EXCLUDED.tags,
                    text = EXCLUDED.text
            """, (
                str(chunk.chunk_id),
                str(chunk.doc_id) if chunk.doc_id else None,
                chunk.chunk_type,
                chunk.canonical_id,
                chunk.title,
                chunk.text,
                json.dumps(tags),
                chunk.source_uri,
                chunk.source_locator,
                publisher,
                chunk.edition,
                chunk.version,
                datetime.now(timezone.utc),
                json.dumps({"link_uri": chunk.link_uri}) if chunk.link_uri else json.dumps({})
            ))
            migrated_count += 1

            if migrated_count % 100 == 0:
                print(f"  Progress: {migrated_count}/{len(chunks)} chunks migrated...")

        except Exception as e:
            print(f"  ✗ Failed to migrate chunk {chunk.chunk_id}: {e}")
            continue

    conn.commit()
    print(f"  ✓ Migrated {migrated_count}/{len(chunks)} chunks")
    cursor.close()


def migrate_from_jsonl(
    chunks_file: str,
    dataset_id: str = "migrated",
    version: str = "2025",
    publisher: str = "Unknown",
    documents_file: str = None
):
    """
    Migrate data from JSONL files to PostgreSQL.

    Args:
        chunks_file: Path to chunks JSONL file
        dataset_id: Dataset identifier (e.g., "owasp_top10")
        version: Version identifier (e.g., "2025")
        publisher: Publisher name (e.g., "OWASP")
        documents_file: Optional path to documents JSONL file
    """
    print("=" * 60)
    print("CyberChunk Migration: JSONL → PostgreSQL")
    print("=" * 60)

    # Verify files exist
    if not os.path.exists(chunks_file):
        print(f"✗ Chunks file not found: {chunks_file}")
        sys.exit(1)

    # Load chunks
    print(f"\nLoading chunks from: {chunks_file}")
    chunks = read_records_from_jsonl(chunks_file, ChunkRecord)
    print(f"  ✓ Loaded {len(chunks)} chunks")

    # Load documents if provided
    documents = []
    if documents_file and os.path.exists(documents_file):
        print(f"\nLoading documents from: {documents_file}")
        documents = read_records_from_jsonl(documents_file, DocumentRecord)
        print(f"  ✓ Loaded {len(documents)} documents")

    # Connect to database
    print("\nConnecting to PostgreSQL...")
    try:
        conn = get_db_connection()
        print("  ✓ Connected to database")
    except Exception as e:
        print(f"  ✗ Failed to connect: {e}")
        print("\nPlease ensure PostgreSQL is running and credentials are correct.")
        print("Run: python scripts/setup_database.py")
        sys.exit(1)

    try:
        # Migrate documents first
        if documents:
            migrate_documents(conn, documents, dataset_id, version, publisher)

        # Migrate chunks
        migrate_chunks(conn, chunks, dataset_id, version, publisher)

        # Verify migration
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM chunks WHERE publisher = %s AND version = %s", (publisher, version))
        chunk_count = cursor.fetchone()[0]
        cursor.close()

        print("\n" + "=" * 60)
        print("✓ Migration complete!")
        print("=" * 60)
        print(f"Dataset: {dataset_id} (version {version})")
        print(f"Publisher: {publisher}")
        print(f"Total chunks in database: {chunk_count}")
        print("\nNext steps:")
        print("  1. Generate embeddings: python -m rag_builder.cli embed --provider ollama")
        print("  2. Query database: psql -h localhost -U postgres -d cyberchunk")

    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()


def migrate_all_from_directory(directory: str, dataset_id: str, version: str, publisher: str):
    """Migrate all *_chunks.jsonl files from a directory"""
    print(f"Scanning directory: {directory}")

    chunk_files = list(Path(directory).glob("*_chunks.jsonl"))

    if not chunk_files:
        print(f"✗ No *_chunks.jsonl files found in {directory}")
        sys.exit(1)

    print(f"Found {len(chunk_files)} chunk files to migrate")

    for chunk_file in chunk_files:
        print(f"\n{'=' * 60}")
        print(f"Migrating: {chunk_file.name}")
        migrate_from_jsonl(
            chunks_file=str(chunk_file),
            dataset_id=dataset_id,
            version=version,
            publisher=publisher
        )


def main():
    """Main migration CLI"""
    import argparse

    parser = argparse.ArgumentParser(description="Migrate JSONL chunks to PostgreSQL")
    parser.add_argument("--chunks-file", type=str, help="Path to chunks JSONL file")
    parser.add_argument("--documents-file", type=str, help="Path to documents JSONL file (optional)")
    parser.add_argument("--directory", type=str, help="Migrate all *_chunks.jsonl from directory")
    parser.add_argument("--dataset-id", type=str, default="migrated", help="Dataset identifier")
    parser.add_argument("--version", type=str, default="2025", help="Version identifier")
    parser.add_argument("--publisher", type=str, default="Unknown", help="Publisher name")

    args = parser.parse_args()

    if args.directory:
        migrate_all_from_directory(
            directory=args.directory,
            dataset_id=args.dataset_id,
            version=args.version,
            publisher=args.publisher
        )
    elif args.chunks_file:
        migrate_from_jsonl(
            chunks_file=args.chunks_file,
            documents_file=args.documents_file,
            dataset_id=args.dataset_id,
            version=args.version,
            publisher=args.publisher
        )
    else:
        parser.print_help()
        print("\nExample usage:")
        print("  # Migrate single file:")
        print("  python scripts/migrate_to_postgres.py \\")
        print("    --chunks-file output/extracted_data/cd39a9c1-1815-4f73-aac3-fb95c08c6cf4_chunks.jsonl \\")
        print("    --dataset-id cwe \\")
        print("    --version 2024 \\")
        print("    --publisher MITRE")
        print()
        print("  # Migrate all files from directory:")
        print("  python scripts/migrate_to_postgres.py \\")
        print("    --directory output/extracted_data \\")
        print("    --dataset-id owasp_top10 \\")
        print("    --version 2025 \\")
        print("    --publisher OWASP")


if __name__ == "__main__":
    main()
