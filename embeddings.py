"""Local embedding model for the RAG vector store.

Deliberately dependency-free: a deterministic hashed bag-of-words embedder.
No model download, no network, identical vectors across processes and runs,
so tests are hermetic and the demo works offline. Vectors are stored in
Chroma at ingestion time, so retrieval and ingestion always agree.

This is the "lightweight embedding model" trade-off noted in the README:
semantic embeddings (e.g. sentence-transformers) can be swapped in here
without touching any other module.
"""

from __future__ import annotations

import hashlib
import math
import re

DIM = 384


def _tokens(text: str) -> list[str]:
    """Lower-case word tokens, with a couple of stop words dropped."""
    stop = {"the", "a", "an", "and", "or", "of", "to", "for", "in", "on", "is", "are", "be"}
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in stop]


def _hash_position(token: str, salt: str) -> int:
    digest = hashlib.sha256(f"{salt}:{token}".encode()).hexdigest()
    return int(digest[:8], 16)


def embed(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts into fixed-dimension normalized vectors."""
    vectors: list[list[float]] = []
    for text in texts:
        vec = [0.0] * DIM
        for token in _tokens(text):
            pos = _hash_position(token, "pos") % DIM
            sign = 1.0 if (_hash_position(token, "sign") % 2) else -1.0
            vec[pos] += sign
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        vectors.append([v / norm for v in vec])
    return vectors


def embed_query(text: str) -> list[float]:
    return embed([text])[0]
