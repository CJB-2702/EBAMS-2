# Phase 4 — Data & Relational Plan

*All models below are **built**. No schema added this phase.*

## Entities

| Model | `db_table` | Key fields | Relationships |
| :--- | :--- | :--- | :--- |
| `CapabilityDefinition` | `capability_definition` | `name` (unique), `code` (unique), `is_active` | catalog root |
| `AssetClassCapability` | `asset_class_capability` | `is_active` | FK `asset_class` (CASCADE); FK `capability_definition` (PROTECT); unique(class, def) |
| `ModelCapability` | `asset_model_capability` | `is_active` | FK `model`→AssetModel (CASCADE); FK `capability_definition` (PROTECT); unique(model, def) |
| `AssetCapability` | `asset_capability` | `is_active`, `notes` | FK `asset` (CASCADE); FK `capability_definition` (PROTECT); unique(asset, def) |

Plus the cached field **`Asset.capability_status`** (CharField, built) — a
summary string recomputed when an asset's capabilities change.

## The cascade

```
CapabilityDefinition  (catalog)
        ▲ referenced by all three layers
        │
AssetClassCapability ──(model create copies active)──▶ ModelCapability
ModelCapability      ──(asset create copies active)──▶ AssetCapability
```

- **On model create** (`AssetModelFactory`): for each active
  `AssetClassCapability` of the model's `asset_class`, create a `ModelCapability`
  (skip existing — unique constraint + idempotency).
- **On asset create** (`AssetCreationOrchestrator` P4 seam): for each active
  `ModelCapability` of the asset's `model`, create an `AssetCapability`.

## Invariants

1. **Uniqueness** per layer (`unique(owner, capability_definition)`) — copy steps
   must be idempotent (get-or-create semantics).
2. **Catalog protection** — layers reference `CapabilityDefinition` via PROTECT;
   only active definitions are cascaded.
3. **`capability_status`** is derived, never authoritative — recompute from
   `AssetCapability` rows; do not let callers set it directly.

## Relational read for "asset readiness"

```
Asset ─1──< AssetCapability ─*──1 CapabilityDefinition
```
The asset's effective capabilities = its `AssetCapability` rows (the per-asset
layer is authoritative; class/model layers are templates/defaults only).
