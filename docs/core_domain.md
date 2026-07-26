---
tier: 1
type: "Domain Doc"
title: "Core Domain"
description: "Concept anchor for the shared business entities every other sub-application depends on: divisions, organizations, data domains, part definitions, part demands, and the typed link tables that connect them."
tags: [applications, domain-doc, core-domain]
context_tier: 2
---

# Core Domain

The shared business entities that every other sub-application depends on: divisions, organizations, data domains, part definitions, part demands, events, assets, files, and the typed link tables that connect them. Detail lives in the Tier 2 files below.

## Status

Active — foundational to every other sub-application.

## Core ideas

- **Domains are the centre of gravity.** Almost every scoped business row carries a single `domain` foreign key. That FK is the row-level access primitive (see [../Authorization.md](../harness/Authorization.md)) and the join axis for cross-app queries.
- **Hierarchy is informational.** Divisions contain organizations; organizations refer to many domains; domains may be referenced by multiple organizations (overlap is intentional). The hierarchy is for navigation, reporting, and admin warnings — not for access decisions.
- **Auditing is universal.** Every persisted table carries `created_at`, `updated_at`, `created_by_id`, `updated_by_id`. The user FK target is the project's custom user model.
- **Prerequisites are explicit.** Events, assets, and part demands all require a domain. Part demands additionally require a part definition. These "must-have" edges are enforced at the schema level, not as soft conventions.
- **Extension via typed link tables, not god-tables.** Comment attachments and maintenance attachments live in separate concrete tables with their own FK targets and defaults. A row that needs to be unioned across multiple link types uses UUID7 for cross-table uniqueness; everything else uses `BigAutoField`.
- **Events may reference assets optionally.** The link is one-way and optional, so timelines and asset-centric views are possible without requiring every event to be asset-bound.

## Deep specs

See [core_domain/index.md](core_domain/index.md) for the full, machine-routable index of Tier 2 guides (core models, divisions).

## Reference directionality

This anchor references **only** files inside `core_domain/`. Access enforcement against the Data Domain primitive is described in [../Authorization.md](../harness/Authorization.md); model patterns (audit columns, abstract bases, PK choice) live under [../Architecture.md](../harness/Architecture.md). The cross-cutting lines are summarised here so an entity question is answerable from this anchor plus its Tier 2 children alone.
