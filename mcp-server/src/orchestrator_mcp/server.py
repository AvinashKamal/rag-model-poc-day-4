from mcp.server.fastmcp import FastMCP

from orchestrator_mcp.tools.corpus import fetch_corpus as _fetch_corpus
from orchestrator_mcp.tools.domain_tagging import tag_domain as _tag_domain
from orchestrator_mcp.tools.k6 import get_k6_summary as _get_k6_summary
from orchestrator_mcp.tools.k6 import trigger_k6_run as _trigger_k6_run
from orchestrator_mcp.tools.pipeline import pipeline_status as _pipeline_status
from orchestrator_mcp.tools.pipeline import trigger_ingestion as _trigger_ingestion

mcp = FastMCP("orchestrator")


@mcp.tool()
async def fetch_corpus(
    domain: str, source: str, query: str, max_results: int = 10
) -> dict:
    """Fetch papers for a domain from arxiv, pubmed, or semantic_scholar."""
    return await _fetch_corpus(domain, source, query, max_results)


@mcp.tool()
def tag_domain(text: str) -> dict:
    """Classify a piece of text (title/abstract) into a known literature domain."""
    return _tag_domain(text)


@mcp.tool()
def trigger_ingestion(domain: str, source: str, query: str) -> dict:
    """Record intent to ingest a corpus batch and return a run_id to poll with pipeline_status."""
    return _trigger_ingestion(domain, source, query)


@mcp.tool()
def pipeline_status(run_id: str | None = None) -> dict:
    """Get the status of one ingestion run by run_id. run_id is required —
    the backend has no "list all runs" endpoint, so omitting it returns a
    clean error dict rather than a list of all runs."""
    return _pipeline_status(run_id)


@mcp.tool()
def trigger_k6_run(script_path: str, base_url: str = "http://localhost:8000") -> dict:
    """Run a k6 load-test script against a local backend target and return a run_id."""
    return _trigger_k6_run(script_path, base_url)


@mcp.tool()
def get_k6_summary(run_id: str) -> dict:
    """Fetch the JSON summary of a previously triggered k6 run."""
    return _get_k6_summary(run_id)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
