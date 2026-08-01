"""Policy document ingestion + retrieval against a local Chroma vector store.

Policy docs in ``policy_docs/*.md`` are chunked per ``##`` section and embedded
with the local embedder (``embeddings.py``). Each chunk carries metadata:
``doc_type``, ``vendor_category``, ``risk_tier``, ``section``.

Retrieval applies a metadata filter so Data Security & IT Vendor Requirements
chunks are only included when the vendor is IT/Software or data-sensitive.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import chromadb

import embeddings
from models import PolicyChunk, VendorCategory

PROJECT_ROOT = Path(__file__).resolve().parent
POLICY_DIR = PROJECT_ROOT / "policy_docs"
VECTOR_STORE_PATH = Path(
    os.environ.get("VECTOR_STORE_PATH", PROJECT_ROOT / "data" / "chroma")
)
COLLECTION_NAME = "vendor_policy"
DATA_SECURITY_DOC_TYPE = "data_security_it_requirements"

# Chroma's telemetry can block on first use in sandboxed envs.
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

_SECTION_RE = re.compile(r"^## (.+)$", re.MULTILINE)
_META_RE = re.compile(r"^([a-z_]+):\s*(.+)$")


def _parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    """Return (metadata dict, body) for a document with ``---`` front matter."""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    header, body = parts[1], parts[2]
    meta: dict[str, str] = {}
    for line in header.splitlines():
        m = _META_RE.match(line.strip())
        if m:
            meta[m.group(1)] = m.group(2).strip()
    return meta, body


def _chunk_document(path: Path) -> list[dict]:
    """Split one markdown policy doc into metadata-tagged chunks."""
    meta, body = _parse_front_matter(path.read_text())
    doc_type = meta.get("doc_type", path.stem)
    risk_tier = meta.get("risk_tier", "general")
    default_category = meta.get("default_category", "general")

    matches = list(_SECTION_RE.finditer(body))
    chunks: list[dict] = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        section_body = body[start:end].strip()
        heading = m.group(1).strip()

        category = default_category
        cat_match = re.search(r"^category:\s*(.+)$", section_body, re.MULTILINE)
        if cat_match:
            category = cat_match.group(1).strip()
            section_body = section_body.replace(cat_match.group(0), "", 1)

        chunks.append(
            {
                "id": f"{doc_type}_{i + 1:02d}",
                "doc_type": doc_type,
                "vendor_category": category,
                "risk_tier": risk_tier,
                "section": heading,
                "text": f"## {heading}\n{section_body}".strip(),
            }
        )
    return chunks


def _collect_chunks() -> list[dict]:
    chunks: list[dict] = []
    for path in sorted(POLICY_DIR.glob("*.md")):
        chunks.extend(_chunk_document(path))
    return chunks


def build_vector_store(force: bool = False) -> chromadb.Collection:
    """Ingest policy docs into Chroma (idempotent unless ``force``)."""
    client = chromadb.PersistentClient(path=str(VECTOR_STORE_PATH))
    collection = client.get_or_create_collection(
        COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
    )
    chunks = _collect_chunks()
    existing = collection.count()
    if existing == 0 or force:
        if force:
            client.delete_collection(COLLECTION_NAME)
            collection = client.create_collection(
                COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
            )
        vectors = embeddings.embed([c["text"] for c in chunks])
        collection.add(
            ids=[c["id"] for c in chunks],
            embeddings=vectors,
            metadatas=[
                {
                    "doc_type": c["doc_type"],
                    "vendor_category": c["vendor_category"],
                    "risk_tier": c["risk_tier"],
                    "section": c["section"],
                }
                for c in chunks
            ],
            documents=[c["text"] for c in chunks],
        )
    return collection


def get_collection() -> chromadb.Collection:
    client = chromadb.PersistentClient(path=str(VECTOR_STORE_PATH))
    collection = client.get_or_create_collection(
        COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
    )
    if collection.count() == 0:
        build_vector_store()
    return collection


def _build_filter(category: VendorCategory, data_sensitive: bool) -> dict:
    """Metadata filter: category-aware, and skip data-security chunks for
    low-risk categories. Chroma requires $and/$or to have >= 2 clauses, so a
    single clause is returned unwrapped."""
    clause: list[dict] = [
        {"vendor_category": {"$in": ["general", category.value]}},
    ]
    include_data_security = category.is_high_risk_category or data_sensitive
    if not include_data_security:
        clause.append({"doc_type": {"$ne": DATA_SECURITY_DOC_TYPE}})
    if len(clause) == 1:
        return clause[0]
    return {"$and": clause}


def retrieve(
    query: str,
    category: VendorCategory,
    data_sensitive: bool,
    k: int = 5,
) -> list[PolicyChunk]:
    """Retrieve the most relevant policy chunks for a request context."""
    collection = get_collection()
    results = collection.query(
        query_embeddings=[embeddings.embed_query(query)],
        n_results=k,
        where=_build_filter(category, data_sensitive),
    )
    ids = results["ids"][0]
    docs = results["documents"][0]
    metas = results["metadatas"][0]
    return [
        PolicyChunk(
            chunk_id=iid,
            doc_type=m["doc_type"],
            vendor_category=VendorCategory(m["vendor_category"])
            if m["vendor_category"] in {c.value for c in VendorCategory}
            else None,
            risk_tier=m["risk_tier"],
            section=m["section"],
            text=doc,
        )
        for iid, doc, m in zip(ids, docs, metas)
    ]


def chunk_count() -> int:
    return get_collection().count()
