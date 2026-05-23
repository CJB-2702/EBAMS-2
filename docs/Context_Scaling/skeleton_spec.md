# `skeleton.md` — Full Context Map Specification

`skeleton.md` lives at `docs/skeleton.md`. It is the single source of structural truth for the documentation system — a complete, always-current index of every doc file across all tiers.

---

## Rules

* **Index only — no content.** Each entry is a file path and a one-line description. No prose, no repeated rules, no code.
* **One-directional.** `skeleton.md` references every other doc file. No other file references `skeleton.md` back.
* **Owned by the docs directory crawler.** When any file is created or removed under `docs/`, run the crawler immediately. Do not manually edit `skeleton.md` or read it to verify correctness — the script output is authoritative.
* **Paths written once.** A path appears in `skeleton.md` and nowhere else in the Tier 0–1 layer.

---

## Structure Template

```markdown
# Context Skeleton

## Tier 0
- Claude.md — Application router, identity, global rules, persona command map.

## Tier 1
- docs/skeleton.md — This file. Full index of all context files.
- docs/Context_Scaling.md — Context scaling framework: tier table, reference directionality rule.
- docs/Architecture.md — Layered architecture, OOP control patterns, model and endpoint rules.
- docs/UX_UI.md — Visual language, density system, HTMX paradigms.
- docs/Authorization.md — Two-gate access model (capability + scope).
- docs/CoreDomain.md — Shared business entities and hierarchy.
- docs/Events.md — Events sub-application anchor.
- docs/Development_Tools.md — Frameworks, toolchain, environment workflows.
- docs/ApplicationGoals.md — Product roadmap and user-centric objectives.
- docs/technical_decisions.md — Summary of locked decisions, active tech debt, incident takeaways.

## Tier 2
- docs/Context_Scaling/tier_reference.md — Detailed per-tier descriptions and Key Files inventories.
- docs/Context_Scaling/persona_routing.md — Persona slash command routing rules.
- docs/Context_Scaling/tools_and_scripts.md — Codebase mapping script and docs crawler spec.
- docs/Context_Scaling/technical_decisions_system.md — Technical decisions folder structure and entry format.
- docs/Context_Scaling/skeleton_spec.md — This file's own rules and structure template.
- docs/Context_Scaling/domain_skeleton_bundles_spec.md — Domain skeleton bundle format and naming convention.
- docs/Context_Scaling/refactoring_guide.md — Drift smells and post-session context synthesis.
- docs/domain_skeleton_bundles/[bundle].md — [task type] skeleton scan instructions.
- docs/Architecture/[file].md — [one-line description]
- docs/UX_UI/[file].md — [one-line description]
- docs/Authorization/[file].md — [one-line description]
- docs/CoreDomain/[file].md — [one-line description]
- docs/Events/[file].md — [one-line description]
- docs/Development_Tools/[file].md — [one-line description]

## Tier 3
- docs/Architecture/Examples/[file] — [one-line description]
- docs/UX_UI/Examples/[file] — [one-line description]
- docs/Authorization/Examples/[file] — [one-line description]
- docs/CoreDomain/Examples/[file] — [one-line description]
- docs/Events/Examples/[file] — [one-line description]
- docs/Development_Tools/Examples/[file] — [one-line description]
```
