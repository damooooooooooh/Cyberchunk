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
    embed_parser.set_defaults(func=run_embed)

    # Index command
    index_parser = subparsers.add_parser("index", help="Build FAISS index from embeddings.")
    index_parser.set_defaults(func=run_index)

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Perform LLM-powered data validation.")
    validate_parser.set_defaults(func=run_validate)

    # Query command
    query_parser = subparsers.add_parser("query", help="Run smoke tests/queries against the index.")
    query_parser.add_argument("--query-string", type=str, required=True, help="Query string for retrieval.")
    query_parser.add_argument("--k", type=int, default=5, help="Number of top results to retrieve.")
    query_parser.set_defaults(func=run_query)

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
            llm_client=llm_client
        )
        print(f"\nSuccessfully ingested document: {doc_record.title} (ID: {doc_record.doc_id})")
        print(f"Extracted {len(section_nodes)} sections.")

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
    print(f"Running embed command using provider: {config['embeddings']['provider']}")
    try:
        embedder = get_embedder(config)
        print(f"Successfully instantiated embedder: {embedder.model_name}")

        output_base_dir = config.get("general", {}).get("output_base_dir", "output")
        tagged_data_dir = os.path.join(output_base_dir, "tagged_data")
        tagged_chunks_file = os.path.join(tagged_data_dir, "chunks_tagged.jsonl")

        if not os.path.exists(tagged_chunks_file):
            print(f"Error: Tagged chunks file not found at {tagged_chunks_file}. Please run 'tag' command first.")
            return

        chunks_to_embed = read_records_from_jsonl(tagged_chunks_file, ChunkRecord)
        if not chunks_to_embed:
            print(f"No tagged chunks found in {tagged_chunks_file}. Nothing to embed.")
            return
        
        print(f"Loaded {len(chunks_to_embed)} tagged chunks for embedding.")

        # Embed the chunks
        embedded_chunks = embed_chunks(chunks_to_embed, embedder)
        print(f"Successfully embedded {len(embedded_chunks)} chunks using {embedder.model_name}.")
        if embedded_chunks and embedded_chunks[0].embedding_vector:
            print(f"First embedded chunk (ID: {embedded_chunks[0].chunk_id}, vector length: {len(embedded_chunks[0].embedding_vector)}).")
        
        # Save the embedded chunks to a model-specific JSONL file
        embed_provider = config.get("embeddings", {}).get("provider")
        embed_model_name = config.get("embeddings", {}).get(embed_provider, {}).get("model")
        sanitized_model_name = embed_model_name.replace(":", "_").replace("/", "_").replace(".", "_")
        
        embedded_chunks_dir = os.path.join(output_base_dir, f"{embed_provider}_{sanitized_model_name}")
        os.makedirs(embedded_chunks_dir, exist_ok=True)
        write_records_to_jsonl(embedded_chunks, embedded_chunks_dir, "chunks_embedded.jsonl", mode='w')
        print(f"Saved embedded chunks to {os.path.join(embedded_chunks_dir, 'chunks_embedded.jsonl')}")

    except Exception as e:
        print(f"Error during embed command: {e}")

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
    print(f"Running query for: '{args.query_string}'")
    try:
        # Determine the model-specific directory
        output_base_dir = config.get("general", {}).get("output_base_dir", "output")
        embed_provider = config.get("embeddings", {}).get("provider")
        embed_model_name = config.get("embeddings", {}).get(embed_provider, {}).get("model")
        sanitized_model_name = embed_model_name.replace(":", "_").replace("/", "_").replace(".", "_")
        model_output_dir = os.path.join(output_base_dir, f"{embed_provider}_{sanitized_model_name}")

        # Check if index exists
        if not os.path.exists(os.path.join(model_output_dir, "chunks.faiss")):
            print(f"Error: FAISS index not found in {model_output_dir}. Please run 'index' command first.")
            return

        # Load the index and chunks
        print("Loading FAISS index and chunk data...")
        faiss_index = FaissIndex.load(model_output_dir, "chunks")
        embedded_chunks = read_records_from_jsonl(os.path.join(model_output_dir, "chunks_embedded.jsonl"), ChunkRecord)
        chunk_map = {chunk.chunk_id: chunk for chunk in embedded_chunks}

        # Embed the query
        print("Embedding query string...")
        embedder = get_embedder(config)
        query_embedding = embedder.embed_text(args.query_string)

        # Perform the search
        print(f"Searching for top {args.k} results...")
        search_results = faiss_index.search(query_embedding, k=args.k)

        # Display results
        if not search_results:
            print("No results found.")
            return
        
        print("\n--- Query Results ---")
        for i, (distance, chunk_uuid) in enumerate(search_results):
            result_chunk = chunk_map.get(chunk_uuid)
            if result_chunk:
                print(f"Result {i+1} (Distance: {distance:.4f}):")
                print(f"  Chunk ID: {result_chunk.chunk_id}")
                print(f"  Title: {result_chunk.title}")
                print(f"  Source: {result_chunk.source_uri}")
                print(f"  Text: {result_chunk.text[:250]}...\n")
            else:
                print(f"Result {i+1}: Could not find chunk data for UUID {chunk_uuid}")

    except Exception as e:
        print(f"Error during query command: {e}")

if __name__ == "__main__":
    main()
