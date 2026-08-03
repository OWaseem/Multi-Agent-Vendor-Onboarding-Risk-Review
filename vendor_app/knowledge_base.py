# This class builds our Chroma DB knowledge base
import re
from pathlib import Path

from langchain_chroma import Chroma
from langchain_community.document_loaders import TextLoader
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from vendor_app.config import COLLECTION_NAME, DATA_DIR, EMBEDDING_MODEL_NAME

metadata_by_source = {
    "vendor_onboarding_policy.md": {
        "department": "procurement",
        "document_type": "policy",
        "workflow_stage": "intake",
        "audience": "procurement_team",
    },

    "required_document_checklist.md": {
        "department": "procurement",
        "document_type": "checklist",
        "workflow_stage": "intake",
        "audience": "procurement_team",
    },

    "risk_scoring_policy.md": {
        "department": "compliance",
        "document_type": "policy",
        "workflow_stage": "risk_review",
        "audience": "risk_reviewer",
    },

    "data_security_requirements.md": {
        "department": "information_security",
        "document_type": "policy",
        "workflow_stage": "risk_review",
        "audience": "risk_reviewer",
    },

    "watchlist_and_sanctions_policy.md": {
        "department": "compliance",
        "document_type": "policy",
        "workflow_stage": "risk_review",
        "audience": "risk_reviewer",
    },

    "vendor_lookup_policy.md": {
        "department": "procurement",
        "document_type": "procedure",
        "workflow_stage": "planning",
        "audience": "procurement_team",
    },

    "policy_exception_guidelines.md": {
        "department": "compliance",
        "document_type": "policy",
        "workflow_stage": "human_review",
        "audience": "risk_reviewer",
    },

    "human_review_procedure.md": {
        "department": "compliance",
        "document_type": "procedure",
        "workflow_stage": "human_review",
        "audience": "human_approver",
    },

    "certificate_validation_policy.md": {
        "department": "procurement",
        "document_type": "procedure",
        "workflow_stage": "intake",
        "audience": "procurement_team",
    },

    "workflow_revision_policy.md": {
        "department": "compliance",
        "document_type": "policy",
        "workflow_stage": "review",
        "audience": "risk_reviewer",
    },

    "vendor_categories.md": {
        "department": "procurement",
        "document_type": "reference",
        "workflow_stage": "planning",
        "audience": "procurement_team",
    },

    "approval_matrix.md": {
        "department": "compliance",
        "document_type": "reference",
        "workflow_stage": "approval",
        "audience": "risk_reviewer",
    },

    "vendor_status_definitions.md": {
        "department": "operations",
        "document_type": "reference",
        "workflow_stage": "workflow",
        "audience": "all",
    },

    "vendor_examples.md": {
        "department": "procurement",
        "document_type": "case_study",
        "workflow_stage": "planning",
        "audience": "procurement_team",
    },
}