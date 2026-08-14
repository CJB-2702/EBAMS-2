---
okf_version: "0.1"
type: "Index"
title: "Technical Decisions Knowledge Bundle"
description: "Cross-cutting engineering decisions and tech debt that don't belong to a single application, plus the master project-history index."
tags: [technical-decisions, index, okf]
context_tier: 1
personas: [backend]
---

# Technical Decisions

Most technical-decision content now lives **per application** — see `docs/<app-name>/{incidents,project_history,tech_debt,decisions_pending}/`. This folder holds only the items that are genuinely cross-cutting: spanning multiple applications, or about harness-side (dev-process) patterns rather than one app's business behavior. Format specification: [../../harness/Context_Scaling/technical_decisions_system.md](../../harness/Context_Scaling/technical_decisions_system.md).

```
technical_decisions/
├── index.md              ← this file
├── project_history.md    ← master chronological index of every archived kit, across all apps
├── tech_debt/             ← cross-cutting deferred work items (not tied to one app)
└── decisions_pending/     ← cross-cutting open design questions (not tied to one app)
```

## Contents

- `tech_debt/` — cross-cutting tech debt notes, dated by discovery. App-specific tech debt lives under that app's own `tech_debt/` instead.
- `decisions_pending/` — cross-cutting open design questions that span multiple applications (including apps not yet built). App-specific open questions live under that app's own `decisions_pending/` instead.
- `project_history.md` — the chronological log of every kit archived via `/kit-complete`, regardless of which app it belongs to. The archived kit folders themselves live under `docs/<app-name>/project_history/<kit-name>/`, not here.

App-specific incidents, decisions pending, and project history live under each application's own folder, not in this one.
