---
tier: 1
---

# Applications

Each self-contained sub-application (beyond the fundamental shared foundations) is documented under `docs/applications/<app-name>/`.

## Fundamental applications — stay at Tier 1/2

Authorization/CoreDomain and Events are so pervasive and cross-cutting that their context belongs at Tier 1/2 alongside architecture and UX rules. They are **not** housed here.

| Application | Location | Reason |
| :--- | :--- | :--- |
| Authorization / Core Domain | `docs/Authorization/`, `docs/CoreDomain/` | Every sub-app depends on the two-gate access model and the domain/org/division hierarchy. Always relevant. |
| Events | `docs/Events/` | Nearly every sub-app emits or consumes events; the event primitives (EventStruct, CommentContext, file handling) are called from everywhere. Always relevant. |

## Application convention

For every other sub-application:

```
docs/applications/<app-name>.md                  ← Tier 1 anchor (code-free, ≤2 pages)
docs/applications/<app-name>/                    ← Tier 2 deep specs
docs/applications/<app-name>/skeleton_instructions.md  ← scan targets for LLM task setup
```

The `skeleton_instructions.md` file lists which directories to scan before starting a task in that application. It mirrors the format of the skeleton instructions now living in Architecture/, UX_UI/, Authorization/, and Events/.

## Planned and active applications

| App | Status | Tier 1 anchor | Folder |
| :--- | :--- | :--- | :--- |
| Asset Management | Planned | `docs/applications/assets.md` | `docs/applications/assets/` |
