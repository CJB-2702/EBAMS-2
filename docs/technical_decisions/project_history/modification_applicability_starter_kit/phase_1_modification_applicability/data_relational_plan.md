# Phase 1 — Data & Relational Plan

*Adds an applicability mode to `DefinedModification` and two allow-list junction tables.
Audit columns (`created_at`, `updated_at`, `created_by_id`, `updated_by_id`) are present
on every table per project convention but omitted from the field lists below. RBAC /
ownership scoping is out of scope for this plan.*

## The shared enum

`ApplicabilityMode` — a `TextChoices` enum, **not a table**, defined once in
`app/assets/models/configurations/applicability_mode.py` and imported by both
`DefinedModification` (this phase) and `ConfigurationTemplate` (Phase 2):

| value | label |
| :--- | :--- |
| `strict` | Class and model |
| `class_only` | Class only |
| `model_set` | Model set |
| `unrestricted` | Unrestricted |

## Changed table

| Table | Change |
| :--- | :--- |
| `defined_modification` | **Add** `applicability_mode` (enum, default `unrestricted`). |

> Default `unrestricted` preserves today's "apply anywhere" behavior
> ([D7](../decisions.md)).

## New tables

| New model | `db_table` | Key fields | Purpose |
| :--- | :--- | :--- | :--- |
| `ModificationAssetClass` | `modification_asset_class` | `defined_modification` FK→`DefinedModification` (CASCADE); `asset_class` FK→`AssetClass` (PROTECT) | One allowed/derived asset class for a modification. |
| `ModificationModel` | `modification_model` | `defined_modification` FK→`DefinedModification` (CASCADE); `model` FK→`AssetModel` (PROTECT) | One allowed asset model for a modification. |

**Conventions (matching `asset_class_capability` / `asset_model_domain`):**

- Owning side (`defined_modification`) → `on_delete=CASCADE`: deleting a modification
  drops its allow-list rows.
- Referenced side (`asset_class` / `model`) → `on_delete=PROTECT`: a class/model in use by
  an allow-list cannot be deleted out from under it.
- `UniqueConstraint` on (`defined_modification`, `asset_class`) →
  `uq_modification_asset_class`; on (`defined_modification`, `model`) →
  `uq_modification_model`.

> **Key note — combine rule (carry into the model docstrings):** the two lists are
> combined with **AND** when both are enforced (`STRICT` mode). In `MODEL_SET` mode the
> `modification_asset_class` rows are **system-derived** (the distinct parents of the
> `modification_model` rows), not hand-authored. See
> [`../modification_class_and_model_matrix_behaviors.md`](../modification_class_and_model_matrix_behaviors.md).

## Relational flow

```
AssetClass ──PROTECT──< ModificationAssetClass >──CASCADE── DefinedModification
AssetModel ──PROTECT──< ModificationModel       >──CASCADE──┘
                                                  (applicability_mode)

   AssetModel ──(exactly one)──▶ AssetClass        ← the single-parent fact that makes
                                                      the class set derivable in MODEL_SET
```

The single mandatory `AssetModel.asset_class` FK (already in the schema) is what lets
`ApplicabilitySyncHandler` compute the derived class set from the model list.

## What does NOT change

- `ActualModification` is unchanged structurally — the applicability check is enforced in
  the control layer at `add_actual_modification` time, not by a new column.
- No changes to `AssetClass` or `AssetModel`.
