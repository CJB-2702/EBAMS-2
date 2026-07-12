---
okf_version: "0.1"
type: "Index"
title: "Architecture Knowledge Bundle"
description: "Layer rules, OOP control patterns, and engineering standards for the Django project — the OKF pilot bundle."
tags: [architecture, index, okf]
---

# Architecture

The source-of-truth architecture docs for this project, packaged as an
[Open Knowledge Format](https://github.com/GoogleCloudPlatform/knowledge-catalog/tree/main/okf)
(OKF v0.1) bundle. Each file carries YAML frontmatter (`type`, `title`,
`description`, `tags`) so agents and tooling can route and filter by kind.

## Guides

- [Architecture Overview](overview.md) — layered sub-application layout and layer responsibilities.
- [Layer Rules (Reads vs Writes)](layer_rules.md) — where reads and writes may run.
- [OOP Control-Layer Patterns](patterns/oop_control_patterns.md) — the class-suffix vocabulary.
- [Endpoint Patterns](patterns/endpoint_patterns.md) — object-oriented entrypoint design.
- [HTMX Patterns](patterns/htmx_patterns.md) — progressive enhancement conventions.
- [Model Patterns](patterns/model_patterns.md) — model naming, grouping, and constraints.
- [Seeding Plan](seeding.md) — fixtures and dev-data rules.
- [Engineering Standards](standards.md) — core principles and defaults.
- [Testing Conventions](tests.md) — how tests are written and organized.

## Skeletons

- [Domain Service / Maintenance Skeleton](skeleton_instructions.md) — context-scan bundle for control-layer and model changes.

## Sub-bundles

- `patterns/` — endpoint, HTMX, model, and OOP control-layer pattern guides.
- [Examples/](Examples/index.md) — concrete markup and code shapes for the guides above.
- [vocabulary/](vocabulary/index.md) — house vocabulary mapped to canonical GoF/Fowler patterns.
