"""API-level tests for app/main.py's synchronous validation paths.

Only exercises requests that return *before* any background ingestion task
is scheduled (bad domain / bad source) — those paths never touch
TEI/Qdrant/OpenRouter, so no mocking of the retrieval/ingestion pipelines is
needed here. The retrieval pipeline itself is covered at the unit level in
test_retrieval_query.py, and ingestion idempotency in
test_ingestion_pipeline.py.
"""

from __future__ import annotations

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
