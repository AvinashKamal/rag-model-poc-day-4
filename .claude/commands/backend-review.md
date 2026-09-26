---
description: Run the read-only backend code-quality review (reusability, dependency footprint, performance, API usability, efficiency) and get a KPI baseline/target table.
argument-hint: [optional focus area, e.g. "just performance"]
---

Launch the `backend-review` subagent (via the Agent tool, `subagent_type: "backend-review"`) to run a full read-only code-quality review of `backend/**`, `mcp-server/**`, `load-tests/**`, `eval/**`, and `shared/domain_lib/**`.

If arguments were given ($ARGUMENTS), narrow the review to that focus while still producing the full KPI table at the end. Otherwise run the complete checklist as defined in `.claude/agents/backend-review.md`.

Report the agent's findings and KPI table back in full — do not summarize away specific file:line references or measured numbers.
