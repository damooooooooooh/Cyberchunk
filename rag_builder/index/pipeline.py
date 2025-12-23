import os
import numpy as np
from typing import List, Dict, Any
from rag_builder.chunk.schema import ChunkRecord
from rag_builder.embed.faiss_index import FaissIndex

def build_faiss_index(embedded_chunks: List[ChunkRecord], config: Dict[str, Any]):
    """
    Builds a FAISS index from a list of embedded ChunkRecord objects and saves it.
    """
    if not embedded_chunks:
        print("No embedded chunks provided to build FAISS index.")
        return

    # Determine embedding dimension from the first chunk
    embedding_dimension = len(embedded_chunks[0].embedding_vector)
    if embedding_dimension == 0:
        raise ValueError("Embedded chunks must have non-empty embedding_vector.")

    # Prepare data for FAISS
    chunk_uuids = [chunk.chunk_id for chunk in embedded_chunks]
    vectors = [chunk.embedding_vector for chunk in embedded_chunks]

    # Initialize FAISS index
    # For now, using FlatL2, which is simple. Can be made configurable later.
    faiss_idx = FaissIndex(embedding_dimension=embedding_dimension, index_type="FlatL2")
    faiss_idx.add_vectors(chunk_uuids, vectors)

    # Determine output directory (model-specific)
    output_base_dir = config.get("general", {}).get("output_base_dir", "output")
    embed_config = config.get("embeddings", {})
    embed_provider = embed_config.get("provider")
    embed_model_name = embed_config.get(embed_provider, {}).get("model")

    if not embed_model_name:
        raise ValueError("Embedding model name not found in config for creating output directory.")

    # Sanitize model name for directory path
    sanitized_model_name = embed_model_name.replace(":", "_").replace("/", "_").replace(".", "_")
    model_output_dir = os.path.join(output_base_dir, f"{embed_provider}_{sanitized_model_name}")
    
    # Save the FAISS index and mapping
    faiss_idx.save(model_output_dir, "chunks")

    print(f"FAISS index built and saved to {model_output_dir}")
    print(f"Index contains {faiss_idx.index.ntotal} vectors.")

if __name__ == '__main__':
    from uuid import uuid4
    from datetime import datetime
    from rag_builder.embed.ollama_embedder import OllamaEmbedder
    from rag_builder.embed.factory import get_embedder # Need get_embedder to mock config correctly

    # Mock config for testing
    mock_config = {
        "general": {"output_base_dir": "test_output_index"},
        "embeddings": {
            "provider": "ollama",
            "ollama": {
                "endpoint": "http://localhost:11434", # Dummy, won't call in this test
                "model": "nomic-embed-text:latest"
            }
        }
    }

    # Generate dummy embedded chunks (simulating output from embed_chunks)
    test_dim = 768 # Example dimension for nomic-embed-text
    dummy_doc_id = uuid4()
    embedded_chunks_for_test = [
        ChunkRecord(
            chunk_id=uuid4(), doc_id=dummy_doc_id, chunk_type="general", text="test text 1",
            source_uri="http://dummy.com/1", section_path=["A"], source_locator="#1", content_hash_sha256="h1",
            embedding_model="nomic-embed-text:latest", embedding_vector=np.random.rand(test_dim).tolist()
        ),
        ChunkRecord(
            chunk_id=uuid4(), doc_id=dummy_doc_id, chunk_type="risk", text="test text 2",
            source_uri="http://dummy.com/1", section_path=["B"], source_locator="#2", content_hash_sha256="h2",
            embedding_model="nomic-embed-text:latest", embedding_vector=np.random.rand(test_dim).tolist()
        )
    ]
    
    # Build and save the index
    build_faiss_index(embedded_chunks_for_test, mock_config)

    # Clean up test output
    test_output_dir = os.path.join("test_output_index", "ollama_nomic-embed-text_latest")
    if os.path.exists(os.path.join(test_output_dir, "chunks.faiss")):
        os.remove(os.path.join(test_output_dir, "chunks.faiss"))
    if os.path.exists(os.path.join(test_output_dir, "chunks_mapping.json")):
        os.remove(os.path.join(test_output_dir, "chunks_mapping.json"))
    if os.path.exists(test_output_dir):
        os.rmdir(test_output_dir)
    if os.path.exists("test_output_index"):
        os.rmdir("test_output_index")
