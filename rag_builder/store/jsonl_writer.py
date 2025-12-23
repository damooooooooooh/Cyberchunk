import json
import os
from typing import List, Union
from pydantic import BaseModel

def write_records_to_jsonl(
    records: List[BaseModel],
    output_dir: str,
    file_name: str,
    mode: str = 'a' # 'a' for append, 'w' for write (overwrite)
):
    """
    Writes a list of Pydantic BaseModel instances to a JSONL file.
    Each record is written as a new line.

    Args:
        records: A list of Pydantic BaseModel instances.
        output_dir: The directory where the JSONL file will be saved.
        file_name: The name of the JSONL file (e.g., "documents.jsonl").
        mode: File open mode, 'a' (append) or 'w' (write, overwrite).
    """
    os.makedirs(output_dir, exist_ok=True)
    file_path = os.path.join(output_dir, file_name)

    with open(file_path, mode, encoding='utf-8') as f:
        for record in records:
            # Pydantic's model_dump_json handles serialization of UUID, datetime, etc.
            f.write(record.model_dump_json() + '\n')
    
    print(f"Wrote {len(records)} records to {file_path}")

def read_records_from_jsonl(
    file_path: str,
    model_type: BaseModel
) -> List[BaseModel]:
    """
    Reads Pydantic BaseModel instances from a JSONL file.

    Args:
        file_path: The path to the JSONL file.
        model_type: The Pydantic BaseModel class to deserialize into.

    Returns:
        A list of Pydantic BaseModel instances.
    """
    records: List[BaseModel] = []
    if not os.path.exists(file_path):
        return records

    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                try:
                    data = json.loads(line)
                    record = model_type.model_validate(data)
                    records.append(record)
                except json.JSONDecodeError as e:
                    print(f"Error decoding JSON from line: {line.strip()} - {e}")
                except Exception as e:
                    print(f"Error validating model from line: {line.strip()} - {e}")
    return records

if __name__ == '__main__':
    from rag_builder.chunk.schema import DocumentRecord, SectionNode
    from uuid import uuid4
    from datetime import datetime

    # Mock Pydantic models for testing
    mock_doc = DocumentRecord(
        doc_id=uuid4(),
        source_uri="http://example.com/doc1",
        content_type="text/html",
        content_hash_sha256="abc",
        normalized_hash_sha256="def",
        title="Test Document 1"
    )
    mock_section = SectionNode(
        doc_id=mock_doc.doc_id,
        heading_text="Section 1",
        heading_level=1,
        section_path=["Section 1"],
        source_locator="#s1",
        raw_text="<p>hello</p>",
        clean_text="hello"
    )
    mock_section_2 = SectionNode(
        doc_id=mock_doc.doc_id,
        heading_text="Section 2",
        heading_level=2,
        section_path=["Section 1", "Section 2"],
        source_locator="#s2",
        raw_text="<p>world</p>",
        clean_text="world"
    )

    test_output_dir = "test_output"
    os.makedirs(test_output_dir, exist_ok=True)

    # Test writing
    write_records_to_jsonl([mock_doc], test_output_dir, "documents.jsonl", mode='w')
    write_records_to_jsonl([mock_section, mock_section_2], test_output_dir, "sections.jsonl", mode='w')

    # Test reading
    read_docs = read_records_from_jsonl(os.path.join(test_output_dir, "documents.jsonl"), DocumentRecord)
    read_sections = read_records_from_jsonl(os.path.join(test_output_dir, "sections.jsonl"), SectionNode)

    print("\nRead documents:")
    for doc in read_docs:
        print(doc.model_dump_json(indent=2))

    print("\nRead sections:")
    for section in read_sections:
        print(section.model_dump_json(indent=2))
    
    # Clean up test files
    os.remove(os.path.join(test_output_dir, "documents.jsonl"))
    os.remove(os.path.join(test_output_dir, "sections.jsonl"))
    os.rmdir(test_output_dir)
