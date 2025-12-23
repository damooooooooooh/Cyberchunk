import os
import json
from typing import List, Dict, Any, Tuple
from uuid import UUID
from rag_builder.chunk.schema import ChunkRecord, RelationshipRecord
from rag_builder.llm.client import LLMClient

def _load_prompt_template(template_name: str) -> str:
    """Loads a prompt template from the prompts directory."""
    script_dir = os.path.dirname(__file__)
    prompt_path = os.path.join(script_dir, "..", "llm", "prompts", template_name)
    if not os.path.exists(prompt_path):
        raise FileNotFoundError(f"Prompt template not found: {prompt_path}")
    with open(prompt_path, 'r', encoding='utf-8') as f:
        return f.read()

def validate_data(
    chunks: List[ChunkRecord],
    relationships: List[RelationshipRecord],
    llm_client: LLMClient
) -> Tuple[List[ChunkRecord], List[RelationshipRecord]]:
    """
    Performs LLM-powered validation on chunks and relationships.
    For this initial version, it focuses on validating MITIGATES relationships.
    """
    if not llm_client:
        print("No LLM client provided for validation. Skipping.")
        return chunks, relationships

    print(f"Starting LLM-powered data validation using model: {llm_client.model_name}")

    # Create a mapping for quick lookup of chunks by ID
    chunk_map: Dict[UUID, ChunkRecord] = {chunk.chunk_id: chunk for chunk in chunks}

    validation_prompt_template = _load_prompt_template("validate_relationships.txt")
    validation_schema = {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["PASS", "FAIL", "WARN"]},
            "reasoning": {"type": "string"}
        },
        "required": ["status", "reasoning"]
    }

    updated_relationships: List[RelationshipRecord] = []
    for rel in relationships:
        if rel.relationship_type == "MITIGATES":
            source_chunk = chunk_map.get(rel.source_chunk_id) # Mitigation
            target_chunk = chunk_map.get(rel.target_chunk_id) # Risk

            if source_chunk and target_chunk:
                print(f"Validating MITIGATES relationship between mitigation (ID: {source_chunk.chunk_id}) and risk (ID: {target_chunk.chunk_id}).")
                
                # Prepare prompt
                formatted_prompt = validation_prompt_template.format(
                    risk_title=target_chunk.title or "N/A",
                    risk_text=target_chunk.text,
                    mitigation_title=source_chunk.title or "N/A",
                    mitigation_text=source_chunk.text
                )

                try:
                    validation_result = llm_client.generate_json(formatted_prompt, validation_schema)
                    rel.validation_results = validation_result
                    print(f"  Validation Status: {validation_result.get('status')}")
                except Exception as e:
                    print(f"  Error validating relationship with LLM: {e}")
                    rel.validation_results = {"status": "ERROR", "reasoning": str(e)}
            else:
                print(f"  Warning: Could not find one or both chunks for relationship {rel.relationship_id}. Skipping validation.")
                rel.validation_results = {"status": "WARN", "reasoning": "Related chunk(s) not found."}
        updated_relationships.append(rel)

    print("LLM-powered data validation complete.")
    # For now, we only update relationships. Chunks can be validated in future iterations.
    return chunks, updated_relationships

if __name__ == '__main__':
    from uuid import uuid4
    from datetime import datetime
    from rag_builder.llm.ollama_llm_client import OllamaLLMClient
    from rag_builder.llm.factory import get_llm_client # Use factory for consistency
    import os

    # Mock configuration for testing
    # Ensure to have Ollama running with 'llama3' or similar model for this test
    # e.g., ollama run llama3
    mock_config = {
        "llm_validation": {
            "enabled": True,
            "provider": "ollama",
            "ollama": {
                "endpoint": "http://localhost:11434",
                "model": "llama3"
            },
            "temperature": 0.1,
            "max_tokens": 500
        }
    }
    # Ensure the prompt file exists in rag_builder/llm/prompts/
    
    # Create dummy chunks
    doc_id = uuid4()
    risk_chunk = ChunkRecord(
        chunk_id=uuid4(), doc_id=doc_id, chunk_type="risk", canonical_id="R-SQLI",
        title="SQL Injection Risk",
        text="A high-severity risk where attackers can execute arbitrary SQL code via input fields, potentially leading to data theft or system compromise.",
        source_uri="http://test.com/doc", section_path=["Risks"], source_locator="#sqli", content_hash_sha256="h1"
    )
    mitigation_chunk_good = ChunkRecord(
        chunk_id=uuid4(), doc_id=doc_id, chunk_type="mitigation",
        title="Parameterized Queries",
        text="Using parameterized queries or prepared statements ensures that user input is treated as data, not executable code, thereby preventing SQL Injection.",
        source_uri="http://test.com/doc", section_path=["Mitigations"], source_locator="#mit1", content_hash_sha256="h2"
    )
    mitigation_chunk_bad = ChunkRecord(
        chunk_id=uuid4(), doc_id=doc_id, chunk_type="mitigation",
        title="Cross-Site Scripting Prevention",
        text="Sanitizing user input to remove script tags is essential for preventing Cross-Site Scripting (XSS) attacks.",
        source_uri="http://test.com/doc", section_path=["Mitigations"], source_locator="#mit2", content_hash_sha256="h3"
    )
    
    # Create dummy relationships
    rel_good = RelationshipRecord(
        relationship_id=uuid4(), source_chunk_id=mitigation_chunk_good.chunk_id,
        target_chunk_id=risk_chunk.chunk_id, relationship_type="MITIGATES"
    )
    rel_bad = RelationshipRecord(
        relationship_id=uuid4(), source_chunk_id=mitigation_chunk_bad.chunk_id,
        target_chunk_id=risk_chunk.chunk_id, relationship_type="MITIGATES"
    )

    test_chunks = [risk_chunk, mitigation_chunk_good, mitigation_chunk_bad]
    test_relationships = [rel_good, rel_bad]

    try:
        llm_client_instance = get_llm_client(mock_config)
        updated_chunks, updated_relationships = validate_data(test_chunks, test_relationships, llm_client_instance)

        print("\n--- Validation Results ---")
        for rel in updated_relationships:
            if rel.validation_results:
                print(f"Relationship {rel.relationship_id} (Type: {rel.relationship_type}):")
                print(f"  Status: {rel.validation_results.get('status')}")
                print(f"  Reasoning: {rel.validation_results.get('reasoning')}\n")
            else:
                print(f"Relationship {rel.relationship_id} (Type: {rel.relationship_type}): No validation results.\n")

    except ConnectionError as e:
        print(f"Connection error during validation test: {e}")
        print("Ensure your Ollama server is running and accessible with the specified model.")
    except Exception as e:
        print(f"An error occurred during validation test: {e}")
