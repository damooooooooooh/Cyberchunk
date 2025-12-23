from typing import List
from rag_builder.chunk.schema import ChunkRecord
from rag_builder.embed.embedder import Embedder

def embed_chunks(chunks: List[ChunkRecord], embedder: Embedder) -> List[ChunkRecord]:
    """
    Generates embeddings for a list of ChunkRecord objects using the provided embedder.
    Updates each ChunkRecord with its embedding vector and the model name used.
    """
    if not chunks:
        print("No chunks to embed.")
        return []

    texts_to_embed = [chunk.text for chunk in chunks]
    print(f"Embedding {len(texts_to_embed)} chunks using model: {embedder.model_name}...")

    embeddings = embedder.embed_texts(texts_to_embed)

    if len(embeddings) != len(chunks):
        raise ValueError(f"Number of embeddings ({len(embeddings)}) does not match number of chunks ({len(chunks)}).")

    for i, chunk in enumerate(chunks):
        chunk.embedding_vector = embeddings[i] # This field needs to be added to ChunkRecord or handled
        chunk.embedding_model = embedder.model_name
        # Note: embedding_vector_id and embedding_vector_path will be set during FAISS indexing

    print("Finished embedding chunks.")
    return chunks

if __name__ == '__main__':
    from uuid import uuid4
    from rag_builder.embed.ollama_embedder import OllamaEmbedder
    # from rag_builder.embed.bedrock_embedder import BedrockEmbedder # Uncomment to test Bedrock

    # Mock ChunkRecord (ensure your schema.py has an `embedding_vector: Optional[List[float]]` field)
    # For testing, we need to add `embedding_vector` to ChunkRecord schema temporarily if it's not there.
    # In a real scenario, this would be part of the schema definition.
    
    # Temporarily define a test ChunkRecord class with embedding_vector for local testing
    class TestChunkRecord(ChunkRecord):
        embedding_vector: Optional[List[float]] = None

    dummy_doc_id = uuid4()
    dummy_chunks_for_test = [
        TestChunkRecord(
            chunk_id=uuid4(),
            doc_id=dummy_doc_id,
            chunk_type="general",
            text="This is a test sentence for embedding in a dummy chunk.",
            source_uri="http://example.com/test",
            section_path=["Test"],
            source_locator="#test",
            content_hash_sha256="hash1"
        ),
        TestChunkRecord(
            chunk_id=uuid4(),
            doc_id=dummy_doc_id,
            chunk_type="risk",
            text="Another sentence to test the embedding process.",
            source_uri="http://example.com/test",
            section_path=["Test"],
            source_locator="#test2",
            content_hash_sha256="hash2"
        )
    ]

    # Test with Ollama
    OLLAMA_ENDPOINT = "https://chat.meshanised.xyz/ollama/api"
    OLLAMA_MODEL = "nomic-embed-text:latest"
    try:
        ollama_embedder_instance = OllamaEmbedder(endpoint=OLLAMA_ENDPOINT, model=OLLAMA_MODEL)
        embedded_ollama_chunks = embed_chunks(dummy_chunks_for_test, ollama_embedder_instance)
        print(f"\nEmbedded {len(embedded_ollama_chunks)} chunks with Ollama.")
        if embedded_ollama_chunks and embedded_ollama_chunks[0].embedding_vector:
            print(f"First chunk embedding length: {len(embedded_ollama_chunks[0].embedding_vector)}")
            print(f"First chunk embedding (first 5 values): {embedded_ollama_chunks[0].embedding_vector[:5]}")
    except Exception as e:
        print(f"Error testing Ollama embedding: {e}")

    # Test with Bedrock (uncomment and configure if you have AWS setup)
    # AWS_REGION = "us-east-1"
    # BEDROCK_MODEL = "amazon.titan-embed-text-v2:0"
    # try:
    #     bedrock_embedder_instance = BedrockEmbedder(region=AWS_REGION, model=BEDROCK_MODEL)
    #     embedded_bedrock_chunks = embed_chunks(dummy_chunks_for_test, bedrock_embedder_instance)
    #     print(f"\nEmbedded {len(embedded_bedrock_chunks)} chunks with Bedrock.")
    #     if embedded_bedrock_chunks and embedded_bedrock_chunks[0].embedding_vector:
    #         print(f"First chunk embedding length: {len(embedded_bedrock_chunks[0].embedding_vector)}")
    # except Exception as e:
    #     print(f"Error testing Bedrock embedding: {e}")
