"""Pydantic request/response models for the backend API.

Grows over time (later milestones add retrieval/query schemas here too) —
starting with just the admin ingestion request shape.
"""

from typing import Literal

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    domain: str
    source: str
    query: str = Field(min_length=1, max_length=2000)
    max_results: int = Field(default=10, gt=0, le=100)


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ReadyResponse(BaseModel):
    status: Literal["ok", "degraded"]


class IngestAcceptedResponse(BaseModel):
    run_id: str
    status: Literal["running"]


class IngestedPaper(BaseModel):
    id: str
    title: str


class IngestResult(BaseModel):
    domain: str
    fetched: int
    upserted: int
    papers: list[IngestedPaper]
    graphify_target: str


class IngestRunStatus(BaseModel):
    """Shape returned by GET /admin/ingest/{run_id}, matching
    app/ingestion/state.py's in-memory run record exactly."""

    run_id: str
    status: Literal["running", "done", "failed"]
    result: IngestResult | None = None
    error: str | None = None
    created_at: str
    updated_at: str


class DomainInfo(BaseModel):
    id: str
    display_name: str


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    domains: list[str] | None = None
    top_k: int = Field(default=5, gt=0, le=50)


class Citation(BaseModel):
    title: str
    source: str
    url: str
    domain: str
    score: float


class QueryResponse(BaseModel):
    answer: str | None
    abstained: bool
    citations: list[Citation]
    reasoning_note: str | None = None
