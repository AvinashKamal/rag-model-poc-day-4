import logging
import uuid

from domain_lib import DomainNotFoundError, get_domain, get_sources
from domain_lib.registry import list_domains
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.clients.qdrant_client import get_qdrant_client
from app.config import settings
from app.errors import QDRANT_ERRORS, UpstreamServiceError
from app.ingestion import state as ingestion_state
from app.ingestion.pipeline import run_ingestion
from app.retrieval.query import answer_query
from app.schemas import (
    DomainInfo,
    HealthResponse,
    IngestAcceptedResponse,
    IngestRequest,
    IngestRunStatus,
    QueryRequest,
    QueryResponse,
    ReadyResponse,
)
from app.telemetry import setup_telemetry

logger = logging.getLogger(__name__)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)
setup_telemetry(app)


@app.get("/health", response_model=HealthResponse)
def health():
    # Must not depend on Qdrant/embeddings/reranker: this endpoint is the
    # container-level liveness check and has to work before those services
    # are reachable (or if they're down).
    return {"status": "ok"}


@app.get("/health/ready", response_model=ReadyResponse)
def health_ready():
    try:
        get_qdrant_client().get_collections()
        return {"status": "ok"}
    except QDRANT_ERRORS:
        # Narrowed to the specific exception types a Qdrant call can raise
        # (connection failure, timeout, or a non-2xx response — see
        # app/errors.py's QDRANT_ERRORS) rather than a blind `except
        # Exception`: readiness should degrade because Qdrant is actually
        # unreachable/unhealthy, not swallow an unrelated programming error.
        return {"status": "degraded"}


def _run_ingestion_job(
    run_id: str, domain: str, source: str, query: str, max_results: int
) -> None:
    try:
        result = run_ingestion(domain, source, query, max_results=max_results)
        ingestion_state.mark_done(run_id, result)
    except Exception as exc:
        # Background job boundary: this runs detached from the request that
        # triggered it, so it must not crash the worker on *any* failure
        # (upstream outage, bad corpus response, programming error) — it's
        # caught here, logged, and surfaced via GET /admin/ingest/{run_id}'s
        # "failed" status instead. logger.exception() below records the full
        # traceback, so this is a deliberately blind-but-logged catch, not a
        # silent one.
        logger.exception("ingestion run %s failed", run_id)
        ingestion_state.mark_failed(run_id, str(exc))


@app.post("/admin/ingest", response_model=IngestAcceptedResponse)
def admin_ingest(request: IngestRequest, background_tasks: BackgroundTasks):
    try:
        get_domain(request.domain)
    except DomainNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    allowed_sources = get_sources(request.domain)
    if request.source not in allowed_sources:
        raise HTTPException(
            status_code=400,
            detail=(
                f"source '{request.source}' is not enabled for domain "
                f"'{request.domain}' (allowed sources: {allowed_sources})"
            ),
        )

    run_id = uuid.uuid4().hex[:12]
    ingestion_state.create_run(run_id)
    background_tasks.add_task(
        _run_ingestion_job,
        run_id,
        request.domain,
        request.source,
        request.query,
        request.max_results,
    )
    return {"run_id": run_id, "status": "running"}


@app.get("/admin/ingest/{run_id}", response_model=IngestRunStatus)
def admin_ingest_status(run_id: str):
    run = ingestion_state.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"no run with id '{run_id}'")
    return run


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest):
    try:
        return answer_query(request)
    except DomainNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except UpstreamServiceError as exc:
        # Any TEI (embeddings/reranker), Qdrant, or OpenRouter failure inside
        # the pipeline surfaces here as one of these, tagged with which
        # stage failed — logged in full server-side, but the client only
        # gets the service tag (never the raw exception text, which can
        # echo upstream response bodies we don't control).
        logger.warning("query failed: upstream '%s' unavailable: %s", exc.service, exc)
        raise HTTPException(
            status_code=502,
            detail=f"upstream service '{exc.service}' is unavailable",
        ) from exc


@app.get("/domains", response_model=list[DomainInfo])
def domains():
    return [
        {"id": domain.id, "display_name": domain.display_name}
        for domain in list_domains(enabled_only=True)
    ]
