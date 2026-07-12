---
type: Skeleton Bundle
title: Domain Service / Maintenance Skeleton
description: A context-scan skeleton for control-layer and model changes on a sub-application.
tags: [architecture, skeleton, context-scaling, control-layer]
---

# Domain service / maintenance — skeleton bundle

For task types: write a new control-layer handler, refactor a context, add a domain struct, change a model on a sub-application.

## Scan targets (run codebase mapping script against each)

- `app/<target_app>/control_layer/` — handlers, contexts, structs, guards.
- `app/<target_app>/models/` — schema and constraints for the domain.
- `app/<target_app>/presentation_layer/search/` — read-side loaders that feed the structs.
- `app/events/` — event integration layer if the domain emits events or uses comments/files.

### Run codebase mapping script

```bash
python dev_tools/get_models_and_control.py --application <target_app>
```
*(If event integration is needed, also run for `events`: `python dev_tools/get_models_and_control.py --application events`)*

## Load alongside scan (Tier 2 docs)

- `docs/Architecture/layer_rules.md` — reads vs writes; what may live in an entrypoint.
- `docs/Architecture/patterns/oop_control_patterns.md` — class-suffix vocabulary, playbook for new features.
- `docs/Architecture/patterns/model_patterns.md` — audit columns, abstract bases, PK choice.

## Skip

- `app/<target_app>/templates/` — UI files not relevant to domain service work (use the UI bundle if templates are involved).
- `app/<target_app>/migrations/` — generated; do not hand-edit unless writing a `RunPython` step.
- `app/public_app/` — unauthenticated routes only; not the right place for domain logic.
