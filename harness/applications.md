---
tier: 1
type: "Concept Anchor"
title: "Applications"
description: "Root concept anchor pointing to per-application documentation under docs/<app-name>/."
tags: [applications, concept-anchor]
context_tier: 1
---

# Applications

Each sub-application is documented under `docs/<app-name>/`, including the pervasive, cross-cutting ones (Core Domain, Events) — see [docs/index.md](../docs/index.md) for the full bundle index. This file (harness) covers the convention; the actual per-app content lives in `docs/` (project-specific), not here.

## Authorization stays at Tier 1/2

Authorization is critical enough that its context stays at Tier 1/2 alongside architecture and UX rules, rather than moving under `applications/`.

| Application | Location | Reason |
| :--- | :--- | :--- |
| Authorization | `harness/Authorization/` | Every sub-app depends on the two-gate access model (capability + Data Domain scope). Always relevant, and load-bearing enough to keep at the top level. |

## Application convention

For every sub-application (fundamental or not):

```
docs/<app-name>.md                  ← Tier 1 anchor (code-free, ≤2 pages)
docs/<app-name>/                    ← Tier 2 deep specs
docs/<app-name>/skeleton_instructions.md  ← scan targets for LLM task setup
docs/<app-name>/{incidents,project_history,tech_debt,decisions_pending}/  ← per-app technical-decision tracking
```

The `skeleton_instructions.md` file lists which directories to scan before starting a task in that application. It mirrors the format of the skeleton instructions living in harness's Architecture/, UX_UI/, and Authorization/.

Cross-cutting technical decisions that don't belong to one app (spanning multiple apps, or about harness-side patterns) stay in `docs/technical_decisions/` instead of a per-app folder.

## Applications

| App | Status | Tier 1 anchor | Folder |
| :--- | :--- | :--- | :--- |
| Core Domain | Active | `docs/core_domain.md` | `docs/core_domain/` |
| Events | Active | `docs/events.md` | `docs/events/` |
| Asset Management | Active | `docs/assets.md` | `docs/assets/` |
| Administration | Active | — | `docs/administration/` |
| Parts | Active | — | `docs/parts/` |
