---
type: "Technical Decision"
title: "Phase 4 — Old → New Migration Notes"
description: "built unique constraints (uq_asset_model_capability, uq_asset_capability)."
tags: [technical-decisions, technical-decision, project-history, asset-control-layer-starter-kit, phase-4-capabilities]
context_tier: 2
---

# Phase 4 — Old → New Migration Notes

## Source files

- `app/business/assets/capabilities/capability_factory.py`
- `app/business/assets/capabilities/capability_manager.py`
- `app/business/assets/capabilities/handlers.py`

## Mapping

| Old | New | Change |
| :--- | :--- | :--- |
| `CapabilityFactory` (copy-on-create) | `CapabilityFactory.copy_class_to_model` + `copy_model_to_asset` | Triggered by the **orchestrator / model factory** seams, not the registry pipeline. |
| `CapabilityManager` | `CapabilityManager` | Keep four-table CRUD/query; rename to suffix vocab; atomic workflows. |
| `MakeModelCapability` | `ModelCapability` | Model already renamed in new schema. |
| `handlers.py` | folded into factory/manager + `CapabilityStatusHandler` | Single-step handlers only where heavy. |
| (status string maintenance) | `CapabilityStatusHandler.recompute` | Sole writer of `Asset.capability_status`. |

## Behavioral notes

- **Cascade idempotency:** copy steps must use `get_or_create` against the
  built unique constraints (`uq_asset_model_capability`, `uq_asset_capability`)
  so re-running creation or backfilling never duplicates.
- **Active-only propagation:** only `is_active` template rows cascade (confirm the
  old rule for whether inactive class capabilities still seed models).
- **Authority model:** the per-asset layer (`AssetCapability`) is the source of
  truth for what an asset can do; class/model layers are defaults/templates.
  Preserve any old logic that let an asset diverge from its model defaults.
- **`capability_status`** was likely computed in the old app — port the exact
  derivation rule into `CapabilityStatusHandler`.

## Drop / avoid

- Registry/pipeline registration of the capability copy step — it is now an
  explicit orchestrator call (D1).
- `db.session` independent commits — copy runs inside the create transaction.
- `make_model` / `major_location` references → `AssetModel` / `domain`.

## Confirm against old source before coding

1. Does asset-create copy **all** model capabilities, or only a default subset?
2. Are inactive definitions skipped at every layer?
3. The exact formula for `capability_status` (counts? a category? a flag?).
