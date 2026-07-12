# Part Definitions Kit

Build a new **`app/parts/`** sub-app: an engineering **Part Definitions & Supply Chain
Registry**. It separates the *internal engineering record* of a part (the canonical "base
part id" the rest of the application references) from the *external supplier reality* of how
that part is actually purchased — while giving every persona (technician, engineer, supply,
sourcing) a single high-performance way to find a part by **any** number it has ever been
known by.

## The core principle

> The wider application — assets, future BOM tooling, future configuration-allowability
> tooling — should only ever know about and reference the **base Part id**. It must never
> need to reach into supplier items, revisions, or documentation. Supplier mapping and
> revision history are *satellites* of the Part; the Part id is the stable hub.

This principle drives the phase order: the engineering core (Part + revisions) is built and
made referenceable **first**, in total isolation from the supply side. The supply side and
the search index are then layered on as satellites that point *inward* at the Part.

## Relationship to existing code

This is **mostly greenfield**. The legacy system had only flat part definitions; everything
else here is new infrastructure. Two existing seams are deliberately reused or kept separate
(see [`existing_seams_audit.md`](existing_seams_audit.md)):

- **Part Manufacturers are a NEW, separate table** from the existing
  `app/assets/models/core/manufacturer.py` (the *asset* manufacturers). The two are kept
  apart on purpose: there will eventually be *many* part manufacturers and *few* asset
  manufacturers, and asset lookups must stay fast. A future merge — or an asset-manufacturer
  pointing at a part-manufacturer row — is left as an explicit later decision ([D2](decisions.md)).
- **Documents reuse the `events` file-management system** — `File` + `Attachment` +
  the `FileSet` thread proxy — rather than introducing a parts-local file table ([D5](decisions.md)).

## Phases

| Phase | Folder | Goal |
| :--- | :--- | :--- |
| 1 | [`phase_1_internal_parts/`](phase_1_internal_parts/) | The engineering core: **Part** (the base id), **Part Revisions** (numeric major/minor model — D4), and **comments + documents** on the Part and each revision via the events thread (D5). The *only* phase the rest of the app is meant to reference. **No supplier concepts.** |
| 2 | [`phase_2_supplier_mapping/`](phase_2_supplier_mapping/) | The supply side: **Part Manufacturers** (new table), **Supplier Items** mapping forward to a Part, and **Supplier Item Revisions** with their own documents. Decoupled from the engineering lifecycle. |
| 3 | [`phase_3_aliases_search/`](phase_3_aliases_search/) | The unified **Alias** index — one searchable identifier table spanning internal numbers, NSNs, legacy codes, and supplier MPNs. Auto-populated when a Supplier Item is added. Resolution walks an alias forward to its owning Part. |
| 4 | [`phase_4_parts_ui/`](phase_4_parts_ui/) | Persona-driven UI: technician quick-lookup, engineer revision tracking, supply ordering/mapping views. Thin shell over phases 1–3. |

### Why this order

Phase 1 establishes the stable hub (the Part id) and proves the revision/document pattern
headless, with zero supplier coupling — satisfying the core principle before anything points
at a Part. Phase 2 adds supplier satellites that reference the Part built in Phase 1. Phase 3
can only build the unified index *after* both internal numbers (Phase 1) and supplier MPNs
(Phase 2) exist to index, and its auto-population orchestrator hooks Phase 2's create path.
Phase 4 is a thin presentation layer over a control layer that is already transactionally
correct. Phases 1–3 are each fully testable headless; Phase 4 is testable in the browser.

## How to use a phase sub-kit

Each `phase_N_*/` folder is self-contained:

- `README.md` — goal, in/out of scope, dependencies, deliverables, **exit-criteria checklist**.
- `business_concept.md` — what the phase delivers in user language (no schema, no class names).
- `data_relational_plan.md` — tables, key fields, FK directions for the phase's scope.
- `control_layer_plan.md` — Structs / Contexts / Managers / Factories / Orchestrators / Narrators and the delegation flow.
- `ui_features_plan.md` — (Phase 4 only) page inventory, classifications, HTMX contracts.

Read the root [`decisions.md`](decisions.md) first — it records the design choices every
phase assumes — then [`open_questions.md`](open_questions.md) for what is **not** yet decided.

## Root documents

| File | Purpose |
| :--- | :--- |
| [`STATUS.md`](STATUS.md) | **Start here when returning** — what's done, what's left, conversation state. |
| [`initial_prompt.md`](initial_prompt.md) | Verbatim system specification + clarifying decisions captured during interrogation. |
| [`decisions.md`](decisions.md) | Architectural decision log (D1–D14). |
| [`model_diagram.md`](model_diagram.md) | **Single consolidated data-model picture** for the whole kit — one ERD across all phases + table summary + key model rules. |
| [`functionality_and_roles.md`](functionality_and_roles.md) | Functionality-set × role matrix for review (where access/permission semantics are decided). |
| [`existing_seams_audit.md`](existing_seams_audit.md) | What already exists in the codebase (asset Manufacturer, events file system) vs. what this kit adds. |
| [`open_questions.md`](open_questions.md) | Resolution log — most questions resolved; residual confirms at the bottom. |
| [`brainstorming_session_20260623.md`](brainstorming_session_20260623.md) | Narrative of the 2026-06-23 session that produced this kit. |

> **Status (2026-06-23):** Kit drafted from the system specification and a codebase seam
> audit. **Not yet reviewed.** Several decisions are provisional pending the review noted in
> [`open_questions.md`](open_questions.md).
