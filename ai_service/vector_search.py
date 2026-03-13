"""Vector similarity search against qcaa_vectors via Supabase RPC."""

import logging

import requests
from sentence_transformers import SentenceTransformer

from config import (
    EMBEDDING_MODEL_NAME,
    SUPABASE_SERVICE_KEY,
    SUPABASE_URL,
    VECTOR_MATCH_COUNT,
    VECTOR_MATCH_THRESHOLD,
)

log = logging.getLogger(__name__)

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        log.info("Loading embedding model '%s' …", EMBEDDING_MODEL_NAME)
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _model


def build_multi_section_query(text: str) -> str:
    """Extract intro, middle, and conclusion segments for a richer RAG query (#8).

    The first 500 chars often only contain introduction boilerplate.
    Sampling from three sections captures a wider range of topics.
    """
    text = text.strip()
    if len(text) <= 1200:
        return text

    intro = text[:400]
    mid_start = len(text) // 2
    middle = text[mid_start : mid_start + 400]
    end = text[-400:]

    return intro + "\n" + middle + "\n" + end


def search(
    query_text: str,
    subject: str | None = None,
    top_k: int = VECTOR_MATCH_COUNT,
    threshold: float = VECTOR_MATCH_THRESHOLD,
) -> list[dict]:
    """Embed query_text locally, then call match_qcaa_vectors RPC.

    Returns list of {id, subject, section, content, metadata, similarity},
    sorted by similarity descending (#9).
    """
    model = _get_model()
    embedding = model.encode(query_text).tolist()

    payload = {
        "query_embedding": embedding,
        "match_threshold": threshold,
        "match_count": top_k,
        "filter_subject": subject,
    }

    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/rpc/match_qcaa_vectors",
        headers={
            "apikey": SUPABASE_SERVICE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )

    if resp.status_code != 200:
        log.error("Vector search failed (%d): %s", resp.status_code, resp.text[:300])
        return []

    results = resp.json()

    # Stabilise retrieval order: sort by similarity descending (#9)
    results = sorted(results, key=lambda x: x.get("similarity", 0), reverse=True)

    log.info(
        "Vector search: %d results for '%s…' (subject=%s)",
        len(results),
        query_text[:60],
        subject or "any",
    )
    return results
