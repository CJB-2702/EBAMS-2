---
type: "Technical Decision"
title: "Phase 1 — Modification Applicability"
description: "Give a DefinedModification its own rules about where it may be applied, and build the."
tags: [technical-decisions, technical-decision, project-history, modification-applicability-starter-kit, phase-1-modification-applicability]
context_tier: 2
---

# Phase 1 — Modification Applicability

Give a `DefinedModification` its own rules about where it may be applied, and build the
**shared applicability engine** that Phase 2 will reuse. Prove the whole pattern on the
simpler one-hop case: a modification → an asset.

## Goal

A `DefinedModification` carries an `applicability_mode` plus a class allow-list and a
model allow-list. Applying it to a real asset (`ModificationManager.add_actual_modification`)
is gated by the matrix in
[`../modification_class_and_model_matrix_behaviors.md`](../modification_class_and_model_matrix_behaviors.md).

## In scope

- NEW field `DefinedModification.applicability_mode` (enum, default `UNRESTRICTED`).
- NEW `ApplicabilityMode` enum (`STRICT` / `CLASS_ONLY` / `MODEL_SET` / `UNRESTRICTED`),
  in a shared module so Phase 2 imports the same one.
- NEW tables `modification_asset_class`, `modification_model`.
- NEW **shared** control: `ApplicabilityPolicy` (pure decision), `ApplicabilitySyncHandler`
  (derive class set from model set), `ApplicabilityStruct` (read model).
- NEW `ModificationApplicabilityManager` — author the lists, set the mode, with
  Checkpoint-1 integrity (sync + dead-model guard).
- NEW `ModificationApplicabilityValidator` (Checkpoint 3) — wired into
  `ModificationManager.add_actual_modification`.
- Full DB rebuild + seed.

## Out of scope

- Templates — Phase 2.
- Any UI / screens — deferred ([D9](../decisions.md)).
- The template↔modification compatibility guard (Checkpoint 2) — Phase 2.

## Dependencies

- None beyond the existing `assets` models and configuration control layer.

## Deliverables

- `app/assets/models/configurations/applicability_mode.py` — `ApplicabilityMode`.
- `applicability_mode` field on `DefinedModification`.
- `ModificationAssetClass`, `ModificationModel` models.
- `app/assets/control_layer/configurations/applicability/` — `applicability_policy.py`,
  `applicability_sync_handler.py`, `applicability_struct.py`,
  `modification_applicability_manager.py`.
- `app/assets/control_layer/guards/modification_applicability_guard.py` —
  `ModificationApplicabilityValidator`.
- `add_actual_modification` calls the validator before creating the row.
- Regenerated migrations; green `seed_dev`.

## Exit criteria

- [ ] A `DefinedModification` can be set to each of the four modes and carry class/model
      allow-lists.
- [ ] `ApplicabilityPolicy.is_allowed(...)` returns the matrix-correct verdict for all
      four modes (unit-tested against the worked examples in the matrix doc).
- [ ] In `MODEL_SET` mode, changing the model list **auto-updates** the class rows to the
      models' distinct parents; the class rows are never hand-authored in this mode.
- [ ] In `STRICT` mode, adding a model whose parent class is not in the class list is
      **rejected** with a clear message (dead-model guard).
- [ ] `add_actual_modification` **refuses** to record a modification on an asset the
      modification's applicability forbids (e.g. an engine mod on a laptop) and **allows**
      a permitted one.
- [ ] A modification left at the default `UNRESTRICTED` applies anywhere — existing
      behavior preserved.
- [ ] `seed_dev` runs green after a full DB rebuild.
