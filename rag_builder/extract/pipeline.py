import re
import yaml
import os
from typing import List, Dict, Any, Tuple, Optional
from uuid import uuid4

from rag_builder.chunk.schema import DocumentRecord, SectionNode, ChunkRecord, RelationshipRecord
from rag_builder.chunk.chunker import process_sections_into_chunks
from rag_builder.llm.client import LLMClient
from rag_builder.llm.factory import get_llm_client
from rag_builder.llm.utils import load_prompt_template

def extract_with_llm(
    doc_record: DocumentRecord,
    section_nodes: List[SectionNode],
    llm_client: LLMClient
) -> Tuple[List[ChunkRecord], List[RelationshipRecord]]:
    """
    Extracts entities and relationships using an LLM with larger context batches.
    Combines related sections to give the model full risk + bullets context.
    Applies guardrails: allowed types, canonical_id fallback, evidence-required MITIGATES, no self-links.
    """
    all_chunks: List[ChunkRecord] = []
    all_relationships: List[RelationshipRecord] = []
    allowed_chunk_types = {"risk", "mitigation", "control", "vulnerability", "threat_actor", "general"}
    prompt_template = _load_prompt_template("extract_entities_and_relationships.txt")

    # Group sections by their top-level path to provide more context (e.g., Description + bullets together)
    batches: List[List[SectionNode]] = []
    current_batch: List[SectionNode] = []
    current_top: tuple = ()
    for sec in section_nodes:
        top = tuple(sec.section_path[:2]) if sec.section_path else ()
        if not current_batch:
            current_batch.append(sec)
            current_top = top
        elif top == current_top:
            current_batch.append(sec)
        else:
            batches.append(current_batch)
            current_batch = [sec]
            current_top = top
    if current_batch:
        batches.append(current_batch)

    for batch in batches:
        combined_text = "\n\n".join(s.clean_text for s in batch if s.clean_text)
        combined_locator = ";".join(s.source_locator for s in batch)
        section_path = batch[0].section_path if batch else []
        print(f"  Processing batch with {len(batch)} sections, top path: {section_path}")

        formatted_prompt = prompt_template.format(
            text=combined_text,
            collection=doc_record.collection or "",
            document_name=doc_record.document_name or "",
            item_id=doc_record.item_id or "",
            publisher=doc_record.publisher or "",
            edition=doc_record.edition or "",
            version=doc_record.version or ""
        )

        try:
            response_json = llm_client.generate_json(formatted_prompt, {})

            temp_entity_map: Dict[str, ChunkRecord] = {}

            if "entities" in response_json and isinstance(response_json["entities"], list):
                for entity in response_json["entities"]:
                    ctype = entity.get("type", "general")
                    if ctype not in allowed_chunk_types:
                        ctype = "general"
                    canonical_id = entity.get("canonical_id") or doc_record.item_id
                    chunk = ChunkRecord(
                        chunk_id=uuid4(),
                        doc_id=doc_record.doc_id,
                        chunk_type=ctype,
                        canonical_id=canonical_id,
                        title=entity.get("title"),
                        text=entity.get("text") or "",
                        source_uri=doc_record.source_uri,
                        publisher=doc_record.publisher,
                        edition=doc_record.edition,
                        version=doc_record.version,
                        section_path=section_path,
                        source_locator=combined_locator,
                        content_hash_sha256=doc_record.content_hash_sha256,
                        llm_model_name=llm_client.model_name
                    )
                    # Skip extremely short/noisy chunks
                    if len(chunk.text.strip()) < 50 and chunk.chunk_type != "general":
                        continue
                    all_chunks.append(chunk)
                    if entity.get("title"):
                        temp_entity_map[entity.get("title")] = chunk

            if "relationships" in response_json and isinstance(response_json["relationships"], list):
                for rel_data in response_json["relationships"]:
                    source_chunk = temp_entity_map.get(rel_data.get("source_title"))
                    target_chunk = temp_entity_map.get(rel_data.get("target_title"))

                    if source_chunk and target_chunk:
                        if source_chunk.chunk_id == target_chunk.chunk_id:
                            continue  # skip self-links
                        relationship = RelationshipRecord(
                            relationship_id=uuid4(),
                            source_chunk_id=source_chunk.chunk_id,
                            target_chunk_id=target_chunk.chunk_id,
                            relationship_type=rel_data.get("relationship_type", "RELATED_TO"),
                            evidence_span=rel_data.get("evidence_span"),
                            llm_derived=True,
                            llm_model_name=llm_client.model_name
                        )
                        # Require evidence for MITIGATES; skip if none provided
                        if relationship.relationship_type == "MITIGATES" and not relationship.evidence_span:
                            continue
                        if relationship.relationship_type == "MITIGATES" and relationship.evidence_span:
                            relationship.strength = rel_data.get("strength") or "medium"
                        all_relationships.append(relationship)

        except Exception as e:
            print(f"  Error processing batch with LLM: {e}")

    return all_chunks, all_relationships


class ExtractorConfig:
    """Helper class to load and access extractor configuration."""
    def __init__(self, config_path: str):
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Extractor config not found at {config_path}")
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        self.extractor_id = self.config.get("metadata", {}).get("extractor_id", "unknown-extractor")

    def get_chunk_type(self, chunk: ChunkRecord) -> str:
        """Determines the chunk type based on chunk content and configured rules."""
        rules = self.config.get("section_classification_rules", [])
        for rule in rules:
            if rule["match_type"] == "heading_alias":
                # For granular chunks, we might match against their inherited title/section path
                # or against the text directly if heading info is less relevant.
                # For now, let's check if the original section_node's heading alias still applies
                # or if the chunk text matches a regex.
                # This requires a slight refactor in how rules are applied.
                # Simplification: Apply to chunk text.
                if self._check_text_regex(chunk.text, rule.get("text_regex")):
                    return rule["chunk_type"]
            elif rule["match_type"] == "always":
                return rule["chunk_type"]
        return "general" # Default fallback

    def is_ignorable(self, section_node: SectionNode) -> bool:
        """Checks if a section should be ignored based on configured rules."""
        ignore_rules = self.config.get("ignore_sections", {})
        if ignore_rules.get("match_type") == "heading_alias":
            patterns = ignore_rules.get("patterns", [])
            for pattern in patterns:
                if pattern.lower() in section_node.heading_text.lower():
                    return True
        return False

    def extract_canonical_id(self, chunk: ChunkRecord) -> Optional[str]:
        """Extracts a canonical ID from the chunk's text or inherited heading based on configured patterns."""
        cid_rules = self.config.get("canonical_id_extraction", [])
        for rule in cid_rules:
            # Check against original heading text from section path
            for path_part in chunk.section_path:
                match = re.search(rule["pattern"], path_part)
                if match:
                    extracted_id = match.group(rule.get("group", 0))
                    return f"{rule.get('prefix', '')}{extracted_id}" if extracted_id else None
            # Also check against chunk text if necessary
            match = re.search(rule["pattern"], chunk.text)
            if match:
                extracted_id = match.group(rule.get("group", 0))
                return f"{rule.get('prefix', '')}{extracted_id}" if extracted_id else None
        return None

    def _check_text_regex(self, text: str, regex_list: Optional[List[str]]) -> bool:
        """Helper to check if any regex in list matches the text."""
        if not regex_list:
            return True # If no regex, rule applies
        for regex_pattern in regex_list:
            if re.search(regex_pattern, text, re.IGNORECASE):
                return True
        return False


def extract_chunks_and_relationships(
    doc_record: DocumentRecord,
    section_nodes: List[SectionNode],
    extractor_config_path: str,
    config: Dict[str, Any], # Main config for LLM client
    use_llm: bool = False,
    chunk_size: int = 512,
    chunk_overlap: int = 128
) -> Tuple[List[ChunkRecord], List[RelationshipRecord]]:
    """
    Extracts ChunkRecord and RelationshipRecord objects from DocumentRecord and SectionNode list.
    Can use rule-based extraction or LLM-assisted extraction.
    """
    if use_llm:
        print("Using LLM for extraction...")
        llm_client = get_llm_client(config)
        return extract_with_llm(doc_record, section_nodes, llm_client)

    # --- Rule-Based Extraction (Fallback) ---
    print("Using rule-based extraction...")
    extractor = ExtractorConfig(extractor_config_path)
    final_chunks: List[ChunkRecord] = []
    relationships: List[RelationshipRecord] = []
    
    canonical_id_map: Dict[str, UUID] = {}

    print(f"Extracting chunks and relationships for Doc ID: {doc_record.doc_id}")

    pre_classified_chunks = []
    for section_node in section_nodes:
        if extractor.is_ignorable(section_node):
            print(f"  Ignoring section: {section_node.heading_text}")
            continue
        
        granular_chunks_from_section = process_sections_into_chunks(
            doc_record,
            [section_node],
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        pre_classified_chunks.extend(granular_chunks_from_section)

    for chunk in pre_classified_chunks:
        chunk.chunk_type = extractor.get_chunk_type(chunk)
        chunk.canonical_id = extractor.extract_canonical_id(chunk)
        final_chunks.append(chunk)
        if chunk.canonical_id:
            canonical_id_map[chunk.canonical_id] = chunk.chunk_id

    for i in range(len(final_chunks) - 1):
        current_chunk = final_chunks[i]
        next_chunk = final_chunks[i+1]

        if current_chunk.chunk_type == "risk" and next_chunk.chunk_type == "mitigation":
            if next_chunk.text and current_chunk.canonical_id and \
               re.search(re.escape(current_chunk.canonical_id), next_chunk.text, re.IGNORECASE):
                relationships.append(
                    RelationshipRecord(
                        relationship_id=uuid4(),
                        source_chunk_id=next_chunk.chunk_id,
                        target_chunk_id=current_chunk.chunk_id,
                        relationship_type="MITIGATES",
                        strength="high"
                    )
                )
            elif not next_chunk.text or not current_chunk.canonical_id:
                 relationships.append(
                    RelationshipRecord(
                        relationship_id=uuid4(),
                        source_chunk_id=next_chunk.chunk_id,
                        target_chunk_id=current_chunk.chunk_id,
                        relationship_type="MITIGATES",
                        strength="medium"
                    )
                )

    print(f"Extracted {len(final_chunks)} chunks and {len(relationships)} relationships.")
    return final_chunks, relationships


if __name__ == '__main__':
    # Example usage
    from rag_builder.ingest.pipeline import ingest_document
    from rag_builder.clean.normalize import normalize_text
    import json

    # Create dummy config and prompt file if they don't exist for testing
    os.makedirs("rag_builder/config/extractors", exist_ok=True)
    with open("rag_builder/config/extractors/generic_html.yml", "w") as f:
        f.write("""
metadata:
  extractor_id: "test-html-extractor"
section_classification_rules:
  - chunk_type: "risk"
    match_type: "heading_alias"
    patterns: ["Risk", "Threat"]
    text_regex: ["vulnerab", "attack"]
  - chunk_type: "mitigation"
    match_type: "heading_alias"
    patterns: ["Mitigation", "Prevention"]
    text_regex: ["prevent", "reduce"]
  - chunk_type: "general"
    match_type: "always"
ignore_sections:
  match_type: "heading_alias"
  patterns: ["Table of Contents", "References"]
canonical_id_extraction:
  - pattern: 'R-(\\d{3})'
    chunk_type: "risk"
    group: 1
    prefix: "TEST-RISK-"
""")
    
    # Mock config
    mock_config = {
        "general": {"output_base_dir": "output"},
        "llm_validation": { # Needed for get_llm_client in LLM path
            "provider": "ollama",
            "ollama": {
                "endpoint": "http://localhost:11434",
                "model": "llama3"
            }
        }
    }

    # Create a dummy HTML file for ingestion
    dummy_html_content = b"""
    <html><body>
        <h1>My Test Document</h1>
        <p>This is some general content.</p>
        <h2>Risk R-001: Injection Flaws</h2>
        <p>Attackers can inject malicious code. This is a severe threat and a major vulnerability in web applications.</p>
        <h3>Mitigation: Input Validation</h3>
        <p>Validating all user input rigorously prevents R-001. This reduces the attack surface significantly.</p>
        <h2>References</h2>
        <p>See our other documents.</p>
    </body></html>
    """
    with open("test_extract_doc.html", "wb") as f:
        f.write(dummy_html_content)

    try:
        # Ingest the dummy document
        doc_record, section_nodes = ingest_document("test_extract_doc.html", mock_config)
        
        # Extract chunks and relationships with rule-based approach
        print("\n--- Testing Rule-Based Extraction ---")
        chunks, relationships = extract_chunks_and_relationships(
            doc_record, section_nodes, "rag_builder/config/extractors/generic_html.yml",
            config=mock_config, use_llm=False
        )

        print("\n--- Extracted Chunks (Rule-Based) ---")
        for chunk in chunks:
            print(f"Chunk ID: {chunk.chunk_id}, Type: {chunk.chunk_type}, Title: {chunk.title}")
        
        print("\n--- Extracted Relationships (Rule-Based) ---")
        for rel in relationships:
            print(f"Rel ID: {rel.relationship_id}, Type: {rel.relationship_type}")
            
        # Example of LLM-assisted extraction (uncomment to test if LLM is running)
        # print("\n--- Testing LLM-Assisted Extraction ---")
        # llm_chunks, llm_relationships = extract_chunks_and_relationships(
        #     doc_record, section_nodes, "rag_builder/config/extractors/generic_html.yml",
        #     config=mock_config, use_llm=True
        # )
        # print(f"LLM Extracted {len(llm_chunks)} chunks and {len(llm_relationships)} relationships.")

    except Exception as e:
        print(f"Error during extraction test: {e}")
    finally:
        if os.path.exists("test_extract_doc.html"):
            os.remove("test_extract_doc.html")
        if os.path.exists("rag_builder/config/extractors/generic_html.yml"):
            os.remove("rag_builder/config/extractors/generic_html.yml")
