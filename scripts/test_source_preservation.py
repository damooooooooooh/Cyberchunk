"""
Test script for source preservation functionality.

Demonstrates how to preserve sources and verify integrity.
"""
from pathlib import Path
from rag_builder.sources import SourceManager


def test_preserve_url():
    """Test preserving a source from URL"""
    print("=" * 60)
    print("TEST 1: Preserve source from URL")
    print("=" * 60)

    manager = SourceManager()

    # Preserve OWASP A01
    print("\n1. Preserving OWASP Top 10 A01 from GitHub...")
    result = manager.preserve_source(
        source_path="https://raw.githubusercontent.com/OWASP/Top10/refs/heads/master/2025/docs/en/A01_2025-Broken_Access_Control.md",
        dataset_id="owasp_top10",
        version="2025",
        publisher="OWASP",
        is_url=True
    )

    print(f"✓ Preserved to: {result['preserved_path']}")
    print(f"  File hash: {result['file_hash'][:32]}...")
    print(f"  Manifest: {result['manifest_path']}")

    # Verify the file exists
    preserved_file = Path(result['preserved_path'])
    assert preserved_file.exists(), "Preserved file should exist"
    print(f"✓ File verified: {preserved_file.stat().st_size} bytes")

    return result


def test_preserve_local():
    """Test preserving a local file"""
    print("\n" + "=" * 60)
    print("TEST 2: Preserve local file")
    print("=" * 60)

    # First, check if we have a local CWE file
    local_file = Path("data/cwe_top25/CWE-79.html")

    if not local_file.exists():
        print(f"⚠ Skipping: {local_file} not found")
        print("  Run: python scripts/fetch_cwe_top25.py first")
        return None

    manager = SourceManager()

    print(f"\n1. Preserving local file: {local_file}")
    result = manager.preserve_source(
        source_path=str(local_file),
        dataset_id="cwe_top25",
        version="2024",
        publisher="MITRE",
        is_url=False
    )

    print(f"✓ Preserved to: {result['preserved_path']}")
    print(f"  File hash: {result['file_hash'][:32]}...")

    return result


def test_list_datasets():
    """Test listing all preserved datasets"""
    print("\n" + "=" * 60)
    print("TEST 3: List all preserved datasets")
    print("=" * 60)

    manager = SourceManager()
    datasets = manager.list_datasets()

    print(f"\nFound {len(datasets)} preserved dataset(s):\n")

    for i, ds in enumerate(datasets, 1):
        print(f"{i}. {ds['dataset_id']} v{ds['version']}")
        print(f"   Publisher: {ds['publisher']}")
        print(f"   Created: {ds['created_at']}")
        print(f"   Files: {ds['total_files']}")
        print(f"   Path: {ds['path']}")
        print()


def test_find_dataset():
    """Test finding a specific dataset"""
    print("=" * 60)
    print("TEST 4: Find specific dataset")
    print("=" * 60)

    manager = SourceManager()

    print("\n1. Looking for 'owasp_top10' version '2025'...")
    dataset_path = manager.get_dataset_path("owasp_top10", "2025")

    if dataset_path:
        print(f"✓ Found: {dataset_path}")

        # Read manifest
        manifest_path = dataset_path / "manifest.json"
        if manifest_path.exists():
            import json
            manifest = json.loads(manifest_path.read_text())
            print(f"  Dataset ID: {manifest['dataset_id']}")
            print(f"  Version: {manifest['version']}")
            print(f"  Files: {manifest['total_files']}")
            print(f"  Created: {manifest['created_at']}")
    else:
        print("✗ Not found")


def test_verify_integrity():
    """Test verifying file integrity"""
    print("\n" + "=" * 60)
    print("TEST 5: Verify source file integrity")
    print("=" * 60)

    manager = SourceManager()
    dataset_path = manager.get_dataset_path("owasp_top10", "2025")

    if not dataset_path:
        print("⚠ No dataset found to verify")
        return

    print(f"\n1. Verifying files in: {dataset_path}")

    import json
    import hashlib

    manifest_path = dataset_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text())

    print(f"   Checking {len(manifest['files'])} file(s)...\n")

    for file_entry in manifest['files']:
        file_path = dataset_path / file_entry['filename']
        expected_hash = file_entry['file_hash_sha256']

        if not file_path.exists():
            print(f"   ✗ {file_entry['filename']}: MISSING")
            continue

        actual_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()

        if actual_hash == expected_hash:
            print(f"   ✓ {file_entry['filename']}: VERIFIED")
        else:
            print(f"   ✗ {file_entry['filename']}: CORRUPTED!")
            print(f"     Expected: {expected_hash[:32]}...")
            print(f"     Actual:   {actual_hash[:32]}...")


if __name__ == "__main__":
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "Source Preservation Test Suite" + " " * 18 + "║")
    print("╚" + "=" * 58 + "╝")
    print()

    try:
        # Run tests
        test_preserve_url()
        test_preserve_local()
        test_list_datasets()
        test_find_dataset()
        test_verify_integrity()

        print("\n" + "=" * 60)
        print("✓ All tests completed successfully!")
        print("=" * 60)
        print("\nNext steps:")
        print("  1. Check data/sources/ directory for preserved files")
        print("  2. Review manifest.json files")
        print("  3. Integrate into ingestion pipeline (see docs/source_preservation_integration.md)")
        print()

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
