# Phase 1 — Data & Relational Plan

*Per [`docs/starter_kit_process/how_to_data_relational_planning_document.md`](../../docs/starter_kit_process/how_to_data_relational_planning_document.md).
Models marked **(built)** already exist; **(NEW)** is added this phase.*

## Entities operated on

| Table | Key fields | Relationships |
| :--- | :--- | :--- |
| `Asset` **(built)** | `name`, `serial_number` (unique), `status`, `capability_status`, `is_active`, `meter1..4`, `tags`, `detail_rows_created` | FK `domain`→Domain (PROTECT); FK `model`→AssetModel (PROTECT); FK `asset_class`→AssetClass (PROTECT, *denormalized*); self-FK `parent_asset`, `root_asset`; `depth_from_root`; O2O `photo_gallery`,`documentation`→ActivityThread |
| `AssetModel` **(built)** | `model_name`, `subtype_name`, `revision`, `is_base_model`, `meterN_unit` | self-FK `base_model`; FK `asset_class`→AssetClass; M2M `manufacturers` (through `ModelManufacturer`); M2M `domains` (through `ModelDomain`) |
| `AssetClass` **(built)** | `name` (unique), `category`, `restrict_to_domain_set` | M2M `domains` (through `AssetClassDomain`) |
| `Manufacturer` **(built)** | `name` (unique), `code`, `website` | reverse of `ModelManufacturer` |
| `ModelManufacturer` **(built)** | `is_primary` | FK `model`, FK `manufacturer`; unique(model, manufacturer) |
| `MeterHistory` **(built)** | `meter_index`, `value`, `recorded_at`, `source` | FK `asset` (CASCADE) |
| `AssetParentHistory` **(built)** | `previous/new_parent`, `previous/new_root`, `previous/new_depth` | FK `asset` (CASCADE) + 4 self-FKs |
| `AssetImage` **(built)** | `is_primary`, `sort_order` | FK `asset`; FK `attachment`→**events.File** |
| `ModelDomain` / `AssetClassDomain` **(built)** | unique pair | scope junctions → Domain |
| **`AssetEvent` (NEW)** | optional `role`; audit | FK `asset`→Asset (CASCADE); FK `event`→events.Event (PROTECT); unique(asset, event) |

## The denormalization to maintain

```
AssetModel.asset_class ──(authoritative)──▶ Asset.asset_class  (cached copy)
```
`Asset.asset_class` is a `# DELIBERATE ANTI-PATTERN` denormalized FK. On asset
create it is copied from the model; when `AssetModel.asset_class` changes, every
child asset must be updated (see `ModelAssetClassPropagationHandler`, P1 control
plan).

## The new asset ↔ event relationship

Old: `Event.asset_id` (one event → one asset, direct FK).
New: `Event` is generic/`domain`-scoped; the link is owned by the assets app.

```
Asset 1───* AssetEvent *───1 Event(event_type=asset_management, domain=asset.domain)
```

See [`../event_context_study.md`](../event_context_study.md) §3 for the open
choice (join table vs. field on `AssetManagementDetail`) — **recommendation: the
`AssetEvent` join table in `app/assets/models/`.**

## Revision tree (AssetModel)

```
AssetModel(is_base_model=True, base_model=None)
   └── AssetModel(is_base_model=False, base_model=▲)   # a revision
```
Duplicate detection key changes from old `(make, model, year)` to
`(model_name, subtype_name, revision)` — validate in `AssetModelFactory`.

## Meter remodel

Old `MeterHistory` had `meter1..4` columns on one row. New writes **one row per
changed meter** `(asset, meter_index, value, recorded_at, source)`. The asset
keeps `meter1..4` as current-value cache. `MeterManager` writes N rows + updates
the cache in one transaction.

## Schema-change flag

Adding `AssetEvent` is a schema change → after defining it, run the full reset
(`/db-rebuild` or `python dev_tools/delete_database_rebuild_models.py --seed`).
No incremental migrations during development (CLAUDE.md rule 1).
