---
type: "Technical Decision"
title: "Phase 1 — Old → New Migration Notes"
description: "Porting checklist for Phase 1, against the old Flask source."
tags: [technical-decisions, technical-decision, project-history, asset-control-layer-starter-kit, phase-1-asset-and-model-contexts]
context_tier: 2
---

# Phase 1 — Old → New Migration Notes

Porting checklist for Phase 1, against the old Flask source.

## Source files

- `app/business/core/asset_context.py`
- `app/business/core/make_model_context.py`
- `app/business/core/post_create_handlers.py`
- `app/business/assets/details/asset_parent_child_relationship_manager.py`
- (reference) `app/business/core/event_context.py`

## `AssetContext` (old) → `AssetContext` + Factory + Orchestrator + Managers

| Old member | New home | Change |
| :--- | :--- | :--- |
| `__init__(asset_or_id)` | `AssetContext(asset_id, actor)` + `AssetStruct` | Backed by a Struct; carries `actor`. |
| `post_create_pipeline`, `register_post_create` | **deleted** | Replaced by `AssetCreationOrchestrator` (D1). |
| `_create_asset_and_event` | `AssetFactory.create` + `AssetEventNarrator` | Threads created first (already in `asset_handler.py`); event via events app + `AssetEvent`; `major_location_id` → `domain_id`. |
| `create` / `create_from_dict` | `AssetCreationOrchestrator.create` | One atomic transaction; no independent per-handler commits. |
| `update_meters` | `MeterManager.record` | One `MeterHistory` **per meter index** (not 1 row of 4 cols); refresh cache. |
| `edit` | `AssetContext.edit` + `AssetEditAdaptor` + `AssetEventNarrator` | Key-field diff → lifecycle event; `make_model_id`→`model_id`; `major_location_id`→`domain_id`. |
| `add_asset_image` / `remove` / `set_primary` | `AssetContext.add_image(...)` | Attachments go through **events.File** + `AssetImage`, not a local `Attachment` table. |
| `creation_event`, `recent_events` | reads via `events` search + `AssetEvent` | Query events through the link, not `Event.asset_id`. |

## `MakeModelContext` (old) → `AssetModelContext` + `AssetModelFactory`

| Old | New | Change |
| :--- | :--- | :--- |
| `MakeModel` everywhere | `AssetModel` | Field remodel below. |
| `make`, `model`, `year` | `model_name`, `subtype_name`, `revision` | "make" string → **`Manufacturer`** via `ModelManufacturer`. |
| duplicate `(make, model, year)` | duplicate `(model_name, subtype_name, revision)` | In `AssetModelUniquenessValidator`. |
| `_create_make_model_and_event` | `AssetModelFactory.create` | "Model Created" via events app. |
| `asset_class` passthrough | `AssetModelContext.set_asset_class` → `ModelAssetClassPropagationHandler` | New: propagate to child assets' denormalized `asset_class`. |
| `get_assets`, `asset_count` | `AssetModelStruct` / search | Move queries behind struct/search. |

## Parent/child manager (old) → `AssetHierarchyManager`

- Port cycle-prevention and root/depth recomputation.
- New: write an **`AssetParentHistory`** row on every change (old code may not
  have; the new model exists and the audit is expected).

## Things to consciously DROP

- `post_create_handlers.py` ABCs and the registry — see
  [`../../optional_detail_hooking.md`](../../optional_detail_hooking.md).
- SQLAlchemy idioms: `db.session`, `.query`, `flush()`, `get_or_404` →
  Django `objects`, `transaction.atomic`, `get_object_or_404`.
- Independent commits inside loops → one atomic workflow.
- Deriving `asset_class` through `make_model` at read time → it is now a stored,
  propagated field on `Asset`.

## Watch-outs

- The two `ActivityThread`s are **required** (O2O, PROTECT) and must be created
  **before** the asset row — already correct in `asset_handler.py`.
- `serial_number` is globally unique in the new model — validator must check
  across all domains.
- `Asset.detail_rows_created` (JSON) is a P2 concern; leave untouched in P1.
