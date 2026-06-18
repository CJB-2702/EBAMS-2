# Architecture Contrast — old `asset_management` vs new `Django-Starter-Kit`

Read before building any phase. Two kinds of change overlap here: a **framework
port** (Flask/SQLAlchemy → Django) and a **domain remodel** (locations →
domains, MakeModel → AssetModel, core → assets, single Event → Event/thread).

## 1. Framework & layering

| Aspect | Old `asset_management` | New `Django-Starter-Kit` |
| :--- | :--- | :--- |
| Web/ORM | Flask + SQLAlchemy (`db.session`, `Model.query.get_or_404`) | Django (`Model.objects`, `transaction.atomic`, `get_object_or_404`) |
| Layers | `data / business / services / presentation`, parallel-mirrored folders | per sub-app `models / control_layer / presentation_layer{entrypoints,search,tools}` |
| "Business" home | `app/business/<domain>/` | `app/<subapp>/control_layer/` |
| Control vocabulary | loose: `Context`, `Factory`, `Manager`, `Handler` | strict suffix vocabulary: `Struct, Context, Factory, BulkFactory, Handler, Manager, Policy/Validator/StateMachine (Guard), Narrator, Adaptor, Orchestrator` |
| Transactions | per-call `db.session.commit()`, independent commits | **one `transaction.atomic()` per workflow**; inner calls cooperate |
| Reads | anywhere (20-line route exception) | simple (≤2 tables) in entrypoints; complex in `presentation_layer/search` or a `domain_struct` loader |
| Audit fields | `created_by_id` / `updated_by_id` via `UserCreatedBase` | `created_at/updated_at/created_by/updated_by` via `AuditFieldsMixin` |
| Soft delete | per-table flags (e.g. `user_viewable`) | `SoftDeleteMixin` (`deleted_at`) on Event/Comment |

**Porting rule:** keep the *intent* of old Context/Manager/Factory classes, but
rename to the strict suffix vocabulary and collapse independent commits into one
atomic workflow per entry point. See
[`docs/Architecture/oop_control_patterns.md`](../docs/Architecture/oop_control_patterns.md).

## 2. Domain remodel (the substance of the migration)

| Old concept | New concept | Implication for control logic |
| :--- | :--- | :--- |
| **`MajorLocation`** FK on Asset; events tagged `major_location_id` | **`Domain`** FK on Asset; class/model scoped via junctions (`AssetClassDomain`, `ModelDomain`); events carry `domain_id` | Everywhere the old code read/wrote `major_location_id`, the new code uses `domain_id`. Access scoping is domain-based (`user.get_all_domain_ids()`). |
| **`MakeModel`** (`make`, `model`, `year`; unique triple) | **`AssetModel`** (`model_name`, `subtype_name`, `revision`; self-ref `base_model` revision tree) + **`Manufacturer`** extracted out (via `ModelManufacturer`, one primary) | "make" is no longer a string on the model — it is a related `Manufacturer`. Duplicate-detection logic changes from make/model/year to model_name/subtype/revision. Revisions form a tree. |
| `asset_class`, `make_model`, `asset` in **`core`** | same entities in the **`assets`** app | Imports move from `app.data.core.asset_info.*` → `app.assets.models.*`. |
| Asset → AssetClass **via** make_model only | Asset has a **direct denormalized `asset_class` FK** (`# DELIBERATE ANTI-PATTERN`) propagated from `AssetModel.asset_class` | New responsibility: a propagation handler keeps `Asset.asset_class` in sync when `AssetModel.asset_class` changes. The old code derived asset_class through make_model at read time. |
| Single **`Event`** model with `asset_id`, `major_location_id`, `event_type` string | **`Event`** (generic, `domain`-scoped, `EventType` enum) + **`ActivityThread`** proxy; asset↔event link **reserved for `app/assets`** | Lifecycle eventing is created via the events app and *linked* to the asset through an asset↔event table this kit must add. Details in [`event_context_study.md`](event_context_study.md). |
| Asset images = `AssetImage` → `Attachment` (own table) | `AssetImage` → **`events.File`**; comments/attachments live in the events app | Image/file writes go through the events app's file tooling, not a local attachment table. |
| `MeterHistory` columns `meter1..4` per row | `MeterHistory` is **one row per (asset, meter_index, value, recorded_at)** | Old "update 4 meters" → new "write N MeterHistory rows, one per changed meter index." Asset still caches `meter1..4` current values. |

## 3. What is already done vs. what this kit plans

- **Done:** all `app/assets/models/` (core, capabilities, configurations,
  details, domain_junctions) and the entire `events` app control layer.
- **Seeded:** `app/assets/control_layer/handlers/asset_handler.py` (creates an
  Asset with its two `ActivityThread`s) — the embryo of the P1 orchestrator.
- **To build (this kit):** the asset/model **control layer** — Structs,
  Contexts, Factories, Managers, Guards, Narrators, Adaptors, and the creation
  **Orchestrator** — plus the lifecycle-eventing wiring and the asset↔event
  link.

## 4. Cross-cutting porting checklist

- [ ] Replace `major_location_id` → `domain_id` everywhere.
- [ ] Replace `make_model` / `MakeModel` → `AssetModel` (+ `Manufacturer` where "make" was used).
- [ ] Replace `db.session` patterns with `transaction.atomic()` + `Model.objects`.
- [ ] Replace independent commits with one atomic block per workflow.
- [ ] Replace direct `Event(asset_id=...)` creation with events-app `EventHandler` + asset↔event link.
- [ ] Rename classes to the strict suffix vocabulary.
- [ ] Move any non-asset logic found in old `business/core` (events, users) **out of scope** — see [`migration_map.md`](migration_map.md).
