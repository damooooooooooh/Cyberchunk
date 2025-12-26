"""
Fetch CWE Top 25 Most Dangerous Software Weaknesses for testing.

Downloads HTML pages for each CWE in the Top 25 list.
"""
import requests
from pathlib import Path
from time import sleep

# CWE Top 25 for 2024
# Source: https://cwe.mitre.org/top25/archive/2024/2024_top25_list.html
CWE_TOP_25_2024 = [
    "CWE-79",   # Cross-site Scripting
    "CWE-787",  # Out-of-bounds Write
    "CWE-89",   # SQL Injection
    "CWE-22",   # Path Traversal
    "CWE-352",  # Cross-Site Request Forgery (CSRF)
    "CWE-434",  # Unrestricted Upload of File with Dangerous Type
    "CWE-862",  # Missing Authorization
    "CWE-78",   # OS Command Injection
    "CWE-798",  # Use of Hard-coded Credentials
    "CWE-918",  # Server-Side Request Forgery (SSRF)
    "CWE-77",   # Command Injection
    "CWE-306",  # Missing Authentication for Critical Function
    "CWE-502",  # Deserialization of Untrusted Data
    "CWE-287",  # Improper Authentication
    "CWE-476",  # NULL Pointer Dereference
    "CWE-125",  # Out-of-bounds Read
    "CWE-20",   # Improper Input Validation
    "CWE-732",  # Incorrect Permission Assignment
    "CWE-94",   # Code Injection
    "CWE-269",  # Improper Privilege Management
    "CWE-611",  # XML External Entity (XXE)
    "CWE-639",  # Insecure Direct Object Reference
    "CWE-416",  # Use After Free
    "CWE-863",  # Incorrect Authorization
    "CWE-426",  # Untrusted Search Path
]

def fetch_cwe(cwe_id: str, output_dir: Path) -> bool:
    """
    Fetch a single CWE page and save as HTML.

    Args:
        cwe_id: CWE identifier (e.g., "CWE-79")
        output_dir: Directory to save HTML files

    Returns:
        True if successful, False otherwise
    """
    # Extract number from CWE-XXX
    cwe_number = cwe_id.split('-')[1]

    # CWE URL format
    url = f"https://cwe.mitre.org/data/definitions/{cwe_number}.html"

    try:
        print(f"Fetching {cwe_id}...", end=" ")
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        # Save HTML
        filename = f"{cwe_id}.html"
        filepath = output_dir / filename
        filepath.write_text(response.text, encoding='utf-8')

        print(f"✓ Saved to {filename}")
        return True

    except Exception as e:
        print(f"✗ Failed: {e}")
        return False


def main():
    """Fetch all CWE Top 25 pages"""

    # Create output directory
    output_dir = Path("data/cwe_top25")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Fetching CWE Top 25 (2024) - {len(CWE_TOP_25_2024)} weaknesses")
    print(f"Output directory: {output_dir}\n")

    success_count = 0

    for i, cwe_id in enumerate(CWE_TOP_25_2024, 1):
        print(f"[{i}/{len(CWE_TOP_25_2024)}] ", end="")

        if fetch_cwe(cwe_id, output_dir):
            success_count += 1

        # Rate limit: be nice to CWE server
        if i < len(CWE_TOP_25_2024):
            sleep(0.5)

    print(f"\n✓ Successfully fetched {success_count}/{len(CWE_TOP_25_2024)} CWEs")
    print(f"\nNext steps:")
    print(f"  1. Review files in {output_dir}/")
    print(f"  2. Run ingestion:")
    print(f"     python -m rag_builder.cli ingest data/cwe_top25/CWE-*.html --use-llm --enrich-tags")


if __name__ == "__main__":
    main()
