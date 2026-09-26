import asyncio
import os
import xml.etree.ElementTree as ET

import httpx

from domain_lib.registry import get_sources

ARXIV_API = "https://export.arxiv.org/api/query"
PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
# ESummary (used for titles below) never returns abstract text — it's a
# summary-metadata endpoint, not a full-record one. EFetch with
# rettype=abstract is the actual NCBI endpoint that returns AbstractText.
PUBMED_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
SEMANTIC_SCHOLAR_SEARCH = "https://api.semanticscholar.org/graph/v1/paper/search"

_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


def _raise_for_status_redacted(resp: httpx.Response) -> None:
    """Same as `resp.raise_for_status()`, but strips the query string from
    the raised exception first.

    `httpx.HTTPStatusError.__str__` embeds the full request URL. PubMed's
    ESearch/ESummary/EFetch calls carry `NCBI_API_KEY` in the query string
    (unlike Semantic Scholar's key, which is header-only and never hits the
    URL) — if that raw exception propagated, it would land in
    `logger.exception(...)` (backend/app/main.py) and OTel
    `span.record_exception(...)` (backend/app/ingestion/pipeline.py) with the
    key intact. Raised with `from None` (not `from exc`) so the redacted
    exception doesn't chain to the original one, since Python tracebacks
    print the full chain including the suppressed cause's message.
    """
    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        redacted_url = exc.request.url.copy_with(query=None)
        raise httpx.HTTPStatusError(
            f"{exc.response.status_code} {exc.response.reason_phrase} "
            f"for url '{redacted_url}'",
            request=exc.request,
            response=exc.response,
        ) from None


async def _get_with_backoff(
    client: httpx.AsyncClient, url: str, **kwargs
) -> httpx.Response:
    delay = 1.0
    for attempt in range(4):
        resp = await client.get(url, **kwargs)
        if resp.status_code != 429:
            _raise_for_status_redacted(resp)
            return resp
        await asyncio.sleep(delay)
        delay *= 2
    _raise_for_status_redacted(resp)
    return resp


async def fetch_arxiv(query: str, max_results: int) -> list[dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await _get_with_backoff(
            client,
            ARXIV_API,
            params={"search_query": f"all:{query}", "max_results": max_results},
        )
    root = ET.fromstring(resp.text)
    papers = []
    for entry in root.findall("atom:entry", _ATOM_NS):
        papers.append(
            {
                "id": entry.findtext("atom:id", default="", namespaces=_ATOM_NS),
                "title": (
                    entry.findtext("atom:title", default="", namespaces=_ATOM_NS) or ""
                ).strip(),
                "abstract": (
                    entry.findtext("atom:summary", default="", namespaces=_ATOM_NS)
                    or ""
                ).strip(),
                "source": "arxiv",
                "url": entry.findtext("atom:id", default="", namespaces=_ATOM_NS),
            }
        )
    return papers


def _parse_pubmed_abstracts(xml_text: str) -> dict[str, str]:
    """Parses an EFetch (db=pubmed, rettype=abstract, retmode=xml) response
    into {pmid: abstract_text}. A PubMed abstract can be split across
    several <AbstractText> elements (structured abstracts use a `Label`
    attribute, e.g. BACKGROUND/METHODS/RESULTS/CONCLUSIONS) — those are
    rejoined here into one plain-text abstract, prefixed with their label
    when present, since the rest of the pipeline (embeddings, LLM context)
    wants a single abstract string per paper, not a structured list.
    """
    abstracts: dict[str, str] = {}
    root = ET.fromstring(xml_text)
    for article in root.findall(".//PubmedArticle"):
        pmid_el = article.find(".//MedlineCitation/PMID")
        if pmid_el is None or not pmid_el.text:
            continue
        parts = []
        for abstract_text in article.findall(".//Abstract/AbstractText"):
            label = abstract_text.get("Label")
            text = (abstract_text.text or "").strip()
            if not text:
                continue
            parts.append(f"{label}: {text}" if label else text)
        abstracts[pmid_el.text] = " ".join(parts)
    return abstracts


async def fetch_pubmed(query: str, max_results: int) -> list[dict]:
    ncbi_key = os.environ.get("NCBI_API_KEY")
    contact_email = os.environ.get("NCBI_CONTACT_EMAIL")

    common_params = {}
    if ncbi_key:
        common_params["api_key"] = ncbi_key
    if contact_email:
        common_params["email"] = contact_email

    async with httpx.AsyncClient(timeout=20) as client:
        search_resp = await _get_with_backoff(
            client,
            PUBMED_ESEARCH,
            params={
                "db": "pubmed",
                "term": query,
                "retmax": max_results,
                "retmode": "json",
                **common_params,
            },
        )
        ids = search_resp.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []

        summary_resp = await _get_with_backoff(
            client,
            PUBMED_ESUMMARY,
            params={
                "db": "pubmed",
                "id": ",".join(ids),
                "retmode": "json",
                **common_params,
            },
        )

        # ESummary (above) never returns abstract text, only title-level
        # metadata — a separate EFetch call (rettype=abstract) is the actual
        # NCBI endpoint that returns AbstractText. Fetched as one extra
        # batched call (same id list) rather than per-paper, matching the
        # single-batched-call shape ESearch/ESummary already use.
        try:
            efetch_resp = await _get_with_backoff(
                client,
                PUBMED_EFETCH,
                params={
                    "db": "pubmed",
                    "id": ",".join(ids),
                    "rettype": "abstract",
                    "retmode": "xml",
                    **common_params,
                },
            )
            abstracts = _parse_pubmed_abstracts(efetch_resp.text)
        except (httpx.HTTPError, ET.ParseError):
            # Degrade to title-only (old behavior) rather than failing the
            # whole ingestion batch over the abstract-enrichment call.
            abstracts = {}

    result = summary_resp.json().get("result", {})
    papers = []
    for pmid in ids:
        doc = result.get(pmid)
        if not doc:
            continue
        papers.append(
            {
                "id": pmid,
                "title": doc.get("title", ""),
                "abstract": abstracts.get(pmid, ""),
                "source": "pubmed",
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            }
        )
    return papers


async def fetch_semantic_scholar(query: str, max_results: int) -> list[dict]:
    headers = {}
    api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await _get_with_backoff(
            client,
            SEMANTIC_SCHOLAR_SEARCH,
            params={
                "query": query,
                "limit": max_results,
                "fields": "title,abstract,year,externalIds",
            },
            headers=headers,
        )
    papers = []
    for item in resp.json().get("data", []):
        papers.append(
            {
                "id": item.get("paperId", ""),
                "title": item.get("title", "") or "",
                "abstract": item.get("abstract", "") or "",
                "source": "semantic_scholar",
                "url": f"https://www.semanticscholar.org/paper/{item.get('paperId', '')}",
            }
        )
    return papers


_FETCHERS = {
    "arxiv": fetch_arxiv,
    "pubmed": fetch_pubmed,
    "semantic_scholar": fetch_semantic_scholar,
}


async def fetch_corpus(
    domain: str, source: str, query: str, max_results: int = 10
) -> dict:
    """Fetch papers for a domain from one source. `domain` selects the domain
    registry entry (config/domains.yaml); `source` must be one of that domain's
    allowed `sources` — this is validated against the registry before fetching,
    rather than trusting the caller to only pass sensible combinations."""
    fetcher = _FETCHERS.get(source)
    if fetcher is None:
        return {
            "error": f"unknown source '{source}', expected one of {list(_FETCHERS)}"
        }

    allowed_sources = get_sources(domain)
    if source not in allowed_sources:
        raise ValueError(
            f"source '{source}' is not enabled for domain '{domain}' "
            f"(allowed sources: {allowed_sources})"
        )

    papers = await fetcher(query, max_results)
    for paper in papers:
        paper["domain"] = domain
    return {
        "domain": domain,
        "source": source,
        "query": query,
        "count": len(papers),
        "papers": papers,
    }
