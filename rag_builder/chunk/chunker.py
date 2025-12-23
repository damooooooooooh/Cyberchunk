import tiktoken # For token counting
from typing import List, Optional, Tuple
from uuid import UUID, uuid4
import re

from rag_builder.chunk.schema import DocumentRecord, SectionNode, ChunkRecord

def count_tokens(text: str, model_name: str = "cl100k_base") -> int:
    """Counts tokens in a string using tiktoken."""
    encoding = tiktoken.get_encoding(model_name)
    return len(encoding.encode(text))

def split_text_into_paragraphs_and_bullets(text: str) -> List[str]:
    """Splits text into paragraphs and bullet points."""
    # Split by double newline (paragraphs)
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    
    # Further split paragraphs that might contain bullet points
    final_splits = []
    for para in paragraphs:
        # Detect common bullet point patterns
        bullet_splits = re.split(r'(\s*[-*•]\s+.*(?:\n\s*[-*•]\s+.*)*)', para, flags=re.MULTILINE)
        for sub_split in bullet_splits:
            if sub_split.strip():
                final_splits.append(sub_split.strip())
    return final_splits or [text.strip()]


def chunk_text_by_tokens(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
    token_model_name: str = "cl100k_base"
) -> List[str]:
    """
    Splits text into smaller chunks based on token limits and overlap.
    Aims to split by natural breaks (paragraphs, sentences) first.
    """
    if not text:
        return []

    chunks = []
    current_chunk = []
    current_token_count = 0

    # Prioritize splitting by paragraphs/bullets
    segments = split_text_into_paragraphs_and_bullets(text)
    
    for segment in segments:
        segment_tokens = count_tokens(segment, token_model_name)

        if segment_tokens > chunk_size:
            # If a single segment is larger than chunk_size, split it further (e.g., by sentences)
            sentences = re.split(r'(?<=[.!?])\s+', segment)
            for sentence in sentences:
                sentence_tokens = count_tokens(sentence, token_model_name)
                if current_token_count + sentence_tokens <= chunk_size:
                    current_chunk.append(sentence)
                    current_token_count += sentence_tokens
                else:
                    if current_chunk:
                        chunks.append(" ".join(current_chunk))
                        # For overlap, take last part of current chunk
                        current_chunk = current_chunk[-max(1, int(len(current_chunk) * chunk_overlap / chunk_size)):] # Simplified overlap
                        current_token_count = count_tokens(" ".join(current_chunk), token_model_name)
                    current_chunk.append(sentence)
                    current_token_count += sentence_tokens
            if current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = []
                current_token_count = 0 # Reset for next large segment
        elif current_token_count + segment_tokens <= chunk_size:
            current_chunk.append(segment)
            current_token_count += segment_tokens
        else:
            # Current segment doesn't fit, finalize current_chunk and start new one
            if current_chunk:
                chunks.append(" ".join(current_chunk))
                # Apply overlap
                overlap_text = " ".join(current_chunk[-max(1, int(len(current_chunk) * chunk_overlap / chunk_size)):]) # Simplified overlap
                current_chunk = [overlap_text] if overlap_text else [] # Start new with overlap
                current_token_count = count_tokens(" ".join(current_chunk), token_model_name) # Count overlap tokens
            
            current_chunk.append(segment)
            current_token_count += segment_tokens
    
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    
    # Final pass to ensure no chunks exceed max_size due to simplified overlap logic
    final_chunks = []
    for chk in chunks:
        if count_tokens(chk, token_model_name) > chunk_size + (chunk_size * 0.1): # Allow a small buffer
            # Fallback to character split if token split is too large (should be rare)
            print(f"Warning: Large chunk found after token splitting ({count_tokens(chk, token_model_name)} tokens). Splitting by characters.")
            words = chk.split(" ")
            temp_char_chunk = []
            temp_char_count = 0
            for word in words:
                if temp_char_count + len(word) + 1 <= chunk_size * 4: # approx 4 chars per token
                    temp_char_chunk.append(word)
                    temp_char_count += len(word) + 1
                else:
                    final_chunks.append(" ".join(temp_char_chunk))
                    temp_char_chunk = [word]
                    temp_char_count = len(word) + 1
            if temp_char_chunk:
                final_chunks.append(" ".join(temp_char_chunk))
        else:
            final_chunks.append(chk)

    return final_chunks


def process_sections_into_chunks(
    doc_record: DocumentRecord,
    section_nodes: List[SectionNode],
    chunk_size: int = 512,
    chunk_overlap: int = 128,
    token_model_name: str = "cl100k_base"
) -> List[ChunkRecord]:
    """
    Processes SectionNode objects into more granular ChunkRecord objects based on token limits.
    Each ChunkRecord will retain its full provenance from the SectionNode and DocumentRecord.
    """
    generated_chunks: List[ChunkRecord] = []

    for section_node in section_nodes:
        # If the section has significant clean text, chunk it
        if section_node.clean_text and count_tokens(section_node.clean_text, token_model_name) > 0:
            
            sub_chunks_text = chunk_text_by_tokens(
                section_node.clean_text,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                token_model_name=token_model_name
            )

            for i, sub_chunk_text in enumerate(sub_chunks_text):
                # Inherit provenance from the parent SectionNode and DocumentRecord
                new_chunk = ChunkRecord(
                    chunk_id=uuid4(),
                    doc_id=doc_record.doc_id,
                    chunk_type="general", # Type will be refined by the extractor pipeline
                    title=f"{section_node.heading_text} Part {i+1}" if section_node.heading_text else f"Section Part {i+1}",
                    text=sub_chunk_text,
                    source_uri=doc_record.source_uri,
                    publisher=doc_record.publisher,
                    edition=doc_record.edition,
                    version=doc_record.version,
                    section_path=section_node.section_path,
                    source_locator=section_node.source_locator, # Locator might need refinement for sub-chunks
                    content_hash_sha256=doc_record.content_hash_sha256
                )
                generated_chunks.append(new_chunk)
        elif section_node.heading_text:
            # Create a chunk just for the heading if there's no body text but a heading exists
            generated_chunks.append(
                ChunkRecord(
                    chunk_id=uuid4(),
                    doc_id=doc_record.doc_id,
                    chunk_type="general",
                    title=section_node.heading_text,
                    text=section_node.heading_text, # Heading text as the chunk content
                    source_uri=doc_record.source_uri,
                    publisher=doc_record.publisher,
                    edition=doc_record.edition,
                    version=doc_record.version,
                    section_path=section_node.section_path,
                    source_locator=section_node.source_locator,
                    content_hash_sha256=doc_record.content_hash_sha256
                )
            )

    return generated_chunks


if __name__ == '__main__':
    # Test cases for chunk_text_by_tokens
    print("--- Testing chunk_text_by_tokens ---")
    long_text = "This is a very long sentence that needs to be split. " * 20 + \
                "\n\nThis is a new paragraph. It also has a bullet point:\n- Item one\n- Item two." + \
                " Another sentence here."
    
    # Assuming 4 chars per token roughly for rough testing
    # chunk_size = 30 tokens means ~120 chars
    # chunk_overlap = 10 tokens means ~40 chars
    
    test_chunks = chunk_text_by_tokens(long_text, chunk_size=30, chunk_overlap=10)
    for i, chk in enumerate(test_chunks):
        print(f"Chunk {i+1} ({count_tokens(chk)} tokens):\n{chk}\n---")

    # Test cases for process_sections_into_chunks
    print("\n--- Testing process_sections_into_chunks ---")
    dummy_doc_id = uuid4()
    mock_doc = DocumentRecord(
        doc_id=dummy_doc_id,
        source_uri="http://example.com/test_doc",
        content_type="text/html",
        content_hash_sha256="abc",
        normalized_hash_sha256="def",
        title="Test Document for Chunker"
    )
    mock_sections = [
        SectionNode(
            section_id=uuid4(), doc_id=dummy_doc_id, heading_text="Introduction", heading_level=1,
            section_path=["Introduction"], source_locator="#intro", raw_text="...",
            clean_text="This is an introductory paragraph. " * 15 # Make it longer than chunk_size
        ),
        SectionNode(
            section_id=uuid4(), doc_id=dummy_doc_id, heading_text="Details", heading_level=2,
            section_path=["Introduction", "Details"], source_locator="#details", raw_text="...",
            clean_text="Detail one.\n\nDetail two.\n- Point A\n- Point B. A very long sentence for point B that should definitely be split by the chunker. " * 5
        ),
        SectionNode(
            section_id=uuid4(), doc_id=dummy_doc_id, heading_text="Conclusion", heading_level=1,
            section_path=["Conclusion"], source_locator="#conclusion", raw_text="...",
            clean_text="Short conclusion."
        ),
        SectionNode( # Section with only heading
            section_id=uuid4(), doc_id=dummy_doc_id, heading_text="Empty Section", heading_level=2,
            section_path=["Conclusion", "Empty Section"], source_locator="#empty", raw_text="...",
            clean_text=""
        )
    ]

    processed_chunks = process_sections_into_chunks(mock_doc, mock_sections, chunk_size=50, chunk_overlap=10)
    print(f"\nGenerated {len(processed_chunks)} chunks from sections:")
    for i, chk in enumerate(processed_chunks):
        print(f"Chunk {i+1} (Type: {chk.chunk_type}, Tokens: {count_tokens(chk.text)}):\n{chk.text}\n---")
