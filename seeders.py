"""Mock data seeders for the vendors master table and the sanctions watchlist.

Idempotent: seeding twice does not create duplicates. Run via ``cli``:

    python seeders.py            # seed the default DB
"""

from __future__ import annotations

import sqlite3

import db

#: (name, category, country, prior_relationship, certifications)
MOCK_VENDORS: list[tuple[str, str, str, bool, str | None]] = [
    # Happy path: existing US office supplies vendor.
    ("Staple Supply Co.", "Office Supplies", "US", True, None),
    # Branching path: new IT/Software vendor with a certification on file.
    ("Acme Cloud Services", "IT/Software", "US", False, "SOC 2"),
    # Revision path: existing foreign (German) facilities vendor.
    ("Firstline Facilities GmbH", "Facilities", "Germany", True, None),
    # Escalation path: new foreign data-sensitive IT vendor.
    ("Helios Data Partners", "IT/Software", "Germany", False, None),
    # Extra: plain logistics vendor for ad-hoc demos.
    ("Contoso Logistics", "Logistics", "US", False, None),
]

#: (name, reason)
MOCK_WATCHLIST: list[tuple[str, str]] = [
    ("Blackrock Shipping LLC", "Sanctioned entity (OFAC)"),
    ("Northwind Traders", "Regulatory action — export controls"),
]


def seed_vendors(conn: sqlite3.Connection | None = None, force: bool = False) -> int:
    """Insert the mock vendor master rows; returns the number inserted."""
    conn = conn or db.get_connection()
    existing = conn.execute("SELECT COUNT(*) FROM vendors").fetchone()[0]
    if existing and not force:
        return 0
    if force:
        conn.execute("DELETE FROM vendors")
    conn.executemany(
        "INSERT INTO vendors (name, category, country, prior_relationship, certifications)"
        " VALUES (?, ?, ?, ?, ?)",
        MOCK_VENDORS,
    )
    conn.commit()
    return len(MOCK_VENDORS)


def seed_watchlist(conn: sqlite3.Connection | None = None, force: bool = False) -> int:
    """Insert the mock watchlist rows; returns the number inserted."""
    conn = conn or db.get_connection()
    existing = conn.execute("SELECT COUNT(*) FROM watchlist").fetchone()[0]
    if existing and not force:
        return 0
    if force:
        conn.execute("DELETE FROM watchlist")
    conn.executemany("INSERT INTO watchlist (name, reason) VALUES (?, ?)", MOCK_WATCHLIST)
    conn.commit()
    return len(MOCK_WATCHLIST)


def seed_all(conn: sqlite3.Connection | None = None, force: bool = False) -> None:
    """Seed both mock tables (plus schema) for the default DB."""
    conn = conn or db.get_connection()
    db.init_db(conn)
    seed_vendors(conn, force=force)
    seed_watchlist(conn, force=force)


if __name__ == "__main__":
    seed_all()
    print(f"Seeded {len(MOCK_VENDORS)} vendors and {len(MOCK_WATCHLIST)} watchlist entries.")
