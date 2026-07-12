---
type: "Context Scaling Spec"
title: "Domain Skeleton Bundles — Specification"
description: "Bundle files live at docs/domain_skeleton_bundles/."
tags: [context-scaling, context-scaling-spec]
context_tier: 2
---

# Domain Skeleton Bundles — Specification

Bundles live inside each Tier 1 concept folder's own `skeleton_instructions.md` (e.g. `docs/Architecture/skeleton_instructions.md`, `docs/UX_UI/skeleton_instructions.md`, `docs/Authorization/skeleton_instructions.md`) or each application's own `skeleton_instructions.md` under `docs/applications/<app-name>/` (e.g. `docs/applications/events/skeleton_instructions.md`). `docs/domain_skeleton_bundles/` holds only this spec and a thin index that links out to them. They are **Tier 2** assets — loaded on-demand at the start of a specific task type, never globally.

Each bundle answers one question: *"For this kind of task, which application directories and core files should I run the codebase mapping script against?"*

---

## Purpose

Prevents the AI from deciding arbitrarily which folders to scan. Instead of exploring the directory tree from scratch, the AI reads the relevant bundle, runs the Tier 4 mapping script against the listed paths, and has targeted structural context before touching any source files.

---

## Bundle Section Rules

* **One `skeleton_instructions.md` per Tier 1 concept folder** — not per application. It covers the task types that belong to that concept: domain service, UI build, RBAC/permission change, event integration, etc.
* **Short** — a list of paths with one-line rationales. No prose paragraphs.
* **Three sections:** scan targets, Tier 2 docs to load alongside the scan, and what to skip.
* **Invocation note:** fold the exact codebase-mapping script call(s) into the scan-targets section as a "Run codebase mapping script" note, so the AI knows what to run.

---

## Example Bundle — `docs/Architecture/skeleton_instructions.md`

```markdown
# Domain Service / Maintenance — Skeleton Bundle

## Scan targets (run codebase mapping script against each)
- app/<target_app>/control_layer/       — Core business logic, handlers, orchestrators.
- app/<target_app>/models/              — Schema and constraints for the domain.
- app/events/                           — Event integration layer (if domain emits events).

## Load alongside scan
- docs/Architecture/layer_rules.md          — Read/write boundaries before touching control layer.
- docs/Architecture/patterns/oop_control_patterns.md — Suffix vocabulary for new classes.

## Skip
- presentation_layer/templates/         — UI files not relevant to domain service work.
```
