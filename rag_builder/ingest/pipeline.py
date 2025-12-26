import os
import hashlib
import html
import json
import re
from typing import List, Tuple, Optional
from urllib.parse import urlparse
from datetime import datetime
from uuid import uuid4

from rag_builder.chunk.schema import DocumentRecord, SectionNode, ChunkRecord
from rag_builder.ingest.fetch import fetch_uri, calculate_hash as fetch_calculate_hash
from rag_builder.ingest.readers import read_file_content, calculate_hash as reader_calculate_hash
from rag_builder.parse.html_to_sections import html_to_sections
from rag_builder.parse.md_to_sections import md_to_sections
from rag_builder.clean.normalize import normalize_text
from rag_builder.llm.client import LLMClient
from rag_builder.llm.utils import load_prompt_template
from rag_builder.enrich.metadata_extractor import extract_chunk_metadata

# Minimal quality guardrails for sections
MIN_SECTION_CHARS = 50  # skip very short/noisy fragments (except top-level headings)

def enrich_chunks_with_tags(chunks: List[ChunkRecord], llm_client) -> List[ChunkRecord]:
    """
    Phase 1: Second LLM pass to extract tags, STRIDE categories, and metadata.

    Args:
        chunks: List of ChunkRecords to enrich
        llm_client: LLM client for API calls

    Returns:
        List of enriched ChunkRecords with populated tags
    """
    if not llm_client:
        print("Warning: No LLM client provided for tag enrichment, skipping")
        return chunks

    print(f"\n--- Phase 1: Enriching {len(chunks)} chunks with tags & STRIDE ---")

    enriched_chunks = []
    for i, chunk in enumerate(chunks, 1):
        try:
            print(f"  Enriching chunk {i}/{len(chunks)} ({chunk.chunk_type}): {chunk.title or chunk.text[:50]}...")

            # Call LLM to extract metadata
            metadata = extract_chunk_metadata(chunk, llm_client)

            # Populate tags
            chunk.tags["keywords"] = metadata.get("keywords", [])
            chunk.tags["topics"] = metadata.get("topics", [])
            chunk.tags["taxonomy"] = metadata.get("taxonomy", [])
            chunk.tags["stride"] = metadata.get("stride_categories", [])
            chunk.tags["asset_types"] = metadata.get("asset_types", [])
            chunk.tags["technologies"] = metadata.get("technologies", [])
            chunk.tags["security_controls"] = metadata.get("security_controls", [])

            print(f"    ✓ Tags: {len(chunk.tags.get('keywords', []))} keywords, "
                  f"{len(chunk.tags.get('stride', []))} STRIDE categories, "
                  f"{len(chunk.tags.get('asset_types', []))} asset types")

            enriched_chunks.append(chunk)

        except Exception as e:
            print(f"  ⚠ Warning: Failed to enrich chunk {chunk.chunk_id}: {e}")
            # Keep chunk without enrichment
            enriched_chunks.append(chunk)

    print(f"✓ Enrichment complete: {len(enriched_chunks)} chunks enriched\n")
    return enriched_chunks

def _load_prompt_template(template_name: str) -> str:
    """Loads a prompt template from the prompts directory."""
    script_dir = os.path.dirname(__file__)
    prompt_path = os.path.join(script_dir, "..", "llm", "prompts", template_name)
    if not os.path.exists(prompt_path):
        raise FileNotFoundError(f"Prompt template not found: {prompt_path}")
    with open(prompt_path, 'r', encoding='utf-8') as f:
        return f.read()

def _find_section_by_heading(heading_text: str, sections: List[SectionNode], section_map: dict) -> Optional[SectionNode]:
    """Find a section by heading text, with fuzzy matching."""
    # Direct match
    if heading_text in section_map:
        return section_map[heading_text]

    # Try case-insensitive match
    heading_lower = heading_text.lower()
    for section in sections:
        if section.heading_text.lower() == heading_lower:
            return section

    # Try partial match (heading contains or is contained in)
    for section in sections:
        if heading_lower in section.heading_text.lower() or section.heading_text.lower() in heading_lower:
            return section

    # Default to first section if no match
    return sections[0] if sections else None

def _parse_llm_response_whole_document(response_json: dict, doc_record, sections: List[SectionNode],
                                       section_map: dict, item_id: Optional[str], llm_client) -> List[ChunkRecord]:
    """
    Parse LLM response for whole document processing.
    Maps chunks back to their source sections using location field.
    """
    chunks = []

    # Normalize response - some LLMs return {"response": "<json string>"}
    if isinstance(response_json, dict) and "response" in response_json and isinstance(response_json["response"], str):
        raw = response_json["response"]
        raw = raw.replace("```json", "").replace("```", "").strip()
        raw = raw.replace("\\n", "\n")
        try:
            response_json = json.loads(raw)
        except Exception:
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                response_json = json.loads(match.group(0))
            else:
                raise ValueError("LLM response did not contain valid JSON.")

    # Extract risk chunk
    risk_data = response_json.get("risk", {}) or {}
    if risk_data:
        risk_text_blocks = risk_data.get("description_verbatim_blocks") or risk_data.get("description_blocks") or []
        risk_text = " ".join([b.get("text_verbatim") or b.get("text") or "" for b in risk_text_blocks if b.get("text_verbatim") or b.get("text")])
        risk_title = risk_data.get("title_verbatim") or risk_data.get("title") or doc_record.title

        # Find section based on location
        risk_location = risk_text_blocks[0].get("location") if risk_text_blocks else None
        section = _find_section_by_heading(risk_location or risk_title, sections, section_map)

        if (risk_title and risk_text and
            risk_title != "Not found in document" and
            risk_text != "Not found in document" and section):
            chunks.append(
                ChunkRecord(
                    doc_id=doc_record.doc_id,
                    section_id=section.section_id,
                    chunk_type="risk",
                    canonical_id=item_id or risk_title,
                    title=risk_title,
                    text=risk_text,
                    source_uri=doc_record.source_uri,
                    publisher=doc_record.publisher,
                    edition=doc_record.edition,
                    version=doc_record.version,
                    section_path=section.section_path,
                    source_locator=section.source_locator,
                    content_hash_sha256=doc_record.content_hash_sha256,
                    llm_model_name=llm_client.model_name
                )
            )

    # Weaknesses
    for w in response_json.get("weaknesses_verbatim", []) + response_json.get("weakness", []):
        text_w = w.get("text") or w.get("weakness_text_verbatim") or w.get("weakness_text")

        if text_w and text_w != "Not found in document":
            # Find section based on location
            location = w.get("location") or w.get("title")
            section = _find_section_by_heading(location, sections, section_map)

            if section:
                chunks.append(
                    ChunkRecord(
                        doc_id=doc_record.doc_id,
                        section_id=section.section_id,
                        chunk_type="weakness",
                        canonical_id=item_id or risk_data.get("title_verbatim") or risk_data.get("title"),
                        title=w.get("title") or section.heading_text or text_w[:80],
                        text=text_w,
                        source_uri=doc_record.source_uri,
                        publisher=doc_record.publisher,
                        edition=doc_record.edition,
                        version=doc_record.version,
                        section_path=section.section_path,
                        source_locator=section.source_locator,
                        content_hash_sha256=doc_record.content_hash_sha256,
                        llm_model_name=llm_client.model_name
                    )
                )

    # Mitigations
    for m in response_json.get("mitigations_verbatim", []) + response_json.get("mitigation", []):
        text_m = m.get("text") or m.get("mitigation_text_verbatim") or m.get("mitigation_text")

        if text_m and text_m != "Not found in document":
            location = m.get("location") or m.get("title")
            section = _find_section_by_heading(location, sections, section_map)

            if section:
                chunks.append(
                    ChunkRecord(
                        doc_id=doc_record.doc_id,
                        section_id=section.section_id,
                        chunk_type="mitigation",
                        canonical_id=item_id or risk_data.get("title_verbatim"),
                        title=m.get("title") or section.heading_text or text_m[:80],
                        text=text_m,
                        source_uri=doc_record.source_uri,
                        publisher=doc_record.publisher,
                        edition=doc_record.edition,
                        version=doc_record.version,
                        section_path=section.section_path,
                        source_locator=section.source_locator,
                        content_hash_sha256=doc_record.content_hash_sha256,
                        llm_model_name=llm_client.model_name
                    )
                )

    # Attack Scenarios
    for a in response_json.get("attack", []) + response_json.get("attack_scenario", []):
        text_a = a.get("text") or a.get("attack_scenario_text_verbatim") or a.get("attack_scenario_text")

        if text_a and text_a != "Not found in document":
            location = a.get("location") or a.get("title")
            section = _find_section_by_heading(location, sections, section_map)

            if section:
                chunks.append(
                    ChunkRecord(
                        doc_id=doc_record.doc_id,
                        section_id=section.section_id,
                        chunk_type="attack_scenario",
                        canonical_id=item_id or risk_data.get("title_verbatim"),
                        title=a.get("title") or section.heading_text or text_a[:80],
                        text=text_a,
                        source_uri=doc_record.source_uri,
                        publisher=doc_record.publisher,
                        edition=doc_record.edition,
                        version=doc_record.version,
                        section_path=section.section_path,
                        source_locator=section.source_locator,
                        content_hash_sha256=doc_record.content_hash_sha256,
                        llm_model_name=llm_client.model_name
                    )
                )

    # Related frameworks
    for ref in response_json.get("related_framework", []) + response_json.get("related_frameworks_and_taxonomies", []):
        text_r = ref.get("text")

        if text_r and text_r != "Not found in document":
            location = ref.get("location")
            section = _find_section_by_heading(location, sections, section_map)

            if section:
                chunks.append(
                    ChunkRecord(
                        doc_id=doc_record.doc_id,
                        section_id=section.section_id,
                        chunk_type="related_framework",
                        canonical_id=item_id or risk_data.get("title_verbatim"),
                        title=text_r[:80],
                        text=text_r,
                        source_uri=doc_record.source_uri,
                        publisher=doc_record.publisher,
                        edition=doc_record.edition,
                        version=doc_record.version,
                        section_path=section.section_path,
                        source_locator=section.source_locator,
                        content_hash_sha256=doc_record.content_hash_sha256,
                        llm_model_name=llm_client.model_name
                    )
                )

    # Related links
    for ref in response_json.get("related_link", []) + response_json.get("related_links", []) + response_json.get("reference_links", []):
        text_r = ref.get("text")

        if text_r and text_r != "Not found in document":
            location = ref.get("location")
            section = _find_section_by_heading(location, sections, section_map)

            if section:
                chunks.append(
                    ChunkRecord(
                        doc_id=doc_record.doc_id,
                        section_id=section.section_id,
                        chunk_type="related_link",
                        canonical_id=item_id or ref.get("url"),
                        title=text_r[:80],
                        text=text_r,
                        link_uri=ref.get("url") or '',
                        source_uri=doc_record.source_uri,
                        publisher=doc_record.publisher,
                        edition=doc_record.edition,
                        version=doc_record.version,
                        section_path=section.section_path,
                        source_locator=section.source_locator,
                        content_hash_sha256=doc_record.content_hash_sha256,
                        llm_model_name=llm_client.model_name
                    )
                )

    return chunks

def _parse_llm_response_for_section(response_json: dict, doc_record, section, item_id: Optional[str], llm_client) -> List[ChunkRecord]:
    """
    Parse LLM response for a single section, creating ChunkRecords.
    Uses section provenance (section_path, source_locator) instead of generic markers.
    """
    chunks = []

    # Normalize response - some LLMs return {"response": "<json string>"}
    if isinstance(response_json, dict) and "response" in response_json and isinstance(response_json["response"], str):
        raw = response_json["response"]
        # Normalize common formatting wrappers/newline escapes
        raw = raw.replace("```json", "").replace("```", "").strip()
        raw = raw.replace("\\n", "\n")
        try:
            response_json = json.loads(raw)
        except Exception:
            # Try to extract the first JSON object in the string
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                response_json = json.loads(match.group(0))
            else:
                raise ValueError("LLM response did not contain valid JSON.")

    # Extract risk chunk
    risk_data = response_json.get("risk", {}) or {}
    if risk_data:
        # Handle both title_verbatim/title and description_verbatim_blocks/description_blocks
        risk_text_blocks = risk_data.get("description_verbatim_blocks") or risk_data.get("description_blocks") or []
        risk_text = " ".join([b.get("text_verbatim") or b.get("text") or "" for b in risk_text_blocks if b.get("text_verbatim") or b.get("text")])
        risk_title = risk_data.get("title_verbatim") or risk_data.get("title") or section.heading_text

        # Skip if LLM said "not found"
        if (risk_title and risk_text and
            risk_title != "Not found in document" and
            risk_text != "Not found in document"):
            chunks.append(
                ChunkRecord(
                    doc_id=doc_record.doc_id,
                    section_id=section.section_id,  # Direct link to source section
                    chunk_type="risk",
                    canonical_id=item_id or risk_title,
                    title=risk_title,
                    text=risk_text,
                    source_uri=doc_record.source_uri,
                    publisher=doc_record.publisher,
                    edition=doc_record.edition,
                    version=doc_record.version,
                    section_path=section.section_path,  # From section, not generic
                    source_locator=section.source_locator,  # From section
                    content_hash_sha256=doc_record.content_hash_sha256,
                    llm_model_name=llm_client.model_name
                )
            )

    # Weaknesses -> vulnerability chunks
    for w in response_json.get("weaknesses_verbatim", []) + response_json.get("weakness", []):
        text_w = w.get("text") or w.get("weakness_text_verbatim") or w.get("weakness_text")

        # Skip if LLM said "not found"
        if text_w and text_w != "Not found in document":
            chunks.append(
                ChunkRecord(
                    doc_id=doc_record.doc_id,
                    section_id=section.section_id,  # Direct link to source section
                    chunk_type="weakness",
                    canonical_id=item_id or risk_data.get("title_verbatim") or risk_data.get("title"),
                    title=w.get("title") or section.heading_text or text_w[:80],
                    text=text_w,
                    source_uri=doc_record.source_uri,
                    publisher=doc_record.publisher,
                    edition=doc_record.edition,
                    version=doc_record.version,
                    section_path=section.section_path,
                    source_locator=w.get("location") or section.source_locator,
                    content_hash_sha256=doc_record.content_hash_sha256,
                    llm_model_name=llm_client.model_name
                )
            )

    # Mitigations
    for m in response_json.get("mitigations_verbatim", []) + response_json.get("mitigation", []):
        text_m = m.get("text") or m.get("mitigation_text_verbatim") or m.get("mitigation_text")

        # Skip if LLM said "not found"
        if text_m and text_m != "Not found in document":
            chunks.append(
                ChunkRecord(
                    doc_id=doc_record.doc_id,
                    section_id=section.section_id,  # Direct link to source section
                    chunk_type="mitigation",
                    canonical_id=item_id or risk_data.get("title_verbatim"),
                    title=m.get("title") or section.heading_text or text_m[:80],  # Fixed: was w.get
                    text=text_m,
                    source_uri=doc_record.source_uri,
                    publisher=doc_record.publisher,
                    edition=doc_record.edition,
                    version=doc_record.version,
                    section_path=section.section_path,
                    source_locator=m.get("location") or section.source_locator,
                    content_hash_sha256=doc_record.content_hash_sha256,
                    llm_model_name=llm_client.model_name
                )
            )

    # Attack Scenarios -> attack_scenario chunks
    for a in response_json.get("attack", []) + response_json.get("attack_scenario", []):
        text_a = a.get("text") or a.get("attack_scenario_text_verbatim") or a.get("attack_scenario_text")

        # Skip if LLM said "not found"
        if text_a and text_a != "Not found in document":
            chunks.append(
                ChunkRecord(
                    doc_id=doc_record.doc_id,
                    section_id=section.section_id,  # Direct link to source section
                    chunk_type="attack_scenario",
                    canonical_id=item_id or risk_data.get("title_verbatim"),
                    title=a.get("title") or section.heading_text or text_a[:80],  # Fixed: was w.get
                    text=text_a,
                    source_uri=doc_record.source_uri,
                    publisher=doc_record.publisher,
                    edition=doc_record.edition,
                    version=doc_record.version,
                    section_path=section.section_path,
                    source_locator=a.get("location") or section.source_locator,
                    content_hash_sha256=doc_record.content_hash_sha256,
                    llm_model_name=llm_client.model_name
                )
            )

    # Related frameworks -> related_framework chunks
    for ref in response_json.get("related_framework", []) + response_json.get("related_frameworks_and_taxonomies", []):
        text_r = ref.get("text")

        # Skip if LLM said "not found"
        if text_r and text_r != "Not found in document":
            chunks.append(
                ChunkRecord(
                    doc_id=doc_record.doc_id,
                    section_id=section.section_id,  # Direct link to source section
                    chunk_type="related_framework",
                    canonical_id=item_id or risk_data.get("title_verbatim"),
                    title=text_r[:80],
                    text=text_r,
                    source_uri=doc_record.source_uri,
                    publisher=doc_record.publisher,
                    edition=doc_record.edition,
                    version=doc_record.version,
                    section_path=section.section_path,
                    source_locator=ref.get("location") or section.source_locator,
                    content_hash_sha256=doc_record.content_hash_sha256,
                    llm_model_name=llm_client.model_name
                )
            )

    # Related links -> related_links chunks
    for ref in response_json.get("related_link", []) + response_json.get("related_links", []) + response_json.get("reference_links", []):
        text_r = ref.get("text")

        # Skip if LLM said "not found"
        if text_r and text_r != "Not found in document":
            chunks.append(
                ChunkRecord(
                    doc_id=doc_record.doc_id,
                    section_id=section.section_id,  # Direct link to source section
                    chunk_type="related_link",
                    canonical_id=item_id or ref.get("url"),
                    title=text_r[:80],
                    text=text_r,
                    link_uri=ref.get("url") or '',
                    source_uri=doc_record.source_uri,
                    publisher=doc_record.publisher,
                    edition=doc_record.edition,
                    version=doc_record.version,
                    section_path=section.section_path,
                    source_locator=ref.get("location") or section.source_locator,
                    content_hash_sha256=doc_record.content_hash_sha256,
                    llm_model_name=llm_client.model_name
                )
            )

    return chunks

def ingest_document(
    source: str,
    config: dict,
    publisher: Optional[str] = None,
    collection: Optional[str] = None,
    document_name: Optional[str] = None,
    item_id: Optional[str] = None,
    edition: Optional[str] = None,
    version: Optional[str] = None,
    llm_client: Optional[LLMClient] = None,
    enrich_tags: bool = True  # Phase 1: Enable tag enrichment by default
) -> Tuple[DocumentRecord, List[SectionNode], List[ChunkRecord]]:
    """
    Ingests a single document from a URI or local file, processes it,
    and returns DocumentRecord and a list of SectionNode objects.
    Optionally, uses an LLM to extract risk-focused chunks at ingest time.
    """
    is_uri = bool(urlparse(source).scheme)

    doc_id = uuid4()
    title: Optional[str] = None # Will try to extract later

    if is_uri:
        print(f"Fetching content from URI: {source}")
        content_bytes, content_type = fetch_uri(source)
    else:
        print(f"Reading content from local file: {source}")
        content_bytes, content_type = read_file_content(source)
        source = os.path.abspath(source) # Use absolute path for local files

    # 1. Calculate raw content hash
    raw_content_hash = hashlib.sha256(content_bytes).hexdigest()

    is_markdown = ('markdown' in content_type) or source.lower().endswith('.md')

    # Assuming HTML for now for parsing
    llm_chunks: List[ChunkRecord] = []

    if 'html' in content_type:
        raw_text_content = content_bytes.decode('utf-8', errors='ignore') # Decode for HTML parsing
        
        # 2. Normalize and clean text
        normalized_text = normalize_text(raw_text_content)
        
        # 3. Calculate normalized text hash
        normalized_hash = hashlib.sha256(normalized_text.encode('utf-8')).hexdigest()

        # 4. Parse sections
        sections = html_to_sections(raw_text_content, doc_id, source)

        # 5. Basic dedupe and length filtering
        seen_hashes = set()
        filtered_sections = []
        for s in sections:
            clean = s.clean_text or ""
            # Keep top-level headings even if short; otherwise enforce a minimum length
            if (not is_markdown) and len(clean) < MIN_SECTION_CHARS and s.heading_level > 1:
                continue
            section_hash = hashlib.sha256(clean.encode("utf-8")).hexdigest()
            if section_hash in seen_hashes:
                continue
            seen_hashes.add(section_hash)
            filtered_sections.append(s)
        sections = filtered_sections
        
        # Attempt to get title from first H1 or document title
        if sections and sections[0].heading_level == 1 and sections[0].heading_text:
            title = normalize_text(sections[0].heading_text)
        elif '<title>' in raw_text_content:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(raw_text_content, 'html.parser')
            title_tag = soup.find('title')
            if title_tag:
                title = normalize_text(html.unescape(title_tag.get_text(strip=True)))

    elif is_markdown:
        raw_text_content = content_bytes.decode('utf-8', errors='ignore')
        normalized_text = normalize_text(raw_text_content)
        normalized_hash = hashlib.sha256(normalized_text.encode('utf-8')).hexdigest()
        sections = md_to_sections(normalized_text, doc_id, source)
        title = os.path.basename(source)
    else:
        # Placeholder for other content types
        print(f"Warning: Only HTML/Markdown parsing is implemented. Skipping section parsing for {content_type}.")
        normalized_text = normalize_text(content_bytes.decode('utf-8', errors='ignore'))
        normalized_hash = hashlib.sha256(normalized_text.encode('utf-8')).hexdigest()
        sections = [
            SectionNode(
                doc_id=doc_id,
                heading_text="Full Document",
                heading_level=1,
                section_path=["Full Document"],
                source_locator="document_start",
                raw_text=content_bytes.decode('utf-8', errors='ignore'),
                clean_text=normalized_text
            )
        ]
        title = os.path.basename(source) # Use filename as title for non-HTML/MD

    # If only edition is provided and version is not, use edition as version too
    effective_version = version or edition

    # Create DocumentRecord
    document_record = DocumentRecord(
        doc_id=doc_id,
        source_uri=source,
        retrieved_at=datetime.utcnow(),
        content_type=content_type,
        content_hash_sha256=raw_content_hash,
        normalized_hash_sha256=normalized_hash,
        title=title,
        publisher=publisher,
        collection=collection,
        document_name=document_name,
        item_id=item_id,
        edition=edition,
        version=effective_version,
        # extractor_id can be set via config later
    )

    print(f"\n--- Ingestion Complete for Doc ID: {document_record.doc_id} ---")
    print(f"Title: {document_record.title}")
    print(f"Source URI: {document_record.source_uri}")
    print(f"Content Type: {document_record.content_type}")
    print(f"Raw Hash: {document_record.content_hash_sha256}")
    print(f"Normalized Hash: {document_record.normalized_hash_sha256}")
    print(f"Sections Found: {len(sections)}")

    llm_raw_response = None

    # HYBRID: Send whole document with section markers for better classification + accurate titles
    if llm_client:
        print(f"\n--- Starting whole-document LLM extraction with section markers ---")

        # Build structured document with clear section boundaries
        structured_sections = []
        section_map = {}  # Map heading text to section for later lookup

        for section in sections:
            if len(section.clean_text.strip()) < MIN_SECTION_CHARS:
                continue

            # Create section marker with metadata
            section_marker = f"""
=== SECTION START ===
Section Path: {' > '.join(section.section_path)}
Heading: {section.heading_text}
Level: {section.heading_level}

{section.clean_text}
=== SECTION END ===
"""
            structured_sections.append(section_marker)
            section_map[section.heading_text] = section

        if not structured_sections:
            print("No sections to process")
        else:
            try:
                # Combine all sections into one structured document
                full_document = "\n\n".join(structured_sections)

                print(f"Sending {len(structured_sections)} sections as structured document ({len(full_document)} chars)")

                # Use existing prompt template
                prompt_template = load_prompt_template("ingest-document-and-extract-chunks.txt")
                placeholder = "<<<DOCUMENT\nPASTE THE OWASP DOCUMENT TEXT HERE\nDOCUMENT>>>"
                injection = f"<<<DOCUMENT\n{full_document}\nDOCUMENT>>>"

                if placeholder in prompt_template:
                    prompt = prompt_template.replace(placeholder, injection)
                else:
                    prompt = prompt_template
                    prompt = prompt.replace("<<<DOCUMENT", f"<<<DOCUMENT\n{full_document}\n")
                    if "DOCUMENT>>>" not in prompt:
                        prompt = prompt + "\nDOCUMENT>>>"

                # Single LLM call for entire document
                response_json = llm_client.generate_json(prompt, {})

                # Store response for debugging
                llm_raw_response = {
                    "prompt": prompt,
                    "model": llm_client.model_name,
                    "params": {
                        "temperature": getattr(llm_client, "_temperature", None),
                        "max_tokens": getattr(llm_client, "_max_tokens", None),
                    },
                    "response": response_json,
                }

                # Parse response and map chunks back to sections
                llm_chunks = _parse_llm_response_whole_document(
                    response_json,
                    document_record,
                    sections,
                    section_map,
                    item_id,
                    llm_client
                )

                print(f"LLM extraction complete: {len(llm_chunks)} total chunks\n")

            except Exception as e:
                print(f"Warning: LLM extraction failed: {e}")
                import traceback
                traceback.print_exc()

    # Phase 1: Enrich chunks with tags & STRIDE (if enabled)
    if enrich_tags and llm_client and llm_chunks:
        llm_chunks = enrich_chunks_with_tags(llm_chunks, llm_client)

    return document_record, sections, llm_chunks, llm_raw_response

if __name__ == '__main__':
    # Simple test run
    class MockConfig:
        pass
    mock_config = MockConfig()

    print("Testing URI ingestion...")
    doc, sects = ingest_document("https://www.owasp.org/www-project-top-ten/", mock_config)
    # print(doc.model_dump_json(indent=2))
    # for i, s in enumerate(sects[:3]): # Print first 3 sections
    #     print(f"Section {i+1}:\n{s.model_dump_json(indent=2)}\n")

    print("\nTesting Local File ingestion (creating dummy file)...")
    dummy_html_content = b"""
    <html><body>
        <h1>Local Test Document</h1>
        <p>This is a paragraph in a local HTML file.</p>
        <h2>Sub-section</h2>
        <p>More content here.</p>
    </body></html>
    """
    with open("local_test_doc.html", "wb") as f:
        f.write(dummy_html_content)

    doc_local, sects_local = ingest_document("local_test_doc.html", mock_config)
    # print(doc_local.model_dump_json(indent=2))
    # for i, s in enumerate(sects_local[:3]):
    #     print(f"Section {i+1}:\n{s.model_dump_json(indent=2)}\n")

    os.remove("local_test_doc.html")
