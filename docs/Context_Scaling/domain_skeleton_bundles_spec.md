# Domain Skeleton Bundles — Specification

Bundle files live at `docs/domain_skeleton_bundles/`. They are **Tier 2** assets — loaded on-demand at the start of a specific task type, never globally.

Each bundle answers one question: *"For this kind of task, which application directories and core files should I run the codebase mapping script against?"*

---

## Purpose

Prevents the AI from deciding arbitrarily which folders to scan. Instead of exploring the directory tree from scratch, the AI reads the relevant bundle, runs the Tier 4 mapping script against the listed paths, and has targeted structural context before touching any source files.

---

## Bundle File Rules

* **One file per task type** — not per application. Task types are modes of work: domain service, UI build, RBAC/permission change, event integration, etc.
* **Short** — a list of paths with one-line rationales. No prose paragraphs.
* **Three sections:** scan targets, Tier 2 docs to load alongside the scan, and what to skip.
* **Invocation note:** include the exact script call pattern so the AI knows what to run.

---

## Naming Convention

`<task-type>_skeleton_instructions.md`

Examples:
* `domain_service_skeleton_instructions.md`
* `ui_skeleton_instructions.md`
* `rbac_skeleton_instructions.md`
* `event_integration_skeleton_instructions.md`

---

## Example Bundle — `domain_service_skeleton_instructions.md`

```markdown
# Domain Service / Maintenance — Skeleton Bundle

## Scan targets (run codebase mapping script against each)
- app/<target_app>/control_layer/       — Core business logic, handlers, orchestrators.
- app/<target_app>/models/              — Schema and constraints for the domain.
- app/events/                           — Event integration layer (if domain emits events).

## Load alongside scan
- docs/Architecture/layer_rules.md          — Read/write boundaries before touching control layer.
- docs/Architecture/oop_control_patterns.md — Suffix vocabulary for new classes.

## Skip
- presentation_layer/templates/         — UI files not relevant to domain service work.
```
