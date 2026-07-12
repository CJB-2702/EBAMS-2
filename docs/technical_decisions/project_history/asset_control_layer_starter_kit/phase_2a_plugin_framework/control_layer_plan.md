---
type: "Technical Decision"
title: "Phase 2a — Control Layer Plan"
description: "app/assets/plugins/."
tags: [technical-decisions, technical-decision, project-history, asset-control-layer-starter-kit, phase-2a-plugin-framework]
context_tier: 2
---

# Phase 2a — Control Layer Plan

## Target tree

```
app/assets/plugins/
├── __init__.py
├── base/
│   ├── plugin_descriptor.py          # AssetPlugin (base contract), PluginTarget, PluginCardinality
│   └── plugin_factory.py             # PluginFactory (base provision; the extension seam)
├── registry.py                       # PLUGIN_REGISTRY (explicit list) + lookups
├── purchase_info/                    # reference asset-target plugin (one-to-one)
│   ├── models.py                     # PurchaseInfo(AssetPluginTableVirtual)
│   ├── plugin.py                     # PurchaseInfoPlugin(AssetPlugin)
│   └── factory.py                    # PurchaseInfoFactory(PluginFactory)   # optional; base used if absent
└── model_info/                       # reference model-target plugin (one-to-one)
    ├── models.py                     # ModelInfo(ModelPluginTableVirtual)
    ├── plugin.py                     # ModelInfoPlugin(AssetPlugin)
    └── factory.py

app/assets/control_layer/plugins/
├── provisioning/
│   ├── asset_plugin_provisioner.py   # AssetPluginProvisioner (Handler)
│   └── model_plugin_provisioner.py   # ModelPluginProvisioner (Handler)
├── managers/
│   ├── asset_plugins_manager.py      # AssetPluginsManager (property on AssetContext)
│   └── model_plugins_manager.py      # ModelPluginsManager (property on AssetModelContext)
├── domain_structs/
│   ├── asset_plugins_struct.py       # AssetPluginsStruct (union read)
│   └── model_plugins_struct.py       # ModelPluginsStruct (union read)
└── guards/
    └── plugin_registry_guard.py      # PluginRegistryValidator
```

> **Layering note.** Plugin *packages* (table + descriptor + factory) live under
> `app/assets/plugins/`. The framework's coordination (provisioners, managers,
> structs, guard) lives in the control layer. The host models never import a
> plugin package; only the registry and provisioners do.

## The plugin contract — `AssetPlugin`

A declarative base (class-level attributes, AppConfig-style). Each plugin package's
`plugin.py` subclasses it and sets the attributes. **Minimum contract:**

| Attribute | Meaning |
| :--- | :--- |
| `key: str` | Stable `plugin_key` used in enablement rows + registry. |
| `label: str` | Human label (for later UI / narration). |
| `target: PluginTarget` | `ASSET` or `MODEL`. |
| `cardinality: PluginCardinality` | `ONE_TO_ONE` or `ONE_TO_MANY` (D5). |
| `primary_model` | The concrete plugin table class. |
| `factory` | The `PluginFactory` subclass (defaults to base). |

`PluginTarget` / `PluginCardinality` are enums in `plugin_descriptor.py`.
*(Reserved seams, declared but unused this phase: `card_template`, `rules` — kept
empty so 2b plugins don't churn the base when UI/rules land.)*

## Registry + Guard

- **`registry.py`** — `PLUGIN_REGISTRY` is an **explicit list** of descriptor
  classes, imported and assembled into `{key: descriptor}` plus helpers
  `descriptors_for_target(target)` and `get(key)`. This is the *only* place that
  knows the full plugin set — explicit, greppable, no import-time self-registration
  ([D1](../decisions.md) spirit preserved).
- **`PluginRegistryValidator`** (`plugin_registry_guard.py`) — resolves a
  `plugin_key` to its descriptor or raises a clear error. Used by every provisioner
  and manager CRUD path. Also validates registry integrity at startup (duplicate
  keys, target/table mismatch).

## Factory (the extension seam)

- **`PluginFactory`** (base) — `provision(*, owner, descriptor, actor)`. Today:
  create **one** primary-table row with audit fields, return it. Stateless class
  methods, `commit=False` friendly (runs inside the outer creation transaction).
  **The seam:** a plugin needing a multi-table cluster subclasses `PluginFactory`
  and overrides `provision()` to create its primary row *plus* dependent rows — the
  provisioner and contract are unchanged. Reference plugins use the base directly.

## Provisioning Handlers (template-driven, on-create)

- **`AssetPluginProvisioner.provision_for_asset(*, asset, actor)`** —
  1. gather enabled keys: `AssetPluginsByAssetClass(asset.asset_class)` +
     `AssetPluginsByModel(asset.model)`;
  2. for each key **not** already in `asset.plugins_provisioned`, resolve the
     descriptor via `PluginRegistryValidator`, then call
     `descriptor.factory.provision(owner=asset, descriptor=descriptor, actor=actor)`;
  3. append the key to `asset.plugins_provisioned`. **Idempotent / backfill-safe.**
- **`ModelPluginProvisioner.provision_for_model(*, model, actor)`** — same shape
  against `ModelPluginsByAssetClass(model.asset_class)`, marking
  `model.plugins_provisioned`.

## Orchestrator wiring (fill the P1 seam)

In `AssetCreationOrchestrator.create`, replace the P2 no-op:

```python
# P2: provision enabled plugins for this asset
AssetPluginProvisioner.provision_for_asset(asset=asset, actor=actor)
```

And in `AssetModelFactory.create` (or the model orchestrator), after the model row:

```python
ModelPluginProvisioner.provision_for_model(model=model, actor=actor)
```

Both run **inside** the existing creation transactions — a provisioning failure
rolls back the whole creation. The orchestrator names one step; it does **not**
import any plugin package.

## Managers (CRUD + read, on the contexts)

- **`AssetPluginsManager`** (property `AssetContext.plugins`) —
  `list()`, `get(plugin_key)`, `add(plugin_key, data)`, `update(plugin_key, row_id,
  data)`, `remove(plugin_key, row_id)`. `add()` enforces **cardinality from the
  descriptor**: `ONE_TO_ONE` rejects a second row; `ONE_TO_MANY` appends.
- **`ModelPluginsManager`** (property `AssetModelContext.plugins`) — same shape.

Both resolve `plugin_key` through `PluginRegistryValidator` and operate on the
descriptor's `primary_model`. Composition, not inheritance (project rule).

## Structs (union reads)

- **`AssetPluginsStruct(asset_id)`** — iterates `descriptors_for_target(ASSET)`,
  queries each descriptor's `primary_model` for the asset, returns a uniform
  `to_dict()` (`{plugin_key: [row_dicts]}`). The old `details_union` concept, now
  registry-driven. Lives behind a loader (complex multi-table read → `domain_struct`
  per layer rules).
- **`ModelPluginsStruct(model_id)`** — model-target union.

## Delegation flow (provision on create)

```
AssetCreationOrchestrator.create  (atomic)
  → AssetFactory.create → Asset
  → AssetPluginProvisioner.provision_for_asset
        enabled keys = AssetPluginsByAssetClass(asset_class) + AssetPluginsByModel(model)
        for key not in asset.plugins_provisioned:
          → PluginRegistryValidator.resolve(key) → descriptor
          → descriptor.factory.provision(owner=asset, descriptor, actor)   # base: 1 row
          → asset.plugins_provisioned.append(key)
```

## Delegation flow (read an asset's plugins)

```
AssetContext(asset_id).plugins.list()
  → AssetPluginsManager
  → AssetPluginsStruct(asset_id)
       for descriptor in descriptors_for_target(ASSET):
         rows = descriptor.primary_model.objects.filter(asset_id=...)
       → to_dict()  # {plugin_key: [...]}
```
