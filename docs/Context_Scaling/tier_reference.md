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
| `docs/skeleton.md` | Machine-maintained full index of every doc file across all tiers. Owned by the docs directory crawler — never edited manually. |
| `docs/Context_Scaling.md` | This framework. Tier table, reference directionality rule, pointers to sub-specs. |
| `docs/Architecture.md` | Layered architecture, OOP control patterns, model and endpoint rules. |
| `docs/UX_UI.md` | Visual language, density contract, HTMX paradigms, layout rules. |
| `docs/Authorization.md` | Two-gate access model: capability (roles + permission groups) and scope (Data Domain). |
| `docs/CoreDomain.md` | Shared business entities and the domain/organization/division hierarchy. |
| `docs/Events.md` | Events sub-application: comments, files, shadow history, contexts. |
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

## Tier 3: Library Patterns & Component Examples (`docs/[Concept]/Examples/*`)

* **Purpose:** Concrete practical reference. Functional code boilerplate, usage patterns, API contract shapes, UI component references.
* **Inclusion:** Strictly isolated. Never scanned programmatically by default. Loaded manually when the AI is actively building or modifying a structural code block that matches an existing pattern.
* **Code rule:** Complete, modular examples are the point. No length restriction.

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
