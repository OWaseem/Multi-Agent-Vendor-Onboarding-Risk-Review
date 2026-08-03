"""Local embedding model for the RAG vector store.

Uses ``sentence-transformers`` (default model ``all-MiniLM-L6-v2``, 384 dims)
so retrieval is based on real semantic similarity rather than token overlap.
The model runs locally (no API key/network needed after the first download,
which pulls the model from the Hugging Face Hub). Vectors are stored in
Chroma at ingestion time, so retrieval and ingestion always agree.

Override the model via the ``SENTENCE_TRANSFORMER_MODEL`` env var.
"""

from __future__ import annotations

import os
from functools import lru_cache

DEFAULT_MODEL = "all-MiniLM-L6-v2"
DIM = 384


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(os.getenv("SENTENCE_TRANSFORMER_MODEL", DEFAULT_MODEL))


def embed(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts into fixed-dimension normalized vectors."""
    vectors = _model().encode(texts, normalize_embeddings=True)
    return vectors.tolist()


def embed_query(text: str) -> list[float]:
    return embed([text])[0]
