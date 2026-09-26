# Pipeline orchestration control plane. Thin HTTP proxy to the backend's
# /admin/ingest endpoints — mirrors k6.py's shape: a local-only base_url
# guard, no embedded pipeline logic. The real ingestion pipeline now lives in
# backend/app/ingestion/pipeline.py; the backend is the source of truth for
# run state, so this file no longer keeps its own JSON state file.

import httpx

from orchestrator_mcp.tools._localguard import target_is_local


def trigger_ingestion(
    domain: str, source: str, query: str, base_url: str = "http://localhost:8000"
) -> dict:
    if not target_is_local(base_url):
        return {"error": f"refusing to call non-local target '{base_url}'"}

    try:
        response = httpx.post(
            f"{base_url}/admin/ingest",
            json={"domain": domain, "source": source, "query": query},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        return {
            "error": f"backend returned {exc.response.status_code}: {exc.response.text}"
        }
    except httpx.HTTPError as exc:
        return {"error": f"failed to reach backend at '{base_url}': {exc}"}


def pipeline_status(
    run_id: str | None = None, base_url: str = "http://localhost:8000"
) -> dict:
    if run_id is None:
        # The old local JSON-state approach supported listing all runs via
        # run_id=None; the backend's GET /admin/ingest/{run_id} has no
        # equivalent "list all" route, so this mode is gone. Kept as a
        # graceful error (not a crash) since server.py's wrapper still
        # defaults run_id to None.
        return {
            "error": "run_id is required — the backend does not support listing all runs"
        }

    if not target_is_local(base_url):
        return {"error": f"refusing to call non-local target '{base_url}'"}

    try:
        response = httpx.get(f"{base_url}/admin/ingest/{run_id}", timeout=10)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        return {
            "error": f"backend returned {exc.response.status_code}: {exc.response.text}"
        }
    except httpx.HTTPError as exc:
        return {"error": f"failed to reach backend at '{base_url}': {exc}"}
