# Skills — when they fire on this project

This documents *this project's* usage of its skills. Most are globally-installed — see `~/.claude/skills/<name>/SKILL.md` for their definitions, not duplicated here. `graphify` is the exception: it's vendored project-locally at `.claude/skills/graphify/` (copied from the global install, same pattern as the `day 4` project's project-exclusive k6 skills) so this project's graphify behavior is pinned rather than drifting if the global copy changes.

| Skill | Fires when | Why here |
|---|---|---|
| `graphify` (project-local: `.claude/skills/graphify/SKILL.md`) | After each ingestion batch completes, run with `--obsidian --obsidian-dir "/home/labuser/POC RAG Model/obsidian-vault"` against the newly ingested corpus. | Produces the literature knowledge graph as the primary researcher-facing artifact — the whole reason graphify and Obsidian are non-negotiable requirements of this project. Vendored locally so it's exclusive to this project rather than shared/mutable global state. |
| `dataviz` | Before building or editing any Grafana panel, or any frontend chart/citation visualization. | Keeps the k6 dashboard, the RAG-app dashboard, and the retrieval-quality dashboard visually consistent instead of three different ad-hoc styles. |
| `frontend-design` (plugin: `frontend-design@claude-plugins-official`, enabled project-scope) | **Mandatory** before any new page, layout, or component is built or restyled in `frontend/**` — not optional, not skippable for "quick" UI changes. | User requirement: the frontend must be held to a real UX/UI design bar (production-grade, non-generic aesthetics) rather than default framework scaffolding. This is the only one of the three design skills the user asked for that actually exists — see note below. |
| `code-review` / `security-review` | On backend/frontend diffs, before the `p3-triage` agent runs its severity pass. | Cheap first filter — catches mechanical issues before triage spends effort on them. |
| `claude-api` | Before writing or editing any code that calls a Claude model. | Still applies even though the call is routed through OpenRouter (`openai`-compatible client) rather than the Anthropic SDK directly — model IDs, context windows, and pricing facts come from here; only the transport differs. |
| `workflow-authoring` | Not used yet. Available if multi-domain corpus ingestion (medicine, logistics, ...) is fanned out across parallel agents later, and only if the user explicitly opts into multi-agent orchestration at that point. | Documented so it isn't forgotten, not because it's active now. |

**Note on `ux-ui-pro-max` / `awesome-design`:** the user asked for these two as mandatory alongside `frontend-design`. Neither exists as an installed skill, a bundled skill, or a plugin in the official marketplace (checked `~/.claude/skills/`, bundled skills, and `claude-plugins-official`'s full catalog — no match, including fuzzy `ux`/`awesome` search). Only `frontend-design` is real and is now enabled and mandatory. If the user has a specific source for the other two (a marketplace URL, a private plugin repo), they need to be pointed to it explicitly before they can be wired in — they aren't skipped by choice, they just don't exist yet in any registry this environment can see.

## Delegation ↔ skill matrix

- `backend` agent: `claude-api`, `code-review`/`security-review`, `dataviz` (for the retrieval-quality dashboard panels it owns).
- `frontend` agent: `frontend-design` (mandatory, every UI build/restyle task), `dataviz` (mandatory, every chart/citation visualization), `code-review`/`security-review`.
- `p3-triage` agent: consumes the output of `code-review`/`security-review` rather than invoking skills itself; its job is synthesis, not another review pass from scratch. Also checks that `frontend`'s reported `KEY_DECISIONS` actually cite `frontend-design` usage when the task touched UI — flags it as an issue if a UI change shipped without it.
