"""Shared pytest fixtures/fakes for the backend test suite.

Nothing here talks to a real TEI/Qdrant/OpenRouter instance — every fixture
is an in-memory fake standing in for one of the four upstream clients
(embeddings, qdrant, reranker, llm), matching the shapes those clients'
real return values have (see app/clients/*.py).
"""

from __future__ import annotations

import httpx
import pytest


class FakePoint:
    """Stand-in for a qdrant_client `ScoredPoint`/`Record` — only `.payload`
    is used by app/retrieval/query.py."""

    def __init__(self, payload: dict):
        self.payload = payload


class FakeQueryResult:
    def __init__(self, points: list[FakePoint]):
        self.points = points


class FakeQdrantClient:
    """Stand-in for qdrant_client.QdrantClient — records the last
    query_points() call's kwargs so tests can assert on filters/limits, and
    returns a pre-set list of fake points."""

    def __init__(self, points: list[FakePoint]):
        self._points = points
        self.last_query_kwargs: dict | None = None

    def query_points(self, **kwargs):
        self.last_query_kwargs = kwargs
        return FakeQueryResult(self._points)


class FakeUsage:
    def __init__(self, prompt_tokens=10, completion_tokens=5):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class FakeMessage:
    def __init__(self, content: str):
        self.content = content


class FakeChoice:
    def __init__(self, content: str):
        self.message = FakeMessage(content)


class FakeCompletionResponse:
    def __init__(self, content: str):
        self.choices = [FakeChoice(content)]
        self.usage = FakeUsage()


class FakeCompletions:
    """Stand-in for openai's `client.chat.completions`. Either returns a
    fixed answer string wrapped as a chat-completion response, or raises a
    pre-set exception (to simulate an OpenRouter outage)."""

    def __init__(self, content: str | None = None, raises: Exception | None = None):
        self._content = content
        self._raises = raises
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._raises is not None:
            raise self._raises
        return FakeCompletionResponse(self._content or "")


class FakeChat:
    def __init__(self, completions: FakeCompletions):
        self.completions = completions


class FakeLLMClient:
    def __init__(self, content: str | None = None, raises: Exception | None = None):
        self.chat = FakeChat(FakeCompletions(content, raises))


@pytest.fixture
def fake_httpx_error() -> httpx.HTTPError:
    return httpx.ConnectError("connection refused")
