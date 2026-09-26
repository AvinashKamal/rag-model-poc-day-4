"""Real ingestion pipeline: domain_lib corpus fetch -> tag (observability only)
-> embed dense -> upsert into the shared `literature` Qdrant collection.

Phase 1 scope: abstract-only, one vector per paper (title + abstract).
Structure-aware chunking is deferred to Phase 2 (see project CLAUDE.md).
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import UTC, datetime

from domain_lib import corpus, registry, tagging
from opentelemetry.trace import Status, StatusCode
from qdrant_client import models as qmodels

from app.clients.embeddings_client import embed
from app.clients.qdrant_client import (
    DENSE_VECTOR_NAME,
    ensure_literature_collection,
    upsert_points,
)
from app.telemetry import (
    rag_ingestion_duration_seconds,
    rag_ingestion_runs_total,
    tracer,
)

logger = logging.getLogger(__name__)

# Fixed namespace so re-ingesting the same source:paper_id always derives the
# same Qdrant point id, turning re-ingestion into an upsert rather than a
# duplicate insert.
NAMESPACE = uuid.UUID("6f6d1f6a-6e4b-4a4d-9a9b-0b8d3c9e2f11")


def run_ingestion(
    domain_id: str, source: str, query: str, max_results: int = 10
) -> dict:
    """Fetch a corpus batch for `domain_id` from `source`, embed, and upsert
    into the `literature` collection. Raises `domain_lib.registry.
    DomainNotFoundError` for an unknown domain, and `ValueError` for a source
    not enabled for that domain — callers (the /admin/ingest endpoint) turn
    both into HTTP 400s.

    Wrapped in a manual OTel span plus a success/failure counter and a
    duration histogram (see app/telemetry.py) — this previously ran with
    zero tracing/metrics despite being the other half of the app (retrieval
    already has rag_retrieval_hit_rate/rag_llm_tokens_total). The span and
    metrics cover the whole run including validation failures (unknown
    domain/source), not just the embed/upsert happy path, since those are
    exactly the failures an operator watching a dashboard needs to see.
    """
    start = time.monotonic()
    status = "failure"
    with tracer.start_as_current_span(
        "ingestion.run_ingestion",
        attributes={
            "domain": domain_id,
            "source": source,
            "max_results": max_results,
        },
    ) as span:
        try:
            result = _run_ingestion_impl(domain_id, source, query, max_results)
            status = "success"
            return result
        except Exception as exc:
            # Blind-but-recorded: this is the ingestion-run span boundary,
            # not a place that decides how to recover — every failure must
            # be visible on the span (record_exception + ERROR status) and
            # then re-raised unchanged for the real caller
            # (main._run_ingestion_job) to log/store against the run_id.
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            raise
        finally:
            attrs = {"domain": domain_id, "status": status}
            rag_ingestion_runs_total.add(1, attrs)
            rag_ingestion_duration_seconds.record(time.monotonic() - start, attrs)


def _run_ingestion_impl(
    domain_id: str, source: str, query: str, max_results: int
) -> dict:
    # Validate domain up front; also lets fetch_corpus's own allowed-sources
    # check produce a clean ValueError instead of a KeyError deeper in.
    registry.get_domain(domain_id)

    fetch_result = asyncio.run(
        corpus.fetch_corpus(domain_id, source, query, max_results=max_results)
    )
    if "error" in fetch_result:
        # fetch_corpus returns (rather than raises) a dict for an unknown
        # source name at the _FETCHERS level; normalize that to a ValueError
        # too, same as the "source not allowed for this domain" case.
        raise ValueError(fetch_result["error"])

    papers = fetch_result["papers"]
    graphify_target = f"obsidian-vault/literature/{domain_id}/"

    if not papers:
        return {
            "domain": domain_id,
            "fetched": 0,
            "upserted": 0,
            "papers": [],
            "graphify_target": graphify_target,
        }

    texts = []
    for paper in papers:
        tag_result = tagging.tag_domain(
            f"{paper.get('title', '')} {paper.get('abstract', '')}"
        )
        if tag_result["domain"] != domain_id:
            # Requested domain always wins for storage — this is logged, not
            # acted on, so a mislabeled corpus query is visible without
            # silently dropping or re-routing papers.
            logger.warning(
                "paper tagged as domain '%s' (confidence %.2f) disagrees with "
                "requested domain '%s'; storing under '%s' regardless "
                "(source=%s id=%s)",
                tag_result["domain"],
                tag_result["confidence"],
                domain_id,
                domain_id,
                source,
                paper.get("id"),
            )
        texts.append(f"{paper.get('title', '')}\n\n{paper.get('abstract', '')}")

    dense_vectors = embed(texts)

    ensure_literature_collection()

    ingested_at = datetime.now(UTC).isoformat()
    points: list[qmodels.PointStruct] = []
    ingested_papers = []
    for paper, dense_vec in zip(papers, dense_vectors):
        point_id = str(uuid.uuid5(NAMESPACE, f"{source}:{paper.get('id')}"))
        points.append(
            qmodels.PointStruct(
                id=point_id,
                vector={DENSE_VECTOR_NAME: dense_vec},
                payload={
                    "domain": domain_id,
                    "title": paper.get("title", ""),
                    "abstract": paper.get("abstract", ""),
                    "source": source,
                    "url": paper.get("url", ""),
                    "ingested_at": ingested_at,
                },
            )
        )
        ingested_papers.append({"id": point_id, "title": paper.get("title", "")})

    upsert_points(points)

    return {
        "domain": domain_id,
        "fetched": len(papers),
        "upserted": len(points),
        "papers": ingested_papers,
        # Next manual/agent step: run /graphify against this directory once a
        # real batch has been ingested. Not invoked from here — see OPEN_ISSUES.
        "graphify_target": graphify_target,
    }
