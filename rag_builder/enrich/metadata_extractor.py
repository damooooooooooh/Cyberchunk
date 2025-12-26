"""
Metadata extraction module for Phase 1 enrichment.

Extracts tags, STRIDE categories, and semantic metadata from chunks
using a second LLM pass.
"""

import json
from typing import Dict, Any
from pathlib import Path
from rag_builder.chunk.schema import ChunkRecord


def load_metadata_prompt() -> str:
    """Load the metadata enrichment prompt template"""
    prompt_path = Path(__file__).parent.parent / "llm" / "prompts" / "enrich-chunk-metadata.txt"
    return prompt_path.read_text()


def extract_chunk_metadata(chunk: ChunkRecord, llm_client) -> Dict[str, Any]:
    """
    Extract metadata tags from a chunk using LLM.

    Args:
        chunk: The ChunkRecord to analyze
        llm_client: LLM client for API calls

    Returns:
        Dictionary with extracted metadata fields
    """
    # Load prompt template
    prompt_template = load_metadata_prompt()

    # Build context string from section_path
    section_context = " > ".join(chunk.section_path)

    # Fill in template
    prompt = prompt_template.format(
        chunk_type=chunk.chunk_type,
        title=chunk.title or "N/A",
        text=chunk.text,
        section_path=section_context,
        source_uri=chunk.source_uri
    )

    # Call LLM
    try:
        response = llm_client.generate_json(prompt, {})
    except Exception as e:
        print(f"Warning: LLM call failed for chunk {chunk.chunk_id}: {e}")
        return _get_empty_metadata()

    # Validate and clean response
    metadata = _validate_metadata_response(response, chunk)

    return metadata


def _get_empty_metadata() -> Dict[str, Any]:
    """Return empty metadata structure"""
    return {
        "keywords": [],
        "topics": [],
        "taxonomy": [],
        "stride_categories": [],
        "asset_types": [],
        "technologies": [],
        "security_controls": []
    }


def _validate_metadata_response(response: Dict[str, Any], chunk: ChunkRecord) -> Dict[str, Any]:
    """Validate and clean the LLM response"""

    # Ensure all required fields exist
    validated = {
        "keywords": response.get("keywords", []),
        "topics": response.get("topics", []),
        "taxonomy": response.get("taxonomy", []),
        "stride_categories": response.get("stride_categories", []),
        "asset_types": response.get("asset_types", []),
        "technologies": response.get("technologies", []),
        "security_controls": response.get("security_controls", [])
    }

    # Clean up lists (remove empty strings, deduplicate)
    for key in validated:
        if isinstance(validated[key], list):
            # Clean string lists
            validated[key] = [
                item.strip()
                for item in validated[key]
                if item and isinstance(item, str) and item.strip()
            ]
            # Deduplicate while preserving order
            seen = set()
            deduped = []
            for item in validated[key]:
                if item not in seen:
                    seen.add(item)
                    deduped.append(item)
            validated[key] = deduped

    # Validate STRIDE categories
    valid_stride = {
        "Spoofing",
        "Tampering",
        "Repudiation",
        "Information Disclosure",
        "Denial of Service",
        "Elevation of Privilege"
    }
    validated["stride_categories"] = [
        s for s in validated["stride_categories"]
        if s in valid_stride
    ]

    # Clean taxonomy list (remove empty strings, deduplicate)
    # Trust LLM to extract only explicitly mentioned codes (no whitelist)
    if isinstance(validated["taxonomy"], list):
        validated["taxonomy"] = [
            item.strip()
            for item in validated["taxonomy"]
            if item and isinstance(item, str) and item.strip()
        ]
        # Deduplicate while preserving order
        seen = set()
        deduped = []
        for item in validated["taxonomy"]:
            if item not in seen:
                seen.add(item)
                deduped.append(item)
        validated["taxonomy"] = deduped

    # Limit keywords to top 10
    if len(validated["keywords"]) > 10:
        validated["keywords"] = validated["keywords"][:10]

    # Limit topics to top 5
    if len(validated["topics"]) > 5:
        validated["topics"] = validated["topics"][:5]

    return validated
