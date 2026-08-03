"""Streamlit UI for the Multi-Agent Vendor Onboarding & Risk Review workflow.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

import streamlit as st

import db
import ingestion
import seeders
from graph.workflow import (
    config_for,
    create_app,
    current_interrupt,
    first_step,
    resume,
    workflow_complete,
)
from models import (
    DocumentType,
    RelationshipStatus,
    SubmittedDocument,
    VendorCategory,
    VendorRequest,
)

DOC_LABELS: dict[str, str] = {
    DocumentType.W9_TAX_ID.value: "W-9 / Tax ID form",
    DocumentType.CERTIFICATE_OF_INSURANCE.value: "Certificate of Insurance (COI)",
    DocumentType.BUSINESS_LICENSE.value: "Business license / Articles of incorporation",
    DocumentType.CODE_OF_CONDUCT.value: "Signed vendor code of conduct",
    DocumentType.SECURITY_QUESTIONNAIRE.value: "Security questionnaire",
    DocumentType.BANKING_ACH_FORM.value: "Banking / ACH form",
}

CATEGORY_LABELS = {c.value: c.value for c in VendorCategory}

SAMPLE_DOCS_DIR = Path(__file__).resolve().parent / "sample_documents"
UPLOAD_DIR = Path(__file__).resolve().parent / "uploads"


def ensure_environment() -> None:
    """One-time env setup per process: schema, mock seeders, vector store."""
    if st.session_state.get("env_ready"):
        return
    db.init_db()
    seeders.seed_all()
    ingestion.build_vector_store()
    st.session_state["app"] = create_app()
    st.session_state["env_ready"] = True


def state_value(snap, key: str, default=None):
    try:
        return snap.values.get(key, default)
    except AttributeError:
        return default


def render_trace(state_values) -> None:
    st.markdown("### Workflow trace")
    trace = state_values.get("workflow_trace") or []
    if not trace:
        st.caption("(workflow not started yet)")
        return
    for step in trace:
        st.markdown(f"- `{step}`")


def render_planner_and_verdict(state_values) -> None:
    rec = state_values.get("planner_recommendation")
    if rec is not None:
        path = rec.recommended_path if hasattr(rec, "recommended_path") else rec.get("recommended_path")
        reasoning = rec.reasoning if hasattr(rec, "reasoning") else rec.get("reasoning", "")
        with st.expander("Planner recommendation", expanded=True):
            st.write(f"**Path:** {path}")
            st.write(reasoning)
    verdict = state_values.get("reviewer_verdict")
    if verdict is not None:
        decision = verdict.decision if hasattr(verdict, "decision") else verdict.get("decision")
        feedback = verdict.feedback if hasattr(verdict, "feedback") else verdict.get("feedback", "")
        risk_score = verdict.risk_score if hasattr(verdict, "risk_score") else verdict.get("risk_score")
        st.markdown("### Reviewer verdict")
        st.write(f"**Decision:** {decision} | **Risk score:** {risk_score:.0f}" if isinstance(risk_score, (int, float)) else f"**Decision:** {decision}")
        if feedback:
            st.write(feedback)


def render_summary(state_values) -> None:
    summary = state_values.get("final_summary")
    if summary:
        st.markdown("### Summary")
        st.write(summary)


def render_llm_error(state_values) -> None:
    error = state_values.get("llm_error")
    if error:
        st.error(f"LLM provider call failed — falling back to template text. {error}")


def render_outcome(state_values) -> None:
    render_planner_and_verdict(state_values)
    if state_values.get("final_status"):
        status = state_values["final_status"]
        label = status.value if hasattr(status, "value") else status
        st.markdown("### Final outcome")
        st.success(f"**{label}**")
    render_summary(state_values)


def render_sample_downloads() -> None:
    """Download buttons for a valid example of each document type.

    Rendered outside any ``st.form`` — Streamlit forbids ``download_button``
    inside a form, and this is shared by both the new-request form and the
    resubmit-on-resume screen.
    """
    with st.expander("Need example documents? Download a valid sample per type"):
        for doc_value, label in DOC_LABELS.items():
            sample_path = SAMPLE_DOCS_DIR / f"{doc_value}_valid_example.pdf"
            if sample_path.exists():
                st.download_button(
                    label,
                    data=sample_path.read_bytes(),
                    file_name=sample_path.name,
                    key=f"sample_{doc_value}",
                )


def document_widgets(prefix: str, defaults: list | None = None) -> list[SubmittedDocument]:
    """Checkboxes + real file uploads for the six document types.

    Each type expects a PDF with labeled fields (see ``document_validation.py``);
    the intake node rejects a submitted file that doesn't match it. See
    ``render_sample_downloads`` for grabbing a valid example of each type.
    """
    existing: dict[str, str] = {}
    for d in defaults or []:
        t = d.type.value if hasattr(d, "type") else d["type"]
        r = d.reference if hasattr(d, "reference") else d.get("reference", "")
        existing[t] = r
    docs: list[SubmittedDocument] = []
    for doc_value, label in DOC_LABELS.items():
        checked = st.checkbox(label, value=doc_value in existing, key=f"{prefix}_has_{doc_value}")
        if not checked:
            continue
        uploaded = st.file_uploader(
            "Upload file (.pdf)", type=["pdf"], key=f"{prefix}_file_{doc_value}"
        )
        if uploaded is not None:
            UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            dest = UPLOAD_DIR / f"{prefix}_{doc_value}_{uuid.uuid4().hex[:8]}.pdf"
            dest.write_bytes(uploaded.getvalue())
            reference = str(dest)
        else:
            reference = existing.get(doc_value, "")
            if not reference:
                st.caption("No file uploaded yet — this document will be treated as missing.")
        if reference:
            docs.append(
                SubmittedDocument(
                    type=DocumentType(doc_value),
                    reference=reference,
                    submitted_at=datetime.now(),
                )
            )
    return docs


def new_request_form() -> None:
    st.header("New vendor request")
    render_sample_downloads()
    # Not wrapped in st.form: the document checkboxes need to immediately
    # reveal a file uploader when checked, but forms only rerun the script on
    # submit, so a checkbox's live state never reaches the code below it
    # until it's too late to react. Plain widgets rerun on every interaction.
    col1, col2 = st.columns(2)
    with col1:
        vendor_name = st.text_input("Vendor name", value="Staple Supply Co.")
        category = st.selectbox("Vendor category", list(CATEGORY_LABELS), key="form_category")
        country = st.text_input("Country of operation", value="US")
    with col2:
        requester_name = st.text_input("Requester name", value="Alice Johnson")
        department = st.text_input("Department", value="Operations")
        relationship = st.selectbox(
            "Relationship status",
            [r.value for r in RelationshipStatus],
            key="form_relationship",
        )
    data_sensitive = st.checkbox("Data-sensitive: will this vendor touch company/customer data or IT systems?")
    business_justification = st.text_area(
        "Business justification (for policy exceptions)", value=""
    )
    st.markdown("**Attached documents**")
    submitted = document_widgets("new")
    submitted_documents = st.button("Submit request", type="primary")

    if submitted_documents:
        request = VendorRequest(
            vendor_name=vendor_name.strip(),
            vendor_category=VendorCategory(category),
            country=country.strip(),
            data_sensitive=data_sensitive,
            relationship_status=RelationshipStatus(relationship),
            requester_name=requester_name.strip(),
            requester_department=department.strip(),
            business_justification=business_justification.strip() or None,
            submitted_documents=submitted,
        )
        st.session_state["active"] = {"request": request}
        st.rerun()


def handle_missing_documents(state_values, snap) -> None:
    intr = current_interrupt(snap)
    missing = intr.get("missing_documents", [])
    invalid = intr.get("invalid_documents", {})
    st.error("**Documents missing or invalid** — the workflow is paused awaiting the requester.")
    if missing:
        st.write("**Missing:** " + ", ".join(DOC_LABELS.get(m, m) for m in missing))
    if invalid:
        st.write("**Format problems:**")
        for doc_value, errors in invalid.items():
            st.write(f"- {DOC_LABELS.get(doc_value, doc_value)}: {'; '.join(errors)}")
    st.write("Please provide the missing documents and/or re-upload corrected files:")
    render_sample_downloads()
    submitted_now = document_widgets("resume", defaults=state_values.get("submitted_documents", []))
    if st.button("Resubmit documents", type="primary"):
        app = st.session_state["app"]
        thread_id = st.session_state["thread_id"]
        out, new_snap = resume(
            app, config_for(thread_id), [d.model_dump() for d in submitted_now]
        )
        st.session_state["out"], st.session_state["snap"] = out, new_snap
        st.rerun()


def handle_human_gate(state_values, snap) -> None:
    intr = current_interrupt(snap)
    st.warning("**Escalated to human review** — final approval requires sign-off.")
    render_planner_and_verdict(state_values)
    render_summary(state_values)
    st.write(intr.get("question", ""))
    col1, col2 = st.columns(2)
    if col1.button("Approve", type="primary"):
        _resume_flow("approve")
    if col2.button("Reject"):
        _resume_flow("reject")


def _resume_flow(value: str) -> None:
    app = st.session_state["app"]
    thread_id = st.session_state["thread_id"]
    out, new_snap = resume(app, config_for(thread_id), value)
    st.session_state["out"], st.session_state["snap"] = out, new_snap
    st.rerun()


def show_pending_approvals() -> None:
    st.markdown("---")
    st.header("Approval requests")
    with db.connection() as conn:
        rows = conn.execute(
            "SELECT id, request_id, vendor_name, status, decided_by, decision_notes, created_at"
            " FROM approval_requests ORDER BY id DESC LIMIT 10"
        ).fetchall()
        rows = [dict(r) for r in rows]
    if rows:
        st.dataframe(rows, use_container_width=True)
    else:
        st.caption("No approval requests yet.")


def show_status_log() -> None:
    st.markdown("---")
    st.header("Vendor status log")
    with db.connection() as conn:
        rows = conn.execute(
            "SELECT id, request_id, vendor_name, final_status, notes, written_at"
            " FROM vendor_status_log ORDER BY id DESC LIMIT 10"
        ).fetchall()
        rows = [dict(r) for r in rows]
    if rows:
        st.dataframe(rows, use_container_width=True)
    else:
        st.caption("No status writes yet.")


def main() -> None:
    st.set_page_config(page_title="Vendor Onboarding & Risk Review", layout="wide")
    st.title("Multi-Agent Vendor Onboarding & Risk Review")
    st.caption(
        "LangGraph pipeline: intake completeness → planner → risk/compliance reviewer "
        "→ human-approval gate → mocked persistence."
    )

    ensure_environment()

    with st.sidebar:
        st.header("Environment")
        st.write(f"DB: `{db.DB_PATH}`")
        st.write(f"Vector store: `{ingestion.VECTOR_STORE_PATH}`")
        st.write(f"Policy chunks indexed: `{ingestion.chunk_count()}`")
        if "active" in st.session_state:
            if st.button("Start a new request"):
                del st.session_state["active"]
                st.rerun()

    if "active" not in st.session_state:
        new_request_form()
        show_pending_approvals()
        show_status_log()
        return

    request: VendorRequest = st.session_state["active"]["request"]
    st.header(f"Vendor: {request.vendor_name}")
    st.caption(
        f"{request.vendor_category.value} · {request.country} · "
        f"{request.relationship_status.value} · data_sensitive={request.data_sensitive}"
    )

    if "snap" not in st.session_state:
        thread_id = uuid.uuid4().hex[:12]
        st.session_state["thread_id"] = thread_id
        app = st.session_state["app"]
        out, snap = first_step(app, config_for(thread_id), request)
        st.session_state["out"], st.session_state["snap"] = out, snap
        st.rerun()

    out, snap = st.session_state["out"], st.session_state["snap"]
    state_values = out if isinstance(out, dict) else out

    render_trace(state_values)
    render_llm_error(state_values)

    intr = current_interrupt(snap)
    if intr:
        if intr["type"] == "missing_documents":
            handle_missing_documents(state_values, snap)
        elif intr["type"] == "human_approval":
            handle_human_gate(state_values, snap)
    elif workflow_complete(snap):
        render_outcome(state_values)
    else:
        st.info("Workflow running…")

    show_pending_approvals()
    show_status_log()


if __name__ == "__main__":
    main()
