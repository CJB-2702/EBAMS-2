---
okf_version: "0.1"
type: "Index"
title: "Procurement Build Plan — Phase Index"
description: "Router into the five phase documents that turn the procurement front-end kit into a built UI: one schema/shell phase, three parallel sector waves, and a deferred diagnostic page."
tags: [front-end-kit, procurement, build-plan, index]
context_tier: 1
personas: [frontend, backend, business]
---

# Procurement Build Plan — Phase Index

Each phase below is a **self-contained agent brief**. A phase document names its own prerequisites,
the exact context to load, an ordered task list, the routes it owns, the control-layer classes it
calls, the permission gates it installs, and how to tell when it is done. Fire an agent at one
phase document and it should not need to be told anything else.

## Phases

| Phase | Document | Runs | Owns |
| :--- | :--- | :--- | :--- |
| 0 | [phase_0_schema_and_shell.md](phase_0_schema_and_shell.md) | **First, alone** | Nine schema changes, the permission vocabulary, `urls.py` route contract, topnav shelf, main-index card, the `/procurement` hub page |
| 1 | [phase_1_demand_loop.md](phase_1_demand_loop.md) | Parallel with 2 and 3 | Demand list, create, edit, detail |
| 2 | [phase_2_buying_loop.md](phase_2_buying_loop.md) | Parallel with 1 and 3 | PO list, create wizard, detail, Edit & Linkage |
| 3 | [phase_3_receiving_loop.md](phase_3_receiving_loop.md) | Parallel with 1 and 2 | Package list, create (both paths), detail, Edit & Linkage, Basic Package Manager |
| 4 | [phase_4_graph_visualizer.md](phase_4_graph_visualizer.md) | **Last, deferred** | The association-network diagnostic page |

**Phase 0 is a hard gate.** Phases 1–3 depend on its schema changes, its permission constants, and
its pre-declared URL names. Do not start them until Phase 0 is merged and migrated.

## How the parallelism works without merge conflicts

Phases 1–3 touch the same two shared files if built naively — `urls.py` and the topnav. Phase 0
removes that collision up front:

- **`app/procurement/urls.py`** is created by Phase 0 as a parent that `include()`s three
  wave-owned modules: `urls_demands.py` (Phase 1), `urls_purchase_orders.py` (Phase 2),
  `urls_packages.py` (Phase 3). Phase 0 populates all three with the **complete** route and name
  inventory, every route pointing at a shared `NotBuiltYetView` placeholder. Each wave then edits
  **only its own module**, swapping placeholders for real entrypoints.
- **The topnav shelf and main-index card** are written in full by Phase 0 against those pre-declared
  names, so `{% url %}` resolves from day one and no wave needs to touch navigation markup.

A wave that needs a route Phase 0 did not declare should add it to its own module and say so in its
completion notes — not edit another wave's file.

## Rules every phase follows

Load these once; the phase documents cite them rather than restating them.

| Rule | Source |
| :--- | :--- |
| Layer boundaries — what a view may and may not do | [../../../harness/Architecture/layer_rules.md](../../../harness/Architecture/layer_rules.md) |
| OOP endpoint design | [../../../harness/Architecture/patterns/endpoint_patterns.md](../../../harness/Architecture/patterns/endpoint_patterns.md) |
| HTMX conventions and the F5 rule | [../../../harness/Architecture/patterns/htmx_patterns.md](../../../harness/Architecture/patterns/htmx_patterns.md) |
| Page shells and layout fractions | [../../../harness/UX_UI/page_structure.md](../../../harness/UX_UI/page_structure.md), [../shared_workflows.md](../shared_workflows.md) §1 |
| `format=` density contract | [../../../harness/UX_UI/format_contract.md](../../../harness/UX_UI/format_contract.md) |
| Card footers and action placement | [../../../harness/UX_UI/form_style_guide.md](../../../harness/UX_UI/form_style_guide.md) |
| When a modal is allowed | [../../../harness/UX_UI/design_patterns/modals.md](../../../harness/UX_UI/design_patterns/modals.md) |
| Search-and-select pattern selection | [../../../harness/UX_UI/search/list_management_patterns.md](../../../harness/UX_UI/search/list_management_patterns.md), [searchbars.md](../../../harness/UX_UI/search/searchbars.md) |
| Cards render even when empty | `.claude/CLAUDE.md` always-apply rule 5 |
| Full DB reset after any schema change | `.claude/CLAUDE.md` always-apply rule 1 |

## The two standing constraints

1. **D62 — the backend has zero permission enforcement.** Every entrypoint built in Phases 1–4 is
   the first and only place authorization becomes real. See
   [../shared_workflows.md](../shared_workflows.md) §3 and Phase 0's permission vocabulary.
2. **Cross-domain records are readable as exposed data, never navigable.** A user whose domain does
   not match a linked PO or package sees its identifying data rendered as plain text on the page
   they already have access to, and gets no link through to that record's own page. The single
   deliberate exception is Phase 4's graph visualizer.

## Source material

- **Starter kit (durable):** [../../../procurement_starter_kit/](../../../procurement_starter_kit/README.md)
  — problem, business rules, models, control layer. Authoritative for anything behind the UI.
- **Front-end kit (disposable):** [../index.md](../index.md) — the sector workflow documents these
  phases implement. Delete after the build; the starter kit survives.
</content>
</invoke>
