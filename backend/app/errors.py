"""Upstream-service error type for the /query pipeline.

`retrieval/query.py` wraps each external call (TEI embeddings, Qdrant,
TEI reranker, OpenRouter LLM) in a narrow try/except around that library's
own exception types and re-raises `UpstreamServiceError` tagged with which
stage failed. `main.py`'s /query route is the single place that turns this
into an HTTP response, so every upstream outage gets the same clean
502 + "which upstream failed" shape instead of an unhandled 500.
"""

from __future__ import annotations

import httpx
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

# Exception types a Qdrant call can raise on a connection failure, a
# timeout, or a non-2xx response — shared by app/retrieval/query.py (query
# path) and app/main.py (health_ready) so both narrow their except clauses
# to the same specific set instead of a blind `except Exception`.
QDRANT_ERRORS = (UnexpectedResponse, ResponseHandlingException, httpx.HTTPError)


class UpstreamServiceError(RuntimeError):
    """Raised when a downstream service the /query pipeline depends on
    (embeddings, qdrant, reranker, llm) fails or times out.

    `service` is a short machine-readable tag (one of "embeddings", "qdrant",
    "reranker", "llm") — safe to return to API callers. The original
    exception is chained via `raise ... from exc` for server-side logs/traces
    only; its string form is deliberately not echoed back in the HTTP
    response body (it can contain upstream response bodies we don't control).
    """

    def __init__(self, service: str, message: str = ""):
        self.service = service
        super().__init__(message or f"upstream service '{service}' failed")
