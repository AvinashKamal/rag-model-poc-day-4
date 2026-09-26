# Project Status — Scientific Literature RAG POC

Snapshot as of 2026-09-26. For the full architecture rationale behind any decision below, see `/home/labuser/.claude/plans/you-are-a-professional-vast-papert.md`.

## What this is

A multi-domain RAG application for reviewing scientific literature. A user picks one or more domains, asks a question, and gets back an LLM-synthesized answer with citations pulled from real ingested abstracts — or an explicit "insufficient evidence" abstention instead of a guess. Built domain-agnostic on purpose: adding a 7th domain is a YAML edit, not a code change.

**Domains live today:** Medicine, Logistics, Manufacturing, Agriculture, Environmental Science, Energy (`config/domains.yaml`) — expanded from the original 3-domain plan (medicine/logistics/manufacturing) per an explicit request mid-build.

## Architecture at a glance

- **Backend:** FastAPI (`backend/`), talks to Qdrant, self-hosted TEI (embeddings + reranker), and OpenRouter directly — never through its own MCP server.
- **Frontend:** Next.js/React (`frontend/`) — domain multi-select, question form, answer + citations view with loading/error/abstained states.
- **Shared domain logic:** `shared/domain_lib/` — registry, corpus fetch (arXiv/PubMed/Semantic Scholar), domain tagging. Used by both `backend/` and `mcp-server/` so neither reimplements it.
- **mcp-server/**: dev-time agent tooling only (ingestion trigger/status, k6 trigger/result) — proxies to the backend's real HTTP endpoints, has no runtime role in the served app.
- **Observability:** OTel Collector → Prometheus/Loki/Tempo → Grafana, 3 dashboards (`rag-app`, `retrieval-quality`, `k6`).
- **Orchestration:** `.claude/agents/` (`frontend`, `backend`, `p3-triage`, plus `frontend-review`/`backend-review`), delegation-by-path rules in root `CLAUDE.md`, `.claude/PROJECT_STATE.md` as the compact shared ledger.
- **Knowledge graph:** graphify (project-local skill) run against each domain's ingested batch, writing into `obsidian-vault/literature/<domain>/`.

## What's done

**Backend (all milestones from the Phase 1 plan, §1–§6):**
- Domain registry + `shared/domain_lib` extraction, 6 real domains with keyword sets and source lists.
- Real ingestion pipeline: `POST /admin/ingest`, `GET /admin/ingest/{run_id}`, idempotent upserts (`uuid5(source:paper_id)`) into Qdrant's `literature` collection (dense + sparse named vectors).
- `POST /query`: hybrid dense+sparse retrieval (Qdrant Query API, RRF fusion) → rerank via TEI → abstention gate (`RERANK_ABSTAIN_THRESHOLD`) → OpenRouter generation with untrusted-data framing → citations bound strictly to reranked candidates, never free-text.
- `GET /domains` — frontend's only source of truth for the domain list.
- OTel metrics wired (`rag_retrieval_hit_rate`, `rag_llm_tokens_total`) alongside existing traces.
- `eval/run_eval.py` rewritten to call the real `/query` endpoint, score abstention accuracy + a new LLM groundedness-judge step, push metrics via OTLP. Gold question sets exist for all 6 domains.
- CORS fixed (frontend/backend were on different origins with no `CORSMiddleware` — would have blocked every browser call).
- p3-triage's P1s from the backend review (missing httpx timeouts, unpinned dependencies) fixed and re-verified.

**Frontend:**
- Full query UI: domain selector (live from `/domains`), question form, answer panel (citations rendered as `[n]` → anchors, never live-linked from untrusted model text), score meter, status panel for loading/error/abstained states.
- Built and verified against `backend/app/schemas.py` field-for-field; `npm run lint` and `npm run build` clean.
- p3-triage found and this session fixed two issues: an untrusted out-of-range `[99](url)` citation marker that would have rendered as a live external link (now always inert unless it's a real `#citation-N` anchor), and a `memo(QuestionForm)` that was a no-op because state lived in the parent (moved local).

**Infra / running stack:** `docker compose` is up — backend, frontend, Qdrant, embeddings (TEI), reranker (TEI), OTel collector, Prometheus, Loki, Tempo, Grafana all healthy. `literature` collection currently holds 48 points across the 6 domains. Live `/health` and `/domains` both respond correctly.

**Knowledge graph:** graphify has run against all 6 domains' ingested batches — `obsidian-vault/literature/<domain>/` populated for medicine, logistics, manufacturing, agriculture, environmental_science, and energy, plus community/relationship notes at the vault root.

**Orchestration tooling built this session:** `frontend-review` and `backend-review` subagents — dedicated, read-only, KPI-producing code-quality reviewers (reusability, bundling/dependency footprint, performance, accessibility/API usability, efficiency) distinct from the lighter cross-cutting `p3-triage` pass — plus `/frontend-review` and `/backend-review` slash commands to invoke them directly.

## What we're working on / just finished

- This document, at the user's request, plus the review-agent slash commands above.
- Most recent backend change: the CORS middleware fix (confirmed present in `backend/app/config.py` / `main.py`).

## What's left to do

**Verification gaps (flagged internally, never closed out against a live stack until now — worth re-running now that docker compose is actually up):**
- `embeddings_client.py`'s `embed_sparse()` and `reranker_client.py`'s `/rerank` response-shape are coded against TEI's *documented* contract but were never confirmed against a live TEI instance until this session's stack came up — worth a real end-to-end query to confirm no shape mismatch.
- No `pytest` suite exists anywhere in `backend/`, `mcp-server/`, or `eval/` — all correctness so far is `ruff`/`py_compile`/manual review, not automated tests.

**Known open issues (from the backend p3-triage report, not yet fixed):**
- `domain_lib/corpus.py`'s `fetch_pubmed()` always sets `abstract: ""` — PubMed's ESummary endpoint doesn't return abstracts, so every PubMed-sourced paper (medicine, agriculture, environmental_science all list `pubmed` as a source) silently degrades embedding/LLM-context quality while reporting a normal ingestion success. Needs a switch to EFetch or an abstract-fetch fallback.
- `mcp-server/tools/pipeline.py`'s `pipeline_status` docstring still claims it returns "all runs if run_id is omitted" — it actually returns a clean error. Misleading to an agent trusting the tool description.
- Gold question sets are only ~2 questions per domain and `expects_citation` is parsed but never scored — low statistical weight per eval run.
- A stray `# noqa: BLE001` in `main.py:53` is now flagged unused by `ruff` (RUF100) — cosmetic, `ruff --fix` clears it.
- `recall_at_k` in the eval harness reports `null` for every domain — no gold question file has `relevant_ids` annotated yet (by design for Phase 1, but it means retrieval-quality's recall panel is currently empty).

**Not started (explicitly deferred to Phase 2 by the approved plan):**
- Full-text ingestion (arXiv PDF, PubMed Central OA subset, Semantic Scholar open-access PDFs) — Phase 1 is abstract-only by design.
- True structure-aware parent-child chunking over full text (current chunking is just title+abstract as one unit).
- Citation granularity moving from paper-level to section/table-level.
- Re-tuning `RERANK_ABSTAIN_THRESHOLD` and gold questions once full-text recall is measurable — current abstract-only numbers aren't a fair Phase 2 baseline.

**Not yet exercised this session:**
- `frontend-review` and `backend-review` haven't actually been run yet — they exist as agents/commands but no findings/KPI table has been produced from them.
- The ingestion corpus (48 points across 6 domains) is thin — a fuller ingestion pass per domain would make retrieval-quality numbers and demo answers more convincing.

## Ideas to improve the application further

- **Close the PubMed abstract gap** (above) — it's the single highest-leverage retrieval-quality fix available right now, since it silently degrades 3 of 6 domains.
- **Add a real `pytest` suite** for `backend/` — retrieval logic (fusion, rerank, abstention gate, citation binding) and the ingestion idempotency guarantee (`uuid5` re-ingestion) are exactly the kind of logic that regresses silently without one.
- **Annotate `relevant_ids`** for at least a handful of gold questions per domain so `recall@k` stops reporting `null` and the retrieval-quality dashboard becomes a real signal instead of an empty panel.
- **Run `frontend-review` and `backend-review` now that the stack is live** — their KPI tables were designed to use real measured numbers (bundle size, image size, p95 latency, token cost) rather than guesses; those numbers only exist once the reviews are actually run against the running stack.
- **Widen the ingested corpus per domain** before any demo — 48 points total (~8/domain) is enough to prove the pipeline works end-to-end but too thin to show off retrieval quality or trigger interesting abstentions.
- **Phase 2 full-text ingestion** is the natural next big lever on answer quality — abstracts cap how specific/detailed an answer can ever be, and several open questions in the gold sets (table-based, SOP-style specifics) are designed to only pass once full text is available.
