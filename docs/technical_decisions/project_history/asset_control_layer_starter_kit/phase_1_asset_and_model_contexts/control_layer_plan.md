---
type: "Technical Decision"
title: "Phase 1 — Control Layer Plan"
description: "and [docs/Architecture/patterns/oop_control_patterns.md](../../docs/Architecture/patterns/oop_control_patterns.md)."
tags: [technical-decisions, technical-decision, project-history, asset-control-layer-starter-kit, phase-1-asset-and-model-contexts]
context_tier: 2
---

# Phase 1 — Control Layer Plan

*Per [`docs/starter_kit_process/how_to_plan_control_layer.md`](../../docs/starter_kit_process/how_to_plan_control_layer.md)
and [`docs/Architecture/patterns/oop_control_patterns.md`](../../docs/Architecture/patterns/oop_control_patterns.md).
Names use the strict suffix vocabulary.*

## Target tree

```
app/assets/control_layer/
├── domain_structs/
│   ├── asset_struct.py            # AssetStruct
│   └── asset_model_struct.py      # AssetModelStruct
├── asset_context.py               # AssetContext
├── asset_model_context.py         # AssetModelContext
├── factories/
│   ├── asset_factory.py           # AssetFactory
│   └── asset_model_factory.py     # AssetModelFactory
├── orchestrators/
│   └── asset_creation_orchestrator.py  # AssetCreationOrchestrator
├── managers/
│   ├── meter_manager.py           # MeterManager
│   └── asset_hierarchy_manager.py # AssetHierarchyManager
├── handlers/
│   ├── asset_handler.py           # EXISTS — fold into AssetFactory/Orchestrator
│   └── model_asset_class_propagation_handler.py  # ModelAssetClassPropagationHandler
├── guards/
│   ├── asset_serial_number_guard.py    # AssetSerialNumberValidator
│   └── asset_model_uniqueness_guard.py # AssetModelUniquenessValidator
├── narrators/
│   └── asset_event_narrator.py    # AssetEventNarrator
└── adapters/
    ├── asset_create_adaptor.py    # AssetCreateAdaptor
    └── asset_edit_adaptor.py      # AssetEditAdaptor
```

## Structs (read models)

- **`AssetStruct`** — base `Asset` row guaranteed; `eager=True` loads model,
  asset_class, domain, both threads, current meters, parent/root, image set.
  `to_dict()` for templates. No mutations.
- **`AssetModelStruct`** — base `AssetModel`; eager loads asset_class,
  manufacturers (+ primary), domains, revision relations, model-detail templates.

## Contexts (entry points, one aggregate id each)

- **`AssetContext(asset_id, actor)`** + `from_struct()`. Domain verbs:
  `edit(post_data)`, `record_meters(readings)`, `reparent(new_parent_id)`,
  `add_image(uploaded_file)`. Delegates to managers; never raw ORM in callers.
  Holds `meters` (→ `MeterManager`) and `hierarchy` (→ `AssetHierarchyManager`)
  as properties.
- **`AssetModelContext(model_id, actor)`** + `from_struct()`. Verbs:
  `edit(post_data)`, `set_asset_class(asset_class_id)` (→ propagation handler),
  `link_manufacturer(...)`, `set_primary_manufacturer(...)`.

## Factories (root creation)

- **`AssetModelFactory.create(*, data, actor)`** — validate via
  `AssetModelUniquenessValidator`; create `AssetModel`; link manufacturers
  (`ModelManufacturer`, one primary); link domains; emit "Model Created" event.
  Returns `AssetModelStruct`.
- **`AssetFactory.create(*, data, actor)`** — the existing `asset_handler.py`
  logic, refactored: validate serial; create the two `ActivityThread`s; create
  the `Asset` (copy `asset_class` from model); set initial parent/depth. **No
  commit of its own** — runs inside the orchestrator's transaction. Returns the
  `Asset` (or `AssetStruct`).

## Orchestrator (the seam — D1)

**`AssetCreationOrchestrator.create(*, data, actor)`** — single
`transaction.atomic()`:
1. `AssetFactory.create(...)` (threads + asset)
2. lifecycle event: `AssetEventNarrator` → events-app event → `AssetEvent` link
3. **extension points (no-ops in P1, filled later):**
   `# P2: provision detail rows`, `# P3: apply default configuration`,
   `# P4: copy capability templates`

This is the one place that names the create-time fan-out. Adding a step later =
edit this method (intentional, visible cost; see
[`../optional_detail_hooking.md`](../../optional_detail_hooking.md)).

## Managers (stable sub-areas on the asset)

- **`MeterManager`** — `record(readings, *, recorded_at=None, source=None)`:
  validate ≥1 reading; write one `MeterHistory` per changed index; refresh
  `Asset.meterN` cache; all in one transaction. (Was `AssetContext.update_meters`.)
- **`AssetHierarchyManager`** — `reparent(new_parent_id)`: recompute root +
  depth, guard against cycles, write `AssetParentHistory`. (Was
  `asset_parent_child_relationship_manager.py`.)

## Handlers (single heavy steps)

- **`ModelAssetClassPropagationHandler.run(*, model, new_asset_class, actor)`** —
  bulk-update `Asset.asset_class` for all assets of the model when the model's
  class changes. Keeps the `# DELIBERATE ANTI-PATTERN` denormalization correct.

## Guards

- **`AssetSerialNumberValidator`** — uniqueness + format of `serial_number`.
- **`AssetModelUniquenessValidator`** — duplicate `(model_name, subtype_name,
  revision)`; base/revision consistency (`is_base_model` ⇔ `base_model`).

## Narrator

- **`AssetEventNarrator`** — human-readable `title`/`description` for lifecycle
  events: created, key-field diff, (optional) meter change. Centralizes the
  strings the old code inlined.

## Adapters

- **`AssetCreateAdaptor` / `AssetEditAdaptor`** — map `request.POST` (strings) to
  typed factory/context inputs (ints, enums), resolving `domain_id`, `model_id`.
  Type-conversion is the adapter's job, never the model's.

## Delegation flow (create an asset)

```
entrypoint (thin)
  → AssetCreateAdaptor.from_post(request.POST)
  → AssetCreationOrchestrator.create(data=…, actor=request.user)
        atomic:
          AssetFactory.create → AssetSerialNumberValidator
                              → ActivityThread ×2 → Asset(asset_class←model)
          AssetEventNarrator → events Event → AssetEvent link
          # P2/P3/P4 extension points (no-op)
  → redirect/render AssetStruct.to_dict()
```

## Open questions for implementation

1. Lifecycle event creation **inside** the asset atomic block (recommended) vs.
   `EventHandler.create` (nested atomic). See event study §4.2.
2. Does `EventHandler` need a "system/already-complete" create path? (event study
   §4.4) — only change to the events app if yes.
3. `AssetEvent` `role` column now, or add when maintenance/dispatch need it?
