---
description: Run the read-only frontend code-quality review (reusability, bundling, performance, accessibility, efficiency) and get a KPI baseline/target table.
argument-hint: [optional focus area, e.g. "just accessibility"]
---

Launch the `frontend-review` subagent (via the Agent tool, `subagent_type: "frontend-review"`) to run a full read-only code-quality review of `frontend/**`.

If arguments were given ($ARGUMENTS), narrow the review to that focus while still producing the full KPI table at the end. Otherwise run the complete checklist as defined in `.claude/agents/frontend-review.md`.

Report the agent's findings and KPI table back in full — do not summarize away specific file:line references or measured numbers.
