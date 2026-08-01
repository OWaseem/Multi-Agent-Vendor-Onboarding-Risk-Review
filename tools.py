"""Tools for the three agents.

Read-only tools query the mock vendor DB, the watchlist table, the RAG vector
store, and the risk rubric. The two "side-effect" tools only ever write to the
local SQLite database — nothing touches a real external service.
"""

from __future__ import annotations

import sqlite3
from typing import Any

import db
import ingestion
import models
from models import (
    DocumentType,
    PolicyChunk,
    RiskFlag,
    VendorCategory,
    risk_score_for,
)


# ---------------------------------------------------------------------------
# Read-only tools
# ---------------------------------------------------------------------------


def vendor_lookup(vendor_name: str) -> dict[str, Any] | None:
    """Look up a vendor in the mock vendor master DB (case-insensitive)."""
    conn = db.get_connection()
    row = conn.execute(
        "SELECT * FROM vendors WHERE lower(name) = lower(?)", (vendor_name,)
    ).fetchone()
    if row is None:
        return None
    return {
        "name": row["name"],
        "category": row["category"],
        "country": row["country"],
        "prior_relationship": bool(row["prior_relationship"]),
        "certifications": row["certifications"],
    }


def watchlist_check(vendor_name: str) -> list[dict[str, Any]]:
    """Check the mock sanctions/watchlist table (case-insensitive partial match)."""
    conn = db.get_connection()
    rows = conn.execute(
        "SELECT name, reason, added_at FROM watchlist WHERE lower(name) LIKE lower(?)",
        (f"%{vendor_name}%",),
    ).fetchall()
    return [dict(r) for r in rows]


def policy_retriever(
    query: str,
    category: VendorCategory,
    data_sensitive: bool,
    k: int = 5,
) -> list[PolicyChunk]:
    """RAG search over the policy vector store, category/metadata-filtered."""
    return ingestion.retrieve(query, category=category, data_sensitive=data_sensitive, k=k)


def risk_score_calculator(
    risk_flags: list[RiskFlag] | set[RiskFlag],
    vendor_category: VendorCategory,
    data_sensitive: bool,
) -> float:
    """Weighted risk score from flags plus inherent category/sensitivity risk."""
    return risk_score_for(risk_flags, vendor_category, data_sensitive)


# ---------------------------------------------------------------------------
# Side-effect tools (mocked — local SQLite only)
# ---------------------------------------------------------------------------


def create_approval_request(
    request_id: str, vendor_name: str, decision_notes: str | None = None
) -> int:
    """Log a pending approval record; returns the new row id."""
    conn = db.get_connection()
    cur = conn.execute(
        "INSERT INTO approval_requests (request_id, vendor_name, status, decision_notes)"
        " VALUES (?, ?, 'pending', ?)",
        (request_id, vendor_name, decision_notes),
    )
    conn.commit()
    return cur.lastrowid


def update_vendor_status(
    request_id: str,
    vendor_name: str,
    final_status: models.OnboardingStatus,
    notes: str | None = None,
) -> int:
    """Write the final onboarding status to the log; returns the new row id."""
    conn = db.get_connection()
    cur = conn.execute(
        "INSERT INTO vendor_status_log (request_id, vendor_name, final_status, notes)"
        " VALUES (?, ?, ?, ?)",
        (request_id, vendor_name, final_status.value, notes),
    )
    conn.commit()
    return cur.lastrowid


def resolve_approval(
    approval_id: int,
    status: str,
    decided_by: str,
    notes: str | None = None,
) -> None:
    """Update an approval request row (e.g. pending -> approved/rejected)."""
    conn = db.get_connection()
    conn.execute(
        "UPDATE approval_requests SET status = ?, decided_by = ?, decision_notes = ?"
        " WHERE id = ?",
        (status, decided_by, notes, approval_id),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Agent-level helpers built on the tools
# ---------------------------------------------------------------------------


def evaluate_risk_flags(
    *,
    vendor_name: str,
    country: str,
    submitted_documents: list[DocumentType],
    vendor_category: VendorCategory,
    data_sensitive: bool,
    relationship_status: models.RelationshipStatus,
) -> list[RiskFlag]:
    """Compute the RiskFlags from a request per the high-risk criteria.

    Used by the planner (sans watchlist, which is the reviewer's check) and
    by the reviewer (with the watchlist).
    """
    flags: list[RiskFlag] = []
    if country.upper() != "US":
        flags.append(RiskFlag.FOREIGN_ENTITY)
    if DocumentType.CERTIFICATE_OF_INSURANCE not in submitted_documents:
        flags.append(RiskFlag.NO_COI)
    if (
        vendor_category.is_high_risk_category or data_sensitive
    ) and DocumentType.SECURITY_QUESTIONNAIRE not in submitted_documents:
        flags.append(RiskFlag.MISSING_SECURITY_QUESTIONNAIRE)
    if (
        relationship_status == models.RelationshipStatus.NEW and data_sensitive
    ):
        flags.append(RiskFlag.NEW_VENDOR_DATA_SENSITIVE)
    return flags
