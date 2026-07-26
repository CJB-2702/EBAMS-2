---
type: "Technical Decision"
title: "Asset Control Layer Starter Kit"
description: "Pre-implementation planning kit for migrating asset/model control logic from the."
tags: [technical-decisions, technical-decision, project-history, asset-control-layer-starter-kit]
context_tier: 2
---

# Asset Control Layer Starter Kit

Pre-implementation planning kit for migrating asset/model control logic from the
old Flask app (`/home/cb/REPOS/asset_management`) into this project's
`app/assets/control_layer`, rebuilt to this repo's layered architecture.

**This kit is documentation, not code.** It follows the methodology in
[`harness/starter_kit_process`](../harness/starter_kit_process/): each phase carries a
Business Concept, a Data/Relational plan, and a Control-Layer plan, plus a
migration map from the old code.

> The new Django models for assets are **already built** (`app/assets/models/`).
> The missing piece is the **control layer** — only `asset_handler.py` exists.
> This kit plans that control layer phase by phase.

## Read these first (kit root)

| Doc | Purpose |
| :--- | :--- |
| [`initial_prompt.md`](initial_prompt.md) | The originating request + clarifying decisions. |
| [`decisions.md`](decisions.md) | Architectural decision log (start: D1 explicit orchestrator). |
| [`architecture_contrast.md`](architecture_contrast.md) | Old Flask/SQLAlchemy vs new Django; the domain remodel (MajorLocation→Domain, MakeModel→AssetModel, core→assets). |
| [`event_context_study.md`](event_context_study.md) | **The core study.** Old `EventContext` vs the new `events` app; the lifecycle-eventing + asset↔event link the migration must add. |
| [`events and Activity Thread useage.md`](events%20and%20Activity%20Thread%20useage.md) | The Event / ActivityThread / FileSet capability gradient, and a per-model outline of which rows get events vs. threads vs. galleries (D2). |
| [`migration_map.md`](migration_map.md) | Global map: every old `business/core` + `business/assets` file → its new home (or "superseded / out of scope"). |
| [`../optional_detail_hooking.md`](../optional_detail_hooking.md) | The rejected pluggable-pipeline alternative, kept for future reconsideration. |

## Phases (build in this order)

| Phase | Folder | Scope |
| :--- | :--- | :--- |
| **1** | [`phase_1_asset_and_model_contexts/`](phase_1_asset_and_model_contexts/) | `AssetContext`, `AssetModelContext`, creation orchestrators, meter history, parent/child tree, asset_class denormalization propagation, lifecycle eventing. |
| **2a** | [`phase_2a_plugin_framework/`](phase_2a_plugin_framework/) | The asset **plugin framework**: plugin descriptor contract, explicit registry, factory seam, on-create provisioning hook, enablement tables, managers + union struct. Proven with two reference plugins. |
| **2b** | [`phase_2b_first_party_plugins/`](phase_2b_first_party_plugins/) | Port the remaining concrete details (vehicle registration, smog, emissions) onto the framework as plugin packages. |
| **3** | [`phase_3_configurations/`](phase_3_configurations/) | Configuration templates, asset configuration lifecycle, defined/actual modifications, template children. |
| **4** | [`phase_4_capabilities/`](phase_4_capabilities/) | Capability catalog; class/model/asset capability layers; copy-on-create fan-out. |

Each phase folder has its own `README.md` with goal, deliverables, dependencies,
and exit criteria.

## Why this order

1. **P1 first — everything depends on it.** Asset and AssetModel are the
   aggregate roots. Their contexts, the creation **orchestrator**, and the
   lifecycle-eventing hook are the seams every later phase plugs into. Nothing
   downstream can be cleanly built until the orchestrator exists.

2. **P2 plugin framework before P3/P4.** Plugin provisioning is *template-driven on
   creation* (`asset_plugins_by_asset_class`, `asset_plugins_by_model`,
   `model_plugins_by_asset_class`). It is the simplest consumer of the creation
   orchestrator, so it validates that seam early with low blast radius. P2 is split:
   **2a** builds the plugin framework (contract + registry + factory seam +
   provisioning hook) proven with two reference plugins; **2b** ports the remaining
   first-party details onto it, proving extensibility. (This recasts the original
   "Asset & Model Details" Phase 2 — see [`decisions.md`](decisions.md) D4/D5.)

3. **P3 configurations before P4 capabilities.** Configurations are largely
   *self-contained assignment* logic (assign a template to an asset, track
   modifications). Capabilities carry the heaviest **copy-on-create cascade**
   (class → model → asset) in the old app and touch the orchestrator the most;
   doing them last lets the orchestrator, details, and eventing settle first.

## How to use a phase sub-kit

1. Read the phase `README.md` for scope + exit criteria.
2. Read `business_concept.md` (what it does for the user), then
   `data_relational_plan.md` (the already-built models it operates on), then
   `control_layer_plan.md` (the Structs/Contexts/Managers/Handlers/Guards to
   build, named per `harness/Architecture/patterns/oop_control_patterns.md`).
3. Use `old_to_new_migration.md` as the porting checklist against the old Flask
   source — what to keep, what to drop, what changes shape.
4. Implement against this repo's layer rules; **all writes in the control
   layer**, thin entrypoints, one transaction per workflow.
