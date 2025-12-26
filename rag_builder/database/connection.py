"""
Database Connection Management
"""
import os
import re
import psycopg2
from typing import Optional, Dict, Any


def _resolve_env_var(value: str) -> str:
    """
    Resolve environment variable placeholders like ${POSTGRES_PASSWORD}.

    Args:
        value: String that may contain ${VAR_NAME} placeholders

    Returns:
        String with placeholders replaced by environment variable values
    """
    if isinstance(value, str):
        # Find all ${VAR_NAME} patterns
        pattern = r'\$\{([^}]+)\}'
        matches = re.findall(pattern, value)

        for var_name in matches:
            env_value = os.getenv(var_name, "")
            value = value.replace(f"${{{var_name}}}", env_value)

    return value


def get_db_connection(
    config: Dict[str, Any] = None,
    host: str = None,
    port: str = None,
    user: str = None,
    password: str = None,
    database: str = None
):
    """
    Get PostgreSQL connection.

    Priority order:
    1. Explicit parameters
    2. Config file (if provided)
    3. Environment variables
    4. Defaults

    Args:
        config: Configuration dictionary (from main_config.yml)
        host: Database host
        port: Database port
        user: Database user
        password: Database password
        database: Database name

    Returns:
        psycopg2 connection object
    """
    # Extract database config if provided
    db_config = config.get("database", {}) if config else {}

    # Resolve values in priority order
    final_host = host or db_config.get("host") or os.getenv("POSTGRES_HOST", "localhost")
    final_port = port or db_config.get("port") or os.getenv("POSTGRES_PORT", "5432")
    final_user = user or db_config.get("user") or os.getenv("POSTGRES_USER", "postgres")
    final_password = password or db_config.get("password") or os.getenv("POSTGRES_PASSWORD", "postgres")
    final_database = database or db_config.get("database") or os.getenv("POSTGRES_DB", "cyberchunk")

    # Resolve environment variable placeholders (e.g., ${POSTGRES_PASSWORD})
    final_password = _resolve_env_var(str(final_password))

    return psycopg2.connect(
        host=final_host,
        port=final_port,
        user=final_user,
        password=final_password,
        database=final_database
    )
