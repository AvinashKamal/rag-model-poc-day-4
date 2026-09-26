---
description: Find security vulnerabilities across the whole app (secrets, SSRF, injection, unsafe rendering, auth gaps, dependency pinning), then fix the AUTO-FIXABLE ones and re-verify.
argument-hint: [optional focus area, e.g. "just backend" or "just the SSRF guard"]
---

Run a full security audit and fix pass:

1. Launch the `security-review` subagent (via the Agent tool, `subagent_type: "security-review"`) to scan the whole app per its checklist in `.claude/agents/security-review.md`. If arguments were given ($ARGUMENTS), narrow scope to that focus while still reporting the full severity/fix-classification table.

2. Read the report. For every finding tagged `AUTO-FIXABLE`, delegate the fix by path per this project's normal routing rule (see root `CLAUDE.md`):
   - Anything under `backend/**`, `mcp-server/**`, `shared/domain_lib/**`, `load-tests/**`, `eval/**` → the `backend` agent.
   - Anything under `frontend/**` → the `frontend` agent.
   - Batch all fixes for the same agent into one delegation (one prompt listing every AUTO-FIXABLE finding in that agent's scope with file:line and the exact fix), rather than one subagent call per finding.
   - Do not delegate `NEEDS-REVIEW` findings — report them to the user for a decision instead.

3. After the build agent(s) report their `STATUS/FILES_CHANGED/KEY_DECISIONS/OPEN_ISSUES` block, spawn `p3-triage` as the mandatory quality gate before considering the fix pass done — this is not optional per project convention.

4. Report back: what was found (full severity table), what got fixed (file:line per fix), what's still open (`NEEDS-REVIEW` items, plus anything p3-triage flagged), and update `PROJECT_STATUS.md`'s open-issues section to match reality.
