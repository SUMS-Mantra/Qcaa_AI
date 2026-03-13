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


def search(
    query_text: str,
    subject: str | None = None,
    top_k: int = VECTOR_MATCH_COUNT,
    threshold: float = VECTOR_MATCH_THRESHOLD,
) -> list[dict]:
    """Embed query_text locally, then call match_qcaa_vectors RPC.

    Returns list of {id, subject, section, content, metadata, similarity}.
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
    log.info(
        "Vector search: %d results for '%s…' (subject=%s)",
        len(results),
        query_text[:60],
        subject or "any",
    )
    return results
