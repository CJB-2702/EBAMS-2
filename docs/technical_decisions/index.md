---
okf_version: "0.1"
type: "Index"
title: "Technical Decisions Knowledge Bundle"
description: "Locked engineering decisions, tech debt, incident takeaways, and archived starter-kit project history."
tags: [technical-decisions, index, okf]
context_tier: 1
personas: [backend]
---

# Technical Decisions

Per-event detail for the locked decisions, tech debt, and incident takeaways summarized in [../technical_decisions.md](../technical_decisions.md). Format specification: [../Context_Scaling/technical_decisions_system.md](../Context_Scaling/technical_decisions_system.md).

```
technical_decisions/
├── index.md              ← this file
├── history/               ← one file per significant design decision (event log)
├── tech_debt/             ← one file per known deferred work item
├── incident_history/      ← one file per notable bug / post-mortem
└── project_history/       ← archived starter kits and major work initiatives
```

When an incident produces a lasting constraint, that constraint must also be surfaced in the base [../technical_decisions.md](../technical_decisions.md) summary so it is always in context.

## Sub-directories

- `history/` — dated records of past architectural renames and migrations (e.g. ownership → Data Domain).
- `incident_history/` — postmortems for bugs and failed approaches (e.g. the web component tab incident).
- `tech_debt/` — open (and `resolved/`, `decisions_pending/`) tech debt notes, dated by discovery.
- `project_history/` — archived starter kits and major work initiatives, logged via `/kit-complete`. See [project_history/project_history.md](project_history/project_history.md) for the chronological index.

This index intentionally does not enumerate every file in `project_history/` — each archived kit is a self-contained folder of phase docs; use `project_history/project_history.md` to find a specific one.
