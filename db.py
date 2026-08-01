"""Mocked persistence layer backed by SQLite.

Every "side-effect" write in this project flows through this module, so nothing
ever touches a real external service. The DDL lives in ``schema.sql``; the mock
seeders (vendor DB + watchlist) land in ``seeders.py`` alongside the other
Step-1 scaffolding.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

DB_PATH = Path(
    os.environ.get("VENDOR_DB_PATH", Path(__file__).resolve().parent / "data" / "vendor_onboarding.db")
)
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def get_connection() -> sqlite3.Connection:
    """Return a connection with rows accessible by column name.

    The database file (and its parent directory) is created lazily on first
    use, so an empty checkout works out of the box. Set ``VENDOR_DB_PATH`` in
    tests to point at a throwaway temp file.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection | None = None) -> None:
    """Create all tables from ``schema.sql`` if they don't already exist."""
    conn = conn or get_connection()
    conn.executescript(SCHEMA_PATH.read_text())
    conn.commit()
