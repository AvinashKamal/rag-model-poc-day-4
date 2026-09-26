"""Covers ingestion upsert idempotency in app/ingestion/pipeline.py: the
same (source, paper_id) pair must always derive the same Qdrant point id
(uuid5 against a fixed namespace), so re-ingesting the same paper is an
upsert, never a duplicate insert.

domain_lib.corpus.fetch_corpus, embeddings, and the Qdrant upsert call are
all monkeypatched — no live arxiv/TEI/Qdrant is required.
"""

from __future__ import annotations

from app.ingestion import pipeline as pipeline_module
from domain_lib import corpus as domain_corpus


async def _fake_fetch_corpus(domain, source, query, max_results=10):
    return {
        "domain": domain,
        "source": source,
        "query": query,
        "count": 1,
        "papers": [
            {
                "id": "paper-123",
                "title": "A Study of Clinical Trial Outcomes",
                "abstract": "Randomized controlled trial results.",
                "source": source,
                "url": "https://arxiv.org/abs/paper-123",
                "domain": domain,
            }
        ],
    }


def _patch_common(monkeypatch, upserted: list):
    monkeypatch.setattr(domain_corpus, "fetch_corpus", _fake_fetch_corpus)
    monkeypatch.setattr(
        pipeline_module, "embed", lambda texts: [[0.1] * 4 for _ in texts]
    )
    monkeypatch.setattr(pipeline_module, "ensure_literature_collection", lambda: None)

    def _fake_upsert(points):
        upserted.append(points)

    monkeypatch.setattr(pipeline_module, "upsert_points", _fake_upsert)


def test_reingesting_same_paper_derives_the_same_point_id(monkeypatch):
    upserted_batches: list = []
    _patch_common(monkeypatch, upserted_batches)

    result_1 = pipeline_module.run_ingestion(
        "medicine", "arxiv", "clinical trial", max_results=5
    )
    result_2 = pipeline_module.run_ingestion(
        "medicine", "arxiv", "clinical trial", max_results=5
    )

    assert result_1["upserted"] == 1
    assert result_2["upserted"] == 1
    id_1 = result_1["papers"][0]["id"]
    id_2 = result_2["papers"][0]["id"]
    assert id_1 == id_2, "same source:paper_id must derive the same point id"

    # Both upsert calls carried a PointStruct with that same id, too — not
    # just the summary dict returned to the caller.
    assert len(upserted_batches) == 2
    assert str(upserted_batches[0][0].id) == id_1
    assert str(upserted_batches[1][0].id) == id_2


def test_point_id_varies_with_source_for_the_same_paper_id(monkeypatch):
    """Different sources reusing the same upstream paper id must not
    collide — the point id is derived from `source:paper_id`, not just
    `paper_id`."""
    upserted_batches: list = []
    _patch_common(monkeypatch, upserted_batches)

    result_arxiv = pipeline_module.run_ingestion(
        "medicine", "arxiv", "q", max_results=5
    )
    result_pubmed = pipeline_module.run_ingestion(
        "medicine", "pubmed", "q", max_results=5
    )

    assert result_arxiv["papers"][0]["id"] != result_pubmed["papers"][0]["id"]


def test_point_id_is_deterministic_uuid5_against_fixed_namespace(monkeypatch):
    """The point id isn't just *stable* across calls — it's specifically a
    uuid5 derived from pipeline_module.NAMESPACE and "source:paper_id", so
    it's independently reproducible without running the pipeline at all."""
    import uuid

    upserted_batches: list = []
    _patch_common(monkeypatch, upserted_batches)

    result = pipeline_module.run_ingestion("medicine", "arxiv", "q", max_results=5)

    expected_id = str(uuid.uuid5(pipeline_module.NAMESPACE, "arxiv:paper-123"))
    assert result["papers"][0]["id"] == expected_id
