---
type: "Process Guide"
title: "How to Write the Route Skeleton"
description: "You are acting as a Product/UX Agent. Produce the page spine — every HTTP route, its goal, the tables it touches, and the actions it performs."
tags: [front-end-kit-process, process-guide]
context_tier: 2
---

# How to Write the Route Skeleton

**Role & Objective:**
You are acting as a Product/UX Agent. Produce `route_skeleton.md` — the spine of the front-end kit. Every other document in the kit attaches to it. Derive it from the starter kit's `functionality_and_roles.md` (what capabilities exist) and `model_diagram.md` (what they operate on).

---

## Instructions

1. **One entry per HTTP route.** Not per screen state, not per HTMX fragment — per canonical URL. This project uses a **single canonical URL per resource** with a `format=` query parameter for density and fragments; density variants and `htmx-*` fragments are *not* separate entries. See [../UX_UI/format_contract.md](../UX_UI/format_contract.md).

2. **Derive from capabilities, not from tables.** Walk `functionality_and_roles.md` and ask "where does a user do this?" A table with no user-facing capability may legitimately have no page. A capability with no page is a gap.

3. **Classify every route** into exactly one type:

   | Type | Meaning |
   | :--- | :--- |
   | **Navigation** | Dashboard, hub, or landing page. Orients the user and routes them onward. Owns few or no writes. |
   | **Search** | A filterable, paginated list over one entity. Its job is *find the record*. |
   | **Detail** | Read-oriented view of one record, with its related sets. |
   | **Simple CRUD** | A create or edit form for one entity with at most one related set. |
   | **Workflow** | A create or edit flow spanning several related sets — a multi-card wizard. Carried into `workflows.md`. |
   | **Action** | A POST-only endpoint with no page of its own (delete, release, approve). Listed for completeness; has no layout. |

4. **Name the tables, with direction.** For each route, list the tables it **reads** and the tables it **writes** separately. This is what makes the coverage report mechanical rather than a guess.

5. **Name the actions, with their control-layer target.** Every button, every form submit. Write the action as a verb phrase plus the class it should call — `"Release work order → WorkOrderContext.release()"`. If `control_layer_plan.md` has no method for an action, write `→ ??` and carry it to open questions. A page action with no control-layer method behind it is a finding, not a detail.

6. **Assign the component and the empty state per region.** One line each. Cite the component guide rather than describing markup. Every card must have an empty-state string — this project requires cards to render even when their data is empty (see the always-apply rules in `.claude/CLAUDE.md`), so the empty text is a design decision made here, not improvised in the template.

7. **Do not write layout.** No wireframes, no column widths, no markup. The route skeleton says *what the page is for and what it touches*. Form is settled by the UX/UI guides.

---

## Entry format

Use one section per route:

```markdown
### `GET/POST /parts/<id>/edit`

**Type:** Simple CRUD
**Roles:** Planner (U), Engineer (U), Viewer — no access

**Goal.** One paragraph, in domain language. What the user came here to accomplish and why it
matters to the business. Written so a non-technical reader understands the point of the screen.

**Reads:** `Part`, `PartCategory`, `Manufacturer`
**Writes:** `Part`

**Actions**
| Action | Control layer target |
| :--- | :--- |
| Save changes | `PartContext.update()` |
| Archive part | `PartContext.archive()` |

**Regions**
| Region | Component | Empty state |
| :--- | :--- | :--- |
| Identity fields | Standard form card ([form_style_guide](../UX_UI/form_style_guide.md)) | — |
| Manufacturers | Left-heavy assignment card pair | "No manufacturers assigned." |

**Open questions**
- Should archiving be permitted while open demands reference the part?
```

---

## Example Scenario: Asset Management Application

*Concept:* Tracking vehicles and assignments.

*Expected output — three entries among many:*

- `GET /fleet` — **Navigation** — high-level overview of active vehicles and alerts; reads `Vehicle`, `Alert`; writes nothing; links onward to search and detail.
- `GET /vehicles` — **Search** — find a vehicle by plate, location, or status; reads `Vehicle`, `Location`; writes nothing.
- `GET/POST /vehicles/create` — **Workflow** — `Vehicle` has reverse FKs from `VehicleAssignment`, `VehicleDocument`, and `ServiceRecord`; more than one is plausibly populated at creation, so this is a multi-card wizard and is carried into `workflows.md`.

---

## Required Output Format

A single markdown document, `route_skeleton.md`, containing:

1. A **summary table** of every route — path, method, type, one-line goal — for scanning.
2. A **detailed section per route** in the entry format above.
3. An **open questions** list collecting every `→ ??` and unresolved decision found while writing.

Order routes by user journey where one exists, not alphabetically — navigation pages first, then the search/detail/edit cluster for each entity.
