import hashlib
import os
from typing import Tuple

def read_file_content(file_path: str) -> Tuple[bytes, str]:
    """Reads content from a local file and returns raw bytes and inferred content type."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found at {file_path}")

    with open(file_path, 'rb') as f:
        content_bytes = f.read()

    # Simple content type inference based on extension
    _, ext = os.path.splitext(file_path)
    if ext == '.html':
        content_type = 'text/html'
    elif ext == '.pdf':
        content_type = 'application/pdf'
    elif ext == '.md':
        content_type = 'text/markdown'
    elif ext == '.txt':
        content_type = 'text/plain'
    elif ext == '.docx':
        content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    else:
        content_type = 'application/octet-stream' # Default for unknown types

    return content_bytes, content_type

def calculate_hash(content_bytes: bytes) -> str:
    """Calculates SHA256 hash of content bytes."""
    return hashlib.sha256(content_bytes).hexdigest()

if __name__ == '__main__':
    # Example usage: create a dummy file and read it
    dummy_file_path = "test_document.html"
    dummy_content = b"<html><body><h1>Test</h1><p>This is a test.</p></body></html>"
    with open(dummy_file_path, 'wb') as f:
        f.write(dummy_content)

    try:
        content, ctype = read_file_content(dummy_file_path)
        print(f"Read {len(content)} bytes of type {ctype}")
        print(f"SHA256: {calculate_hash(content)}")
    except Exception as e:
        print(f"Error reading {dummy_file_path}: {e}")
    finally:
        if os.path.exists(dummy_file_path):
            os.remove(dummy_file_path)
