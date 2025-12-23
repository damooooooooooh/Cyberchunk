import os
from typing import List, Dict, Any
from rag_builder.chunk.schema import ChunkRecord
from rag_builder.tag.keywords import KeywordExtractor
from rag_builder.tag.topics import TopicModeler
from rag_builder.tag.taxonomy import TaxonomyTagger
import traceback

def tag_chunks(chunks: List[ChunkRecord], config: Dict[str, Any]) -> List[ChunkRecord]:
    """
    Applies keyword, topic, and taxonomy tagging to a list of ChunkRecord objects.
    Trains models if they don't exist.
    """
    if not chunks:
        print("No chunks provided for tagging.")
        return []

    output_base_dir = config.get("general", {}).get("output_base_dir", "output")
    models_dir = os.path.join(output_base_dir, "models")
    os.makedirs(models_dir, exist_ok=True)

    print("--- Starting Keyword Extraction ---")
    keyword_extractor_path = os.path.join(models_dir, "keywords.pkl")
    keyword_extractor: KeywordExtractor
    if os.path.exists(keyword_extractor_path):
        keyword_extractor = KeywordExtractor.load(keyword_extractor_path)
    else:
        print("Training KeywordExtractor...")
        keyword_extractor = KeywordExtractor(top_n=5)
        all_texts = [chunk.text for chunk in chunks]
        keyword_extractor.train(all_texts)
        keyword_extractor.save(keyword_extractor_path)
    
    chunks = keyword_extractor.extract_keywords_from_chunks(chunks)
    print(f"Applied keyword tagging to {len(chunks)} chunks.")
    print("--- Finished Keyword Extraction ---")

    print("\n--- Starting Topic Modeling ---")
    vectorizer_path = os.path.join(models_dir, "topic_vectorizer.pkl")
    topic_model_path = os.path.join(models_dir, "topic_model.pkl")
    topic_modeler: TopicModeler
    num_topics = config.get("tagging", {}).get("num_topics", 5) # Configurable number of topics
    if os.path.exists(vectorizer_path) and os.path.exists(topic_model_path):
        topic_modeler = TopicModeler.load(vectorizer_path, topic_model_path, num_topics=num_topics)
    else:
        print("Training TopicModeler...")
        topic_modeler = TopicModeler(num_topics=num_topics)
        all_texts = [chunk.text for chunk in chunks]
        topic_modeler.train(all_texts)
        topic_modeler.save(vectorizer_path, topic_model_path)
    
    chunks = topic_modeler.assign_topics_to_chunks(chunks)
    print(f"Applied topic tagging to {len(chunks)} chunks.")
    print("--- Finished Topic Modeling ---")

    print("\n--- Starting Taxonomy Tagging ---")
    taxonomy_config_path = "rag_builder/config/taxonomy.yml" # Hardcoded path for now
    taxonomy_tagger = TaxonomyTagger(config_path=taxonomy_config_path)
    chunks = taxonomy_tagger.assign_tags_to_chunks(chunks)
    print(f"Applied taxonomy tagging to {len(chunks)} chunks.")
    print("--- Finished Taxonomy Tagging ---")

    print("Chunk tagging complete.")
    return chunks

if __name__ == '__main__':
    from uuid import uuid4
    import json

    # Mock config for testing
    mock_config = {
        "general": {"output_base_dir": "test_tag_output"},
        "tagging": {"num_topics": 2}
    }
    
    # Create dummy taxonomy config for testing if it doesn't exist
    TAXONOMY_CONFIG_PATH = "rag_builder/config/taxonomy.yml"
    os.makedirs(os.path.dirname(TAXONOMY_CONFIG_PATH), exist_ok=True)
    if not os.path.exists(TAXONOMY_CONFIG_PATH):
        with open(TAXONOMY_CONFIG_PATH, "w") as f:
            f.write("""
threat_actor_types:
  - "apt"
  - "nation-state"
attack_vectors:
  - "phishing"
  - "sql injection"
security_controls:
  - "mfa"
  - "firewall"
"""
)

    # Create dummy chunks
    dummy_doc_id = uuid4()
    dummy_chunks_for_test = [
        ChunkRecord(
            chunk_id=uuid4(), doc_id=dummy_doc_id, chunk_type="risk",
            text="SQL injection is a severe web vulnerability. Always validate inputs to prevent attacks.",
            source_uri="http://test.com", section_path=["risk"], source_locator="#sql", content_hash_sha256="h1"
        ),
        ChunkRecord(
            chunk_id=uuid4(), doc_id=dummy_doc_id, chunk_type="mitigation",
            text="Implement multi-factor authentication (MFA) to prevent unauthorized access and data breaches.",
            source_uri="http://test.com", section_path=["mit"], source_locator="#auth", content_hash_sha256="h2"
        ),
        ChunkRecord(
            chunk_id=uuid4(), doc_id=dummy_doc_id, chunk_type="general",
            text="Recent attacks by a nation-state actor used sophisticated phishing techniques.",
            source_uri="http://test.com", section_path=["gen"], source_locator="#gen", content_hash_sha256="h3"
        ),
        ChunkRecord(
            chunk_id=uuid4(), doc_id=dummy_doc_id, chunk_type="general",
            text="General security advice about best practices and monitoring systems.",
            source_uri="http://test.com", section_path=["gen2"], source_locator="#gen2", content_hash_sha256="h4"
        )
    ]

    try:
        updated_chunks = tag_chunks(dummy_chunks_for_test, mock_config)

        print("\n--- Chunks after Tagging ---")
        for chunk in updated_chunks:
            print(f"Chunk ID: {chunk.chunk_id}")
            print(f"  Text: {chunk.text[:50]}...")
            print(f"  Tags: {json.dumps(chunk.tags, indent=2)}\n")
    except Exception as e:
        print(f"Error during tagging test: {e}")
    finally:
        # Clean up test output
        test_models_dir = os.path.join(mock_config["general"]["output_base_dir"], "models")
        if os.path.exists(os.path.join(test_models_dir, "keywords.pkl")):
            os.remove(os.path.join(test_models_dir, "keywords.pkl"))
        if os.path.exists(os.path.join(test_models_dir, "topic_vectorizer.pkl")):
            os.remove(os.path.join(test_models_dir, "topic_vectorizer.pkl"))
        if os.path.exists(os.path.join(test_models_dir, "topic_model.pkl")):
            os.remove(os.path.join(test_models_dir, "topic_model.pkl"))
        if os.path.exists(test_models_dir):
            os.rmdir(test_models_dir)
        if os.path.exists(mock_config["general"]["output_base_dir"]):
            os.rmdir(mock_config["general"]["output_base_dir"])
        if os.path.exists(TAXONOMY_CONFIG_PATH):
            os.remove(TAXONOMY_CONFIG_PATH)
            os.rmdir(os.path.dirname(TAXONOMY_CONFIG_PATH))