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
- **Version control:** git repo initialized 2026-09-26, pushed to `https://github.com/AvinashKamal/rag-model-poc-day-4` (public).

## v0 → v1 comparison

"v0" = state as of 2026-09-19 (original Phase 1 build, plus that day's own p3-triage P1 fixes: httpx timeouts, dependency floors, CORS). "v1" = state as of this snapshot, after 2026-09-26's backend refactor, two rounds of frontend redesign, and real `backend-review`/`frontend-review` KPI passes actually run against the current code (the v0 side of this table has no equivalent measured pass — those two review agents didn't exist yet on 09-19, so v0 numbers below are reconstructed from that day's ledger entries and p3-triage report, not a KPI table).

### Backend

| Metric | v0 (2026-09-19) | v1 (2026-09-26, measured) |
|---|---|---|
| PubMed abstract quality | `fetch_pubmed()` always returned `abstract: ""` (ESummary has no abstracts) — silently degraded medicine/agriculture/environmental_science | Fixed: real EFetch call, `_parse_pubmed_abstracts` parses structured `AbstractText` elements |
| Test coverage | 0% — no pytest suite existed anywhere | `backend/app`: 78% (389 stmts, 85 missed); `shared/domain_lib`: 0% (still no tests, 392 lines uncovered) |
| HTTP client timeouts | Missing at start of day; added same day (60s embed, 30s rerank) | Present + upgraded to singleton clients with `threading.Lock` double-checked pattern for all 4 upstream clients |
| Dependency pinning | Unpinned at start of day; floors added same day for fastapi/uvicorn/qdrant-client/openai/opentelemetry-* | All of 09-19's pins still hold, but `pydantic-settings` (used directly by `Settings`) has no floor — missed by both the 09-19 fix and this session's refactor |
| Eval gold set size | 2 questions/domain, `relevant_ids` unannotated (`recall@k` always `null`) | 24 questions (4/domain × 6), `relevant_ids` populated for citation-bearing questions |
| Secrets in logs/traces | Not checked | **New P1**: `NCBI_API_KEY` is a PubMed URL query param; any failed PubMed call propagates the raw key into OTel trace spans and application logs |
| SSRF / local-only guard | Not checked | **New P1**: `_localguard.target_is_local()` uses substring containment (`"evil-backend.attacker.com" in base_url` style check) — bypassable, confirmed via direct execution |
| `/query` 502 path test coverage | N/A (no tests existed) | Still untested at the `TestClient` HTTP layer — `UpstreamServiceError`→502 mapping only exercised via direct `answer_query()` unit calls |
| ruff import-sort errors | Not tracked | 3 (1 each in `test_ingestion_pipeline.py`, `test_main.py`, `test_retrieval_query.py`) — auto-fixable, still unfixed |
| Docker image size (backend) | Not measured | 443MB disk / 105MB content — single-stage build bakes in a ~61MB `pip install uv` bootstrap layer |
| Cyclomatic complexity | Not measured | `radon cc`: 74 blocks, avg A (2.55), worst C (13, `answer_query` — reasonable for a 5-stage pipeline) |
| CORS | Missing until fixed same day 09-19 | Fixed, unchanged since |

### Frontend

| Metric | v0 (2026-09-19) | v1 (2026-09-26, measured) |
|---|---|---|
| Visual design | Functional but plain — standard rounded cards/buttons/form fields, blue accent, system fonts. User later called this "boring." | Two redesign rounds: v1 (WCAG AA contrast pass, semantic labels, error boundary, stable callbacks, token dedup) then v2 (vermillion accent, `next/font/google` Archivo + IBM Plex Mono, radius scale flipped to sharp/0, asymmetric flush-left layout, motion tokens) |
| Bundle size (`/` route) | Not measured (review agent didn't exist yet) | First Load JS 126 kB (route-specific 39.1 kB + shared 87.3 kB) |
| Code splitting | Not measured | **Finding**: `AnswerPanel` + `react-markdown` are statically imported into the initial chunk despite only rendering after a query resolves — never `next/dynamic`-split |
| Citation-safety (untrusted model output) | Fixed same day 09-19 (P1: out-of-range `[99](url)` marker could render as a live external link) | Unchanged/verified — non-citation hrefs always render inert, confirmed byte-identical logic across both redesign rounds |
| Accessibility violations | 1 fixed same day (citation link hijack risk, not a contrast issue) | **New P1 (v2 regression)**: `CitationCard`'s bibliography index numeral is `color: var(--gridline)` — measured 1.24–1.29:1 contrast in both themes, fails even the large-text 3:1 AA floor, and is the only visible link between an inline `[n]` marker and its citation |
| `StatusPanel` error icon contrast | Not checked | Confirmed non-violation on independent recheck: 4.80:1 light / 3.23:1 dark, but icon is `aria-hidden` and decorative so it clears the 3:1 non-text bar; still hardcoded hex instead of a token |
| Test coverage | 0% — no test runner configured | Still 0% — no jest/vitest config, no test files anywhere under `frontend/**` |
| `npm run lint && npm run build` | Clean (09-19) | Clean, unchanged bundle size across the v2 restyle (126 kB before and after) |
| Design token hygiene | 3-tier radius system documented, not unified | v2's "Shape Consistency Lock" collapsed the whole radius scale to one token value (`0`); 2 remaining hardcoded hex colors in `StatusPanel.module.css` bypass the token layer |

## What's done

**Backend (all milestones from the Phase 1 plan, §1–§6, plus the 09-26 refactor):**
- Domain registry + `shared/domain_lib` extraction, 6 real domains with keyword sets and source lists.
- Real ingestion pipeline: `POST /admin/ingest`, `GET /admin/ingest/{run_id}`, idempotent upserts (`uuid5(source:paper_id)`) into Qdrant's `literature` collection (dense + sparse named vectors).
- `POST /query`: hybrid dense+sparse retrieval (Qdrant Query API, RRF fusion) → rerank via TEI → abstention gate (`RERANK_ABSTAIN_THRESHOLD`) → OpenRouter generation with untrusted-data framing → citations bound strictly to reranked candidates, never free-text.
- `GET /domains` — frontend's only source of truth for the domain list.
- OTel metrics wired (`rag_retrieval_hit_rate`, `rag_llm_tokens_total`) alongside existing traces.
- `eval/run_eval.py` rewritten to call the real `/query` endpoint, score abstention accuracy + a new LLM groundedness-judge step, push metrics via OTLP. 24 gold questions across all 6 domains, `relevant_ids` now populated.
- CORS fixed.
- `fetch_pubmed()` switched to real NCBI EFetch — no more silently-empty abstracts for PubMed-sourced papers.
- 18-test pytest suite added for `backend/app` (78% coverage): abstention gate, citation-binding, ingestion idempotency.
- All 4 upstream HTTP clients (embeddings/reranker/llm/qdrant) upgraded to singleton pooled clients with explicit timeouts.

**Frontend:**
- Full query UI: domain selector (live from `/domains`), question form, answer panel (citations rendered as `[n]` → anchors, never live-linked from untrusted model text), score meter, status panel for loading/error/abstained states.
- Two redesign rounds completed this session (see comparison table above) — v1 for accessibility/architecture, v2 for a drastic visual overhaul the user explicitly requested after rejecting v1 as too conservative.
- `npm run lint` and `npm run build` clean throughout both redesign rounds; 126 kB First Load JS unchanged.

**Infra / running stack:** `docker compose` is up — backend, frontend, Qdrant, embeddings (TEI), reranker (TEI), OTel collector, Prometheus, Loki, Tempo, Grafana all healthy. `literature` collection currently holds 48 points across the 6 domains. Live `/health` and `/domains` both respond correctly.

**Knowledge graph:** graphify has run against all 6 domains' ingested batches — `obsidian-vault/literature/<domain>/` populated for medicine, logistics, manufacturing, agriculture, environmental_science, and energy, plus community/relationship notes at the vault root.

**Orchestration tooling:** `frontend-review` and `backend-review` subagents — dedicated, read-only, KPI-producing code-quality reviewers — plus `/frontend-review` and `/backend-review` slash commands. Both have now actually been run against the live v1 codebase (results folded into the comparison table above), closing the gap flagged in the previous snapshot.

**Process / project hygiene (2026-09-26):**
- Root-caused and fixed a silent `SubagentStop` capture-hook failure that had been dropping every milestone entry this session into `.claude/PROJECT_STATE.md` (wrong transcript-path field, plus a `SubagentHandback` tool-call content shape the hook never checked). Ledger backfilled with the real entries.
- Repo brought under version control (`git init`, initial commit, `.gitignore` covering `.env`/`node_modules`/`.venv`/build artifacts) and pushed to GitHub at `https://github.com/AvinashKamal/rag-model-poc-day-4` via `gh` (installed and authenticated this session).

## What's left to do

**New findings from this session's `backend-review`/`frontend-review` passes, not yet fixed (highest priority first):**
- **P1 — secret leak into logs/traces**: `shared/domain_lib/src/domain_lib/corpus.py` passes `NCBI_API_KEY` as a URL query param; any failed PubMed call (429, 5xx, network blip) propagates the raw key into OTel spans and application logs via `httpx.HTTPStatusError`'s string representation. Fix: strip query params before logging/recording exceptions, or move the key to a header.
- **P1 — SSRF guard bypassable**: `mcp-server/src/orchestrator_mcp/tools/_localguard.py`'s `target_is_local()` uses substring containment instead of proper URL-host parsing — `"http://evil-backend.attacker.com" ` passes. Fix: `urllib.parse.urlsplit(base_url).hostname in _ALLOWED_HOSTS`.
- **P1 — CitationCard index numeral contrast**: `color: var(--gridline)` on the bibliography index numeral measures 1.24–1.29:1 (light/dark), failing AA even at large-text size — this is the only visual link between an inline `[n]` marker and its citation. Likely a v2 redesign regression (`--gridline` chosen as a border color, never vetted as text). Fix: recolor to `--text-secondary` or `--accent-strong` (both ≥5:1 against both surfaces per existing measurements).
- **P1 — 502 path untested**: `UpstreamServiceError`→502 mapping in `main.py`'s `/query` handler has no `TestClient`-level test exercising it end-to-end.
- **P2 — ruff import-sort**: 3 auto-fixable `I001` violations (`test_ingestion_pipeline.py`, `test_main.py`, `test_retrieval_query.py`).
- **P2 — `pydantic-settings` unpinned** in `backend/pyproject.toml`, unlike every sibling dependency.
- **P2 — `shared/domain_lib` has zero tests** (392 lines, 0% coverage) despite being correctness-critical shared code for both `backend` and `mcp-server`.
- **P2 — OpenAPI schema incomplete**: `/admin/ingest`, `/admin/ingest/{run_id}`, `/query` only declare 200/422 — the real 400/404/502 paths exist in code but aren't declared, invisible to schema-driven clients.
- **P2 — `AnswerPanel`/`react-markdown` not code-split** from the initial route bundle despite only rendering post-query.
- **P3 — 0% frontend test coverage**, no jest/vitest configured.
- **P3 — no length validation** on `QueryRequest.question` / `IngestRequest.query` (empty string passes, still drives a full pipeline round trip).
- **P3 — `StatusPanel` hardcoded hex colors** (`#fff`, `#3a2900`) bypass the token layer; not a live violation but a maintenance risk (this is likely how the CitationCard regression above slipped through unnoticed).

**Not started (explicitly deferred to Phase 2 by the approved plan):**
- Full-text ingestion (arXiv PDF, PubMed Central OA subset, Semantic Scholar open-access PDFs) — Phase 1 is abstract-only by design.
- True structure-aware parent-child chunking over full text (current chunking is just title+abstract as one unit).
- Citation granularity moving from paper-level to section/table-level.
- Re-tuning `RERANK_ABSTAIN_THRESHOLD` and gold questions once full-text recall is measurable — current abstract-only numbers aren't a fair Phase 2 baseline.

**Still thin, not yet addressed:**
- The ingestion corpus (48 points across 6 domains) is unchanged this session — still thin for a convincing demo.
- No live k6/eval run against a reachable stack happened this session (both backend-review/frontend-review ran source-level checks only — no live TEI/Qdrant/OpenRouter/OTel collector was reachable in that environment).

## Ideas to improve the application further

- **Fix the two new P1 security findings first** (NCBI key leak, SSRF substring bypass) — both are quick, contained fixes with disproportionate risk if left in place.
- **Fix the CitationCard contrast regression** — one-line CSS fix, closes a real accessibility violation introduced by the v2 redesign.
- **Add a `shared/domain_lib` test suite** — it's shared, correctness-critical code (including the just-fixed EFetch parsing) with zero coverage today.
- **Close the `/query` 502 path test gap** and the 3 ruff import-sort errors — both cheap, both flagged twice now (once by p3-triage, once by backend-review).
- **Code-split `AnswerPanel`/`react-markdown`** out of the initial frontend bundle — real, measured 39.1 kB of route weight not needed on first paint.
- **Widen the ingested corpus per domain** before any demo — 48 points total (~8/domain) is enough to prove the pipeline works end-to-end but too thin to show off retrieval quality or trigger interesting abstentions.
- **Phase 2 full-text ingestion** is the natural next big lever on answer quality — abstracts cap how specific/detailed an answer can ever be.
