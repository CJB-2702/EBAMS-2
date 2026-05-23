# Technical Specification: Context Scaling Framework

## 1. Core Philosophy
As development environments grow, unmanaged context injection degrades LLM performance, introduces hallucinations, and wastes token allocations. **Context Scaling** solves this by establishing a strictly tiered, hierarchical information architecture governed by **Work Personas**. High-level rules route to deeper specifications, ensuring an AI agent only ingests the exact depth of context required for a given task.

---

## 2. Hierarchical Context Tiers

| Tier | File / Location | Scope & Target Length | Injection Mechanic & Rules |
| :--- | :--- | :--- | :--- |
| **Tier 0** | `Claude.md` (Root) | Main router & core identity. Max 3 pages. | **Global:** Always included. Defines active persona mappings. Code permitted only when truly essential (e.g., critical run commands). |
| **Tier 1** | `Docs/*` (Root docs) | Concept anchors & file references. 1–2 pages. | **Global:** Always included. **Must avoid code** — pure concept and routing documents. |
| **Tier 2** | `Docs/[Concept]/*.md` | Full feature specs & requirements. Few pages. | **On-Demand:** Loaded via Persona Slash Commands or dynamic domain triggers. Code ≤ 40 lines. |
| **Tier 3** | `Docs/[Concept]/Examples/*` | Implementation guides, patterns, usage. | **Targeted:** Never scanned by default. Injected manually when writing active code. |
| **Tier 4** | Automated Overviews | Structural maps, class maps, module boundaries. | **Automated:** Programmatically generated repository signatures. |
| **Tier 5** | Base Codebase | The actual repository files and active code. | **Execution:** Live implementation logic. |

### Tier 0: The Application Router (`Claude.md`)
* **Purpose:** Acts as the primary entry point for any AI session. It defines the application's foundational identity, active development phase, and the global mapping for **Persona Slash Commands**.
* **Inclusion:** Included in **every single** LLM interaction, build, or project integration.

### Tier 1: Conceptual Anchors (`Docs/*`)
* **Purpose:** Provides a one-to-two-page breakdown of macro-concepts. These files **must avoid code** — they are pure concept and routing documents that govern the *rules of engagement* for specific domains.
* **Inclusion:** Included globally during code generation, refactoring runs, or major system builds.
* **Key Files:**
  * `skeleton.md`: **Full context map.** A machine-maintained index of every doc file across all tiers. Never edited manually — the directory crawler script owns its content. See §7.
  * `Architecture.md`: Domain-driven design principles, service layers, and boundary separation.
  * `UX_UI.md`: Visual language, density system, HTMX paradigms, and layout rules.
  * `ApplicationGoals.md`: Product roadmap, user-centric objectives, and business logic intent.
  * `Development_Tools.md`: Frameworks, custom automated rulesets (`.cursorrules`, `.clauderules`), and environment workflows.
  * `technical_decisions.md`: Rolling summary of locked design decisions, tech debt, and incident history. See §5.
  * `domain_skeleton_bundles/`: Folder of bundle instruction files. Each file defines which app directories to scan (Tier 4) for a given task type. See §8.

### Tier 2: Deep Feature Specifications (`Docs/[Concept]/`)
* **Purpose:** Fleshes out the granular requirements of a single Tier 1 concept. If `Docs/UX_UI.md` dictates how the application looks, `Docs/UX_UI/Coloring_concepts.md` dictates the exact palette, token variables, and utility classes.
* **Inclusion:** Safe to add to context on demand. Injected explicitly via **Persona Slash Commands** initialized in the system layer, or dynamically when a code modification actively touches that specific sub-domain.
* **Constraint:** Focuses heavily on descriptive requirements and rationale. Code should be avoided unless a complex structural skeleton is absolutely necessary to prevent logic drift.

### Tier 3: Library Patterns & Component Examples
* **Purpose:** The concrete practical reference layer. Contains functional code boilerplate, usage patterns, API contract shapes, and references to UI components or external service mockups.
* **Inclusion:** **Strictly isolated.** Must never be programmatically scanned into context by default. These files must be actively related to the immediate work defined in a Tier 2 document or an active project task. They are loaded only when the AI needs to build or modify structural code blocks matching existing patterns.

### Tier 4: Structural Maps (Automated Overviews)
* **Purpose:** A bridge layer generated programmatically. Instead of reading thousands of lines of raw source code to find where a class lives, a script parses the codebase to supply a lightweight structural summary.

### Tier 5: The Base Codebase
* **Purpose:** The final layer of execution. This represents the raw reality of the application—the actual directories, modules, tests, and configuration files.

---

## 3. Persona-Driven Context Routing (Slash Commands)

To prevent context pollution, the system uses **Slash Commands** to switch between specialized development roles. Each command configures the AI with explicit instructions regarding which Tier 2 files to load into context.

```text
[/architecture] -> Activates System Architect Persona
                -> Loads: Docs/Architecture/*
                -> Focuses on: Boundaries, DB schemas, API contracts, decoupled logic.

[/frontend]     -> Activates UI/UX Engineer Persona
                -> Loads: Docs/UX_UI/*
                -> Focuses on: Component states, HTMX behaviors, accessibility, styling tokens.

[/tools]        -> Activates DevOps/DX Engineer Persona
                -> Loads: Docs/Development_Tools/*
                -> Focuses on: Automation scripts, environmental configs, test runners.
```

**Core Persona Rules:**
* **Context Isolation:** Invoking a persona command purges unrelated Tier 2 files from the immediate context window, maintaining strict token hygiene.
* **Dynamic Tier 3 Pulls:** When a persona is active and encounters a complex implementation task, it must explicitly look at the active Tier 2 document to identify and pull only the specific Tier 3 example files explicitly tied to that component.

---

## 4. Dynamic Context Tools & Scripts

### Codebase Mapping Script

To prevent the AI from blindly searching directories, a repository utility script must be maintained. This script is designed for **low context cost** — its output is a compact structural summary, not raw source code.

* **Input Parameter:** Directory path string (or a list of paths defined in a `domain_skeleton_bundle`).
* **Output:** A concise markdown map displaying:
  1. A clean, visual file tree.
  2. Public classes found per module.
  3. Extracted docstring descriptions for each class and major service method.
* **Execution rule:** The script **must be run before reading the target files into context.** Never read raw source files first and then run the script — the script output is the lightweight entry point; raw files are the fallback for deep dives only.
* **Manual invocation is fine.** No automation required. The rule is simply that it runs first.

### Docs Directory Crawler

A companion script targets the `Docs/` folder specifically and regenerates `skeleton.md`. It is the **only mechanism** that writes to `skeleton.md`.

* **Trigger:** Run whenever a new file is created anywhere under `Docs/`.
* **Rule:** Do not manually edit `skeleton.md` or attempt to verify its correctness by reading it — trust the script output.
* **Output:** Replaces `skeleton.md` with a freshly generated index of every file under `Docs/`, grouped by tier, with one-line descriptions derived from each file's first heading or opening sentence.

---

## 5. Technical Decisions (`Docs/technical_decisions.md`)

Architectural drift happens when an AI suggests a patterns-compliant alternative that conflicts with locked engineering decisions, or when known debt and past incidents are forgotten between sessions.

### Base file (`technical_decisions.md`)

A short Tier 1 summary — 1–2 pages maximum. Synthesizes the current state of the three history sub-folders below. Contains no raw event entries; only distilled takeaways and the most critical active constraints.

* **Core Rule:** Once a design pattern, aesthetic direction, or library choice is locked after a trade-off discussion, it is codified here. The AI must treat locked decisions as constraints, not suggestions to revisit.

### Sub-folder: `technical_decisions/history/`

Event summaries for significant design decisions. Each file covers one decision event.

* **Structure per entry:**
  * **Context/Feature:** What area of the system does this touch?
  * **Decision:** What specific approach was selected?
  * **Rationale:** Why was this chosen over the alternatives?
  * **Date:** When was this decided?

### Sub-folder: `technical_decisions/tech_debt/`

Known debt items: shortcuts taken, deferred work, and architectural compromises. Each file is a brief note on one item — what it is, why it was deferred, and what the eventual fix looks like.

### Sub-folder: `technical_decisions/incident_history/`

Post-mortems and notable bugs. Each file covers one incident — what failed, root cause, and what changed as a result. Referenced by the base `technical_decisions.md` summary when an incident produced a lasting constraint.

---

## 6. Reference Directionality

All cross-file references in this system are **strictly one-directional: parent → child only.**

* A Tier 0 file (`Claude.md`) may reference Tier 1 files.
* A Tier 1 file may reference Tier 2 files within its own concept folder.
* A Tier 2 file may reference Tier 3 examples within its own concept folder.
* **No file may reference a file at the same tier or a higher tier.** A Tier 2 spec never links back to `Claude.md`. A Tier 3 example never links to `Architecture.md`.

**Why:** Upward or lateral references create circular discovery paths and force the AI to re-ingest already-loaded context. One-directional flow means reading the tree top-down is always sufficient.

**Path hygiene rule:** A file path is written only once — in its immediate parent's reference list. If `Claude.md` already lists `Docs/Architecture.md`, no other Tier 0 or Tier 1 file should repeat that path. Duplication across files signals that a concept is being discussed at the wrong tier level or should be consolidated.

---

## 7. `skeleton.md` — Full Context Map (Tier 1)

`skeleton.md` is a Tier 1 file maintained at `Docs/skeleton.md`. It is the **single source of structural truth** for the documentation system itself.

### Purpose

* Provides a complete, always-current index of every doc file across all tiers.
* Eliminates the need to scan directory trees to discover what documentation exists.
* Serves as the onboarding entry point for any new AI session or team member.

### Rules

* **Index only — no content.** Each entry is a file path and a one-line description. No prose, no repeated rules, no code.
* **One-directional.** `skeleton.md` references every other doc file. No other file references `skeleton.md`.
* **Owned by the directory crawler script.** When any file is created under `Docs/`, run the docs crawler immediately. Do not manually edit `skeleton.md` or read it to verify correctness — the script output is authoritative.
* **Paths written once.** A path appears in `skeleton.md` and nowhere else in the Tier 0–1 layer.

### Structure template

```markdown
# Context Skeleton

## Tier 0
- Claude.md — Application router, identity, global rules, persona command map.

## Tier 1
- Docs/skeleton.md — This file. Full index of all context files.
- Docs/Architecture.md — Layer rules, service boundaries, DDD principles.
- Docs/UX_UI.md — Visual language, density system, HTMX paradigms.
- Docs/ApplicationGoals.md — Product roadmap and user-centric objectives.
- Docs/Development_Tools.md — Frameworks, toolchain, environment workflows.
- Docs/technical_decisions.md — Summary of locked decisions, active tech debt, and incident takeaways.
- Docs/domain_skeleton_bundles/[bundle].md — [task type] skeleton scan instructions.

## Tier 2
- Docs/Architecture/[file].md — [one-line description]
- Docs/UX_UI/[file].md — [one-line description]

## Tier 3
- Docs/Architecture/Examples/[file] — [one-line description]
- Docs/UX_UI/Examples/[file] — [one-line description]
```

---

## 8. Domain Skeleton Bundles (`Docs/domain_skeleton_bundles/`)

A folder of short instruction files that define **what to scan** when starting work on a given task type. Each bundle answers one question: *"For this kind of task, which application directories and core files should I run the codebase mapping script against?"*

### Purpose

Prevents the AI from deciding arbitrarily which folders to scan. Instead of exploring the directory tree from scratch, it reads the relevant bundle, runs the mapping script against the listed paths, and has a targeted structural context ready before touching any source files.

### Bundle file rules

* One file per task type (not per application). A task type is a mode of work: domain service problem, UI build, RBAC/permission change, event integration, etc.
* Short — list of paths + one-line rationale per path. No prose paragraphs.
* Includes the specific Tier 4 script invocation pattern (which paths to pass).
* References the Tier 2 docs most critical for that task type, so the AI knows what to load alongside the scan.

### Example bundle — `maintenance_skeleton_instructions.md`

```markdown
# Domain Service / Maintenance — Skeleton Bundle

## Scan targets (run codebase mapping script against each)
- app/<target_app>/control_layer/       — Core business logic, handlers, orchestrators.
- app/<target_app>/models/              — Schema and constraints for the domain.
- app/events/                           — Event integration layer (if domain emits events).

## Load alongside scan
- Docs/ARCHITECTURE/LAYER_RULES.md      — Read/write boundaries before touching control layer.
- Docs/ARCHITECTURE/OOP_CONTROL_PATTERNS.md — Suffix vocabulary for new classes.

## Skip
- presentation_layer/templates/         — UI files not relevant to domain service work.
```

### Naming convention

`<task-type>_skeleton_instructions.md` — for example:
* `domain_service_skeleton_instructions.md`
* `ui_skeleton_instructions.md`
* `rbac_skeleton_instructions.md`
* `event_integration_skeleton_instructions.md`