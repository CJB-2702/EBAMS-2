---
type: "Technical Decision"
title: "Phase 2 — Template Applicability"
description: "Give a ConfigurationTemplate the same applicability rules as a modification, **reusing**."
tags: [technical-decisions, technical-decision, project-history, modification-applicability-starter-kit, phase-2-template-applicability]
context_tier: 2
---

# Phase 2 — Template Applicability

Give a `ConfigurationTemplate` the same applicability rules as a modification, **reusing**
the engine from Phase 1, and add the earliest cross-entity guard: blocking an
incompatible modification from being grouped into a template.

## Goal

A `ConfigurationTemplate` carries an `applicability_mode` + class/model allow-lists; the
existing exact-single-model assignment gate is generalized into the mode system; and
adding a modification to a template is checked for provable incompatibility at author
time.

## In scope

- NEW field `ConfigurationTemplate.applicability_mode` (enum, default `MODEL_SET`).
- NEW tables `template_asset_class`, `template_model`.
- NEW `TemplateApplicabilityManager` — mirrors `ModificationApplicabilityManager`, reusing
  the shared `ApplicabilitySyncHandler` and Checkpoint-1 integrity rules.
- **Refactor** `ConfigurationAssignmentValidator` (Checkpoint 4) to delegate to the shared
  `ApplicabilityPolicy` instead of hard-coding `template.model_id == asset.model_id`.
- NEW `ApplicabilityCompatibilityPolicy` + `TemplateModificationCompatibilityValidator`
  (Checkpoint 2) — wired into `TemplateModificationManager.add_modification`.
- Seed/default: a new template defaults to `MODEL_SET` with its own `model` auto-included
  in `template_model` ([D7](../decisions.md)).
- Full DB rebuild + seed.

## Out of scope

- Any UI / screens — deferred ([D9](../decisions.md)).
- Re-deriving applicability for child templates (`TemplateChild`) — the compatibility
  guard covers modifications, not nested templates, this pass.

## Dependencies

- **Phase 1 complete** — `ApplicabilityMode`, `ApplicabilityPolicy`, `ApplicabilityStruct`,
  and `ApplicabilitySyncHandler` exist and are tested. Phase 2 imports them unchanged.

## Deliverables

- `applicability_mode` field on `ConfigurationTemplate`; `TemplateAssetClass`,
  `TemplateModel` models.
- `applicability/template_applicability_manager.py`.
- `applicability/applicability_compatibility_policy.py`.
- `guards/template_modification_compatibility_guard.py` —
  `TemplateModificationCompatibilityValidator`.
- Refactored `guards/configuration_assignment_guard.py`.
- Default-seeding of the template's own model into `template_model` at create time.
- Regenerated migrations; green `seed_dev`.

## Exit criteria

- [ ] A `ConfigurationTemplate` supports all four modes + class/model allow-lists, using
      the **same** `ApplicabilityPolicy` as modifications (no duplicated matrix logic).
- [ ] A newly created template defaults to `MODEL_SET` containing its `model`, and is
      assignable only to assets of that model — **reproducing today's gate** until widened.
- [ ] Widening a template to `CLASS_ONLY` lets it be assigned to any asset in the listed
      classes; `ConfigurationManager.assign` enforces it via `ApplicabilityPolicy`.
- [ ] Adding a modification whose applicability **provably** excludes assets the template
      permits is **rejected** at `add_modification` time with a clear reason.
- [ ] Adding a modification with indeterminate compatibility is **allowed**, and a later
      `add_actual_modification` on a disallowed asset is still refused (backstop).
- [ ] `MODEL_SET` auto-derive and `STRICT` dead-model guard behave identically to Phase 1
      (shared handler).
- [ ] `seed_dev` runs green after a full DB rebuild.
