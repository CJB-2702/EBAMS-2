---
okf_version: "0.1"
type: "Index"
title: "Front-End Kit — Procurement"
description: "Index of the procurement front-end plan: gap analysis against the legacy app, and per-sector workflow documents covering part demands, purchase orders, and packages."
tags: [front-end-kit, procurement, index]
context_tier: 1
personas: [frontend, business]
---

# Front-End Kit — Procurement

Disposable UI plan for the `procurement_starter_kit/` backend (models + control layer built,
no entrypoints/urls/templates yet — see the starter kit's `README.md`). Per the two-kit split, this
folder is **never resynced** to the starter kit after the UI is built, and is deleted once spent;
the starter kit stays durable.

**Reads the starter kit as source of truth, code second** — there is no built procurement UI to
cross-check yet.

## Start here

**[build_plan/index.md](build_plan/index.md)** — five phase documents, one per build wave. Each is a
self-contained agent brief: prerequisites, context to load, ordered tasks, routes owned,
control-layer targets, permission gates, and a definition of done. **Phase 0 is a hard gate**; waves
1–3 then run in parallel.

The sector documents below are the *design* the build plan implements. Read the phase document
first; it tells you which of these to load and in what order.

## Contents

| Document | Covers |
| :--- | :--- |
| [build_plan/](build_plan/index.md) | **The phased build brief — start here.** Schema/shell gate, three parallel sector waves, deferred diagnostics |
| [gap_analysis.md](gap_analysis.md) | What the legacy `asset_management/inventory` Flask routes did, what changed in the new design, and the six concrete gaps this kit has to design against |
| [part_demand_workflows.md](part_demand_workflows.md) | Requesting material and the four-axis demand lifecycle up to (not including) physical issuance |
| [purchase_order_workflows.md](purchase_order_workflows.md) | The create-PO wizard (highest-traffic screen in the app), line editing, and PO status lifecycle |
| [package_workflows.md](package_workflows.md) | Shipment tracking, inspection/acceptance — **being revised incrementally by the `packages/` subfolder below**, where the three newer documents disagree with this one |
| [packages/basic_package_manager.md](packages/basic_package_manager.md) | The preferred, drag-and-drop, session-backed portal for the common one-PO/2-3-non-overlapping-packages case; delivered or split packages are locked out of it (D69) and edited on `package_edit_and_linkage.md` instead |
| [packages/package_edit_and_linkage.md](packages/package_edit_and_linkage.md) | `packages/<id>/edit` — header edit plus a PO-Linkage-Portal-style master-detail line assignment tool, superseding the standalone line-splitting wizard route |
| [packages/package_comments_and_files.md](packages/package_comments_and_files.md) | The Event-vs-ActivityThread call for `Package` (recommendation: Event, `decisions.md` D68), narration rules, and the package view page's comments/files/photos card layout |
| [graph_association_visualizer.md](graph_association_visualizer.md) | The admin-only diagnostic page rendering the full transitive PO/demand/package association network (`decisions.md` D70) — three linked columns, no join-table rows shown directly |
| [shared_workflows.md](shared_workflows.md) | Cross-sector concerns: the portal hub, the shared-demand-session display, permission enforcement (deferred entirely by the backend, D62), layout fraction conventions, and reused search services |

## Status

Draft — actions, pages, control-layer targets, search apparatus, and card-level layout are
sketched per sector. **Not yet done, per the standard front-end-kit process** (see
`../../harness/front_end_kit_process/index.md`):

- ~~No `route_skeleton.md`~~ **Resolved** — the complete route and name inventory now lives in
  [build_plan/phase_0_schema_and_shell.md](build_plan/phase_0_schema_and_shell.md) §6, split into
  three wave-owned URL modules so waves 1–3 can be built in parallel without merge conflicts.
- ~~Navigation reachability gate: not run.~~ **Resolved** — every route is reachable from the topnav
  shelf, the main-index card, or the `/procurement` hub, all specified in
  [build_plan/phase_0_schema_and_shell.md](build_plan/phase_0_schema_and_shell.md) §7.
- **Workflow review gate: partially run.** The create-PO wizard and create-package form have
  written verdicts (wizard vs. simple form, with reasons) in their respective sector files, but
  the verdict table format from `how_to_identify_workflows.md` hasn't been assembled as its own
  artifact, and the wizard hasn't been promoted to its own `key-workflows/` document yet (flagged
  in `purchase_order_workflows.md`).
- No coverage report (advisory, table × CRUD, role × capability).

Next natural step: promote the create-PO wizard to `key-workflows/create_purchase_order.md`
following `how_to_write_a_key_workflow.md`'s full skeleton (enablement conditions, draft keys,
commit sequence, abandonment, validation/failure) — it's the one workflow in this kit that
qualifies on every promotion criterion (central to the app, 4+ cards, has branching via D28's cap
decision).
