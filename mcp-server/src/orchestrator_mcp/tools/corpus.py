# Thin re-export shim. The real fetch logic (arXiv/PubMed/Semantic Scholar)
# now lives in shared/domain_lib/src/domain_lib/corpus.py so backend and
# mcp-server share one implementation. Kept here so server.py's imports
# (orchestrator_mcp.tools.corpus.fetch_corpus) don't need to change.

from domain_lib.corpus import (
    fetch_arxiv,
    fetch_corpus,
    fetch_pubmed,
    fetch_semantic_scholar,
)

__all__ = ["fetch_arxiv", "fetch_corpus", "fetch_pubmed", "fetch_semantic_scholar"]
