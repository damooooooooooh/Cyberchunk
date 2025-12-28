import argparse
import os
import yaml
from typing import Dict, Any, List
from datetime import datetime, timezone

from rag_builder.ingest.pipeline import ingest_document
from rag_builder.embed.factory import get_embedder
from rag_builder.store.jsonl_writer import write_records_to_jsonl, read_records_from_jsonl
from rag_builder.chunk.schema import DocumentRecord, SectionNode, ChunkRecord, RelationshipRecord
from rag_builder.embed.pipeline import embed_chunks
from rag_builder.index.pipeline import build_faiss_index
from rag_builder.llm.factory import get_llm_client
from rag_builder.validate.pipeline import validate_data
from rag_builder.extract.pipeline import extract_chunks_and_relationships
from rag_builder.tag.pipeline import tag_chunks
from rag_builder.embed.faiss_index import FaissIndex
from uuid import UUID, uuid4

# New modular imports
from rag_builder.query import execute_query
from rag_builder.ask import execute_rag, analyze_query as ask_analyze_query
from rag_builder.enrich.pipeline import re_enrich_chunks

def load_config(config_path: str) -> Dict[str, Any]:
    """Loads the YAML configuration file."""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found at {config_path}")
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config

def main():
    parser = argparse.ArgumentParser(description="RAG Source Builder for Cybersecurity Knowledge")
    parser.add_argument("--config-path", type=str, default="rag_builder/config/main_config.yml",
                        help="Path to the main configuration YAML file.")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Ingest command
    ingest_parser = subparsers.add_parser("ingest", help="Ingest raw documents.")
    ingest_parser.add_argument("--source", type=str, required=True, help="Path to sources.yml or a direct URL/file.")
    ingest_parser.add_argument("--publisher", type=str, help="Publisher metadata override (e.g., OWASP, NIST).")
    ingest_parser.add_argument("--collection", type=str, help="Collection name (e.g., OWASP Top 10, NIST 800-53).")
    ingest_parser.add_argument("--document-name", type=str, help="Document name within the collection (e.g., Top 10 2021).")
    ingest_parser.add_argument("--item-id", type=str, help="Item identifier within the collection (e.g., A01, AC-3).")
    ingest_parser.add_argument("--edition", type=str, help="Edition or year metadata override (e.g., 2021).")
    ingest_parser.add_argument("--version", type=str, help="Version metadata override (e.g., A01 or v1).")
    ingest_parser.add_argument("--use-llm", action="store_true", help="Use configured LLM to extract risk-focused chunks during ingest.")
    ingest_parser.add_argument("--enrich-tags", action="store_true", default=True, help="Phase 1: Enrich chunks with tags & STRIDE (default: True).")
    ingest_parser.add_argument("--no-enrich-tags", dest="enrich_tags", action="store_false", help="Skip tag enrichment.")
    ingest_parser.add_argument("--preserve-source", action="store_true", help="Preserve original source file with manifest for audit trail.")
    ingest_parser.add_argument("--use-postgres", action="store_true", help="Write chunks directly to PostgreSQL instead of JSONL.")
    ingest_parser.add_argument("--dataset-id", type=str, help="Dataset identifier for PostgreSQL (e.g., owasp_top10, cwe).")
    ingest_parser.add_argument("--dataset-name", type=str, help="Human-readable dataset name (e.g., 'API Security Top 10'). Defaults to --collection if not specified.")
    ingest_parser.set_defaults(func=run_ingest)

    # Extract command
    extract_parser = subparsers.add_parser("extract", help="Extract entities and relationships from ingested documents.")
    extract_parser.add_argument("--doc-id", type=str, help="Process a specific document ID.")
    extract_parser.add_argument("--extractor-config", type=str, default="rag_builder/config/extractors/generic_html.yml",
                                help="Path to the extractor configuration YAML file.")
    extract_parser.add_argument("--use-llm", action="store_true", help="Use LLM for extraction.")
    extract_parser.set_defaults(func=run_extract)

    # Tag command
    tag_parser = subparsers.add_parser("tag", help="Tag chunks with keywords and topics.")
    tag_parser.set_defaults(func=run_tag)

    # Embed command
    embed_parser = subparsers.add_parser("embed", help="Generate embeddings for chunks.")
    embed_parser.add_argument("--provider", type=str, choices=["openai", "ollama", "bedrock"], default="ollama",
                             help="Embedding provider (default: ollama)")
    embed_parser.add_argument("--model", type=str, help="Model name (provider-specific, e.g., nomic-embed-text)")
    embed_parser.add_argument("--batch-size", type=int, default=50, help="Batch size for embedding generation")
    embed_parser.add_argument("--dataset-id", type=str, help="Only embed chunks from this dataset")
    embed_parser.set_defaults(func=run_embed)

    # Index command
    index_parser = subparsers.add_parser("index", help="Build FAISS index from embeddings.")
    index_parser.set_defaults(func=run_index)

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Perform LLM-powered data validation.")
    validate_parser.set_defaults(func=run_validate)

    # Query command
    query_parser = subparsers.add_parser("query", help="Semantic search against PostgreSQL vector store.")
    query_parser.add_argument("query_text", type=str, help="Query text for semantic search")
    query_parser.add_argument("--limit", type=int, default=10, help="Number of results to return (default: 10)")
    query_parser.add_argument("--chunk-type", type=str, help="Filter by chunk type (e.g., mitigation, weakness, risk)")
    query_parser.add_argument("--asset-types", type=str, nargs="+", help="Filter by asset types (e.g., API Web)")
    query_parser.add_argument("--taxonomy", type=str, nargs="+", help="Filter by taxonomy (e.g., CWE-79 CWE-89)")
    query_parser.add_argument("--version", type=str, help="Filter by specific version (e.g., 2025)")
    query_parser.add_argument("--provider", type=str, choices=["openai", "ollama", "bedrock"], default="ollama",
                             help="Embedding provider for query (default: ollama)")
    query_parser.add_argument("--model", type=str, help="Model name (provider-specific)")
    query_parser.add_argument("--show-full", action="store_true", help="Show full text instead of preview")
    query_parser.add_argument("--include-inactive", action="store_true", help="Include chunks from inactive datasets")
    query_parser.set_defaults(func=run_query)

    # Ask command (RAG with LLM generation)
    ask_parser = subparsers.add_parser("ask", help="Ask a question with LLM-generated answer (full RAG flow)")
    ask_parser.add_argument("question", type=str, help="Your question")
    ask_parser.add_argument("--llm-provider", type=str, choices=["openai", "ollama"], default="openai",
                           help="LLM provider for answer generation (default: openai)")
    ask_parser.add_argument("--llm-model", type=str, help="LLM model name (e.g., gpt-4o, llama3.1)")
    ask_parser.add_argument("--embed-provider", type=str, choices=["openai", "ollama", "bedrock"], default="ollama",
                           help="Embedding provider for retrieval (default: ollama)")
    ask_parser.add_argument("--embed-model", type=str, help="Embedding model name")
    ask_parser.add_argument("--limit", type=int, default=20, help="Number of chunks to retrieve (default: 20)")
    ask_parser.add_argument("--chunk-type", type=str, help="Filter by chunk type (manual override only)")
    ask_parser.add_argument("--asset-types", type=str, nargs="+", help="Filter by asset types")
    ask_parser.add_argument("--taxonomy", type=str, nargs="+", help="Filter by taxonomy")
    ask_parser.add_argument("--version", type=str, help="Filter by version")
    ask_parser.add_argument("--show-context", action="store_true", help="Show retrieved context chunks")
    ask_parser.add_argument("--include-inactive", action="store_true", help="Include inactive datasets")
    ask_parser.set_defaults(func=run_ask)

    # Enrich-tags command (re-enrich existing chunks with enhanced keywords)
    enrich_tags_parser = subparsers.add_parser("enrich-tags", help="Re-enrich existing chunks with synonym-expanded keywords and metadata")
    enrich_tags_parser.add_argument("--dataset-id", type=str, help="Only enrich chunks from this dataset (default: all)")
    enrich_tags_parser.add_argument("--llm-provider", type=str, choices=["openai", "ollama"], default="openai",
                                   help="LLM provider for keyword expansion (default: openai)")
    enrich_tags_parser.add_argument("--llm-model", type=str, help="LLM model name")
    enrich_tags_parser.add_argument("--batch-size", type=int, default=50, help="Number of chunks to process per batch (default: 50)")
    enrich_tags_parser.add_argument("--update-stride", action="store_true",
                                   help="Re-extract all metadata including STRIDE tags (tags.stride array)")
    enrich_tags_parser.add_argument("--regenerate-embeddings", action="store_true",
                                   help="Clear embeddings after enrichment to trigger regeneration")
    enrich_tags_parser.set_defaults(func=run_enrich_tags)

    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        exit(1)

    try:
        config = load_config(args.config_path)
        print(f"Loaded configuration from: {args.config_path}")
        # print(f"Config: {config}") # For debugging
        args.func(args, config)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        exit(1)

def run_ingest(args, config):
    print(f"Starting ingest for source: {args.source}")
    try:
        from urllib.parse import urlparse

        # Source preservation (if enabled)
        source_manager = None
        preserved_info = None
        source_file_path = None
        source_file_hash = None

        if args.preserve_source:
            from rag_builder.sources import SourceManager
            source_manager = SourceManager()

            is_url = bool(urlparse(args.source).scheme)
            dataset_id = args.dataset_id or args.collection or "unknown"
            version = args.version or args.edition or "unknown"
            publisher = args.publisher or "Unknown"

            print(f"\nPreserving source file for audit trail...")
            preserved_info = source_manager.preserve_source(
                source_path=args.source,
                dataset_id=dataset_id,
                version=version,
                publisher=publisher,
                is_url=is_url
            )

            source_file_path = preserved_info['preserved_path']
            source_file_hash = preserved_info['file_hash']
            print(f"  ✓ Source preserved: {source_file_path}")
            print(f"  ✓ SHA256: {source_file_hash}")

        # Run ingestion
        llm_client = get_llm_client(config) if args.use_llm else None
        doc_record, section_nodes, llm_chunks, llm_raw = ingest_document(
            args.source,
            config,
            publisher=args.publisher,
            collection=args.collection,
            document_name=args.document_name,
            item_id=args.item_id,
            edition=args.edition,
            version=args.version,
            llm_client=llm_client,
            enrich_tags=args.enrich_tags
        )
        print(f"\nSuccessfully ingested document: {doc_record.title} (ID: {doc_record.doc_id})")
        print(f"Extracted {len(section_nodes)} sections.")

        # Write to PostgreSQL (if enabled)
        if args.use_postgres:
            from rag_builder.database import get_db_connection, insert_document, insert_chunk, insert_llm_interaction

            print(f"\nWriting to PostgreSQL...")
            try:
                conn = get_db_connection(config)

                # Ensure dataset exists
                cursor = conn.cursor()
                dataset_id = args.dataset_id or args.collection or "unknown"
                dataset_name = args.dataset_name or args.collection  # Use --dataset-name or fall back to --collection
                cursor.execute("""
                    INSERT INTO datasets (dataset_id, version, publisher, name, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (dataset_id, version) DO UPDATE SET
                        name = EXCLUDED.name
                """, (
                    dataset_id,
                    args.version or args.edition or "unknown",
                    args.publisher or "Unknown",
                    dataset_name,
                    datetime.now(timezone.utc)
                ))
                conn.commit()
                cursor.close()

                # Insert document
                insert_document(
                    conn,
                    doc_id=doc_record.doc_id,
                    dataset_id=dataset_id,
                    source_uri=doc_record.source_uri,
                    publisher=args.publisher or "Unknown",
                    version=args.version or args.edition or "unknown",
                    source_file_path=source_file_path,
                    source_file_hash=source_file_hash,
                    edition=args.edition,
                    metadata={
                        "title": doc_record.title,
                        "collection": args.collection,
                        "document_name": args.document_name,
                        "item_id": args.item_id
                    }
                )
                print(f"  ✓ Inserted document: {doc_record.doc_id}")

                # Insert chunks
                if llm_chunks:
                    for chunk in llm_chunks:
                        # ChunkRecord stores tags in chunk.tags dictionary
                        tags = chunk.tags if chunk.tags else {
                            "keywords": [],
                            "topics": [],
                            "taxonomy": [],
                            "stride": [],
                            "asset_types": [],
                            "technologies": [],
                            "security_controls": []
                        }

                        # Build metadata for chunk-type-specific fields
                        metadata = {}
                        if chunk.chunk_type == "related_link" and chunk.link_uri:
                            metadata["link_uri"] = chunk.link_uri
                            # Could add more link-specific fields:
                            # metadata["link_title"] = chunk.title
                            # metadata["link_description"] = ...

                        insert_chunk(
                            conn,
                            chunk_id=chunk.chunk_id,
                            doc_id=chunk.doc_id,
                            section_id=chunk.section_id,
                            section_path=chunk.section_path,
                            chunk_type=chunk.chunk_type,
                            text=chunk.text,
                            canonical_id=chunk.canonical_id,
                            title=chunk.title,
                            tags=tags,
                            source_uri=chunk.source_uri,
                            source_locator=chunk.source_locator,
                            source_file_path=source_file_path,
                            source_file_hash=source_file_hash,
                            ingestion_id=f"{dataset_id}_{args.version or 'unknown'}_{datetime.now(timezone.utc).strftime('%Y%m%d')}",
                            publisher=args.publisher,
                            edition=args.edition,
                            version=args.version or args.edition,
                            metadata=metadata if metadata else None
                        )

                    print(f"  ✓ Inserted {len(llm_chunks)} chunks to PostgreSQL")

                # Log LLM interaction for audit trail
                if llm_raw and llm_client:
                    try:
                        insert_llm_interaction(
                            conn,
                            doc_id=doc_record.doc_id,
                            llm_provider="openai",  # TODO: Get from config
                            llm_model=llm_client.model_name,
                            prompt=llm_raw.get("prompt", ""),
                            response=llm_raw.get("response", {}),
                            operation="ingest",
                            prompt_template="ingest-document-and-extract-chunks.txt"
                        )
                        print(f"  ✓ Logged LLM interaction for audit")
                    except Exception as e:
                        print(f"  ⚠ Warning: Failed to log LLM interaction: {e}")

                conn.close()

            except Exception as e:
                print(f"  ✗ PostgreSQL write failed: {e}")
                import traceback
                traceback.print_exc()
                print(f"\nFalling back to JSONL output...")
                args.use_postgres = False

        # Write to JSONL (if not using PostgreSQL or as backup)
        if not args.use_postgres:
            output_base_dir = config.get("general", {}).get("output_base_dir", "output")
            ingested_data_dir = os.path.join(output_base_dir, "ingested_data")
            os.makedirs(ingested_data_dir, exist_ok=True)

            write_records_to_jsonl([doc_record], ingested_data_dir, "documents.jsonl", mode='a')
            write_records_to_jsonl(section_nodes, ingested_data_dir, "sections.jsonl", mode='a')
            print(f"Saved DocumentRecord and SectionNodes to {ingested_data_dir}")

            if llm_chunks:
                extracted_data_dir = os.path.join(config.get("general", {}).get("output_base_dir", "output"), "extracted_data")
                os.makedirs(extracted_data_dir, exist_ok=True)
                per_doc_chunks = f"{doc_record.doc_id}_chunks.jsonl"
                write_records_to_jsonl(llm_chunks, extracted_data_dir, per_doc_chunks, mode='w')
                print(f"Saved {len(llm_chunks)} LLM-ingest chunks to {os.path.join(extracted_data_dir, per_doc_chunks)}")

        # Save raw LLM response (always for debugging)
        if llm_raw:
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            per_doc_raw = f"{doc_record.doc_id}_{llm_client.model_name}_{ts}_response.json"
            extracted_data_dir = os.path.join(config.get("general", {}).get("output_base_dir", "output"), "extracted_data")
            os.makedirs(extracted_data_dir, exist_ok=True)
            raw_path = os.path.join(extracted_data_dir, per_doc_raw)
            with open(raw_path, "w", encoding="utf-8") as f:
                import json
                json.dump(llm_raw, f, ensure_ascii=False, indent=2)
            print(f"Saved raw LLM response to {raw_path}")

    except Exception as e:
        print(f"Error during ingestion: {e}")
        import traceback
        traceback.print_exc()

def run_extract(args, config):
    print(f"Starting extraction for doc_id: {args.doc_id or 'all'}")
    try:
        output_base_dir = config.get("general", {}).get("output_base_dir", "output")
        ingested_data_dir = os.path.join(output_base_dir, "ingested_data")
        extracted_data_dir = os.path.join(output_base_dir, "extracted_data")
        os.makedirs(extracted_data_dir, exist_ok=True)

        # Load all documents and sections
        all_documents = read_records_from_jsonl(os.path.join(ingested_data_dir, "documents.jsonl"), DocumentRecord)
        all_sections = read_records_from_jsonl(os.path.join(ingested_data_dir, "sections.jsonl"), SectionNode)

        if not all_documents or not all_sections:
            print(f"No ingested documents or sections found in {ingested_data_dir}. Please run 'ingest' first.")
            return

        documents_to_process: List[DocumentRecord] = []
        if args.doc_id:
            try:
                target_doc_uuid = UUID(args.doc_id)
                doc_to_process = next((d for d in all_documents if d.doc_id == target_doc_uuid), None)
                if doc_to_process:
                    documents_to_process.append(doc_to_process)
                else:
                    print(f"Document with ID {args.doc_id} not found.")
                    return
            except ValueError:
                print(f"Invalid UUID format for --doc-id: {args.doc_id}")
                return
        else:
            documents_to_process = all_documents

        all_extracted_chunks = []
        all_extracted_relationships = []

        for doc_record in documents_to_process:
            sections_for_doc = [s for s in all_sections if s.doc_id == doc_record.doc_id]
            if not sections_for_doc:
                print(f"No sections found for document ID {doc_record.doc_id}. Skipping extraction for this document.")
                continue

            print(f"\nProcessing document: {doc_record.title} (ID: {doc_record.doc_id})")
            chunks, relationships = extract_chunks_and_relationships(doc_record, sections_for_doc, args.extractor_config, config=config, use_llm=args.use_llm)
            all_extracted_chunks.extend(chunks)
            all_extracted_relationships.extend(relationships)
            print(f"Extracted {len(chunks)} chunks and {len(relationships)} relationships for doc ID {doc_record.doc_id}.")

        if all_extracted_chunks:
            write_records_to_jsonl(all_extracted_chunks, extracted_data_dir, "chunks.jsonl", mode='w')
            print(f"Saved {len(all_extracted_chunks)} chunks to {os.path.join(extracted_data_dir, 'chunks.jsonl')}")
        if all_extracted_relationships:
            write_records_to_jsonl(all_extracted_relationships, extracted_data_dir, "relationships.jsonl", mode='w')
            print(f"Saved {len(all_extracted_relationships)} relationships to {os.path.join(extracted_data_dir, 'relationships.jsonl')}")

    except FileNotFoundError as e:
        print(f"Error: {e}. Please ensure ingested data files exist.")
    except Exception as e:
        print(f"Error during extraction: {e}")

def run_tag(args, config):
    print("Running tag command.")
    try:
        output_base_dir = config.get("general", {}).get("output_base_dir", "output")
        extracted_data_dir = os.path.join(output_base_dir, "extracted_data")
        tagged_data_dir = os.path.join(output_base_dir, "tagged_data") # New directory for tagged output
        os.makedirs(tagged_data_dir, exist_ok=True)

        chunks_file = os.path.join(extracted_data_dir, "chunks.jsonl")
        if not os.path.exists(chunks_file):
            print(f"Error: Chunks file not found at {chunks_file}. Please run 'extract' command first.")
            return
        
        chunks = read_records_from_jsonl(chunks_file, ChunkRecord)
        if not chunks:
            print(f"No chunks found in {chunks_file}. Nothing to tag.")
            return

        print(f"Loaded {len(chunks)} chunks from {chunks_file}.")

        # Perform tagging
        tagged_chunks = tag_chunks(chunks, config)

        # Save tagged chunks
        write_records_to_jsonl(tagged_chunks, tagged_data_dir, "chunks_tagged.jsonl", mode='w')
        print(f"Saved {len(tagged_chunks)} tagged chunks to {os.path.join(tagged_data_dir, 'chunks_tagged.jsonl')}")

    except Exception as e:
        print(f"Error during tag command: {e}")

def run_embed(args, config):
    """
    Phase 2: Generate embeddings for chunks in PostgreSQL.

    Uses switchable embedding providers (OpenAI, Ollama, Bedrock).
    """
    print(f"\n=== Phase 2: Embedding Generation ===")
    print(f"Provider: {args.provider}")

    try:
        from rag_builder.embeddings import get_embedding_provider
        from rag_builder.database import get_db_connection, get_chunks_without_embeddings, update_chunk_embedding

        # Initialize embedding provider
        print(f"\nInitializing embedding provider...")
        provider = get_embedding_provider(
            provider=args.provider,
            model=args.model
        )
        print(f"  ✓ Provider: {args.provider}")
        print(f"  ✓ Model: {provider.get_model_name()}")
        print(f"  ✓ Dimension: {provider.get_dimension()}")

        # Connect to database
        print(f"\nConnecting to PostgreSQL...")
        try:
            conn = get_db_connection(config)
            print(f"  ✓ Connected to database")
        except Exception as e:
            print(f"  ✗ Failed to connect: {e}")
            print(f"\nPlease ensure PostgreSQL is running:")
            print(f"  python scripts/setup_database.py")
            return

        # Get chunks without embeddings
        print(f"\nFetching chunks without embeddings...")
        chunks_to_embed = get_chunks_without_embeddings(
            conn,
            dataset_id=args.dataset_id
        )

        if not chunks_to_embed:
            print(f"  ℹ No chunks found without embeddings")
            return

        print(f"  ✓ Found {len(chunks_to_embed)} chunks to embed")

        # Batch processing
        batch_size = args.batch_size
        total_batches = (len(chunks_to_embed) + batch_size - 1) // batch_size

        print(f"\nGenerating embeddings...")
        print(f"  Batch size: {batch_size}")
        print(f"  Total batches: {total_batches}")

        embedded_count = 0
        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, len(chunks_to_embed))
            batch = chunks_to_embed[start_idx:end_idx]

            print(f"\n  Processing batch {batch_num + 1}/{total_batches} ({len(batch)} chunks)...")

            try:
                # Extract chunk data: (chunk_id, text, title, canonical_id)
                chunk_ids = [chunk[0] for chunk in batch]

                # Build augmented text: "Title (canonical_id): content"
                augmented_texts = []
                for chunk in batch:
                    chunk_id, text, title, canonical_id = chunk

                    # Build augmented text with metadata
                    parts = []
                    if title:
                        parts.append(title)
                    if canonical_id and canonical_id != title:
                        parts.append(f"({canonical_id})")

                    if parts:
                        augmented_text = " ".join(parts) + ": " + text
                    else:
                        augmented_text = text

                    augmented_texts.append(augmented_text)

                # Show sample of augmented text (first chunk in batch)
                if batch_num == 0 and len(augmented_texts) > 0:
                    sample = augmented_texts[0]
                    print(f"\n    Sample augmented text (first chunk):")
                    print(f"    {sample[:200]}{'...' if len(sample) > 200 else ''}\n")

                # Generate embeddings with augmented text (batch for OpenAI, sequential for Ollama/Bedrock)
                embeddings = provider.embed_batch(augmented_texts)

                # Update database
                for chunk_id, embedding in zip(chunk_ids, embeddings):
                    update_chunk_embedding(
                        conn,
                        chunk_id=chunk_id,
                        embedding=embedding,
                        embedding_model=provider.get_model_name()
                    )
                    embedded_count += 1

                print(f"    ✓ Embedded {len(batch)} chunks")

            except Exception as e:
                print(f"    ✗ Batch {batch_num + 1} failed: {e}")
                continue

        conn.close()

        print(f"\n{'=' * 60}")
        print(f"✓ Embedding generation complete!")
        print(f"{'=' * 60}")
        print(f"Provider: {args.provider}")
        print(f"Model: {provider.get_model_name()}")
        print(f"Embedded: {embedded_count}/{len(chunks_to_embed)} chunks")

        # Suggest creating vector index
        if embedded_count > 0:
            print(f"\nNext steps:")
            print(f"  1. Create vector index (run once after all embeddings):")
            print(f"     psql -h localhost -U postgres -d cyberchunk -c \\")
            print(f"       \"CREATE INDEX idx_chunks_embedding ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);\"")
            print(f"  2. Test semantic search with hybrid filters")

    except ImportError as e:
        print(f"\n✗ Missing dependency: {e}")
        print(f"\nInstall required packages:")
        print(f"  pip install psycopg2-binary pgvector requests")
        if args.provider == "openai":
            print(f"  pip install openai")
        elif args.provider == "bedrock":
            print(f"  pip install boto3")
    except Exception as e:
        print(f"\n✗ Error during embed command: {e}")
        import traceback
        traceback.print_exc()

def run_index(args, config):
    print(f"Running index command using provider: {config['embeddings']['provider']}")
    try:
        output_base_dir = config.get("general", {}).get("output_base_dir", "output")
        embed_provider = config.get("embeddings", {}).get("provider")
        embed_model_name = config.get("embeddings", {}).get(embed_provider, {}).get("model")
        sanitized_model_name = embed_model_name.replace(":", "_").replace("/", "_").replace(".", "_")
        
        embedded_chunks_dir = os.path.join(output_base_dir, f"{embed_provider}_{sanitized_model_name}")
        embedded_chunks_file = os.path.join(embedded_chunks_dir, "chunks_embedded.jsonl")

        if not os.path.exists(embedded_chunks_file):
            print(f"Error: Embedded chunks file not found at {embedded_chunks_file}.")
            print("Please run the 'embed' command first to generate embedded chunks.")
            return

        embedded_chunks = read_records_from_jsonl(embedded_chunks_file, ChunkRecord)
        if not embedded_chunks:
            print(f"No embedded chunks found in {embedded_chunks_file}.")
            return

        print(f"Loaded {len(embedded_chunks)} embedded chunks from {embedded_chunks_file}.")
        build_faiss_index(embedded_chunks, config)

    except Exception as e:
        print(f"Error during index command: {e}")

def run_validate(args, config):
    if not config.get('llm_validation', {}).get('enabled', False):
        print("LLM validation is disabled in the configuration.")
        return

    print(f"Running validate command using provider: {config['llm_validation']['provider']}")
    try:
        llm_client = get_llm_client(config)
        print(f"Successfully instantiated LLM Client for validation: {llm_client.model_name}")

        output_base_dir = config.get("general", {}).get("output_base_dir", "output")
        extracted_data_dir = os.path.join(output_base_dir, "extracted_data")
        validated_data_dir = os.path.join(output_base_dir, "validated_data")
        os.makedirs(validated_data_dir, exist_ok=True)

        chunks_file = os.path.join(extracted_data_dir, "chunks.jsonl")
        relationships_file = os.path.join(extracted_data_dir, "relationships.jsonl")

        if not os.path.exists(chunks_file) or not os.path.exists(relationships_file):
            print(f"Missing extracted data. Expected files: {chunks_file} and {relationships_file}. Please run 'extract' first.")
            return

        chunks = read_records_from_jsonl(chunks_file, ChunkRecord)
        relationships = read_records_from_jsonl(relationships_file, RelationshipRecord)
        if not chunks or not relationships:
            print("No chunks or relationships found to validate.")
            return

        updated_chunks, updated_relationships = validate_data(chunks, relationships, llm_client)

        write_records_to_jsonl(updated_chunks, validated_data_dir, "chunks_validated.jsonl", mode='w')
        write_records_to_jsonl(updated_relationships, validated_data_dir, "relationships_validated.jsonl", mode='w')

        print(f"Validation complete. Saved outputs to {validated_data_dir}")

    except Exception as e:
        print(f"Error during LLM validation: {e}")

def run_query(args, config):
    """
    Semantic search using PostgreSQL pgvector with hybrid filtering.
    Thin wrapper around query.execute_query().
    """
    print(f"\n{'=' * 60}")
    print(f"Query: {args.query_text}")
    print(f"{'=' * 60}\n")

    try:
        from rag_builder.embeddings import get_embedding_provider

        # Build filter summary
        filters = []
        if args.chunk_type:
            filters.append(f"Type: {args.chunk_type}")
        if args.asset_types:
            filters.append(f"Assets: {', '.join(args.asset_types)}")
        if args.taxonomy:
            filters.append(f"Taxonomy: {', '.join(args.taxonomy)}")
        if args.version:
            filters.append(f"Version: {args.version}")
        if not args.include_inactive:
            filters.append("Active datasets only")

        if filters:
            print(f"Filters:")
            for f in filters:
                print(f"  • {f}")
            print()

        # Execute query using modular pipeline
        print(f"Initializing embedding provider: {args.provider}")
        results = execute_query(
            query_text=args.query_text,
            config=config,
            embed_provider=args.provider,
            embed_model=args.model,
            limit=args.limit,
            chunk_type=args.chunk_type,
            asset_types=args.asset_types,
            taxonomy=args.taxonomy,
            version=args.version,
            include_inactive=args.include_inactive
        )

        # Display results
        if not results:
            print(f"✗ No results found\n")
            return

        print(f"✓ Found {len(results)} results\n")
        print(f"{'=' * 60}\n")

        for i, result in enumerate(results, 1):
            # Color-coded similarity score
            similarity = result['similarity']
            if similarity >= 0.8:
                sim_color = "🟢"
            elif similarity >= 0.6:
                sim_color = "🟡"
            else:
                sim_color = "🔴"

            print(f"{i}. {sim_color} [{similarity:.3f}] {result['title'] or '(No title)'}")
            print(f"   ID: {result['canonical_id'] or 'N/A'} | Type: {result['chunk_type']} | Version: {result['version']}")

            # Show STRIDE tags if present
            if result.get('tags') and result['tags'].get('stride'):
                stride_tags = result['tags']['stride']
                if stride_tags:
                    print(f"   STRIDE: {', '.join(stride_tags)}")

            # Show taxonomy if present
            if result.get('tags') and result['tags'].get('taxonomy'):
                taxonomy = result['tags']['taxonomy']
                if taxonomy:
                    print(f"   Taxonomy: {', '.join(taxonomy[:5])}")  # First 5

            # Show text (full or preview)
            if args.show_full:
                print(f"\n   {result['text']}\n")
            else:
                preview = result['text'][:300] + "..." if len(result['text']) > 300 else result['text']
                print(f"   {preview}")

            print(f"   Source: {result['source_uri']}")
            print()

        print(f"{'=' * 60}\n")

    except ImportError as e:
        print(f"\n✗ Missing dependency: {e}")
        print(f"\nInstall required packages:")
        print(f"  pip install psycopg2-binary pgvector requests")
    except Exception as e:
        print(f"\n✗ Error during query: {e}")
        import traceback
        traceback.print_exc()

def run_ask(args, config):
    """
    Full RAG flow with intelligent query planning.
    Thin wrapper around ask.execute_rag().
    """
    print(f"\n{'=' * 60}")
    print(f"Question: {args.question}")
    print(f"{'=' * 60}\n")

    try:
        # Execute RAG using modular pipeline
        print(f"Step 1: Analyzing query intent...")
        print(f"  LLM provider: {args.llm_provider}\n")

        result = execute_rag(
            question=args.question,
            config=config,
            llm_provider=args.llm_provider,
            llm_model=args.llm_model,
            embed_provider=args.embed_provider,
            embed_model=args.embed_model,
            limit=args.limit,
            chunk_type=args.chunk_type,
            asset_types=args.asset_types,
            taxonomy=args.taxonomy,
            version=args.version,
            include_inactive=args.include_inactive,
            show_context=args.show_context
        )

        # Display query analysis
        query_analysis = result.get('query_analysis', {})
        if query_analysis:
            print(f"  Intent: {query_analysis.get('intent', 'N/A')}")
            if query_analysis.get('reasoning'):
                print(f"  Reasoning: {query_analysis['reasoning']}")
            print()

        # Display auto-detected filters
        filters_used = result.get('filters_used', {})
        if any(filters_used.values()):
            print(f"  Auto-detected filters:")
            if filters_used.get('chunk_type'):
                print(f"    • Chunk type: {filters_used['chunk_type']}")
            if filters_used.get('asset_types'):
                print(f"    • Asset types: {', '.join(filters_used['asset_types'])}")
            if filters_used.get('taxonomy'):
                print(f"    • Taxonomy: {', '.join(filters_used['taxonomy'])}")
            if filters_used.get('version'):
                print(f"    • Version: {filters_used['version']}")
            print()

        # Display retrieved context if requested
        if args.show_context and result.get('context'):
            print(f"{'─' * 60}")
            print("RETRIEVED CONTEXT:")
            print(f"{'─' * 60}\n")
            for i, chunk in enumerate(result['context'], 1):
                print(f"{i}. [{chunk['similarity']:.3f}] {chunk['title'] or '(No title)'}")
                print(f"   {chunk['text'][:200]}...\n")
            print(f"{'─' * 60}\n")

        # Display answer
        print(f"{'=' * 60}")
        print("ANSWER:")
        print(f"{'=' * 60}\n")
        print(result['answer'])
        print(f"\n{'=' * 60}")

        # Show retrieval stats
        filter_info = []
        if filters_used.get('chunk_type'):
            filter_info.append(f"type={filters_used['chunk_type']}")
        if filters_used.get('asset_types'):
            filter_info.append(f"assets={','.join(filters_used['asset_types'])}")
        if filters_used.get('taxonomy'):
            filter_info.append(f"taxonomy={','.join(filters_used['taxonomy'][:2])}")
        if filters_used.get('version'):
            filter_info.append(f"v={filters_used['version']}")

        filter_str = f" ({', '.join(filter_info)})" if filter_info else ""
        chunk_count = result.get('chunk_count', len(result.get('context', [])))  # Use chunk_count if available
        print(f"Retrieved {chunk_count} chunks{filter_str} | LLM: {args.llm_provider}/{args.llm_model or 'default'}")
        print(f"{'=' * 60}\n")

    except ImportError as e:
        print(f"\n✗ Missing dependency: {e}")
        print(f"\nInstall required packages:")
        print(f"  pip install psycopg2-binary pgvector requests")
        print(f"  pip install openai  # for OpenAI provider")
    except Exception as e:
        print(f"\n✗ Error during ask command: {e}")
        import traceback
        traceback.print_exc()

def run_enrich_tags(args, config):
    """
    Re-enrich existing chunks with synonym-expanded keywords.
    Thin wrapper around enrich.re_enrich_chunks().
    """
    print(f"\n{'=' * 60}")
    if args.update_stride:
        print("Re-enriching chunks with full metadata extraction and synonym expansion")
    else:
        print("Re-enriching chunks with synonym expansion")
    print(f"{'=' * 60}\n")

    try:
        # Override config with CLI arguments if provided
        enrichment_config = config.copy()
        if args.llm_provider or args.llm_model:
            if 'llm_validation' not in enrichment_config:
                enrichment_config['llm_validation'] = {}

            if args.llm_provider:
                enrichment_config['llm_validation']['provider'] = args.llm_provider

            if args.llm_model:
                provider = args.llm_provider or enrichment_config.get('llm_validation', {}).get('provider', 'openai')
                if provider not in enrichment_config['llm_validation']:
                    enrichment_config['llm_validation'][provider] = {}
                enrichment_config['llm_validation'][provider]['model'] = args.llm_model

        # Initialize LLM client
        print(f"Initializing LLM provider...")
        llm_client = get_llm_client(enrichment_config)
        print(f"  ✓ Provider: {enrichment_config.get('llm_validation', {}).get('provider', 'openai')}")
        print(f"  ✓ Model: {llm_client.model_name}\n")

        # Execute enrichment using modular pipeline
        result = re_enrich_chunks(
            config=config,
            llm_client=llm_client,
            dataset_id=args.dataset_id,
            batch_size=args.batch_size,
            regenerate_embeddings=args.regenerate_embeddings,
            update_stride=args.update_stride
        )

        # Display results
        print(f"\n{'=' * 60}")
        print("ENRICHMENT COMPLETE")
        print(f"{'=' * 60}")
        print(f"Total chunks: {result['total_chunks']}")
        print(f"Enhanced: {result['enhanced_count']}")
        print(f"Failed: {result['failed_count']}")
        print(f"{'=' * 60}\n")

        if args.regenerate_embeddings:
            print("Next step: Regenerate embeddings")
            print("  python -m rag_builder.cli embed --provider ollama --batch-size 50\n")

    except ImportError as e:
        print(f"\n✗ Missing dependency: {e}")
        print(f"\nInstall required packages:")
        print(f"  pip install psycopg2-binary pgvector requests")
        print(f"  pip install openai  # for OpenAI provider")
    except Exception as e:
        print(f"\n✗ Error during enrich-tags command: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
