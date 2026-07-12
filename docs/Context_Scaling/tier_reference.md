---
type: "Context Scaling Spec"
title: "Tier Reference — Detailed Definitions"
description: "Detailed per-tier purpose, inclusion rules, and key-file inventories for the Context Scaling framework."
tags: [context-scaling, context-scaling-spec]
context_tier: 2
---

# Tier Reference — Detailed Definitions

## Tier 0: The Application Router (`Claude.md`)

* **Purpose:** Primary entry point for any AI session. Defines the application's foundational identity, active development phase, and the global mapping for Persona Slash Commands.
* **Inclusion:** Included in every LLM interaction, build, or project integration.
* **Code rule:** Permitted only when truly essential — critical run commands, short structural examples that cannot be described in prose. Never decorative.

---

## Tier 1: Conceptual Anchors (`docs/*`)

* **Purpose:** One-to-two-page macro-concept files. Never contain implementation details — they govern the rules of engagement for specific domains.
* **Inclusion:** Included globally during code generation, refactoring runs, or major system builds.
* **Code rule:** Must avoid code entirely. These are pure concept and routing documents.

### Key Files

| File | Purpose |
| :--- | :--- |
| `docs/Context_Scaling.md` | This framework. Tier table, reference directionality rule, pointers to sub-specs. |
| `docs/Architecture.md` | Layered architecture, OOP control patterns, model and endpoint rules. |
| `docs/UX_UI.md` | Visual language, density contract, HTMX paradigms, layout rules. |
| `docs/Authorization.md` | Two-gate access model: capability (roles + permission groups) and scope (Data Domain). |
| `docs/applications.md` | Per-application doc convention; why Authorization alone stays at Tier 1/2 while Core Domain, Events, and feature apps live under `docs/applications/`. |
| `docs/Development_Tools.md` | Dev workflow, DB rebuild, environment generation, seeded users. |
| `docs/ApplicationGoals.md` | Product roadmap, user-centric objectives, business logic intent. |
| `docs/technical_decisions.md` | Rolling summary of locked decisions, active tech debt, incident takeaways. |

---

## Tier 2: Deep Feature Specifications (`docs/[Concept]/`)

* **Purpose:** Granular requirements for a single Tier 1 concept. If `UX_UI.md` governs how the app looks, `docs/UX_UI/visual_language.md` governs the exact palette and utility classes.
* **Inclusion:** On-demand. Loaded via Persona Slash Commands or dynamically when a task touches that sub-domain.
* **Code rule:** Avoid unless a structural skeleton is absolutely necessary to prevent logic drift. Max 40 lines.

### Tier 2 Assets

* Sub-directories under each Tier 1 concept folder (e.g., `docs/Architecture/`, `docs/UX_UI/`).
* **Domain skeleton bundles** (`docs/domain_skeleton_bundles/`): On-demand instruction files that define which app directories to scan (Tier 4) for a given task type. Loaded at the start of a task, not globally. See [domain_skeleton_bundles_spec.md](domain_skeleton_bundles_spec.md).

---

## Tier 3: Library Patterns & Component Examples (`docs/[Concept]/<sub category>/*`)

* **Purpose:** Concrete practical reference, in two flavors:
  * **Code patterns:** Functional code boilerplate, usage patterns, API contract shapes, UI component references.
  * **Detailed concept walkthroughs:** Higher-detail explanations, direct examples, or thorough worked-through rules that fully explain a single concept but were too long or too specific to fit cleanly into a Tier 1/Tier 2 summary without diluting it. These stay prose-first (code only where it clarifies), but go deep on one concept rather than surveying many.
* **Inclusion:** Strictly isolated. Never scanned programmatically by default. Loaded manually when the AI is actively building or modifying a structural code block that matches an existing pattern, or when a Tier 1/2 summary references a concept that needs the fuller explanation.
* **Code rule:** Complete, modular examples are the point for the code-pattern flavor. No length restriction for either flavor.

---

## Tier 4: Structural Maps (Automated Overviews)

* **Purpose:** A programmatically generated bridge layer. Supplies a lightweight structural summary of a target directory — classes, docstrings, file tree — without reading thousands of lines of source.
* **Execution rule:** Must be run before reading target source files. It is the entry point; raw files are the fallback for deep dives only.
* **Context cost:** Designed to be low. Output is compact structural metadata, not implementation logic.
* **Tools:** See [tools_and_scripts.md](tools_and_scripts.md).

---

## Tier 5: The Base Codebase

* **Purpose:** The final execution layer. Raw directories, modules, tests, and configuration files.
* **Inclusion:** Read directly only when Tier 4 structural context is insufficient — i.e., when the actual implementation logic is needed, not just the shape.
