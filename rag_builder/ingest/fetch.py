import requests
import hashlib
from typing import Tuple

def fetch_uri(uri: str) -> Tuple[bytes, str]:
    """Fetches content from a URI and returns raw bytes and content type."""
    response = requests.get(uri)
    response.raise_for_status() # Raise an exception for HTTP errors
    content_type = response.headers.get('Content-Type', 'application/octet-stream').split(';')[0]
    return response.content, content_type

def calculate_hash(content_bytes: bytes) -> str:
    """Calculates SHA256 hash of content bytes."""
    return hashlib.sha256(content_bytes).hexdigest()

if __name__ == '__main__':
    # Example usage
    test_uri = "https://www.google.com"
    try:
        content, ctype = fetch_uri(test_uri)
        print(f"Fetched {len(content)} bytes of type {ctype}")
        print(f"SHA256: {calculate_hash(content)}")
    except Exception as e:
        print(f"Error fetching {test_uri}: {e}")
