---
tier: 1
type: "Concept Anchor"
title: "Applications"
description: "Root concept anchor pointing to per-application documentation under docs/applications/<app-name>/."
tags: [applications, concept-anchor]
context_tier: 1
---

# Applications

Each sub-application is documented under `docs/applications/<app-name>/`, including the pervasive, cross-cutting ones (Core Domain, Events) — see [applications/index.md](applications/index.md) for the full bundle index.

## Authorization stays at Tier 1/2

Authorization is critical enough that its context stays at Tier 1/2 alongside architecture and UX rules, rather than moving under `applications/`.

| Application | Location | Reason |
| :--- | :--- | :--- |
| Authorization | `docs/Authorization/` | Every sub-app depends on the two-gate access model (capability + Data Domain scope). Always relevant, and load-bearing enough to keep at the top level. |

## Application convention

For every sub-application (fundamental or not):

```
docs/applications/<app-name>.md                  ← Tier 1 anchor (code-free, ≤2 pages)
docs/applications/<app-name>/                    ← Tier 2 deep specs
docs/applications/<app-name>/skeleton_instructions.md  ← scan targets for LLM task setup
```

The `skeleton_instructions.md` file lists which directories to scan before starting a task in that application. It mirrors the format of the skeleton instructions living in Architecture/, UX_UI/, and Authorization/.

## Applications

| App | Status | Tier 1 anchor | Folder |
| :--- | :--- | :--- | :--- |
| Core Domain | Active | `docs/applications/core_domain.md` | `docs/applications/core_domain/` |
| Events | Active | `docs/applications/events.md` | `docs/applications/events/` |
| Asset Management | Planned | `docs/applications/assets.md` | `docs/applications/assets/` |
