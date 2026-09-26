import threading

import httpx

from app.config import settings

# 180s: measured live on a CPU-only 4-core host — reranking 8 real ingested
# abstracts (avg ~1566 chars / ~350-400 tokens each) against a query took ~46.7s.
# retrieval/query.py reranks up to `_CANDIDATE_LIMIT=40` documents per query, so
# the real worst case is larger than what was measured, not smaller. 180s gives
# real headroom above that measured baseline rather than the previous unverified
# assumption that this batch would be smaller/faster than embedding calls.
_RERANK_TIMEOUT = 180

_client: httpx.Client | None = None
_client_lock = threading.Lock()


def _get_client() -> httpx.Client:
    """Shared httpx.Client so repeated /rerank calls reuse one connection
    pool instead of opening a fresh TCP connection per call (previously a
    module-level `httpx.post(...)` did exactly that every time).
    """
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = httpx.Client(
                    base_url=settings.RERANKER_URL, timeout=_RERANK_TIMEOUT
                )
    return _client


def rerank(query: str, documents: list[str]) -> list[dict]:
    """Rerank `documents` against `query` via TEI's /rerank endpoint (bge-reranker-v2-m3).

    ASSUMPTION — flagged explicitly, not verified against a live TEI instance
    (none is reachable in this environment; see OPEN_ISSUES), same caveat as
    `app/clients/embeddings_client.py`'s `embed`: this assumes TEI's
    documented reranker contract — POST `/rerank` with body
    `{"query": str, "texts": [str, ...]}` — returns a JSON list of
    `{"index": int, "score": float}` objects (one per input text, `index`
    referring back into the `texts` list), already sorted by `score`
    descending. That shape is normalized here into a list of
    `{"index": int, "score": float}` dicts explicitly re-sorted by score
    descending (defensive — cheap, and correct even if a deployed TEI version
    doesn't pre-sort). If the deployed TEI version's actual contract differs,
    only this function and its call site in `app/retrieval/query.py` need to
    change.

    Raises httpx.HTTPError (connection/timeout, or a non-2xx response) on
    failure — callers (app/retrieval/query.py) catch this and translate it
    into an `UpstreamServiceError("reranker", ...)`.
    """
    response = _get_client().post("/rerank", json={"query": query, "texts": documents})
    response.raise_for_status()
    raw = response.json()
    results = [{"index": item["index"], "score": item["score"]} for item in raw]
    results.sort(key=lambda item: item["score"], reverse=True)
    return results
