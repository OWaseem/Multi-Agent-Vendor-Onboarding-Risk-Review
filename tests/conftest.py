"""pytest fixtures: isolated temp DB + vector store, seeded mock data, app."""

from __future__ import annotations

import os
import tempfile

import pytest

# Point the mocked persistence + vector store at a throwaway location BEFORE
# any project module is imported (db.py / ingestion.py resolve paths at import).
_TMP_DIR = tempfile.mkdtemp(prefix="vendor_onboarding_test_")
os.environ["VENDOR_DB_PATH"] = os.path.join(_TMP_DIR, "test.db")
os.environ["VECTOR_STORE_PATH"] = os.path.join(_TMP_DIR, "chroma")

import db  # noqa: E402
import ingestion  # noqa: E402
import seeders  # noqa: E402
from graph.workflow import (  # noqa: E402
    config_for,
    create_app,
    current_interrupt,
    first_step,
    resume,
    workflow_complete,
)
from models import (  # noqa: E402
    DocumentType,
    RelationshipStatus,
    SubmittedDocument,
    VendorCategory,
    VendorRequest,
)


@pytest.fixture(scope="session", autouse=True)
def seeded_env():
    """Build schema, seed mock vendors/watchlist, index policy chunks once."""
    db.init_db()
    seeders.seed_all()
    ingestion.build_vector_store()
    return _TMP_DIR


@pytest.fixture(scope="session")
def app(seeded_env):
    return create_app()


def base_documents(extra: list[DocumentType] | None = None) -> list[SubmittedDocument]:
    """The four base-required documents, plus any extra types."""
    types = [
        DocumentType.W9_TAX_ID,
        DocumentType.CERTIFICATE_OF_INSURANCE,
        DocumentType.BUSINESS_LICENSE,
        DocumentType.CODE_OF_CONDUCT,
    ] + list(extra or [])
    return [SubmittedDocument(type=t, reference=f"{t.value}.pdf") for t in types]


@pytest.fixture
def make_request():
    def _make(**kwargs) -> VendorRequest:
        defaults = dict(
            vendor_name="Staple Supply Co.",
            vendor_category=VendorCategory.OFFICE_SUPPLIES,
            country="US",
            data_sensitive=False,
            relationship_status=RelationshipStatus.EXISTING,
            requester_name="Alice",
            requester_department="Operations",
            business_justification=None,
            submitted_documents=[],
        )
        defaults.update(kwargs)
        return VendorRequest(**defaults)

    return _make


def drive(app, request: VendorRequest, human: str = "approve", supply_missing: bool = True):
    """Run a workflow to completion, auto-handling interrupts.

    Missing documents are supplied automatically (unless ``supply_missing`` is
    False, to inspect the pause). The human gate resolves with ``human``.
    """
    thread_id = os.urandom(6).hex()
    cfg = config_for(thread_id)
    out, snap = first_step(app, cfg, request)

    while not workflow_complete(snap):
        intr = current_interrupt(snap)
        if intr is None:
            break
        if intr["type"] == "missing_documents":
            if not supply_missing:
                return out, snap
            missing = set(intr["missing_documents"])
            existing = snap.values.get("submitted_documents", []) or []
            existing_types = {d["type"] if isinstance(d, dict) else d.type.value for d in existing}
            docs = [SubmittedDocument.model_validate(d) if isinstance(d, dict) else d for d in existing]
            for m in missing:
                if m not in existing_types:
                    docs.append(SubmittedDocument(type=DocumentType(m), reference=f"{m}.pdf"))
            out, snap = resume(app, cfg, [d.model_dump() for d in docs])
        elif intr["type"] == "human_approval":
            out, snap = resume(app, cfg, human)
        else:  # pragma: no cover
            raise AssertionError(f"Unexpected interrupt: {intr['type']}")
    return out, snap
