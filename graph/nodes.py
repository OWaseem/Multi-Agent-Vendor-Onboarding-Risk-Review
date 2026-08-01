"""LangGraph nodes for the three-agent workflow.

Roles:
- intake (document completeness, with requester interrupt)
- gather_evidence (vendor lookup + RAG policy retrieval)
- planner (drafts the recommended onboarding path)
- reviewer (critic: validates against policy, score, watchlist)
- open_approval / human_review (human-approval gate via interrupt)
- mock_action / reject (mocked side-effects + final status writes)
"""

from __future__ import annotations

from typing import Any

from langgraph.types import interrupt

import llm
import models
import tools
from models import (
    DocumentType,
    HumanDecision,
    OnboardingStatus,
    PlannerRecommendation,
    RecommendedPath,
    RelationshipStatus,
    ReviewerDecision,
    ReviewerVerdict,
    RiskFlag,
    SubmittedDocument,
    VendorCategory,
    VendorRequest,
    WorkflowState,
    required_document_types,
)
from tools import evaluate_risk_flags

# Revision cap: after the 2nd revision a 3rd revise request auto-escalates.
REVISION_CAP = 2


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------


def state_from_request(request: VendorRequest) -> WorkflowState:
    """Build the initial workflow state from an intake submission."""
    return WorkflowState(
        vendor_name=request.vendor_name,
        vendor_category=request.vendor_category,
        country=request.country,
        data_sensitive=request.data_sensitive,
        vendor_history=request.relationship_status,
        requester_name=request.requester_name,
        requester_department=request.requester_department,
        business_justification=request.business_justification,
        submitted_documents=list(request.submitted_documents),
    )


def _is_new_vendor(state: WorkflowState) -> bool:
    """Ground truth from the vendor master DB; fall back to the claim."""
    if state.vendor_record:
        return not state.vendor_record["prior_relationship"]
    return state.vendor_history == RelationshipStatus.NEW


def _submitted_types(state: WorkflowState) -> list[DocumentType]:
    return [d.type for d in state.submitted_documents]


def _trace(state: WorkflowState, node: str) -> list[str]:
    return state.workflow_trace + [node]


# ---------------------------------------------------------------------------
# 1. Intake / document-completeness agent
# ---------------------------------------------------------------------------


def intake(state: WorkflowState) -> dict[str, Any]:
    """Check the required-document checklist for the vendor's category.

    Pauses via ``interrupt`` asking the requester for missing documents. On
    resume the caller supplies the *complete* updated document list, which is
    re-validated (looping if still incomplete).
    """
    trace = _trace(state, "intake")
    required = required_document_types(state.vendor_category, state.data_sensitive)
    docs = list(state.submitted_documents)
    submitted_types = {d.type for d in docs}
    missing = sorted(required - submitted_types, key=lambda d: d.value)

    while missing:
        resumed_value = interrupt(
            {
                "type": "missing_documents",
                "request_id": state.request_id,
                "missing_documents": [m.value for m in missing],
                "message": "Please submit the missing documents listed above.",
            }
        )
        # Resume value: the full, updated list of submitted documents.
        docs = _normalize_documents(resumed_value)
        submitted_types = {d.type for d in docs}
        missing = sorted(required - submitted_types, key=lambda d: d.value)

    return {
        "submitted_documents": docs,
        "missing_documents": [],
        "workflow_trace": trace,
    }


def _normalize_documents(value: Any) -> list[SubmittedDocument]:
    """Coerce a resume value into a list of SubmittedDocument models."""
    items = value if isinstance(value, list) else [value]
    return [
        SubmittedDocument.model_validate(d) if isinstance(d, dict) else d for d in items
    ]


# ---------------------------------------------------------------------------
# 2. Evidence gathering (vendor lookup + RAG policy retrieval)
# ---------------------------------------------------------------------------


def gather_evidence(state: WorkflowState) -> dict[str, Any]:
    """Run vendor_lookup and the metadata-filtered policy_retriever."""
    trace = _trace(state, "gather_evidence")
    vendor = tools.vendor_lookup(state.vendor_name)
    query = (
        f"onboarding requirements for a {state.vendor_category.value} vendor, "
        f"data_sensitive={state.data_sensitive}, new_vendor={_is_new_vendor(state)}"
    )
    chunks = tools.policy_retriever(
        query, category=state.vendor_category, data_sensitive=state.data_sensitive
    )
    return {
        "vendor_record": vendor if vendor is not None else {},
        "retrieved_policy_chunks": chunks,
        "workflow_trace": trace,
    }


# ---------------------------------------------------------------------------
# 3. Onboarding planner
# ---------------------------------------------------------------------------


def _planner_prompt(state: WorkflowState, flags: list[RiskFlag], path: RecommendedPath) -> str:
    flag_names = ", ".join(f.value for f in flags) or "none"
    return (
        f"You are the onboarding planner. Vendor {state.vendor_name} "
        f"({state.vendor_category.value}, country={state.country}). "
        f"Risk flags identified: {flag_names}. "
        f"Recommended path per rubric: {path.value}. "
        f"Business justification: {state.business_justification or 'none'}. "
        f"Write a concise 2-3 sentence onboarding recommendation."
    )


def _fallback_reasoning(state: WorkflowState, flags: list[RiskFlag], path: RecommendedPath) -> str:
    flag_names = ", ".join(f.value for f in flags) or "none"
    lines = [
        f"Recommended path: {path.value}.",
        f"Risk flags identified: {flag_names}.",
    ]
    if state.business_justification:
        lines.append("Requester supplied a business justification for review.")
    return " ".join(lines)


def planner(state: WorkflowState) -> dict[str, Any]:
    """Draft the recommended onboarding path.

    First pass (revision_count == 0) is deliberately conservative: any risk
    flag drafts high_risk, so the reviewer's stricter rubric has something to
    correct (see the revision test scenario). Later passes use the strict
    rubric so the loop converges.
    """
    trace = _trace(state, "planner")
    flags = evaluate_risk_flags(
        vendor_name=state.vendor_name,
        country=state.country,
        submitted_documents=_submitted_types(state),
        vendor_category=state.vendor_category,
        data_sensitive=state.data_sensitive,
        relationship_status=(
            RelationshipStatus.EXISTING if not _is_new_vendor(state) else RelationshipStatus.NEW
        ),
    )

    has_justification = bool(state.business_justification)
    if state.revision_count == 0:
        # Conservative draft: any flag => high_risk (reviewer may correct).
        if has_justification and flags:
            path = RecommendedPath.NEEDS_EXCEPTION
        elif flags:
            path = RecommendedPath.HIGH_RISK
        else:
            path = RecommendedPath.STANDARD
    else:
        # Strict rubric (mirrors the reviewer): score-driven.
        score = tools.risk_score_calculator(flags, state.vendor_category, state.data_sensitive)
        if has_justification and flags:
            path = RecommendedPath.NEEDS_EXCEPTION
        elif score >= models.ESCALATION_THRESHOLD:
            path = RecommendedPath.HIGH_RISK
        else:
            path = RecommendedPath.STANDARD

    reasoning = llm.llm_text(_planner_prompt(state, flags, path)) or _fallback_reasoning(
        state, flags, path
    )
    recommendation = PlannerRecommendation(
        recommended_path=path,
        reasoning=reasoning,
        cited_policy_chunks=[c.chunk_id for c in state.retrieved_policy_chunks],
    )
    return {"risk_flags": flags, "planner_recommendation": recommendation, "workflow_trace": trace}


# ---------------------------------------------------------------------------
# 4. Risk / compliance reviewer (critic)
# ---------------------------------------------------------------------------


def _reviewer_prompt(state: WorkflowState, verdict_text: str) -> str:
    return (
        f"You are the risk/compliance reviewer. Vendor {state.vendor_name}, "
        f"planner recommendation: {state.planner_recommendation.recommended_path.value}. "
        f"Verdict: {verdict_text}. Write a concise review note."
    )


def reviewer(state: WorkflowState) -> dict[str, Any]:
    """Validate the planner's draft against policy, risk score, and watchlist."""
    trace = _trace(state, "reviewer")
    hits = tools.watchlist_check(state.vendor_name)
    flags = evaluate_risk_flags(
        vendor_name=state.vendor_name,
        country=state.country,
        submitted_documents=_submitted_types(state),
        vendor_category=state.vendor_category,
        data_sensitive=state.data_sensitive,
        relationship_status=(
            RelationshipStatus.EXISTING if not _is_new_vendor(state) else RelationshipStatus.NEW
        ),
    )
    if hits:
        flags.append(RiskFlag.ON_WATCHLIST)

    score = tools.risk_score_calculator(flags, state.vendor_category, state.data_sensitive)
    rec = state.planner_recommendation.recommended_path
    mandatory_gate = state.vendor_category.is_high_risk_category or state.data_sensitive

    if (
        RiskFlag.ON_WATCHLIST in flags
        or score >= models.ESCALATION_THRESHOLD
        or mandatory_gate
        or rec == RecommendedPath.NEEDS_EXCEPTION
    ):
        decision, feedback = ReviewerDecision.ESCALATE, (
            "Escalated: requires human sign-off (high risk, watchlist, "
            "exception, or mandatory IT/data-sensitive review)."
        )
    elif rec == RecommendedPath.HIGH_RISK:
        decision, feedback = ReviewerDecision.REVISE, (
            "Planner over-flagged: recompute the risk score. Flags present do "
            "not reach the escalation threshold, so recommend the standard path."
        )
    else:
        decision, feedback = ReviewerDecision.APPROVED, ""

    revision_count = state.revision_count + (1 if decision == ReviewerDecision.REVISE else 0)
    verdict_text = (
        f"{decision.value} (risk_score={score:.0f}, revision_count={revision_count})"
    )
    verdict = ReviewerVerdict(
        decision=decision,
        feedback=llm.llm_text(_reviewer_prompt(state, verdict_text)) or feedback,
        risk_score=score,
    )
    return {
        "risk_flags": flags,
        "risk_score": score,
        "reviewer_verdict": verdict,
        "revision_count": revision_count,
        "workflow_trace": trace,
    }


# ---------------------------------------------------------------------------
# 5. Human-approval gate
# ---------------------------------------------------------------------------


def open_approval(state: WorkflowState) -> dict[str, Any]:
    """Create the (mocked) pending approval request before human review."""
    trace = _trace(state, "open_approval")
    notes = f"requires human review; risk_score={state.risk_score:.0f}"
    approval_id = tools.create_approval_request(state.request_id, state.vendor_name, notes)
    return {
        "pending_approval_id": approval_id,
        "requires_human_review": True,
        "workflow_trace": trace,
    }


def human_review(state: WorkflowState) -> dict[str, Any]:
    """Interrupt for the human approver; applies the decision on resume."""
    trace = _trace(state, "human_review")
    decision = interrupt(
        {
            "type": "human_approval",
            "request_id": state.request_id,
            "pending_approval_id": state.pending_approval_id,
            "vendor_name": state.vendor_name,
            "question": "Approve this vendor onboarding?",
        }
    )
    approve = decision in (HumanDecision.APPROVE.value, "approve")
    tools.resolve_approval(
        state.pending_approval_id,
        status="approved" if approve else "rejected",
        decided_by="human",
        notes=str(decision),
    )
    return {
        "human_decision": HumanDecision.APPROVE if approve else HumanDecision.REJECT,
        "workflow_trace": trace,
    }


# ---------------------------------------------------------------------------
# 6. Terminal side-effect nodes (mocked)
# ---------------------------------------------------------------------------


def mock_action(state: WorkflowState) -> dict[str, Any]:
    """Create/resolve the approval record and write the final status."""
    trace = _trace(state, "mock_action")
    if state.pending_approval_id is None:
        approval_id = tools.create_approval_request(
            state.request_id, state.vendor_name, "auto-approved by reviewer"
        )
        tools.resolve_approval(approval_id, status="approved", decided_by="auto", notes="")
        final_status = OnboardingStatus.STANDARD_ONBOARDING
    else:
        final_status = OnboardingStatus.APPROVED
    tools.update_vendor_status(
        state.request_id,
        state.vendor_name,
        final_status,
        notes=f"risk_score={state.risk_score:.0f}",
    )
    return {"final_status": final_status, "workflow_trace": trace}


def reject(state: WorkflowState) -> dict[str, Any]:
    """Record the rejected outcome."""
    trace = _trace(state, "reject")
    tools.update_vendor_status(
        state.request_id, state.vendor_name, OnboardingStatus.REJECTED, notes="human rejected"
    )
    return {"final_status": OnboardingStatus.REJECTED, "workflow_trace": trace}
