import re
from pathlib import Path

from langchain_chroma import Chroma
from langchain_community.document_loaders import TextLoader, DirectoryLoader
from langchain_core.documents import BaseDocumentTransformer
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from vendor_app.config import DATA_DIR, COLLECTION_NAME, EMBEDDING_MODEL_NAME

metadata_by_source = {

    "vendor_onboarding_policy.md": {
        "department": "procurement",
        "document_type": "policy",
        "workflow_stage": "intake",
        "vendor_category": "all",
        "risk_level": "all"
    },

    "required_document_checklist.md": {
        "department": "procurement",
        "document_type": "checklist",
        "workflow_stage": "intake",
        "vendor_category": "all",
        "risk_level": "all"
    },

    "risk_scoring_policy.md": {
        "department": "compliance",
        "document_type": "policy",
        "workflow_stage": "review",
        "vendor_category": "all",
        "risk_level": "all"
    },

    "data_security_requirements.md": {
        "department": "information_security",
        "document_type": "policy",
        "workflow_stage": "review",
        "vendor_category": "IT/Software",
        "risk_level": "high"
    },

    "watchlist_and_sanctions_policy.md": {
        "department": "compliance",
        "document_type": "policy",
        "workflow_stage": "review",
        "vendor_category": "all",
        "risk_level": "critical"
    },

    "vendor_lookup_policy.md": {
        "department": "procurement",
        "document_type": "procedure",
        "workflow_stage": "planning",
        "vendor_category": "all",
        "risk_level": "all"
    },

    "policy_exception_guidelines.md": {
        "department": "compliance",
        "document_type": "policy",
        "workflow_stage": "human_review",
        "vendor_category": "all",
        "risk_level": "high"
    },

    "human_review_procedure.md": {
        "department": "compliance",
        "document_type": "procedure",
        "workflow_stage": "human_review",
        "vendor_category": "all",
        "risk_level": "high"
    },

    "certificate_validation_policy.md": {
        "department": "procurement",
        "document_type": "procedure",
        "workflow_stage": "intake",
        "vendor_category": "all",
        "risk_level": "all"
    },

    "workflow_revision_policy.md": {
        "department": "compliance",
        "document_type": "policy",
        "workflow_stage": "review",
        "vendor_category": "all",
        "risk_level": "all"
    },

    "vendor_categories.md": {
        "department": "procurement",
        "document_type": "reference",
        "workflow_stage": "planning",
        "vendor_category": "all",
        "risk_level": "all"
    },

    "approval_matrix.md": {
        "department": "compliance",
        "document_type": "reference",
        "workflow_stage": "approval",
        "vendor_category": "all",
        "risk_level": "all"
    },

    "vendor_status_definitions.md": {
        "department": "operations",
        "document_type": "reference",
        "workflow_stage": "workflow",
        "vendor_category": "all",
        "risk_level": "all"
    },

    "vendor_examples.md": {
        "department": "procurement",
        "document_type": "case_study",
        "workflow_stage": "planning",
        "vendor_category": "mixed",
        "risk_level": "mixed"
    }
}

def load_documents():
    loader = DirectoryLoader(
        "knowledge_base",
        glob="*.md",
        loader_cls=TextLoader
    )

    documents = loader.load()

    for doc in documents:
        filename= doc.metadata["source"]

load_documents()  

