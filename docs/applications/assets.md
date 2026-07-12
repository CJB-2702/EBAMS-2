---
tier: 1
type: "Domain Doc"
title: "Asset Management"
description: "Concept doc for the planned Asset Management sub-application: lifecycle, ownership, and part demands."
tags: [applications, domain-doc, assets]
context_tier: 2
---

# Asset Management

The Asset Management sub-application tracks physical and virtual assets across the organizational hierarchy — including lifecycle state, ownership, part demands, and maintenance history.

## Status

Planned — not yet built.

## Scope anchors

- Assets are scoped to a **Data Domain** (the Golden Rule applies — `asset.domain_id in user_domain_ids`).
- Assets emit **Events** for lifecycle transitions (commissioning, decommissioning, repair requests).
- Asset part demands link assets to a parts/inventory domain (to be defined).

## Deep specs

- `docs/applications/assets/` — detail files added here as the application is designed and built.

## Skeleton instructions

For task setup (what to scan before starting an assets task): [skeleton_instructions.md](assets/skeleton_instructions.md) — add content when the application is scaffolded.
