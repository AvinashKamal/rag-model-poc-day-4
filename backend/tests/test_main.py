"""API-level tests for app/main.py's synchronous validation paths.

Only exercises requests that return *before* any background ingestion task
is scheduled (bad domain / bad source) — those paths never touch
TEI/Qdrant/OpenRouter, so no mocking of the retrieval/ingestion pipelines is
needed here. The retrieval pipeline itself is covered at the unit level in
test_retrieval_query.py, and ingestion idempotency in
test_ingestion_pipeline.py.
"""

from __future__ import annotations

import app.main as main_module
from app.errors import UpstreamServiceError
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_domains_returns_known_ids():
    resp = client.get("/domains")
    assert resp.status_code == 200
    ids = {d["id"] for d in resp.json()}
    assert "medicine" in ids
    for domain in resp.json():
        assert set(domain.keys()) == {"id", "display_name"}


def test_admin_ingest_rejects_unknown_domain_synchronously():
    resp = client.post(
        "/admin/ingest",
        json={"domain": "not-a-real-domain", "source": "arxiv", "query": "q"},
    )
    assert resp.status_code == 400


def test_admin_ingest_rejects_source_not_allowed_for_domain_synchronously():
    # "pubmed" is not in logistics' allowed sources (config/domains.yaml) —
    # this must be a synchronous 400, not accepted and only failing later
    # when the caller polls GET /admin/ingest/{run_id}.
    resp = client.post(
        "/admin/ingest",
        json={"domain": "logistics", "source": "pubmed", "query": "q"},
    )
    assert resp.status_code == 400
    assert "pubmed" in resp.json()["detail"]


def test_admin_ingest_status_unknown_run_id_is_404():
    resp = client.get("/admin/ingest/does-not-exist")
    assert resp.status_code == 404


def test_query_rejects_unknown_domain():
    resp = client.post("/query", json={"question": "q?", "domains": ["not-a-domain"]})
    assert resp.status_code == 400


def test_query_rejects_empty_question():
    # QueryRequest.question has min_length=1 precisely so an empty string
    # is rejected by validation (422) before it can drive a full
    # embed/search/rerank/LLM round trip for nothing.
    resp = client.post("/query", json={"question": ""})
    assert resp.status_code == 422
    # NOTE: pydantic's min_length does not strip whitespace, so a
    # whitespace-only question ("   ") currently still passes this
    # validator — that's a separate, not-yet-fixed gap, not asserted here.


def test_query_maps_upstream_service_error_to_502_without_leaking_details(
    monkeypatch,
):
    # Regression test for the 502 path: /query must never echo the raw
    # exception text (which can contain upstream response bodies, or in
    # other stages, redacted-but-still-sensitive details) back to the
    # caller — only the fixed, safe "which service failed" message.
    def _raise_upstream_error(request):
        raise UpstreamServiceError("qdrant", "connection refused: 10.0.0.5:6333")

    monkeypatch.setattr(main_module, "answer_query", _raise_upstream_error)

    resp = client.post("/query", json={"question": "q?"})

    assert resp.status_code == 502
    detail = resp.json()["detail"]
    assert detail == "upstream service 'qdrant' is unavailable"
    assert "10.0.0.5" not in detail
    assert "connection refused" not in detail
