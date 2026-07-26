---
type: "Technical Decision"
title: "Phase 4 — Control Layer Plan"
description: "app/assets/control_layer/."
tags: [technical-decisions, technical-decision, project-history, asset-control-layer-starter-kit, phase-4-capabilities]
context_tier: 2
---

# Phase 4 — Control Layer Plan

## Target tree (built)

```
app/assets/control_layer/
├── capabilities/
│   ├── capability_factory.py           # CapabilityFactory (copy-on-create cascade)
│   └── capability_manager.py           # CapabilityManager (4-layer CRUD)
├── domain_structs/
│   └── asset_capability_struct.py      # AssetCapabilityStruct
└── guards/
    └── capability_assignment_guard.py  # CapabilityAssignmentValidator
```

`CapabilityStatusHandler` is **not built** — `Asset.capability_status` is owned by
the maintenance module (driven by `AssetLimitationRecord`), not by `AssetCapability`
rows.  See decisions below.

## Factory (copy-on-create cascade)

### `CapabilityFactory.copy_class_to_model(model, actor)`
- Get all active `AssetClassCapability` for `model.asset_class`.
- For each, `get_or_create ModelCapability(model, cap_def)` — idempotent.
- **No events emitted** (template-layer copy only).
- Called from `AssetModelFactory.create()` after plugin provisioning.

### `CapabilityFactory.copy_model_to_asset(asset, actor)`
- Get all active `ModelCapability` for `asset.model`.
- For each, `get_or_create AssetCapability(asset, cap_def)` — idempotent.
- For each **newly created** row: emit "Capability Added" `Event` + `AssetEvent` link.
- Called from `AssetCreationOrchestrator.create()` inside the creation transaction (P4 seam).

## Manager (day-to-day CRUD)

### `CapabilityManager(actor)`

**Catalog:**
- `define(name, code, description)` — unique name + code (raises on collision).
- `deactivate_definition(cap_def)` — soft-delete.

**Class layer:**
- `add_to_class(asset_class, cap_def)` — guarded; no events.
- `remove_from_class(class_cap)` — soft-deactivate.
- `update_class_capability(class_cap, is_active)`

**Model layer:**
- `add_to_model(model, cap_def)` — guarded; no events.
- `remove_from_model(model_cap)` — soft-deactivate.
- `update_model_capability(model_cap, is_active)`

**Asset layer (event-tracked):**
- `add_to_asset(asset, cap_def, qty, notes)` — guards + creates "Capability Added" event.
- `remove_from_asset(asset_cap)` — creates "Capability Removed" event, sets `is_active=False`.
- `annotate_asset_capability(asset_cap, qty, notes)` — content update, no event.

## Guard

### `CapabilityAssignmentValidator`
- `check_definition_active(cap_def)` — raises if `is_active=False`.
- `check_no_duplicate_class(asset_class, cap_def)` — raises if row exists.
- `check_no_duplicate_model(model, cap_def)` — raises if row exists.
- `check_no_duplicate_asset(asset, cap_def)` — raises if row exists (active or inactive;
  remove first then re-add).

## Struct

### `AssetCapabilityStruct.from_asset(asset, active_only=True)`
- Loads all `AssetCapability` rows with resolved `CapabilityDefinition`.
- Loads active `ModelCapability` IDs to compute provenance.
- `is_from_model(asset_cap)` → True if cap came from model template.
- `to_dict()` — id, name, code, is_active, qty, notes, provenance ("model"|"manual").

## Orchestrator wiring (seams filled)

`AssetModelFactory.create`:
```python
# P4: copy class capability templates to new model.
CapabilityFactory.copy_class_to_model(model=model, actor=actor)
```

`AssetCreationOrchestrator.create`:
```python
# 4. P4: copy model capability templates to asset.
CapabilityFactory.copy_model_to_asset(asset=asset, actor=actor)
```

## Schema additions (applied)

| Model | Field added |
| :--- | :--- |
| `AssetCapability` | `qty` PositiveSmallIntegerField(null, blank) |

## Event pattern

Asset-layer events follow the same pattern as P3:
```python
event = Event.objects.create(domain_id=asset.domain_id, event_type=ASSET_MANAGEMENT, ...)
AssetEvent.objects.create(asset=asset, event=event, role="capability", ...)
```
Narrator strings: `capability_added`, `capability_added_from_model`, `capability_removed`.

## Decisions from interrogation session (2026-06-04)

- D1: Factory events — **one event per row** (old behavior preserved).
- D2: `AssetCapability.qty` — **added back**; no expiry/certification dates.
- D3: `CapabilityStatusHandler` — **dropped**.  `Asset.capability_status` is driven by
  `AssetLimitationRecord` in the maintenance module, not by `AssetCapability` rows.
  The field remains on `Asset` for the maintenance module to write.
