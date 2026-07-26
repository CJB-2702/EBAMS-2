---
okf_version: "0.1"
type: "Index"
title: "Applications Knowledge Bundle"
description: "Per-application documentation for sub-applications, including the pervasive foundational ones (Core Domain, Events) and self-contained feature applications."
tags: [applications, index, okf]
context_tier: 1
personas: [business]
---

# Applications

Documentation for sub-applications, filed under `docs/<app-name>/`. See [../harness/applications.md](../harness/applications.md) for the per-application convention (`<app-name>.md` Tier 1 anchor, `<app-name>/` Tier 2 specs, `<app-name>/skeleton_instructions.md` scan targets) and for why Authorization alone stays outside this folder.

- [Core Domain](core_domain.md) — shared business entities and the domain/organization/division hierarchy every sub-application depends on.
- [core_domain/](core_domain/index.md) — Tier 2 guides: core models, divisions.
- [Events](events.md) — events sub-application: comments, files, shadow history, contexts.
- [events/](events/index.md) — Tier 2 guides and skeletons for the events sub-application.
- [Asset Management](assets.md) — assets sub-application: extensions, modification applicability, capabilities.
- [assets/](assets/index.md) — Tier 2 guides, UI plan, and skeleton bundle for the assets application.
- [administration/](administration/) — RBAC, ownership groups, user assignments; per-app technical-decision history.
- [parts/](parts/) — part demand tracking; per-app technical-decision history.

Cross-cutting technical decisions that don't belong to one app live in [technical_decisions/](technical_decisions/index.md) instead.

## Folders in this directory

| Folder | Application | Status |
| :--- | :--- | :--- |
| `core_domain/` | Core Domain | Active |
| `events/` | Events | Active |
| `assets/` | Asset Management | Active |
| `administration/` | Administration | Active |
| `parts/` | Parts | Active |
| `technical_decisions/` | (cross-cutting, not an application) | — |
