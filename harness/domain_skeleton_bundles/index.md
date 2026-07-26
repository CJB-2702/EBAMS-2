---
okf_version: "0.1"
type: "Index"
title: "Domain Skeleton Bundles"
description: "Router to the per-domain skeleton_instructions.md files, which each carry their own codebase-mapping scan targets."
tags: [skeleton, context-scaling, index, okf]
context_tier: 1
personas: [backend, frontend, admin]
---

# Domain Skeleton Bundles

Skeleton bundles are no longer standalone files here — each lives as the `skeleton_instructions.md` in its Tier 1 concept folder, with a "Run codebase mapping script" note folded into its scan targets. This directory is the canonical spec location (see [../Context_Scaling/domain_skeleton_bundles_spec.md](../Context_Scaling/domain_skeleton_bundles_spec.md)); use the links below to jump straight to a bundle.

- [Domain Service / Maintenance — Skeleton Bundle](../Architecture/skeleton_instructions.md) — backend services, control layer, domain logic changes.
- [UI / Frontend — Skeleton Bundle](../UX_UI/skeleton_instructions.md) — frontend templates, Bulma layout, HTMX interactivity.
- [RBAC / Authorization / Domain Scope — Skeleton Bundle](../Authorization/skeleton_instructions.md) — authorization, permission templates, roles, domain templates.
- [Events Integration — Skeleton Bundle](../../docs/events/skeleton_instructions.md) — integrating other apps with the events sub-application.
