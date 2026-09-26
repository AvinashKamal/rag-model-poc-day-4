import threading

from qdrant_client import QdrantClient
from qdrant_client import models as qmodels
from qdrant_client.http.exceptions import UnexpectedResponse

from app.config import settings

# One collection for all domains — domain is a payload field (see
# .claude/settings.json's qdrant MCP entry, which hardcodes this same name).
COLLECTION_NAME = "literature"

DENSE_VECTOR_NAME = "dense"
# BAAI/bge-m3's dense output dimensionality.
DENSE_VECTOR_SIZE = 1024

# 30s: Qdrant is on the local docker network, not a CPU-bound TEI batch call,
# so this doesn't need TEI's 60-180s headroom. But it does need to comfortably
# cover the largest single request the app makes against it: an ingestion
# upsert of up to 100 points (max_results cap in schemas.IngestRequest), each
# carrying a 1024-dim dense vector plus payload text. 30s is well above what
# that should ever take on a healthy local Qdrant, while still failing fast
# (as an UpstreamServiceError, see errors.py) on a genuinely stuck/down
# instance instead of hanging on the client library's own unset-timeout
# default.
_QDRANT_TIMEOUT_S = 30

_client: QdrantClient | None = None
_client_lock = threading.Lock()


def get_qdrant_client() -> QdrantClient:
    """Process-wide singleton QdrantClient so repeated calls reuse one
    connection pool instead of opening a fresh client (and its underlying
    HTTP connection) on every request. Lazily created, guarded by a lock so
    concurrent first-callers (e.g. two in-flight requests at app startup)
    can't race into constructing two separate clients.
    """
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = QdrantClient(
                    url=settings.QDRANT_URL, timeout=_QDRANT_TIMEOUT_S
                )
    return _client


def ensure_literature_collection(client: QdrantClient | None = None) -> None:
    """Idempotently ensure the shared `literature` collection exists with a
    named dense vector for bge-m3 dense-only search. Only creates the
    collection if it's missing; never recreates or alters an existing one.

    Race-safe: two concurrent first-ever-ingestion calls can both observe
    "collection missing" from `get_collections()` before either creates it.
    Rather than relying on the check-then-create sequence being atomic (it
    isn't), the create call itself is allowed to fail with "already exists"
    and that specific failure is swallowed — the collection existing is the
    only postcondition this function promises, not "this call created it".

    Dense-only for now: TEI does not expose true sparse (SPLADE-pooling)
    output for bge-m3, so RRF hybrid fusion is deferred until/unless eval
    shows dense-only recall is insufficient (see project CLAUDE.md).
    """
    client = client or get_qdrant_client()
    existing = {c.name for c in client.get_collections().collections}
    if COLLECTION_NAME in existing:
        return
    try:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config={
                DENSE_VECTOR_NAME: qmodels.VectorParams(
                    size=DENSE_VECTOR_SIZE,
                    distance=qmodels.Distance.COSINE,
                ),
            },
        )
    except UnexpectedResponse as exc:
        # Qdrant returns 409 Conflict for "collection already exists". That's
        # exactly the race this function is meant to survive; any other
        # status is a real failure and must still propagate as an
        # UnexpectedResponse for the caller (ingestion/pipeline.py) to see.
        if exc.status_code != 409:
            raise


def upsert_points(
    points: list[qmodels.PointStruct], client: QdrantClient | None = None
) -> None:
    client = client or get_qdrant_client()
    client.upsert(collection_name=COLLECTION_NAME, points=points)
