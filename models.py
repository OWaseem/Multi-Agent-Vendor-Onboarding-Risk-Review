"""Pydantic data models for the vendor onboarding & risk review workflow.

These models define every object that moves through the LangGraph workflow:
the intake submission, the RAG policy chunks, the planner/reviewer outputs, and
the shared workflow state. The mocked persistence layer in ``db.py`` uses the
same vocabulary as ``schema.sql``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class VendorCategory(str, Enum):
    """Business categories a vendor can belong to."""

    IT_SOFTWARE = "IT/Software"
    PROFESSIONAL_SERVICES = "Professional Services"
    LOGISTICS = "Logistics"
    FACILITIES = "Facilities"
    MARKETING = "Marketing"
    OFFICE_SUPPLIES = "Office Supplies"

    @property
    def is_high_risk_category(self) -> bool:
        """IT/Software is treated as an inherently elevated-risk category."""
        return self is VendorCategory.IT_SOFTWARE


class RelationshipStatus(str, Enum):
    """Whether the organization already works with this vendor."""

    NEW = "new"
    EXISTING = "existing"


class DocumentType(str, Enum):
    """Every document a vendor may be asked to submit."""

    W9_TAX_ID = "w9_tax_id"
    CERTIFICATE_OF_INSURANCE = "certificate_of_insurance"
    BUSINESS_LICENSE = "business_license"
    CODE_OF_CONDUCT = "code_of_conduct"
    SECURITY_QUESTIONNAIRE = "security_questionnaire"
    BANKING_ACH_FORM = "banking_ach_form"


class RiskFlag(str, Enum):
    """Each high-risk criterion from the policy (any one trips the flag)."""

    FOREIGN_ENTITY = "foreign_entity"
    NO_COI = "no_coi"
    MISSING_SECURITY_QUESTIONNAIRE = "missing_security_questionnaire"
    ON_WATCHLIST = "on_watchlist"
    NEW_VENDOR_DATA_SENSITIVE = "new_vendor_data_sensitive"

    @property
    def severity(self) -> int:
        """Weight used by risk_score_calculator; higher = more severe."""
        return _RISK_SEVERITY[self]


class RecommendedPath(str, Enum):
    """Onboarding path the planner can draft."""

    STANDARD = "standard"
    HIGH_RISK = "high_risk"
    NEEDS_EXCEPTION = "needs_exception"


class ReviewerDecision(str, Enum):
    """Verdict the risk/compliance reviewer can issue."""

    APPROVED = "approved"
    REVISE = "revise"
    ESCALATE = "escalate"


class ApprovalStatus(str, Enum):
    """Lifecycle of a (mocked) approval request row."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class OnboardingStatus(str, Enum):
    """Final statuses written by the (mocked) update_vendor_status tool."""

    IN_PROGRESS = "in_progress"
    STANDARD_ONBOARDING = "standard_onboarding"
    APPROVED = "approved"
    ESCALATED = "escalated_to_human_review"
    REJECTED = "rejected"
    PAUSED_MISSING_INFO = "paused_missing_information"


class HumanDecision(str, Enum):
    """How the human approver resolved an escalated case."""

    APPROVE = "approve"
    REJECT = "reject"


# ---------------------------------------------------------------------------
# Document requirements
# ---------------------------------------------------------------------------

#: Base set of documents required for every vendor, regardless of category.
BASE_REQUIRED_DOCUMENTS: set[DocumentType] = {
    DocumentType.W9_TAX_ID,
    DocumentType.CERTIFICATE_OF_INSURANCE,
    DocumentType.BUSINESS_LICENSE,
    DocumentType.CODE_OF_CONDUCT,
}

#: Banking/ACH form is required only before final "approved" status; it is NOT
#: a blocker for the onboarding review itself, so the intake agent ignores it.
BANKING_ACH_FORM_REQUIRED_FOR_APPROVAL = DocumentType.BANKING_ACH_FORM


def required_document_types(category: VendorCategory, data_sensitive: bool) -> set[DocumentType]:
    """Return the full set of documents the intake agent requires for review.

    Base set for all vendors, plus the security questionnaire when the vendor
    is IT/Software or touches sensitive data. The banking/ACH form is excluded
    here on purpose (see ``BANKING_ACH_FORM_REQUIRED_FOR_APPROVAL``).
    """
    docs = set(BASE_REQUIRED_DOCUMENTS)
    if category.is_high_risk_category or data_sensitive:
        docs.add(DocumentType.SECURITY_QUESTIONNAIRE)
    return docs


# ---------------------------------------------------------------------------
# Risk scoring design (used by the risk_score_calculator tool)
# ---------------------------------------------------------------------------

#: Weight per RiskFlag; higher = more severe. A single on_watchlist hit
#: (45) exceeds the escalation threshold on its own.
_RISK_SEVERITY: dict[RiskFlag, int] = {
    RiskFlag.ON_WATCHLIST: 45,
    RiskFlag.MISSING_SECURITY_QUESTIONNAIRE: 20,
    RiskFlag.FOREIGN_ENTITY: 15,
    RiskFlag.NO_COI: 15,
    RiskFlag.NEW_VENDOR_DATA_SENSITIVE: 10,
}

#: Inherent risk added for IT/Software vendors (elevated category).
INHERENT_IT_CATEGORY_RISK = 20
#: Inherent risk added when the vendor touches company/customer data.
INHERENT_DATA_SENSITIVE_RISK = 15

#: Below this score the reviewer may approve a standard path; at/above this
#: score the reviewer escalates to human review.
ESCALATION_THRESHOLD = 30.0


def risk_score_for(
    risk_flags: set[RiskFlag] | list[RiskFlag],
    vendor_category: VendorCategory,
    data_sensitive: bool,
) -> float:
    """Weighted risk score used to tier the recommendation.

    ``sum(flag severities) + inherent category/sensitivity risk``. A lone
    foreign_entity flag scores 15 (standard); adding missing security
    questionnaire or data sensitivity crosses the 30 escalation threshold.
    """
    score = sum(RiskFlag(f).severity for f in risk_flags)
    if vendor_category.is_high_risk_category:
        score += INHERENT_IT_CATEGORY_RISK
    if data_sensitive:
        score += INHERENT_DATA_SENSITIVE_RISK
    return float(score)


# ---------------------------------------------------------------------------
# Core models
# ---------------------------------------------------------------------------


class SubmittedDocument(BaseModel):
    """One document the requester attached to the vendor request."""

    type: DocumentType                       # which required/optional doc this is
    reference: str                           # filename or reference id of the upload
    submitted_at: datetime = Field(default_factory=_now)  # when it was attached


class VendorRequest(BaseModel):
    """The intake submission captured from the Streamlit form."""

    vendor_name: str = Field(..., min_length=1, description="Legal/trade name of the vendor")
    vendor_category: VendorCategory          # drives document + policy requirements
    country: str                             # country of operation (non-US trips foreign_entity)
    data_sensitive: bool = False             # touches company/customer data or IT systems?
    relationship_status: RelationshipStatus  # new vs. existing/prior relationship
    requester_name: str                      # employee submitting the request
    requester_department: str                # department of the requester
    business_justification: Optional[str] = None  # credible rationale for a policy exception
    submitted_documents: list[SubmittedDocument] = Field(default_factory=list)


class PolicyChunk(BaseModel):
    """A single retrieved chunk from the RAG policy vector store."""

    chunk_id: str                                    # unique id, e.g. "wp_03"
    doc_type: str                                    # source policy document name
    vendor_category: Optional[VendorCategory] = None  # category this clause applies to
    risk_tier: Optional[str] = None                  # "high" | "medium" | "low" | "general"
    section: str                                     # section/clause heading
    text: str                                        # the chunk text


class PlannerRecommendation(BaseModel):
    """The onboarding planner's draft recommendation."""

    recommended_path: RecommendedPath                # standard / high_risk / needs_exception
    reasoning: str                                   # human-readable justification
    cited_policy_chunks: list[str] = Field(default_factory=list)  # chunk_ids cited


class ReviewerVerdict(BaseModel):
    """The risk/compliance reviewer's verdict on the planner's draft."""

    decision: ReviewerDecision                       # approved / revise / escalate
    feedback: str                                    # guidance to planner on "revise"
    risk_score: float                                # final weighted risk score (0-100)


class ApprovalRecord(BaseModel):
    """A (mocked) approval request row persisted in ``approval_requests``."""

    request_id: str                                  # the workflow request this belongs to
    vendor_name: str                                 # vendor under review
    created_at: datetime = Field(default_factory=_now)
    status: ApprovalStatus = ApprovalStatus.PENDING  # pending until someone decides
    decided_by: Optional[str] = None                 # "auto" or "human"
    decision_notes: Optional[str] = None             # free-text notes from the decision


# ---------------------------------------------------------------------------
# Workflow state (LangGraph)
# ---------------------------------------------------------------------------


class WorkflowState(BaseModel):
    """Full LangGraph shared state; the README draft expanded into typed fields.

    ``extra="allow"`` lets LangGraph attach its internal channels (e.g. the
    interrupt mechanism) without triggering pydantic validation errors.
    """

    model_config = ConfigDict(extra="allow")

    # --- identity ---
    request_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])

    # --- intake ---
    vendor_name: str = ""
    vendor_category: Optional[VendorCategory] = None
    country: str = ""
    data_sensitive: bool = False
    vendor_history: Optional[RelationshipStatus] = None  # what the requester claimed
    requester_name: str = ""
    requester_department: str = ""
    business_justification: Optional[str] = None
    submitted_documents: list[SubmittedDocument] = Field(default_factory=list)
    missing_documents: list[DocumentType] = Field(default_factory=list)

    # --- risk & retrieval ---
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    risk_score: float = 0.0
    vendor_record: Optional[dict] = None  # result of the vendor_lookup tool
    retrieved_policy_chunks: list[PolicyChunk] = Field(default_factory=list)

    # --- planner & reviewer ---
    planner_recommendation: Optional[PlannerRecommendation] = None
    reviewer_verdict: Optional[ReviewerVerdict] = None
    revision_count: int = 0

    # --- human gate & outcome ---
    requires_human_review: bool = False
    human_decision: Optional[HumanDecision] = None
    final_status: Optional[OnboardingStatus] = None
    pending_approval_id: Optional[int] = None  # row id in approval_requests

    # --- observability ---
    workflow_trace: list[str] = Field(default_factory=list)  # ordered node visits
