"""Verify Alembic uses the backend's current database configuration."""

import os
import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def test_alembic_loads_migrations_with_the_shared_database_configuration():
    """Load the migration environment offline without opening a database connection."""
    environment = os.environ.copy()
    environment["DATABASE_URL"] = "postgresql+psycopg:///migration_test"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            "alembic.ini",
            "upgrade",
            "head",
            "--sql",
        ],
        cwd=BACKEND_ROOT,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "CREATE TABLE events" in result.stdout
    assert "CREATE TABLE alembic_version" in result.stdout
