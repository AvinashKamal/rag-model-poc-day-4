# Project State — compact ledger

Append-only. One entry per completed subagent milestone, written by the `capture_subagent_summary.sh` `SubagentStop` hook from the agent's `STATUS / FILES_CHANGED / KEY_DECISIONS / OPEN_ISSUES` block. This file is what gets read into a new delegation prompt — never a full transcript replay.

Entry format:
```
## <ISO date> — <agent> — <one-line task>
STATUS: <done|blocked|partial>
FILES_CHANGED: <paths>
KEY_DECISIONS: <bullets>
OPEN_ISSUES: <bullets, or "none">
```

---

## 2026-09-19 — backend — domain registry (6 domains) + shared/domain_lib extraction
STATUS: done
FILES_CHANGED: config/domains.yaml, shared/domain_lib/** (new), mcp-server/src/orchestrator_mcp/tools/corpus.py, mcp-server/src/orchestrator_mcp/tools/domain_tagging.py, backend/pyproject.toml, mcp-server/pyproject.toml
KEY_DECISIONS:
- Registry expanded from the plan's original 3 domains to 6 per explicit user request: medicine, logistics, manufacturing, agriculture, environmental_science, energy — real keyword sets for all 6, registry designed for config-only future additions.
- domain_lib.tagging tie-break for overlapping keyword vocab (env-science/agriculture/energy) resolved by YAML declaration order; documented in code comment.
- domain-lib wired as a local editable path dependency in both backend/pyproject.toml and mcp-server/pyproject.toml; mcp-server's corpus.py/domain_tagging.py are now thin re-export shims, server.py's import surface unchanged.
OPEN_ISSUES: none

## 2026-09-19 — backend — real ingestion pipeline + /admin/ingest endpoints + mcp-server pipeline.py rewrite
STATUS: done
FILES_CHANGED: backend/app/ingestion/pipeline.py, backend/app/ingestion/state.py, backend/app/ingestion/__init__.py, backend/app/schemas.py, backend/app/main.py, backend/app/clients/qdrant_client.py, backend/app/clients/embeddings_client.py, mcp-server/src/orchestrator_mcp/tools/pipeline.py
KEY_DECISIONS:
- run_ingestion validates domain via registry, fetches via domain_lib.corpus, tags for observability only (requested domain always wins over a tag mismatch, logged not dropped), uuid5(NAMESPACE, "source:paper_id") point ids for idempotent re-ingestion.
- Qdrant literature collection created idempotently with named dense (1024, cosine) + sparse vectors in qdrant_client.ensure_literature_collection().
- embeddings_client.embed_sparse() added against an unverified assumption about TEI's /embed_sparse response shape — flagged as an open issue.
- mcp-server/pipeline.py rewritten as a thin HTTP proxy to /admin/ingest (mirrors k6.py's local-only base_url guard); server.py call sites unchanged.
OPEN_ISSUES:
- embed_sparse's TEI /embed_sparse contract assumption is unverified against a live TEI instance.
- No live docker-compose/Qdrant/TEI/OpenRouter calls were made — verification was mocked only.
- graphify still needs to be run live against obsidian-vault/literature/<domain>/ once a real docker-compose ingest happens (not invoked yet).

## 2026-09-19 — backend — /query + /domains endpoints + metrics instrumentation
STATUS: done
FILES_CHANGED: backend/app/config.py, backend/app/schemas.py, backend/app/main.py, backend/app/telemetry.py, backend/app/clients/reranker_client.py, backend/app/retrieval/query.py, backend/app/retrieval/__init__.py
KEY_DECISIONS:
- Confirmed via installed opentelemetry-instrumentation-fastapi==0.65b0 source that leaving OTEL_SEMCONV_STABILITY_OPT_IN unset already emits the OLD http.server.duration (ms) convention -> http_server_duration_milliseconds_bucket, matching rag-app.json exactly — left unset rather than reconciling.
- rag_retrieval_hit_rate implemented as a Histogram (0.0/1.0 per query) rather than ObservableGauge, since it's a per-call event not a sampled process value.
- Citations built strictly from reranked-candidate payload data by 1-based [n] position, never from model-generated text; untrusted-data framing wraps retrieved docs in a <documents> block per the prompt-injection non-negotiable.
- reranker_client.py's TEI /rerank response-shape and embed_sparse's /embed_sparse shape remain unverified documented assumptions (no live TEI reachable).
OPEN_ISSUES:
- reranker_client.py and embeddings_client.embed_sparse() need verification against a live TEI instance once docker compose is actually run.
- No pytest suite exists yet for backend/ — verification so far is py_compile + mocked ad hoc checks only.

## 2026-09-19 — backend — eval/run_eval.py upgrade + gold questions for 4 new domains
STATUS: done
FILES_CHANGED: eval/gold_questions/manufacturing.jsonl, agriculture.jsonl, environmental_science.jsonl, energy.jsonl (new), eval/run_eval.py (rewritten)
KEY_DECISIONS:
- run() now calls real POST /query per gold question, scores abstention_correct + recall@k (only when relevant_ids is populated, currently none are) + a new groundedness-judge LLM call (second cheap OpenRouter call) producing eval_groundedness_score/eval_unsupported_claim_rate.
- Eval harness duplicates its own OpenRouter client + OTLP MeterProvider/exporter setup rather than importing backend.app.* (backend isn't installed as a package here); pushes 4 aggregate metrics as OTel Gauges with 1000ms export interval + explicit shutdown() flush, matching exact names/labels retrieval-quality.json queries.
- Citation schema has no document-id field, so recall@k uses citation `url` as the retrieved-id surrogate — future relevant_ids annotation must use the same url values.
- Gracefully degrades at 3 levels: backend unreachable, /query error on one question, judge-call/parse failure on one question — none of these abort the whole run.
OPEN_ISSUES:
- Real end-to-end path (live backend, live OpenRouter judge call, live OTLP push) is unverified — no docker compose stack has been run yet. Verified via py_compile, ruff, and a stub httpx MockTransport + fake judge/meter-provider run only.

## 2026-09-19 — p3-triage — review of backend milestone (steps 1-4)
STATUS: done
FILES_CHANGED: none (read-only review)
KEY_DECISIONS: No live Grafana/Prometheus/Qdrant/TEI/OpenRouter reachable — all checks static (source reading, py_compile, direct interrogation of installed library versions). Verified clean: Qdrant Query API surface real and correct against installed qdrant-client 1.19.1; [n]-citation extraction only binds to real candidates, can't be hijacked by untrusted document content; 6-domain tagging tie-break correct, zero exact keyword overlaps across domains; embed_sparse/rerank TEI shape assumptions internally consistent with consumers (still unverified live, as already flagged); OTEL_SEMCONV_STABILITY_OPT_IN reasoning reproduced correct against installed instrumentation source; eval + telemetry metric names/labels match both dashboard JSONs exactly; no secrets leaked anywhere.
OPEN_ISSUES:
- P1: embeddings_client.py/reranker_client.py httpx calls have no explicit timeout (inherit httpx's 5s default) — TEI CPU inference on 40-100 docs plausibly exceeds this, producing a hard 500/failed background job instead of the intended graceful abstain path.
- P1: backend/pyproject.toml has zero version floors on qdrant-client/openai/fastapi/uvicorn/httpx/opentelemetry-* — all correctness verification above only holds for the exact versions currently installed; an unpinned fresh install could silently break retrieval or metrics.
- P2: mcp-server/tools/pipeline.py's pipeline_status docstring ("or all runs if run_id is omitted") no longer matches real behavior (returns a clean error instead) — misleading to an agent trusting the tool description, not a functional bug.
- P2: domain_lib/corpus.py's fetch_pubmed() always sets abstract:"" (ESummary doesn't return abstracts) — silently degrades embedding/LLM-context quality for every PubMed-sourced paper (medicine/agriculture/environmental_science), reported as a normal ingestion success.
- P3: eval gold sets are only 2 questions/domain and expects_citation is parsed but never scored — low statistical weight per eval run.

## 2026-09-19 — backend — fixed p3-triage P1s (timeouts + dependency pinning)
STATUS: done
FILES_CHANGED: backend/app/clients/embeddings_client.py, backend/app/clients/reranker_client.py, backend/pyproject.toml
KEY_DECISIONS: Added explicit httpx timeout=60 (embed/embed_sparse, up to 100-doc batches) and timeout=30 (rerank, up to 40-doc batches) matching the repo's existing bare-numeric timeout style. Pinned backend/pyproject.toml deps to >= floors matching installed versions (fastapi, uvicorn, qdrant-client, openai, opentelemetry-*, httpx); mcp-server/domain_lib pyproject.toml files already had floors, no change needed.
OPEN_ISSUES: none. Backend milestone (steps 1-4 + P1 fixes) is now considered done — proceeding to frontend query UI.

## 2026-09-19 — frontend — query UI (§7): domain select, question form, answer+citations, design-rules revision
STATUS: done
FILES_CHANGED: frontend/app/page.tsx, page.module.css, globals.css, layout.tsx, types.ts, frontend/app/components/{ScoreMeter,DomainSelector,QuestionForm,StatusPanel,CitationCard,AnswerPanel}.tsx + .module.css, frontend/lib/api.ts, frontend/package.json
KEY_DECISIONS:
- Built against GET /domains and POST /query exactly as specified in backend/app/schemas.py (Domain{id,display_name}, QueryRequest, QueryResponse, Citation) — domain list never hardcoded.
- Decomposed into reusable components (DomainSelector, QuestionForm, StatusPanel, CitationCard, AnswerPanel, ScoreMeter) rather than one monolithic page.tsx.
- Answer rendered via react-markdown in default-safe mode (no rehype-raw, no dangerouslySetInnerHTML) since answer text is downstream of untrusted retrieved literature; [n] citation markers rewritten to #citation-n anchors pre-render.
- User-mandated design constraints applied and independently verified (grep + lint + build, not just subagent self-report): no em dashes, no emoji, no purple gradient, no AI-marketing copy, all local imports via @/ alias, design tokens (incl. spacing scale) in globals.css used throughout component CSS instead of ad hoc values, px minimized (only 1px hairline borders + em-based media breakpoints excepted), mobile-first CSS structure, CSS-only entrance animations respecting prefers-reduced-motion.
- QuestionForm owns its own keystroke state locally, bubbling only the trimmed submitted string via a stable onSubmit callback, so memo(QuestionForm) is a real optimization rather than a no-op.
OPEN_ISSUES: none. No live backend was reachable during this build — /domains and /query were coded against the documented schema, not exercised against a running server; still needs a real end-to-end pass once docker compose is up.

## 2026-09-19 — p3-triage — review of frontend query UI milestone
STATUS: done
FILES_CHANGED: none (read-only review)
KEY_DECISIONS: No grafana-mcp reachable — source-code-only review. Verified clean: QueryRequest/QueryResponse/Citation/Domain shapes match backend/app/schemas.py and main.py field-for-field; domains fetched live never hardcoded; [n] citation binding correct; no rehype-raw/dangerouslySetInnerHTML/any-casts/eslint-disable anywhere; all design-rule constraints (em dashes, emoji, @/ imports, design tokens, px minimization, mobile-first, reduced-motion) independently confirmed true in the actual files.
OPEN_ISSUES:
- P1 (fixed same session): AnswerPanel's AnswerLink rendered any non-citation-anchor href from the model's answer as a live external link, including an out-of-range [99](url) marker slipped into untrusted answer content — fixed by making every non-#citation-N href render as inert text instead of a link; re-verified via lint+build after the fix.
- P2 (fixed same session): memo(QuestionForm) was a no-op since `question` changed every keystroke — fixed by moving textarea state local to QuestionForm, bubbling only the submitted string.
- P3 (left as-is, reviewer's own judgment): duplicated hairline-border CSS comment across 7 module.css files — CSS Modules has no cross-file snippet-sharing mechanism in this project, not worth introducing a preprocessor for.

## 2026-09-19 — frontend — P1 fix: inert-rendered non-citation links in AnswerPanel + QuestionForm memo fix
STATUS: done
FILES_CHANGED: frontend/app/components/AnswerPanel.tsx, frontend/app/components/AnswerPanel.module.css, frontend/app/components/QuestionForm.tsx, frontend/app/page.tsx
KEY_DECISIONS:
- AnswerLink now only ever renders a real <a> for its own self-generated #citation-N anchors; every other href (in-range or not) renders as inert children with no wrapper — closes the p3-triage P1 without a URL-allowlist approach. Removed the now-dead .externalLink CSS class.
- QuestionForm now owns its own textarea state locally, bubbling only the trimmed submitted string via onSubmit(question) — makes memo(QuestionForm) a real optimization instead of a no-op; page.tsx's handleSubmit dropped `question` from its useCallback deps.
- Independently re-verified via lint + build (both clean) after the fix, not just the subagent's self-report.
OPEN_ISSUES: none. Frontend milestone (step 6-7 of the Phase 1 plan) is now considered done.

## 2026-09-19 — backend — CORS middleware fix (frontend/backend wiring gap)
STATUS: done
FILES_CHANGED: backend/app/config.py, backend/app/main.py
KEY_DECISIONS:
- User asked whether frontend/backend were wired properly; audit found zero CORS config on the FastAPI app while frontend (port 3001) and backend (port 8000) are different browser origins per docker-compose — every browser fetch from the frontend, especially the POST /query preflight, would have been blocked live despite the request/response schemas matching perfectly.
- Added Settings.CORS_ORIGINS (comma-separated str, default "http://localhost:3000,http://localhost:3001") + a cors_origins_list property, matching the existing plain-field Settings style; wired via CORSMiddleware in main.py with allow_credentials=False (endpoints use no cookies/auth headers).
- Confirmed FastAPIInstrumentor.instrument_app wraps the ASGI app directly rather than via add_middleware, so CORSMiddleware's placement relative to setup_telemetry(app) doesn't matter.
- infra/docker-compose.yml untouched — the new default already matches its existing port layout.
OPEN_ISSUES: none. Frontend/backend wiring (schema shapes + base URL + CORS) is now considered verified at the source level; still no live docker-compose run to confirm in a real browser.

## [removed 2026-09-26] Three duplicate/mislabeled "unknown"/"backend" CORS entries were here.
Root cause found and fixed 2026-09-26: `capture_subagent_summary.sh`'s hook script was
reading the SubagentStop payload's `transcript_path` (the *parent* session's shared
transcript) instead of `agent_transcript_path` (the subagent's own transcript), so every
firing that day scanned the same orchestrator conversation and re-captured whatever
STATUS-shaped text happened to be nearby — producing near-identical duplicates under
inconsistent agent-name labels instead of three real distinct events. A second bug
compounded it: recent reports are delivered via a `SubagentHandback` tool call
(`content` part `type: "tool_use"`, `name: "SubagentHandback"`, block in `input.message`)
rather than plain assistant text, which the script never inspected — silently dropping
every milestone this session (frontend v1, backend v1, frontend v2 below) even after the
transcript-path fix alone. Both are fixed in `.claude/hooks/capture_subagent_summary.py`.
The three corrupted entries were deleted rather than kept, since they described no real
independent event. Real milestones for this date, backfilled from each subagent's own
transcript, follow below.

## 2026-09-26 — frontend — v1 redesign (ui-ux-pro-max + design-taste-frontend)
STATUS: done
FILES_CHANGED: frontend/app/globals.css, frontend/app/page.tsx, frontend/app/page.module.css, frontend/app/error.tsx (new), frontend/app/error.module.css (new), frontend/app/components/AnswerPanel.tsx, frontend/app/components/AnswerPanel.module.css, frontend/app/components/StatusPanel.module.css, frontend/app/components/CitationCard.module.css, frontend/app/components/QuestionForm.tsx, frontend/app/components/QuestionForm.module.css, frontend/app/components/DomainSelector.tsx, frontend/app/components/DomainSelector.module.css, frontend/lib/api.ts
KEY_DECISIONS: kept CSS Modules (no Tailwind/Motion lib) since the task requires preserving mobile-first CSS structure; introduced --on-accent token instead of uniformly recoloring --accent in both modes, avoiding a broken dark-mode hover state; used compound selectors (.panel.error) instead of relying on composes stylesheet order for specificity; reused existing --status-critical token rather than inventing a new one for the DomainSelector error text; documented (not unified) the existing 3-tier radius system (lg outer / md nested / pill chips).
OPEN_ISSUES: no live browser/visual QA available in this environment; contrast fixes verified via computed relative-luminance ratios against the actual compiled CSS output, not visual inspection. (Superseded visually by the v2 redesign below — user found this result too conservative/boring.)

## 2026-09-26 — backend — v1 refactor (fetch_pubmed EFetch fix, pytest suite, client timeouts, OTel instrumentation)
STATUS: done
FILES_CHANGED: backend/app/{errors.py(new),main.py,schemas.py,telemetry.py,clients/{qdrant_client,llm_client,embeddings_client,reranker_client}.py,retrieval/query.py,ingestion/{pipeline.py,state.py}}, backend/pyproject.toml, backend/tests/{__init__,conftest,test_main,test_retrieval_query,test_ingestion_pipeline}.py, shared/domain_lib/src/domain_lib/{corpus.py,__init__.py}, mcp-server/src/orchestrator_mcp/{server.py,tools/{_localguard.py(new),pipeline.py,k6.py}}, eval/pyproject.toml(new), eval/gold_questions/*.jsonl, load-tests/k6/health_check_load.js
KEY_DECISIONS: fetch_pubmed() switched to real NCBI EFetch (was always abstract:""); added singleton pattern + explicit timeouts to all HTTP clients (LLM connect=5s/pool=60s, Qdrant=30s); added 18-test pytest suite (abstention gate, citation-binding, ingestion idempotency); annotated relevant_ids in gold_questions/*.jsonl so recall_at_k stops reporting null.
OPEN_ISSUES: p3-triage found 1 P1 (502-mapping path for UpstreamServiceError never exercised by a TestClient-level test — unit-tested only via direct answer_query() calls) and confirmed 3 ruff import-sort errors in test_retrieval_query.py (auto-fixable) that the build agent's "ruff clean" claim missed. Neither fixed yet.

## 2026-09-26 — frontend — v2 drastic redesign (vermillion accent, next/font, asymmetric sharp-radius layout)
STATUS: done
FILES_CHANGED: frontend/app/layout.tsx (next/font/google: Archivo + IBM Plex Mono, zero new deps); frontend/app/globals.css (full token rewrite: vermillion accent light+dark, meter ramp, font tokens, radius flip to 0, new stampIn/sweep keyframes; all surface/text/border/gridline/status tokens byte-preserved); frontend/app/page.tsx (className renames only — header->masthead, searchCard->console — hooks/handlers/refs untouched); frontend/app/page.module.css (full rewrite); frontend/app/components/{DomainSelector,QuestionForm,AnswerPanel,ScoreMeter,StatusPanel}.module.css (restyle only); frontend/app/components/CitationCard.tsx + .module.css (wrapper-markup only, oversized mono numeral); frontend/app/error.module.css (button restyle only)
KEY_DECISIONS: avoided composes: card-shell/eyebrow in AnswerPanel.answerCard/StatusPanel.panel/CitationCard.index (cross-stylesheet specificity risk with the new sharp-radius/font tokens), writing those rules self-contained instead; no new motion library (pure CSS keyframes, covered for free by the existing global prefers-reduced-motion override); dark-mode accent-strong hover fills paired with dark --on-accent ink, not white, to stay AA-compliant.
OPEN_ISSUES: no live "answer with citations" render captured (shared backend returned 500 on /query in the build agent's environment, backend/**-scope, not touched) — AnswerPanel/CitationCard rendering verified by code review + byte-diff of citation-safety logic only, not a live browser render. p3-triage confirmed no P0/P1; flagged (project-level, not this milestone) that this repo has no git/VCS and the capture hook above was broken all session — both addressed 2026-09-26.
