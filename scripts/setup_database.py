"""
Database Setup Script

Creates PostgreSQL database and schema for CyberChunk.
Handles Docker or local PostgreSQL installation.
"""
import os
import sys
import subprocess
from pathlib import Path


def check_postgres_running():
    """Check if PostgreSQL is accessible"""
    import psycopg2
    try:
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", "postgres"),
            database="postgres"
        )
        conn.close()
        return True
    except Exception as e:
        print(f"PostgreSQL not accessible: {e}")
        return False


def start_postgres_docker():
    """Start PostgreSQL using Docker"""
    print("Starting PostgreSQL with Docker...")

    # Check if container already exists
    result = subprocess.run(
        ["docker", "ps", "-a", "--filter", "name=cyberchunk-postgres", "--format", "{{.Names}}"],
        capture_output=True,
        text=True
    )

    if "cyberchunk-postgres" in result.stdout:
        print("Container 'cyberchunk-postgres' already exists. Starting...")
        subprocess.run(["docker", "start", "cyberchunk-postgres"])
    else:
        print("Creating new PostgreSQL container...")
        subprocess.run([
            "docker", "run", "-d",
            "--name", "cyberchunk-postgres",
            "-e", "POSTGRES_PASSWORD=postgres",
            "-e", "POSTGRES_DB=cyberchunk",
            "-p", "5432:5432",
            "-v", "cyberchunk-pgdata:/var/lib/postgresql/data",
            "pgvector/pgvector:pg16"  # PostgreSQL 16 with pgvector pre-installed
        ])

    print("Waiting for PostgreSQL to be ready...")
    import time
    for i in range(30):
        if check_postgres_running():
            print("✓ PostgreSQL is ready!")
            return True
        time.sleep(1)
        print(f"  Waiting... ({i+1}/30)")

    print("✗ PostgreSQL failed to start")
    return False


def create_database():
    """Create cyberchunk database if it doesn't exist"""
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

    print("\nCreating database 'cyberchunk'...")

    try:
        # Connect to default postgres database
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", "postgres"),
            database="postgres"
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        # Check if database exists
        cursor.execute("SELECT 1 FROM pg_database WHERE datname='cyberchunk'")
        exists = cursor.fetchone()

        if exists:
            print("  Database 'cyberchunk' already exists")
        else:
            cursor.execute("CREATE DATABASE cyberchunk")
            print("  ✓ Created database 'cyberchunk'")

        cursor.close()
        conn.close()
        return True

    except Exception as e:
        print(f"  ✗ Failed to create database: {e}")
        return False


def run_schema():
    """Execute schema.sql to create tables"""
    import psycopg2

    print("\nCreating schema...")

    try:
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", "postgres"),
            database="cyberchunk"
        )

        cursor = conn.cursor()

        # Read schema.sql
        schema_path = Path(__file__).parent.parent / "database" / "schema.sql"
        schema_sql = schema_path.read_text()

        # Execute schema
        cursor.execute(schema_sql)
        conn.commit()

        print("  ✓ Schema created successfully")

        # Verify tables were created
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        tables = cursor.fetchall()

        print(f"\n  Created {len(tables)} tables:")
        for table in tables:
            print(f"    - {table[0]}")

        cursor.close()
        conn.close()
        return True

    except Exception as e:
        print(f"  ✗ Failed to create schema: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_pgvector():
    """Verify pgvector extension is installed"""
    import psycopg2

    print("\nVerifying pgvector extension...")

    try:
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", "postgres"),
            database="cyberchunk"
        )

        cursor = conn.cursor()
        cursor.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        version = cursor.fetchone()

        if version:
            print(f"  ✓ pgvector version {version[0]} is installed")
        else:
            print("  ✗ pgvector extension not found")
            return False

        cursor.close()
        conn.close()
        return True

    except Exception as e:
        print(f"  ✗ Failed to verify pgvector: {e}")
        return False


def print_connection_info():
    """Print database connection information"""
    print("\n" + "=" * 60)
    print("DATABASE CONNECTION INFO")
    print("=" * 60)
    print(f"Host:     {os.getenv('POSTGRES_HOST', 'localhost')}")
    print(f"Port:     {os.getenv('POSTGRES_PORT', '5432')}")
    print(f"Database: cyberchunk")
    print(f"User:     {os.getenv('POSTGRES_USER', 'postgres')}")
    print(f"Password: {os.getenv('POSTGRES_PASSWORD', 'postgres')}")
    print("\nConnection string:")
    print(f"  postgresql://postgres:postgres@localhost:5432/cyberchunk")
    print("\npsql command:")
    print(f"  psql -h localhost -U postgres -d cyberchunk")
    print("=" * 60)


def main():
    """Main setup flow"""
    print("=" * 60)
    print("CyberChunk Database Setup")
    print("=" * 60)

    # Check if psycopg2 is installed
    try:
        import psycopg2
    except ImportError:
        print("\n✗ psycopg2 not installed")
        print("  Install with: pip install psycopg2-binary")
        sys.exit(1)

    # Step 1: Check if PostgreSQL is running
    print("\n1. Checking PostgreSQL...")
    if not check_postgres_running():
        print("\n  PostgreSQL is not running.")
        response = input("\n  Start PostgreSQL with Docker? (y/n): ")

        if response.lower() == 'y':
            if not start_postgres_docker():
                print("\n✗ Failed to start PostgreSQL")
                sys.exit(1)
        else:
            print("\n  Please start PostgreSQL manually and re-run this script")
            print("  Or set connection via environment variables:")
            print("    export POSTGRES_HOST=localhost")
            print("    export POSTGRES_PORT=5432")
            print("    export POSTGRES_USER=postgres")
            print("    export POSTGRES_PASSWORD=yourpassword")
            sys.exit(1)

    # Step 2: Create database
    print("\n2. Creating database...")
    if not create_database():
        sys.exit(1)

    # Step 3: Run schema
    print("\n3. Creating schema...")
    if not run_schema():
        sys.exit(1)

    # Step 4: Verify pgvector
    print("\n4. Verifying pgvector...")
    if not verify_pgvector():
        print("\n  ⚠ Warning: pgvector not installed")
        print("  Install instructions: https://github.com/pgvector/pgvector")
        print("  Or use Docker image: pgvector/pgvector:pg16")

    # Done
    print("\n" + "=" * 60)
    print("✓ Database setup complete!")
    print("=" * 60)

    print_connection_info()

    print("\nNext steps:")
    print("  1. Generate embeddings: python -m rag_builder.cli embed")
    print("  2. Query database: psql -h localhost -U postgres -d cyberchunk")


if __name__ == "__main__":
    main()
