"""Covers the /query pipeline in app/retrieval/query.py:

- the abstention gate (no points found; top rerank score below threshold)
- citation binding only ever pointing at real reranked candidates, never at
  free-text URLs/markers the model's answer text might contain
- each upstream call (embeddings/qdrant/reranker/llm) failing being wrapped
  as an UpstreamServiceError tagged with which stage failed

All four upstream clients (embed/get_qdrant_client/rerank/get_llm_client)
are monkeypatched with in-memory fakes from conftest.py — no TEI/Qdrant/
OpenRouter instance is required to run this suite.
"""

from __future__ import annotations

import httpx
import openai
import pytest
from app.errors import UpstreamServiceError
from app.retrieval import query as query_module
from app.schemas import QueryRequest
from qdrant_client.http.exceptions import UnexpectedResponse

from tests.conftest import FakeLLMClient, FakePoint, FakeQdrantClient

PAYLOAD_A = {
    "title": "Paper A",
    "abstract": "Abstract A",
    "source": "arxiv",
    "url": "https://arxiv.org/abs/A",
    "domain": "medicine",
}
PAYLOAD_B = {
    "title": "Paper B",
    "abstract": "Abstract B",
    "source": "pubmed",
    "url": "https://pubmed.ncbi.nlm.nih.gov/B/",
    "domain": "medicine",
}


def _patch_embed(monkeypatch, vec=None):
    monkeypatch.setattr(query_module, "embed", lambda texts: [vec or [0.1] * 4])


def _patch_qdrant(monkeypatch, points):
    fake_client = FakeQdrantClient(points)
    monkeypatch.setattr(query_module, "get_qdrant_client", lambda: fake_client)
    return fake_client


def _patch_rerank(monkeypatch, reranked):
    monkeypatch.setattr(query_module, "rerank", lambda question, docs: reranked)


def _patch_llm(monkeypatch, content=None, raises=None):
    fake_llm = FakeLLMClient(content=content, raises=raises)
    monkeypatch.setattr(query_module, "get_llm_client", lambda: fake_llm)
    return fake_llm


def _request(**overrides) -> QueryRequest:
    defaults = {"question": "What does the corpus say?", "domains": None, "top_k": 5}
    defaults.update(overrides)
    return QueryRequest(**defaults)


# --- Abstention gate --------------------------------------------------------


def test_abstains_when_no_points_found(monkeypatch):
    _patch_embed(monkeypatch)
    _patch_qdrant(monkeypatch, points=[])
    llm = _patch_llm(monkeypatch, content="should never be called")

    result = query_module.answer_query(_request())

    assert result.abstained is True
    assert result.answer is None
    assert result.citations == []
    assert llm.chat.completions.calls == [], "LLM must not be called on abstain"


def test_abstains_when_top_rerank_score_below_threshold(monkeypatch):
    _patch_embed(monkeypatch)
    _patch_qdrant(monkeypatch, points=[FakePoint(PAYLOAD_A), FakePoint(PAYLOAD_B)])
    # Both scores below the default RERANK_ABSTAIN_THRESHOLD (0.3).
    _patch_rerank(
        monkeypatch, [{"index": 0, "score": 0.1}, {"index": 1, "score": 0.05}]
    )
    llm = _patch_llm(monkeypatch, content="should never be called")

    result = query_module.answer_query(_request())

    assert result.abstained is True
    assert result.citations == []
    assert llm.chat.completions.calls == []


def test_answers_when_top_rerank_score_clears_threshold(monkeypatch):
    _patch_embed(monkeypatch)
    _patch_qdrant(monkeypatch, points=[FakePoint(PAYLOAD_A), FakePoint(PAYLOAD_B)])
    _patch_rerank(monkeypatch, [{"index": 0, "score": 0.9}, {"index": 1, "score": 0.5}])
    _patch_llm(monkeypatch, content="Evidence found [1].")

    result = query_module.answer_query(_request())

    assert result.abstained is False
    assert result.answer == "Evidence found [1]."


# --- Citation binding --------------------------------------------------------


def test_citations_bind_only_to_real_reranked_candidates(monkeypatch):
    """The model's answer text may contain [n] markers pointing outside the
    numbered document list it was given, or arbitrary free-text URLs — only
    in-range [n] markers get turned into citations, and every citation's
    fields always come from the actual reranked candidate's payload, never
    from any text inside the answer itself."""
    _patch_embed(monkeypatch)
    _patch_qdrant(monkeypatch, points=[FakePoint(PAYLOAD_A), FakePoint(PAYLOAD_B)])
    _patch_rerank(monkeypatch, [{"index": 0, "score": 0.9}, {"index": 1, "score": 0.8}])
    # [99] is out of range (only 2 candidates); the free-text URL is
    # attacker/model-controlled content and must never end up as a citation.
    answer = (
        "See [1] and [2]. Also see [99] and this link "
        "https://evil.example.com/not-a-real-paper [1]"
    )
    _patch_llm(monkeypatch, content=answer)

    result = query_module.answer_query(_request(top_k=5))

    assert result.abstained is False
    assert len(result.citations) == 2  # [99] dropped, duplicate [1] deduped
    urls = {c.url for c in result.citations}
    assert urls == {PAYLOAD_A["url"], PAYLOAD_B["url"]}
    assert "evil.example.com" not in " ".join(urls)
    for citation in result.citations:
        assert citation.title in (PAYLOAD_A["title"], PAYLOAD_B["title"])


def test_citations_respect_top_k_truncation(monkeypatch):
    """A [n] marker for a candidate that was retrieved/reranked but fell
    outside `top_k` (so never made it into the documents shown to the model)
    must not bind either — top_k truncation happens before the documents
    block is built."""
    _patch_embed(monkeypatch)
    _patch_qdrant(
        monkeypatch,
        points=[FakePoint(PAYLOAD_A), FakePoint(PAYLOAD_B), FakePoint(PAYLOAD_A)],
    )
    _patch_rerank(
        monkeypatch,
        [
            {"index": 0, "score": 0.9},
            {"index": 1, "score": 0.8},
            {"index": 2, "score": 0.7},
        ],
    )
    # top_k=1 means only candidate [1] was ever shown to the model.
    answer = "See [1] and [2]."
    _patch_llm(monkeypatch, content=answer)

    result = query_module.answer_query(_request(top_k=1))

    assert len(result.citations) == 1
    assert result.citations[0].url == PAYLOAD_A["url"]


# --- Upstream error wrapping -------------------------------------------------


def test_embeddings_failure_wrapped_as_upstream_error(monkeypatch, fake_httpx_error):
    def _raise(texts):
        raise fake_httpx_error

    monkeypatch.setattr(query_module, "embed", _raise)

    with pytest.raises(UpstreamServiceError) as exc_info:
        query_module.answer_query(_request())
    assert exc_info.value.service == "embeddings"


def test_qdrant_failure_wrapped_as_upstream_error(monkeypatch):
    _patch_embed(monkeypatch)

    class RaisingQdrantClient:
        def query_points(self, **kwargs):
            raise UnexpectedResponse(503, "Service Unavailable", b"", httpx.Headers())

    monkeypatch.setattr(
        query_module, "get_qdrant_client", lambda: RaisingQdrantClient()
    )

    with pytest.raises(UpstreamServiceError) as exc_info:
        query_module.answer_query(_request())
    assert exc_info.value.service == "qdrant"


def test_reranker_failure_wrapped_as_upstream_error(monkeypatch, fake_httpx_error):
    _patch_embed(monkeypatch)
    _patch_qdrant(monkeypatch, points=[FakePoint(PAYLOAD_A)])

    def _raise(question, docs):
        raise fake_httpx_error

    monkeypatch.setattr(query_module, "rerank", _raise)

    with pytest.raises(UpstreamServiceError) as exc_info:
        query_module.answer_query(_request())
    assert exc_info.value.service == "reranker"


def test_llm_failure_wrapped_as_upstream_error(monkeypatch):
    _patch_embed(monkeypatch)
    _patch_qdrant(monkeypatch, points=[FakePoint(PAYLOAD_A)])
    _patch_rerank(monkeypatch, [{"index": 0, "score": 0.9}])
    llm_error = openai.APIConnectionError(
        message="boom", request=httpx.Request("POST", "http://openrouter.example")
    )
    _patch_llm(monkeypatch, raises=llm_error)

    with pytest.raises(UpstreamServiceError) as exc_info:
        query_module.answer_query(_request())
    assert exc_info.value.service == "llm"
