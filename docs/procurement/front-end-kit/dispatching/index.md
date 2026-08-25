---
okf_version: "0.1"
type: "Index"
title: "Front-End Kit — Dispatching (the dispatch record)"
description: "Disposable UI plan for the dispatch record's own screens — index, create, detail, edit — plus the Requested-state backend change they depend on and the reservation-creation handoff."
tags: [front-end-kit, dispatching, index]
context_tier: 1
personas: [frontend, backend]
---

# Front-End Kit — Dispatching (the dispatch record)

Disposable UI plan for **the dispatch itself** — the last unbuilt surface in the dispatching
module. Skills, certifications, dispatch templates, and asset reservations are already built and
live; this kit covers only the dispatch record's own four screens and the backend change they
require.

Per the two-kit split this folder is **never resynced** after the UI is built, and is deleted once
spent. [`dispatching_starter_kit/`](../../dispatching_starter_kit/index.md) stays durable and
remains authoritative for anything behind the UI.

## Start here

**[build_plan/index.md](build_plan/index.md)** — six phase documents, one per build wave. Each is a
self-contained agent brief: prerequisites, context to load, ordered tasks, routes owned,
control-layer targets, permission gates, and a definition of done. **Phase 0 is a hard gate** — it
changes the workflow-status vocabulary every other phase renders.

## Contents

| Document | Covers |
| :--- | :--- |
| [build_plan/](build_plan/index.md) | **The phased build brief — start here.** State change + shell gate, then detail, create, edit, index, and the reservation handoff |
| [decisions.md](decisions.md) | Twelve decisions taken with the developer in the planning session, each with its rationale and how to reverse it |
| [status_vocabulary.md](status_vocabulary.md) | The seven workflow states after the Draft removal — meanings, legal transitions, tag colours, banner copy, and which axis is derived rather than chosen |
| [control_layer_map.md](control_layer_map.md) | Every UI action mapped to the exact control-layer call, the guard that can refuse it, and how the refusal must surface |
| [reference_index.md](reference_index.md) | Every file a builder needs to read or copy, and what each one supplies |

## The state of the module before this kit

| Layer | Status |
| :--- | :--- |
| Models | **Built.** `DispatchingDetail` (in `app/events/`), requirements ×4, demand link, crew, expenses, reservations, templates, skills |
| Control layer | **Built and complete for dispatches — entirely unexercised by any screen.** `DispatchContext` plus nine managers, two factories, two structs, seven guards, one narrator |
| Search helpers | Two dispatch queries exist (`dispatch_queue_search.py`); everything else is reservation/template/skill-shaped |
| Entrypoints / URLs / templates | **Zero for dispatches.** The hub's "Dispatcher Queue" card is a disabled button |
| Permissions | **Seeded.** All five `events.dispatch_*` codenames plus `dispatching.expense_record` are already in `dev_auth_groups.json` under `generic_admin` |

So this is a presentation-layer build over a finished backend, with one deliberate backend change
(Phase 0) that the developer asked for during planning.

## Scope

**In scope:** the dispatch index/search page, create, detail, edit; the crew and expense cards that
live on detail; the material-demand panel; the requested-asset reference picker; the URL-parameter
handoff to and from the existing reservation create page; the Draft-to-Requested state change.

**Out of scope:** a separate dispatcher queue page (folded into the index — see
[decisions.md](decisions.md) D3), asset and personnel calendars, standalone expense pages,
checkout/return (already built on reservations), and any change to the skills or template screens
beyond adding one button and one search box.

## Source material

- **Starter kit (durable):** [`dispatching_starter_kit/`](../../dispatching_starter_kit/index.md) —
  especially [2_dispatch.md](../../dispatching_starter_kit/2_dispatch.md) (the record itself),
  [4_dispatch_line_items.md](../../dispatching_starter_kit/4_dispatch_line_items.md) (expenses and
  narration), and [5_roles_and_permissions.md](../../dispatching_starter_kit/5_roles_and_permissions.md) §4
  (the gate on every screen).
- **Built code as the visual specification:** the templates and reservations screens under
  `app/dispatching/templates/dispatching/`. This kit repeatedly says "port this layout"; those are
  the layouts.
- **Legacy app:** not needed. The developer confirmed it during planning, and the two screens worth
  porting shape from were already ported into the template and reservation surfaces.
