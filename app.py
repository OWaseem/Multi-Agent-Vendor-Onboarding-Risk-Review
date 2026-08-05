"""Streamlit UI for the Multi-Agent Vendor Onboarding & Risk Review workflow.
NEw
Run with:  streamlit run app.py

Layout is a four-stage wizard (Intake -> Plan -> Risk review -> Approval) with a
persistent readiness rail on the right. File order: theme -> constants ->
environment -> primitives -> readiness -> renderers -> documents -> screens ->
entrypoint, so nothing is referenced before it is defined.

No icon fonts are used anywhere. Every marker is a CSS shape or plain text, so
the UI cannot fall back to literal ligature names ("arrow_upward") if Streamlit's
Material Symbols font fails to load.
"""

from __future__ import annotations

import html
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

# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------
# Five-stop ramp, dark plum -> pale aqua. The ramp is structural, not decorative:
# the stage rail and the readiness meter both walk it left to right, so progress
# through the pipeline reads as movement from --vp-c1 toward --vp-c5.

RAMP = ["#533747", "#5F506B", "#6A6B83", "#76949F", "#86BBBD"]

THEME_CSS = """
<style>
:root {
  --vp-c1: #533747;
  --vp-c2: #5F506B;
  --vp-c3: #6A6B83;
  --vp-c4: #76949F;
  --vp-c5: #86BBBD;

  --vp-bg:        #1E161C;
  --vp-bg-grad:   radial-gradient(1100px 520px at 8% -12%, #3A2735 0%, #1E161C 62%);
  --vp-surface:   #2B2130;
  --vp-surface-2: #352A3B;
  --vp-line:      rgba(134, 187, 189, 0.18);
  --vp-line-soft: rgba(134, 187, 189, 0.09);

  --vp-text:  #ECF2F2;
  --vp-muted: #A3B2BA;
  --vp-faint: #7B858D;

  --vp-radius: 14px;
  --vp-sans: ui-sans-serif, system-ui, "Segoe UI", Inter, Helvetica, Arial, sans-serif;
  --vp-mono: ui-monospace, "SF Mono", "JetBrains Mono", Menlo, Consolas, monospace;
}

/* ---- canvas ---- */
.stApp { background: var(--vp-bg-grad); background-color: var(--vp-bg); color: var(--vp-text); }
[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 2.2rem; max-width: 1240px; }
.stApp, .stApp p, .stApp li, .stApp label { font-family: var(--vp-sans); }

/* Material Symbols ligatures. Streamlit puts the literal icon name
   ("arrow_upward", "expand_more") in a span and lets the icon font fuse it into
   a glyph - so never set font-family on these, or the words render as text. */
[data-testid="stIconMaterial"],
span[class*="material-symbols"],
span[class*="material-icons"] {
  font-family: "Material Symbols Rounded", "Material Symbols Outlined",
               "Material Icons" !important;
  font-variation-settings: normal;
  letter-spacing: normal;
  text-transform: none;
}

/* ---- type ---- */
h1, h2, h3 { color: var(--vp-text); letter-spacing: -0.015em; }
h1 { font-size: 1.85rem; font-weight: 640; }
h2 { font-size: 1.15rem; font-weight: 600; }
[data-testid="stCaptionContainer"], .stCaption { color: var(--vp-muted) !important; }
hr { border-color: var(--vp-line-soft) !important; }

/* ---- stage rail ---- */
.vp-stages { display: flex; align-items: center; flex-wrap: wrap; gap: 0.15rem;
             margin: 0 0 0.35rem; padding: 0; list-style: none; }
.vp-stage { display: flex; align-items: center; gap: 0.5rem; padding: 0.4rem 0.95rem;
            border-radius: 999px; font-size: 0.92rem; color: var(--vp-faint);
            border: 1px solid transparent; white-space: nowrap; }
.vp-stage-num { font-family: var(--vp-mono); font-size: 0.75rem; opacity: 0.85; }
.vp-stage[data-state="done"] { color: var(--vp-c5); }
.vp-stage[data-state="active"] { color: #FFFFFF; border-color: rgba(134,187,189,0.55);
  background: linear-gradient(100deg, var(--vp-c2), var(--vp-c4)); font-weight: 600; }
/* Connector is a drawn rule, never a glyph. */
.vp-stage-link { width: 30px; height: 1px; background: var(--vp-line); flex: 0 0 auto; }
.vp-stage-link[data-state="done"] { background: var(--vp-c4); }

.vp-status { text-align: right; color: var(--vp-faint); font-size: 0.9rem;
             margin: -1.9rem 0 1.5rem; }

/* ---- cards (st.container(border=True)) ---- */
[data-testid="stVerticalBlockBorderWrapper"] {
  background: var(--vp-surface); border: 1px solid var(--vp-line-soft) !important;
  border-radius: var(--vp-radius) !important; padding: 1.15rem 1.3rem !important;
}
.vp-card-title { font-size: 1.02rem; font-weight: 600; color: var(--vp-text);
                 margin-bottom: 0.15rem; }
.vp-card-sub { font-size: 0.84rem; color: var(--vp-faint); margin-bottom: 0.7rem; }

/* ---- readiness panel ---- */
.vp-meter-label { font-size: 0.86rem; color: var(--vp-muted); }
.vp-meter-value { font-size: 2.5rem; font-weight: 650; color: var(--vp-text);
                  line-height: 1.1; letter-spacing: -0.02em; }
.vp-meter-track { height: 6px; border-radius: 999px; background: rgba(134,187,189,0.13);
                  overflow: hidden; margin: 0.6rem 0 0.2rem; }
.vp-meter-fill { height: 100%; border-radius: 999px;
                 background: linear-gradient(90deg, var(--vp-c2), var(--vp-c5)); }
.vp-panel-rule { border-top: 1px solid var(--vp-line-soft); margin: 1rem 0 0.85rem; }
.vp-panel-head { font-size: 0.86rem; color: var(--vp-muted); margin-bottom: 0.55rem; }

/* Blocker marker: a hollow square drawn in CSS, not an icon glyph. */
.vp-block { display: flex; align-items: center; gap: 0.65rem; padding: 0.28rem 0;
            font-size: 0.94rem; color: var(--vp-text); }
.vp-block::before { content: ""; width: 9px; height: 9px; flex: 0 0 auto;
                    border: 1.5px solid var(--vp-c5); border-radius: 2px; }
.vp-clear { font-size: 0.92rem; color: var(--vp-c5); }

/* ---- callout ---- */
.vp-callout { border-radius: 10px; padding: 0.85rem 1rem; margin: 0.2rem 0 0.1rem;
              background: rgba(83,55,71,0.62); border: 1px solid rgba(134,187,189,0.28);
              border-left: 3px solid var(--vp-c5); }
.vp-callout-t { color: var(--vp-c5); font-weight: 600; font-size: 0.95rem; }
.vp-callout-s { color: var(--vp-muted); font-size: 0.85rem; margin-top: 0.15rem; }

/* ---- document rows ---- */
.vp-doc { display: flex; align-items: center; gap: 0.7rem; padding: 0.62rem 0;
          border-bottom: 1px solid var(--vp-line-soft); font-size: 0.95rem; }
.vp-doc:last-child { border-bottom: none; }
.vp-doc-dot { width: 8px; height: 8px; border-radius: 2px; flex: 0 0 auto;
              background: var(--vp-c5); }
.vp-doc[data-state="missing"] .vp-doc-dot { background: transparent;
              border: 1.5px solid var(--vp-c3); }
.vp-doc-name { color: var(--vp-text); overflow: hidden; text-overflow: ellipsis;
               white-space: nowrap; }
.vp-doc[data-state="missing"] .vp-doc-name { color: var(--vp-faint); }
.vp-doc-tag { margin-left: auto; color: var(--vp-faint); font-size: 0.85rem;
              white-space: nowrap; padding-left: 0.8rem; }

/* ---- verdict ---- */
.vp-verdict { display: flex; align-items: baseline; gap: 0.85rem; flex-wrap: wrap; }
.vp-decision { font-size: 1.2rem; font-weight: 650; color: var(--vp-accent, var(--vp-c5)); }
.vp-score { font-family: var(--vp-mono); font-size: 0.85rem; color: var(--vp-muted); }
.vp-body { color: var(--vp-muted); font-size: 0.93rem; line-height: 1.55; }
.vp-final-status { font-size: 1.45rem; font-weight: 660; color: var(--vp-c5); }
.vp-empty { font-size: 0.9rem; color: var(--vp-faint); border: 1px dashed var(--vp-line);
            border-radius: 10px; padding: 0.85rem 1rem; }
.vp-trace { font-family: var(--vp-mono); font-size: 0.78rem; color: var(--vp-faint);
            word-break: break-word; }

/* ---- inputs ---- */
.stTextInput input, .stTextArea textarea, [data-baseweb="select"] > div {
  background: var(--vp-surface-2) !important; color: var(--vp-text) !important;
  border: 1px solid var(--vp-line) !important; border-radius: 9px !important;
  font-size: 1.02rem !important;
}
.stTextInput input:focus, .stTextArea textarea:focus {
  border-color: var(--vp-c5) !important; box-shadow: 0 0 0 2px rgba(134,187,189,0.2) !important; }
[data-testid="stWidgetLabel"] p { color: var(--vp-faint) !important; font-size: 0.86rem; }
[data-testid="stCheckbox"] label p { color: var(--vp-text) !important; font-size: 0.93rem; }
[data-baseweb="checkbox"] div[data-checked="true"] {
  background: var(--vp-c4) !important; border-color: var(--vp-c4) !important; }
[data-baseweb="popover"] li:hover { background: var(--vp-surface-2) !important; }
[data-testid="stFileUploaderDropzone"] { background: var(--vp-surface-2) !important;
  border: 1px dashed var(--vp-line) !important; border-radius: 9px; }
[data-testid="stFileUploaderDropzone"]:hover { border-color: var(--vp-c5) !important; }

/* ---- buttons ---- */
.stButton > button, .stDownloadButton > button {
  background: transparent; color: var(--vp-text); border: 1px solid var(--vp-line);
  border-radius: 9px; font-weight: 520; padding: 0.5rem 1.05rem;
  transition: border-color .15s, background .15s;
}
.stButton > button:hover, .stDownloadButton > button:hover {
  border-color: var(--vp-c5); background: rgba(118,148,159,0.18); color: var(--vp-text); }
.stButton > button:focus-visible, .stDownloadButton > button:focus-visible {
  outline: 2px solid var(--vp-c5); outline-offset: 2px; }
.stButton > button[kind="primary"] {
  background: linear-gradient(100deg, var(--vp-c2), var(--vp-c4)); color: #FFFFFF;
  border: 1px solid rgba(134,187,189,0.5); font-weight: 600; }
.stButton > button[kind="primary"]:hover {
  background: linear-gradient(100deg, var(--vp-c3), var(--vp-c5)); color: #1E161C; }

/* ---- expander / alerts / tables ---- */
[data-testid="stExpander"] { border: 1px solid var(--vp-line-soft) !important;
  border-radius: 10px !important; background: var(--vp-surface); }
[data-testid="stExpander"] summary { color: var(--vp-c5) !important; font-size: 0.9rem; }
[data-testid="stAlert"] { background: var(--vp-surface) !important; color: var(--vp-text) !important;
  border: 1px solid var(--vp-line-soft) !important; border-left: 3px solid var(--vp-c3) !important;
  border-radius: 9px !important; }
[data-testid="stAlert"] p { color: var(--vp-text) !important; }
[data-testid="stAlertContentError"], [data-testid="stNotificationContentError"] {
  border-left-color: var(--vp-c1) !important; }
[data-testid="stAlertContentWarning"], [data-testid="stNotificationContentWarning"] {
  border-left-color: var(--vp-c2) !important; }
[data-testid="stAlertContentSuccess"], [data-testid="stNotificationContentSuccess"] {
  border-left-color: var(--vp-c5) !important; }
[data-testid="stDataFrame"] { border: 1px solid var(--vp-line-soft); border-radius: 10px; }

@media (prefers-reduced-motion: reduce) {
  .stButton > button, .stDownloadButton > button { transition: none; }
}
@media (max-width: 640px) {
  .vp-stage-link { width: 14px; }
  .vp-status { text-align: left; margin-top: 0.4rem; }
}
</style>
"""

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DOC_LABELS: dict[str, str] = {
    DocumentType.W9_TAX_ID.value: "W-9 / Tax ID form",
    DocumentType.CERTIFICATE_OF_INSURANCE.value: "Certificate of Insurance (COI)",
    DocumentType.BUSINESS_LICENSE.value: "Business license / Articles of incorporation",
    DocumentType.CODE_OF_CONDUCT.value: "Signed vendor code of conduct",
    DocumentType.SECURITY_QUESTIONNAIRE.value: "Security questionnaire",
    DocumentType.BANKING_ACH_FORM.value: "Banking / ACH form",
}

# Short right-aligned tag for the document list.
DOC_TAGS: dict[str, str] = {
    DocumentType.W9_TAX_ID.value: "W-9",
    DocumentType.CERTIFICATE_OF_INSURANCE.value: "Insurance",
    DocumentType.BUSINESS_LICENSE.value: "License",
    DocumentType.CODE_OF_CONDUCT.value: "Conduct",
    DocumentType.SECURITY_QUESTIONNAIRE.value: "Security",
    DocumentType.BANKING_ACH_FORM.value: "Banking",
}

# Which documents block submission. This distinction does NOT exist in models.py
# - it is a UI-layer policy so the readiness panel has something to measure.
# Move it into the intake node or a policy module if it should be authoritative.
ALWAYS_REQUIRED_DOCS = (
    DocumentType.W9_TAX_ID.value,
    DocumentType.CERTIFICATE_OF_INSURANCE.value,
)
# Ticking "data-sensitive" adds a third required document, which is what makes
# the callout in the risk card meaningful rather than ornamental.
DATA_SENSITIVE_DOC = DocumentType.SECURITY_QUESTIONNAIRE.value

STAGES = ("Intake", "Plan", "Risk review", "Approval")

CATEGORY_LABELS = {c.value: c.value for c in VendorCategory}

DECISION_ACCENT = {
    "approve": "#86BBBD",
    "approved": "#86BBBD",
    "escalate": "#76949F",
    "review": "#6A6B83",
    "reject": "#533747",
    "rejected": "#533747",
}

SAMPLE_DOCS_DIR = Path(__file__).resolve().parent / "sample_documents"
UPLOAD_DIR = Path(__file__).resolve().parent / "uploads"


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# UI primitives
# ---------------------------------------------------------------------------

def inject_theme() -> None:
    st.markdown(THEME_CSS, unsafe_allow_html=True)


def stage_rail(active: int) -> None:
    """Four-stage wizard rail. ``active`` is a 0-based index into STAGES."""
    parts: list[str] = []
    for i, name in enumerate(STAGES):
        state = "active" if i == active else ("done" if i < active else "todo")
        if i:
            link = "done" if i <= active else "todo"
            parts.append(f'<li class="vp-stage-link" data-state="{link}"></li>')
        parts.append(
            f'<li class="vp-stage" data-state="{state}">'
            f'<span class="vp-stage-num">{i + 1}</span>'
            f"<span>{html.escape(name)}</span></li>"
        )
    st.markdown(f'<ul class="vp-stages">{"".join(parts)}</ul>', unsafe_allow_html=True)


def stage_status(text: str) -> None:
    st.markdown(f'<div class="vp-status">{html.escape(text)}</div>', unsafe_allow_html=True)


def card_title(title: str, sub: str = "") -> None:
    sub_html = f'<div class="vp-card-sub">{html.escape(sub)}</div>' if sub else ""
    st.markdown(
        f'<div class="vp-card-title">{html.escape(title)}</div>{sub_html}',
        unsafe_allow_html=True,
    )


def meter(percent: int) -> None:
    pct = max(0, min(100, int(percent)))
    st.markdown(
        f'<div class="vp-meter-label">Completeness</div>'
        f'<div class="vp-meter-value">{pct}%</div>'
        f'<div class="vp-meter-track"><div class="vp-meter-fill" style="width:{pct}%"></div></div>',
        unsafe_allow_html=True,
    )


def callout(title: str, sub: str) -> None:
    st.markdown(
        f'<div class="vp-callout"><div class="vp-callout-t">{html.escape(title)}</div>'
        f'<div class="vp-callout-s">{html.escape(sub)}</div></div>',
        unsafe_allow_html=True,
    )


def body_text(text: str) -> None:
    st.markdown(f'<div class="vp-body">{html.escape(str(text))}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Readiness
# ---------------------------------------------------------------------------

def required_docs(data_sensitive: bool) -> tuple[str, ...]:
    docs = list(ALWAYS_REQUIRED_DOCS)
    if data_sensitive:
        docs.append(DATA_SENSITIVE_DOC)
    return tuple(docs)


def readiness(
    fields: dict[str, str],
    attached: set[str],
    data_sensitive: bool,
    justification: str,
) -> tuple[int, list[str]]:
    """Percent complete plus the list of things blocking submission.

    Every check is worth the same: text fields that must be non-empty, each
    required document, and the justification when a data-sensitive vendor makes
    it a policy exception.
    """
    checks: list[tuple[bool, str | None]] = [
        (bool(fields["vendor_name"].strip()), "Vendor name empty"),
        (bool(fields["requester_name"].strip()), "Requester name empty"),
        (bool(fields["country"].strip()), "Country empty"),
        (bool(fields["department"].strip()), "Department empty"),
    ]
    for doc_value in required_docs(data_sensitive):
        checks.append((doc_value in attached, f"{DOC_LABELS[doc_value]} missing"))
    if data_sensitive:
        checks.append((bool(justification.strip()), "Justification empty"))

    met = sum(1 for ok, _ in checks if ok)
    percent = round(100 * met / len(checks)) if checks else 100
    blockers = [msg for ok, msg in checks if not ok and msg]
    return percent, blockers


def current_stage(state_values, snap) -> int:
    """Map workflow position onto the four rail stages."""
    intr = current_interrupt(snap)
    if intr and intr.get("type") == "missing_documents":
        return 0
    if intr and intr.get("type") == "human_approval":
        return 3
    if workflow_complete(snap):
        return 3
    if state_values.get("reviewer_verdict") is not None:
        return 2
    if state_values.get("planner_recommendation") is not None:
        return 2
    return 1


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------

def render_trace(state_values) -> None:
    trace = state_values.get("workflow_trace") or []
    if not trace:
        return
    steps = " / ".join(str(s) for s in trace)
    st.markdown(f'<div class="vp-trace">{html.escape(steps)}</div>', unsafe_allow_html=True)


def render_planner_and_verdict(state_values) -> None:
    rec = state_values.get("planner_recommendation")
    if rec is not None:
        path = rec.recommended_path if hasattr(rec, "recommended_path") else rec.get("recommended_path")
        reasoning = rec.reasoning if hasattr(rec, "reasoning") else rec.get("reasoning", "")
        with st.container(border=True):
            card_title("Planner recommendation", f"Path: {path}")
            if reasoning:
                body_text(reasoning)

    verdict = state_values.get("reviewer_verdict")
    if verdict is None:
        return
    decision = verdict.decision if hasattr(verdict, "decision") else verdict.get("decision")
    feedback = verdict.feedback if hasattr(verdict, "feedback") else verdict.get("feedback", "")
    risk_score = verdict.risk_score if hasattr(verdict, "risk_score") else verdict.get("risk_score")

    decision_text = getattr(decision, "value", decision)
    accent = DECISION_ACCENT.get(str(decision_text).lower(), RAMP[2])
    score_html = (
        f'<span class="vp-score">risk {risk_score:.0f}</span>'
        if isinstance(risk_score, (int, float))
        else ""
    )
    with st.container(border=True):
        card_title("Risk and compliance verdict")
        st.markdown(
            f'<div class="vp-verdict" style="--vp-accent:{accent}">'
            f'<span class="vp-decision">{html.escape(str(decision_text))}</span>'
            f"{score_html}</div>",
            unsafe_allow_html=True,
        )
        if feedback:
            body_text(feedback)

        breakdown = state_values.get("risk_score_breakdown") or []
        if breakdown:
            st.markdown('<div class="vp-panel-rule"></div>', unsafe_allow_html=True)
            st.markdown('<div class="vp-panel-head">Score breakdown</div>', unsafe_allow_html=True)
            rows = []
            for item in breakdown:
                label = item.label if hasattr(item, "label") else item.get("label")
                points = item.points if hasattr(item, "points") else item.get("points")
                rows.append(
                    '<div class="vp-doc"><span class="vp-doc-dot"></span>'
                    f'<span class="vp-doc-name">{html.escape(str(label))}</span>'
                    f'<span class="vp-doc-tag">+{points}</span></div>'
                )
            st.markdown("".join(rows), unsafe_allow_html=True)


def render_summary(state_values) -> None:
    summary = state_values.get("final_summary")
    if summary:
        with st.container(border=True):
            card_title("Summary")
            body_text(summary)


def render_llm_error(state_values) -> None:
    error = state_values.get("llm_error")
    if error:
        st.error(f"The LLM provider call failed, so this run used template text instead. {error}")


def render_content_safety_warning(state_values) -> None:
    """Guardrail banner: unsafe content or a disclosed security incident in free text."""
    if state_values.get("unsafe_content_detected"):
        reason = state_values.get("unsafe_content_reason") or "no reason recorded"
        st.error(f"Guardrail: unsafe content detected in this request's text ({reason}). This forces human review.")
    if state_values.get("security_incident_disclosed"):
        reason = state_values.get("security_incident_reason") or "no reason recorded"
        st.warning(f"Guardrail: this request's text discloses a possible security incident ({reason}).")


def render_outcome(state_values) -> None:
    render_planner_and_verdict(state_values)
    if state_values.get("final_status"):
        status = state_values["final_status"]
        label = status.value if hasattr(status, "value") else status
        with st.container(border=True):
            card_title("Recorded status")
            st.markdown(
                f'<div class="vp-final-status">{html.escape(str(label))}</div>',
                unsafe_allow_html=True,
            )
    render_summary(state_values)


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

def render_sample_downloads() -> None:
    """Download buttons for a valid example of each document type.

    Rendered outside any ``st.form`` - Streamlit forbids ``download_button``
    inside a form, and this is shared by the intake screen and the resubmit
    screen.
    """
    with st.expander("Download a valid sample per document type"):
        for doc_value, label in DOC_LABELS.items():
            sample_path = SAMPLE_DOCS_DIR / f"{doc_value}_valid_example.pdf"
            if sample_path.exists():
                st.download_button(
                    label,
                    data=sample_path.read_bytes(),
                    file_name=sample_path.name,
                    key=f"sample_{doc_value}",
                )


def _sample_document_defaults() -> list[SubmittedDocument]:
    """Pre-attach the bundled valid sample PDF for every type."""
    docs = []
    for doc_value in DOC_LABELS:
        sample_path = SAMPLE_DOCS_DIR / f"{doc_value}_valid_example.pdf"
        if sample_path.exists():
            docs.append(SubmittedDocument(type=DocumentType(doc_value), reference=str(sample_path)))
    return docs


def document_widgets(prefix: str, defaults: list | None = None) -> list[SubmittedDocument]:
    """Checkboxes + real file uploads for the six document types.

    Each type expects a PDF with labeled fields (see ``document_validation.py``);
    the intake node rejects a submitted file that doesn't match it. ``defaults``
    pre-attaches a reference (e.g. the bundled sample, or a prior submission) per
    type; uploading a file always overrides it.
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
            "Upload file (.pdf) - replaces the attached file below",
            type=["pdf"],
            key=f"{prefix}_file_{doc_value}",
        )
        if uploaded is not None:
            UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            dest = UPLOAD_DIR / f"{prefix}_{doc_value}_{uuid.uuid4().hex[:8]}.pdf"
            dest.write_bytes(uploaded.getvalue())
            reference = str(dest)
            st.caption(f"Attached: {uploaded.name} (just uploaded)")
        else:
            reference = existing.get(doc_value, "")
            if reference:
                st.caption(f"Attached: {Path(reference).name} - upload a file above to replace it.")
            else:
                st.caption("No file uploaded yet - this document will be treated as missing.")
        if reference:
            docs.append(
                SubmittedDocument(
                    type=DocumentType(doc_value),
                    reference=reference,
                    submitted_at=datetime.now(),
                )
            )
    return docs


def document_list(docs: list[SubmittedDocument], data_sensitive: bool) -> None:
    """Read-only status list: attached files first, then required gaps."""
    attached = {d.type.value: d.reference for d in docs}
    needed = required_docs(data_sensitive)
    met = sum(1 for d in needed if d in attached)

    card_title("Attached documents", f"{met} of {len(needed)} required")
    rows: list[str] = []
    for doc_value in DOC_LABELS:
        reference = attached.get(doc_value)
        if reference:
            name = Path(reference).name
            rows.append(
                f'<div class="vp-doc" data-state="ok"><span class="vp-doc-dot"></span>'
                f'<span class="vp-doc-name">{html.escape(name)}</span>'
                f'<span class="vp-doc-tag">{html.escape(DOC_TAGS[doc_value])}</span></div>'
            )
        elif doc_value in needed:
            rows.append(
                f'<div class="vp-doc" data-state="missing"><span class="vp-doc-dot"></span>'
                f'<span class="vp-doc-name">{html.escape(DOC_LABELS[doc_value])}</span>'
                f'<span class="vp-doc-tag">Missing</span></div>'
            )
    if not rows:
        st.markdown('<div class="vp-empty">Nothing attached yet.</div>', unsafe_allow_html=True)
        return
    st.markdown("".join(rows), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Screens
# ---------------------------------------------------------------------------

def new_request_form() -> None:
    stage_rail(0)
    stage_status("Draft - not submitted")

    # Every widget below is keyed with this generation number. "Start a new
    # request" bumps it (see the entrypoint), which gives every widget a key
    # it has never used before - the only reliable way to reset a
    # file_uploader, and it resets the text/checkbox fields the same way a
    # true first launch would, instead of Streamlit replaying whatever was
    # last typed/checked/uploaded from the previous request.
    gen = st.session_state.get("form_generation", 0)
    prefix = f"new_{gen}"

    left, right = st.columns([2.1, 1], gap="medium")
    panel = right.container()

    # Not wrapped in st.form: the document checkboxes need to immediately reveal
    # a file uploader when checked, but forms only rerun the script on submit,
    # so a checkbox's live state never reaches the code below it until it's too
    # late to react. Plain widgets rerun on every interaction.
    with left:
        with st.container(border=True):
            card_title("Who and what")
            c1, c2 = st.columns(2)
            vendor_name = c1.text_input(
                "Vendor name", value="Staple Supply Co.", key=f"{prefix}_vendor_name"
            )
            requester_name = c2.text_input(
                "Requester name", value="Alice Johnson", key=f"{prefix}_requester_name"
            )
            category = c1.selectbox(
                "Category", list(CATEGORY_LABELS), key=f"{prefix}_category"
            )
            department = c2.text_input(
                "Department", value="Operations", key=f"{prefix}_department"
            )

        with st.container(border=True):
            card_title("Risk profile")
            c3, c4 = st.columns(2)
            country = c3.text_input(
                "Country of operation", value="US", key=f"{prefix}_country"
            )
            relationship = c4.selectbox(
                "Relationship",
                [r.value for r in RelationshipStatus],
                key=f"{prefix}_relationship",
            )
            data_sensitive = st.checkbox(
                "Touches company or customer data, or IT systems",
                key=f"{prefix}_data_sensitive",
            )
            if data_sensitive:
                callout(
                    "Touches company or customer data",
                    "Adds a security review step, and makes the security questionnaire "
                    "and a written justification required.",
                )
            business_justification = st.text_area(
                "Business justification (for policy exceptions)",
                value="",
                height=90,
                key=f"{prefix}_business_justification",
            )

        with st.container(border=True):
            doc_slot = st.container()
            st.markdown('<div class="vp-panel-rule"></div>', unsafe_allow_html=True)
            with st.expander("Add or replace documents"):
                use_samples_key = f"{prefix}_use_samples"
                if st.button("Attach the bundled sample set"):
                    for doc_value in DOC_LABELS:
                        st.session_state[f"{prefix}_has_{doc_value}"] = True
                    st.session_state[use_samples_key] = True
                    st.rerun()
                render_sample_downloads()
                defaults = (
                    _sample_document_defaults()
                    if st.session_state.get(use_samples_key)
                    else None
                )
                submitted = document_widgets(prefix, defaults=defaults)
            # Rendered into a slot above the expander so the status list reads
            # first, even though the widgets that produce it run afterwards.
            with doc_slot:
                document_list(submitted, data_sensitive)

    fields = {
        "vendor_name": vendor_name,
        "requester_name": requester_name,
        "country": country,
        "department": department,
    }
    attached = {d.type.value for d in submitted}
    percent, blockers = readiness(fields, attached, data_sensitive, business_justification)

    with panel:
        with st.container(border=True):
            meter(percent)
            st.markdown('<div class="vp-panel-rule"></div>', unsafe_allow_html=True)
            if blockers:
                st.markdown('<div class="vp-panel-head">Blocking</div>', unsafe_allow_html=True)
                st.markdown(
                    "".join(f'<div class="vp-block">{html.escape(b)}</div>' for b in blockers),
                    unsafe_allow_html=True,
                )
            else:
                st.markdown('<div class="vp-panel-head">Blocking</div>', unsafe_allow_html=True)
                st.markdown(
                    '<div class="vp-clear">Nothing outstanding.</div>', unsafe_allow_html=True
                )
            st.write("")
            # Deliberately not disabled when blockers exist: the intake node runs
            # its own validation and interrupts, and that path needs to stay
            # reachable for testing. The label carries the warning instead.
            label = "Submit anyway" if blockers else "Submit for review"
            go = st.button(label, type="primary", use_container_width=True)
            if blockers:
                st.caption("Intake will pause and ask for the missing items.")

    if go:
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

    left, right = st.columns([2.1, 1], gap="medium")

    with right:
        with st.container(border=True):
            st.markdown('<div class="vp-panel-head">Blocking</div>', unsafe_allow_html=True)
            rows = [f'<div class="vp-block">{html.escape(DOC_LABELS.get(m, m))} missing</div>'
                    for m in missing]
            rows += [
                f'<div class="vp-block">{html.escape(DOC_LABELS.get(k, k))} rejected</div>'
                for k in invalid
            ]
            st.markdown("".join(rows) or '<div class="vp-clear">Nothing outstanding.</div>',
                        unsafe_allow_html=True)

    with left:
        st.error("Intake paused. The requester needs to supply documents before planning starts.")
        if invalid:
            with st.container(border=True):
                card_title("Format problems", "These files were read but rejected.")
                for doc_value, errors in invalid.items():
                    st.markdown(
                        f'<div class="vp-doc" data-state="missing"><span class="vp-doc-dot"></span>'
                        f'<span class="vp-doc-name">{html.escape(DOC_LABELS.get(doc_value, doc_value))}'
                        f"</span></div>"
                        f'<div class="vp-body">{html.escape("; ".join(errors))}</div>',
                        unsafe_allow_html=True,
                    )
        with st.container(border=True):
            card_title("Provide the missing files", "Add what is missing and re-upload anything rejected.")
            render_sample_downloads()
            submitted_now = document_widgets(
                "resume", defaults=state_values.get("submitted_documents", [])
            )
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
    left, right = st.columns([2.1, 1], gap="medium")

    with left:
        st.warning("Escalated to human review. Final approval needs a sign-off.")
        render_planner_and_verdict(state_values)
        render_summary(state_values)

    with right:
        with st.container(border=True):
            card_title("Decision needed")
            body_text(intr.get("question", "Approve or reject this vendor."))
            st.write("")
            if st.button("Approve", type="primary", use_container_width=True):
                _resume_flow("approve")
            if st.button("Reject", use_container_width=True):
                _resume_flow("reject")


def _resume_flow(value: str) -> None:
    app = st.session_state["app"]
    thread_id = st.session_state["thread_id"]
    out, new_snap = resume(app, config_for(thread_id), value)
    st.session_state["out"], st.session_state["snap"] = out, new_snap
    st.rerun()


def show_pending_approvals() -> None:
    st.markdown('<div class="vp-panel-rule"></div>', unsafe_allow_html=True)
    st.markdown("## Approval requests")
    with db.connection() as conn:
        rows = conn.execute(
            "SELECT id, request_id, vendor_name, status, decided_by, decision_notes, created_at"
            " FROM approval_requests ORDER BY id DESC LIMIT 10"
        ).fetchall()
        rows = [dict(r) for r in rows]
    if rows:
        st.dataframe(rows, use_container_width=True)
    else:
        st.markdown('<div class="vp-empty">Nothing waiting on a human yet.</div>',
                    unsafe_allow_html=True)


def show_status_log() -> None:
    st.markdown('<div class="vp-panel-rule"></div>', unsafe_allow_html=True)
    st.markdown("## Vendor status log")
    with db.connection() as conn:
        rows = conn.execute(
            "SELECT id, request_id, vendor_name, final_status, notes, written_at"
            " FROM vendor_status_log ORDER BY id DESC LIMIT 10"
        ).fetchall()
        rows = [dict(r) for r in rows]
    if rows:
        st.dataframe(rows, use_container_width=True)
    else:
        st.markdown('<div class="vp-empty">No decisions have been written yet.</div>',
                    unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(page_title="Vendor Onboarding & Risk Review", layout="wide")
    inject_theme()
    ensure_environment()

    if "active" not in st.session_state:
        new_request_form()
        show_pending_approvals()
        show_status_log()
        return

    request: VendorRequest = st.session_state["active"]["request"]

    if "snap" not in st.session_state:
        thread_id = uuid.uuid4().hex[:12]
        st.session_state["thread_id"] = thread_id
        app = st.session_state["app"]
        out, snap = first_step(app, config_for(thread_id), request)
        st.session_state["out"], st.session_state["snap"] = out, snap
        st.rerun()

    out, snap = st.session_state["out"], st.session_state["snap"]
    state_values = out if isinstance(out, dict) else out

    stage_rail(current_stage(state_values, snap))
    stage_status(f"{request.vendor_name} - {request.vendor_category.value} - {request.country}")
    render_llm_error(state_values)
    render_content_safety_warning(state_values)

    intr = current_interrupt(snap)
    if intr:
        if intr["type"] == "missing_documents":
            handle_missing_documents(state_values, snap)
        elif intr["type"] == "human_approval":
            handle_human_gate(state_values, snap)
    elif workflow_complete(snap):
        left, right = st.columns([2.1, 1], gap="medium")
        with left:
            render_outcome(state_values)
        with right:
            if st.button("Start a new request", use_container_width=True):
                for key in ("active", "snap", "out", "thread_id"):
                    st.session_state.pop(key, None)
                # Bump the form generation so every widget on the next
                # new_request_form() render gets a key it has never used
                # before, instead of Streamlit replaying the previous
                # request's typed/checked/uploaded values.
                st.session_state["form_generation"] = st.session_state.get("form_generation", 0) + 1
                st.rerun()
    else:
        st.info("Running the next step.")

    render_trace(state_values)
    show_pending_approvals()
    show_status_log()


if __name__ == "__main__":
    main()