---
type: "Skeleton Bundle"
title: "Asset Management — skeleton bundle"
description: "For task types: build or modify the asset management sub-application (models, control layer, endpoints, templates)."
tags: [applications, skeleton-bundle, assets]
context_tier: 2
---

# Asset Management — skeleton bundle

For task types: build or modify the asset management sub-application (models, control layer, endpoints, templates).

> **Stub** — populate scan targets once the application is scaffolded.

## Scan targets (add as built)

- `app/assets/control_layer/` — handlers, managers, domain structs.
- `app/assets/models/` — Asset and related models.
- `app/assets/presentation_layer/entrypoints/` — endpoint routing.
- `app/assets/templates/` — Bulma + HTMX templates.

## Load alongside scan

- `docs/assets.md` — application overview and scope anchors.
- `harness/Architecture/layer_rules.md` — reads vs writes.
- `harness/Authorization/data_ownership.md` — Golden Rule and domain scoping.
- `docs/events/events.md` — how to emit events from this app.

## Key reminders

- Every asset row must carry a `domain_id`. No domain-less assets.
- Lifecycle transitions go through an event (use `EventHandler.create()`).
- Control layer never sees hashids — decode at the URL boundary.
