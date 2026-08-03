"""The 5 required test scenarios + routing extras.

1. Happy path — existing US office-supplies vendor, complete docs → standard.
2. Branching path — new IT/Software vendor, complete docs → reviewer routes
   through the human gate (mandatory IT review).
3. Missing-information path — missing COI → pause → resume → complete.
4. Failure/revision path — reviewer rejects the over-cautious draft → loops to
   planner → revised recommendation approved within the retry limit.
5. Escalation path — foreign, data-sensitive, no security questionnaire →
   escalated to human review.
"""

from __future__ import annotations

import models
from graph.workflow import current_interrupt, first_step, resume, workflow_complete
from models import (
    DocumentType,
    HumanDecision,
    OnboardingStatus,
    RelationshipStatus,
    ReviewerDecision,
    RiskFlag,
    VendorCategory,
)
from tools import watchlist_check

from conftest import base_documents, drive

ALL_DOCS = list(DocumentType)


def _config_for(thread_id: str):
    from graph.workflow import config_for

    return config_for(thread_id)


# ---------------------------------------------------------------------------
# 1. Happy path
# ---------------------------------------------------------------------------


def test_happy_path_standard_onboarding_auto_completes(app, make_request, seeded_env):
    req = make_request(
        vendor_name="Staple Supply Co.",
        vendor_category=VendorCategory.OFFICE_SUPPLIES,
        country="US",
        relationship_status=RelationshipStatus.EXISTING,
        submitted_documents=base_documents(),
    )
    out, snap = drive(app, req)

    assert workflow_complete(snap)
    assert out["reviewer_verdict"].decision == ReviewerDecision.APPROVED
    assert out["risk_score"] == 0.0
    assert out["final_status"] == OnboardingStatus.STANDARD_ONBOARDING
    assert out["workflow_trace"] == [
        "intake",
        "gather_evidence",
        "planner",
        "reviewer",
        "mock_action",
        "summarize",
    ]
    assert "human_review" not in out["workflow_trace"]
    assert out["final_summary"]


# ---------------------------------------------------------------------------
# 2. Branching path — new IT/Software vendor
# ---------------------------------------------------------------------------


def test_branching_it_software_routes_through_human_gate(app, make_request):
    req = make_request(
        vendor_name="Acme Cloud Services",
        vendor_category=VendorCategory.IT_SOFTWARE,
        country="US",
        relationship_status=RelationshipStatus.NEW,
        data_sensitive=False,
        submitted_documents=base_documents([DocumentType.SECURITY_QUESTIONNAIRE]),
    )
    out, snap = drive(app, req, human="approve")

    assert workflow_complete(snap)
    assert out["reviewer_verdict"].decision == ReviewerDecision.ESCALATE
    assert out["requires_human_review"] is True
    assert out["human_decision"] == HumanDecision.APPROVE
    assert out["final_status"] == OnboardingStatus.APPROVED
    trace = out["workflow_trace"]
    assert "human_review" in trace and "mock_action" in trace
    assert trace != [
        "intake",
        "gather_evidence",
        "planner",
        "reviewer",
        "mock_action",
    ], "IT vendor must take the human-gate route, not auto-complete"


# ---------------------------------------------------------------------------
# 3. Missing-information path
# ---------------------------------------------------------------------------


def test_missing_coi_pauses_and_resumes(app, make_request):
    docs_without_coi = [
        d for d in base_documents() if d.type != DocumentType.CERTIFICATE_OF_INSURANCE
    ]
    req = make_request(
        vendor_name="Staple Supply Co.",
        submitted_documents=docs_without_coi,
    )
    cfg = _config_for("missing-info")
    out, snap = first_step(app, cfg, req)

    # Workflow is paused at the intake interrupt, asking for the COI.
    intr = current_interrupt(snap)
    assert workflow_complete(snap) is False
    assert intr is not None and intr["type"] == "missing_documents"
    assert DocumentType.CERTIFICATE_OF_INSURANCE.value in intr["missing_documents"]
    assert "intake" in snap.next, "workflow must be paused inside the intake node"

    # Requester resubmits with the COI included.
    resubmit = [d for d in base_documents()]
    out, snap = resume(app, cfg, [d.model_dump() for d in resubmit])

    assert workflow_complete(snap)
    assert out["final_status"] == OnboardingStatus.STANDARD_ONBOARDING
    assert out["workflow_trace"][0] == "intake"


# ---------------------------------------------------------------------------
# 4. Failure / revision path
# ---------------------------------------------------------------------------


def test_reviewer_revises_planner_then_approves(app, make_request):
    req = make_request(
        vendor_name="Firstline Facilities GmbH",
        vendor_category=VendorCategory.FACILITIES,
        country="Germany",  # foreign entity: planner over-flags on first pass
        relationship_status=RelationshipStatus.EXISTING,
        submitted_documents=base_documents(),
    )
    out, snap = drive(app, req)

    assert workflow_complete(snap)
    # The planner's over-cautious first draft was corrected (one revision).
    assert out["revision_count"] == 1
    assert out["reviewer_verdict"].decision == ReviewerDecision.APPROVED
    assert out["final_status"] == OnboardingStatus.STANDARD_ONBOARDING
    assert "planner" in out["workflow_trace"]
    assert out["workflow_trace"].count("planner") == 2, "must have looped back to the planner"
    assert RiskFlag.FOREIGN_ENTITY in out["risk_flags"]
    assert out["risk_score"] < models.ESCALATION_THRESHOLD


# ---------------------------------------------------------------------------
# 5. Escalation path
# ---------------------------------------------------------------------------


def test_escalation_foreign_data_sensitive_no_security_questionnaire(app, make_request):
    req = make_request(
        vendor_name="Helios Data Partners",
        vendor_category=VendorCategory.IT_SOFTWARE,
        country="Germany",
        data_sensitive=True,
        relationship_status=RelationshipStatus.NEW,
        submitted_documents=base_documents(),  # deliberately no security questionnaire
    )
    cfg = _config_for("escalation")

    # The missing security questionnaire blocks intake first (missing-information
    # path); once supplied, the residual profile still escalates.
    out, snap = first_step(app, cfg, req)
    intr = current_interrupt(snap)
    assert intr is not None and intr["type"] == "missing_documents"
    assert DocumentType.SECURITY_QUESTIONNAIRE.value in intr["missing_documents"]

    complete = base_documents([DocumentType.SECURITY_QUESTIONNAIRE])
    out, snap = resume(app, cfg, [d.model_dump() for d in complete])

    assert out["requires_human_review"] is True
    assert out["reviewer_verdict"].decision == ReviewerDecision.ESCALATE
    assert RiskFlag.FOREIGN_ENTITY in out["risk_flags"]
    assert RiskFlag.NEW_VENDOR_DATA_SENSITIVE in out["risk_flags"]
    assert out["risk_score"] >= models.ESCALATION_THRESHOLD
    assert current_interrupt(snap) is not None

    # Human gate: rejected.
    out, snap = resume(app, cfg, "reject")
    assert workflow_complete(snap)
    assert out["human_decision"] == HumanDecision.REJECT
    assert out["final_status"] == OnboardingStatus.REJECTED
    assert "human_review" in out["workflow_trace"]


# ---------------------------------------------------------------------------
# Extras
# ---------------------------------------------------------------------------


def test_watchlist_hit_always_escalates(app, make_request):
    # Watchlist check confirms the seeded entry exists.
    assert watchlist_check("Blackrock Shipping LLC")

    req = make_request(
        vendor_name="Blackrock Shipping LLC",
        submitted_documents=base_documents(),
    )
    out, snap = drive(app, req, human="reject")

    assert out["requires_human_review"] is True
    assert out["reviewer_verdict"].decision == ReviewerDecision.ESCALATE
    assert RiskFlag.ON_WATCHLIST in out["risk_flags"]
    assert out["risk_score"] >= models.ESCALATION_THRESHOLD


def test_policy_retrieval_metadata_filter(app, make_request):
    import ingestion
    from models import PolicyChunk

    low_risk = ingestion.retrieve(
        "office supplies onboarding requirements",
        category=VendorCategory.OFFICE_SUPPLIES,
        data_sensitive=False,
    )
    assert low_risk
    assert all(c.doc_type != "data_security_it_requirements" for c in low_risk)

    it_risk = ingestion.retrieve(
        "IT vendor security requirements",
        category=VendorCategory.IT_SOFTWARE,
        data_sensitive=False,
    )
    assert any(c.doc_type == "data_security_it_requirements" for c in it_risk)
    # Category-aware: the IT/Software checklist section is retrievable.
    assert any(
        c.vendor_category == VendorCategory.IT_SOFTWARE
        and c.doc_type == "document_checklist_by_category"
        for c in it_risk
    )


def test_revision_cap_auto_escalates_to_human(app):
    """A third revise request must route to open_approval, not the planner."""
    from graph.workflow import _route_reviewer
    from models import ReviewerVerdict, WorkflowState

    state = WorkflowState(
        reviewer_verdict=ReviewerVerdict(decision=ReviewerDecision.REVISE, feedback="again", risk_score=5),
        revision_count=3,  # cap of 2 exceeded
    )
    assert _route_reviewer(state) == "open_approval"

    state2 = WorkflowState(
        reviewer_verdict=ReviewerVerdict(decision=ReviewerDecision.REVISE, feedback="again", risk_score=5),
        revision_count=2,  # within cap
    )
    assert _route_reviewer(state2) == "planner"
