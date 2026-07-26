---
type: "Technical Decision"
title: "Phase 2 — Data & Relational Plan"
description: "exactly mirroring Phase 1."
tags: [technical-decisions, technical-decision, project-history, modification-applicability-starter-kit, phase-2-template-applicability]
context_tier: 2
---

# Phase 2 — Data & Relational Plan

*Adds an applicability mode to `ConfigurationTemplate` and two allow-list junction tables,
exactly mirroring Phase 1. Reuses the `ApplicabilityMode` enum from Phase 1 — no new enum.
Audit columns present per convention, omitted below. RBAC/ownership out of scope.*

## Changed table

| Table | Change |
| :--- | :--- |
| `configuration_template` | **Add** `applicability_mode` (enum, default `model_set`). The existing single `model` FK is **kept** as the authored-for anchor (revision tree, `TemplateChild` guard) — it is no longer the assignment gate. |

> Default `model_set` + auto-seeding the template's own `model` into `template_model`
> reproduces today's exact-model assignment gate ([D7](../decisions.md)).

## New tables

| New model | `db_table` | Key fields | Purpose |
| :--- | :--- | :--- | :--- |
| `TemplateAssetClass` | `template_asset_class` | `template` FK→`ConfigurationTemplate` (CASCADE); `asset_class` FK→`AssetClass` (PROTECT) | One allowed/derived asset class for a template. |
| `TemplateModel` | `template_model` | `template` FK→`ConfigurationTemplate` (CASCADE); `model` FK→`AssetModel` (PROTECT) | One allowed asset model for a template. |

**Conventions (identical to Phase 1 / existing junctions):**

- Owning side (`template`) → `CASCADE`; referenced side (`asset_class`/`model`) → `PROTECT`.
- `UniqueConstraint` on (`template`, `asset_class`) → `uq_template_asset_class`; on
  (`template`, `model`) → `uq_template_model`.

> **Key note — combine rule (carry into docstrings):** same **AND** semantics and same
> `MODEL_SET` class-derivation as modifications. See
> [`../modification_class_and_model_matrix_behaviors.md`](../modification_class_and_model_matrix_behaviors.md).

## Relational flow

```
AssetClass ──PROTECT──< TemplateAssetClass >──CASCADE── ConfigurationTemplate ──PROTECT──▶ AssetModel (authored `model`)
AssetModel ──PROTECT──< TemplateModel       >──CASCADE──┘   (applicability_mode)

ConfigurationTemplate ──< TemplateModification >── DefinedModification   (existing; gated by Checkpoint 2)
ConfigurationTemplate ──< AssetConfiguration  >── Asset                  (existing; gated by Checkpoint 4)
```

## Relationship to the existing template tables

- `TemplateModification` (existing) is unchanged structurally; the **compatibility guard**
  is enforced in the control layer at `add_modification` time (Checkpoint 2), not by a new
  column.
- `AssetConfiguration` (existing) is unchanged; the **assignment gate** is enforced by the
  refactored `ConfigurationAssignmentValidator` (Checkpoint 4).
- The single `ConfigurationTemplate.model` FK stays — `create_new_revision()` and the
  `TemplateChild` self-reference guard depend on it.

## What does NOT change

- `AssetClass`, `AssetModel`, `TemplateModification`, `TemplateChild`, `AssetConfiguration`
  schemas.
- The Phase 1 modification tables and the shared enum.
