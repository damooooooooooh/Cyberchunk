import yaml
import os
import re
from typing import List, Dict, Any, Set
from rag_builder.chunk.schema import ChunkRecord

class TaxonomyTagger:
    """
    Assigns taxonomy tags to chunks based on a YAML configuration.
    Uses keyword matching (including synonyms).
    """
    def __init__(self, config_path: str):
        self._config_path = config_path
        self.taxonomy: Dict[str, Set[str]] = {} # Category -> Set of terms
        self._load_taxonomy()
        print(f"Initialized TaxonomyTagger with config: {config_path}")

    def _load_taxonomy(self):
        """Loads and processes the taxonomy YAML configuration."""
        if not os.path.exists(self._config_path):
            raise FileNotFoundError(f"Taxonomy config not found at {self._config_path}")
        with open(self._config_path, 'r', encoding='utf-8') as f:
            raw_taxonomy = yaml.safe_load(f)
        
        for category, terms in raw_taxonomy.items():
            self.taxonomy[category] = set()
            for term in terms:
                self.taxonomy[category].add(term.lower()) # Store all terms in lowercase

    def assign_tags(self, text: str) -> List[str]:
        """
        Assigns taxonomy tags to a given text.
        Returns a list of matching categories.
        """
        assigned_categories = set()
        text_lower = text.lower()

        for category, terms in self.taxonomy.items():
            for term in terms:
                # Use word boundaries to avoid partial matches (e.g., "sql" matching "squall")
                if re.search(r'\b' + re.escape(term) + r'\b', text_lower):
                    assigned_categories.add(category)
                    break # Found a match for this category, move to next category
        return sorted(list(assigned_categories))

    def assign_tags_to_chunks(self, chunks: List[ChunkRecord]) -> List[ChunkRecord]:
        """Assigns taxonomy tags to each ChunkRecord and updates its tags."""
        updated_chunks = []
        for chunk in chunks:
            tags = self.assign_tags(chunk.text)
            chunk.tags["taxonomy"] = list(set(chunk.tags.get("taxonomy", []) + tags)) # Add new tags, avoid duplicates
            updated_chunks.append(chunk)
        return updated_chunks

if __name__ == '__main__':
    # Example usage
    from uuid import uuid4
    import os

    # Create dummy taxonomy config for testing
    TAXONOMY_CONFIG_PATH = "rag_builder/config/taxonomy.yml"
    os.makedirs(os.path.dirname(TAXONOMY_CONFIG_PATH), exist_ok=True)
    with open(TAXONOMY_CONFIG_PATH, "w") as f:
        f.write("""
threat_actor_types:
  - "apt"
  - "nation-state"
  - "insider threat"
attack_vectors:
  - "phishing"
  - "sql injection"
  - "xss"
  - "ddos"
security_controls:
  - "mfa"
  - "firewall"
  - "encryption"
"""
)

    # Create dummy chunks
    dummy_doc_id = uuid4()
    dummy_chunks_for_test = [
        ChunkRecord(
            chunk_id=uuid4(), doc_id=dummy_doc_id, chunk_type="risk",
            text="SQL injection is a severe web vulnerability. Always validate inputs.",
            source_uri="http://test.com", section_path=["risk"], source_locator="#sql", content_hash_sha256="h1"
        ),
        ChunkRecord(
            chunk_id=uuid4(), doc_id=dummy_doc_id, chunk_type="mitigation",
            text="Implement multi-factor authentication (MFA) to prevent unauthorized access.",
            source_uri="http://test.com", section_path=["mit"], source_locator="#auth", content_hash_sha256="h2"
        ),
        ChunkRecord(
            chunk_id=uuid4(), doc_id=dummy_doc_id, chunk_type="general",
            text="Recent attacks by a nation-state actor used sophisticated phishing techniques.",
            source_uri="http://test.com", section_path=["gen"], source_locator="#gen", content_hash_sha256="h3"
        ),
        ChunkRecord(
            chunk_id=uuid4(), doc_id=dummy_doc_id, chunk_type="general",
            text="This chunk has no relevant tags.",
            source_uri="http://test.com", section_path=["gen2"], source_locator="#gen2", content_hash_sha256="h4"
        )
    ]

    try:
        tagger = TaxonomyTagger(config_path=TAXONOMY_CONFIG_PATH)
        updated_chunks = tagger.assign_tags_to_chunks(dummy_chunks_for_test)

        print("\n--- Taxonomy Tags Assigned to Chunks ---")
        for chunk in updated_chunks:
            print(f"Chunk ID: {chunk.chunk_id}")
            print(f"  Text: {chunk.text[:50]}...")
            print(f"  Taxonomy Tags: {chunk.tags['taxonomy']}\n")
    except Exception as e:
        print(f"Error during TaxonomyTagger test: {e}")
    finally:
        if os.path.exists(TAXONOMY_CONFIG_PATH):
            os.remove(TAXONOMY_CONFIG_PATH)
            os.rmdir(os.path.dirname(TAXONOMY_CONFIG_PATH))
