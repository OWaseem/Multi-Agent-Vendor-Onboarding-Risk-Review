"""LangGraph workflow wiring and run helpers.

Graph shape::

    START -> intake -> content_safety_check -> gather_evidence -> planner -> reviewer
    reviewer: approved -> mock_action -> summarize -> END
              rejected (risk_score >= AUTO_REJECT_THRESHOLD) -> reject -> summarize -> END
              escalate -> open_approval -> human_review
              revise (revision_count <= cap) -> planner
              revise (revision_count > cap) -> open_approval
    human_review: approve -> mock_action -> summarize -> END
                  reject -> reject -> summarize -> END

The human-approval gate and the missing-document flow both pause the graph via
``interrupt``; resume with :class:`langgraph.types.Command` using the same
``thread_id`` config.
"""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from models import HumanDecision, ReviewerDecision, VendorRequest, WorkflowState

from . import nodes

REVISION_CAP = nodes.REVISION_CAP

#: Nested pydantic models round-trip through the msgpack checkpointer without
#: deprecation warnings once their module is allowlisted.
_MSGPACK_ALLOWLIST = [
    ("models", t)
    for t in (
        "VendorCategory",
        "RelationshipStatus",
        "DocumentType",
        "SubmittedDocument",
        "PolicyChunk",
        "RecommendedPath",
        "PlannerRecommendation",
        "ReviewerDecision",
        "ReviewerVerdict",
        "OnboardingStatus",
        "HumanDecision",
        "RiskFlag",
        "RiskScoreItem",
        "ApprovalStatus",
    )
]


def create_checkpointer() -> MemorySaver:
    serde = JsonPlusSerializer(allowed_msgpack_modules=_MSGPACK_ALLOWLIST)
    return MemorySaver(serde=serde)


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


def _route_reviewer(state: WorkflowState) -> str:
    decision = state.reviewer_verdict.decision
    if decision == ReviewerDecision.APPROVED:
        return "mock_action"
    if decision == ReviewerDecision.REJECTED:
        return "reject"
    if decision == ReviewerDecision.ESCALATE:
        return "open_approval"
    if state.revision_count > REVISION_CAP:
        return "open_approval"
    return "planner"


def _route_human(state: WorkflowState) -> str:
    if state.human_decision == HumanDecision.APPROVE:
        return "mock_action"
    return "reject"


def build_graph():
    graph = StateGraph(WorkflowState)
    graph.add_node("intake", nodes.intake)
    graph.add_node("content_safety_check", nodes.content_safety_check)
    graph.add_node("gather_evidence", nodes.gather_evidence)
    graph.add_node("planner", nodes.planner)
    graph.add_node("reviewer", nodes.reviewer)
    graph.add_node("open_approval", nodes.open_approval)
    graph.add_node("human_review", nodes.human_review)
    graph.add_node("mock_action", nodes.mock_action)
    graph.add_node("reject", nodes.reject)
    graph.add_node("summarize", nodes.summarize)

    graph.add_edge(START, "intake")
    graph.add_edge("intake", "content_safety_check")
    graph.add_edge("content_safety_check", "gather_evidence")
    graph.add_edge("gather_evidence", "planner")
    graph.add_edge("planner", "reviewer")

    graph.add_conditional_edges("reviewer", _route_reviewer)
    graph.add_edge("open_approval", "human_review")
    graph.add_conditional_edges("human_review", _route_human)
    graph.add_edge("mock_action", "summarize")
    graph.add_edge("reject", "summarize")
    graph.add_edge("summarize", END)
    return graph


def create_app(checkpointer: MemorySaver | None = None):
    """Compile the workflow with an in-memory checkpointer (interrupt support)."""
    return build_graph().compile(checkpointer=checkpointer or create_checkpointer())


# ---------------------------------------------------------------------------
# Run helpers (shared by the Streamlit app and the pytest scenarios)
# ---------------------------------------------------------------------------


def config_for(thread_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}}


def first_step(app, config: dict[str, Any], request: VendorRequest):
    """Start a workflow from a VendorRequest; returns (state_values, snapshot)."""
    initial = nodes.state_from_request(request).model_dump()
    output = app.invoke(initial, config=config)
    return output, app.get_state(config)


def resume(app, config: dict[str, Any], value: Any):
    """Resume a paused workflow (missing docs or human gate)."""
    output = app.invoke(Command(resume=value), config=config)
    return output, app.get_state(config)


def current_interrupt(snapshot) -> dict | None:
    """Return the latest interrupt payload, or None if not paused."""
    if snapshot is None or not snapshot.interrupts:
        return None
    return snapshot.interrupts[-1].value


def workflow_complete(snapshot) -> bool:
    """True once the graph has no pending nodes left."""
    return snapshot is not None and not snapshot.next
