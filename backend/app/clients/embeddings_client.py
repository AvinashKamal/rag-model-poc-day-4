import threading

import httpx

from app.config import settings

# 60s: CPU-bound TEI batch inference (up to 100 papers in ingestion/pipeline.py)
# is far slower than a typical API call and can exceed httpx's 5s default.
_EMBED_TIMEOUT = 60

_client: httpx.Client | None = None
_client_lock = threading.Lock()


def _get_client() -> httpx.Client:
    """Shared httpx.Client so repeated /embed calls reuse one connection pool
    instead of opening a fresh TCP connection per call (previously a
    module-level `httpx.post(...)` did exactly that every time).
    """
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = httpx.Client(
                    base_url=settings.EMBEDDINGS_URL, timeout=_EMBED_TIMEOUT
                )
    return _client


def embed(texts: list[str]) -> list[list[float]]:
    """Dense embeddings via TEI's /embed endpoint (bge-m3 dense branch).

    Raises httpx.HTTPError (connection/timeout, or a non-2xx response) on
    failure — callers (app/retrieval/query.py) catch this and translate it
    into an `UpstreamServiceError("embeddings", ...)`.
    """
    response = _get_client().post("/embed", json={"inputs": texts})
    response.raise_for_status()
    return response.json()
