# Phase 2b — Control Layer Plan

**This phase adds no control-layer infrastructure.** It only adds plugin *packages*
and one registry line each. If a step below requires touching the framework, that
gap belongs back in Phase 2a.

## Target tree (additions only)

```
app/assets/plugins/
├── vehicle_registration/
│   ├── models.py     # VehicleRegistration(AssetPluginTableVirtual)
│   └── plugin.py     # VehicleRegistrationPlugin(AssetPlugin)
├── smog_record/
│   ├── models.py     # SmogRecord(AssetPluginTableVirtual)
│   └── plugin.py     # SmogRecordPlugin(AssetPlugin)   # cardinality = ONE_TO_MANY
└── emissions_info/
    ├── models.py     # EmissionsInfo(ModelPluginTableVirtual)
    └── plugin.py     # EmissionsInfoPlugin(AssetPlugin) # target = MODEL

app/assets/plugins/registry.py   # +3 descriptor entries in PLUGIN_REGISTRY
```

No `factory.py` per plugin — all three provision a single primary row, so each
descriptor's `factory` defaults to the base `PluginFactory`.

## The descriptor for each plugin

Each `plugin.py` subclasses `AssetPlugin` and sets the contract attributes:

| Plugin | `key` | `target` | `cardinality` | `primary_model` |
| :--- | :--- | :--- | :--- | :--- |
| `VehicleRegistrationPlugin` | `vehicle_registration` | `ASSET` | `ONE_TO_ONE`* | `VehicleRegistration` |
| `SmogRecordPlugin` | `smog_record` | `ASSET` | `ONE_TO_MANY` | `SmogRecord` |
| `EmissionsInfoPlugin` | `emissions_info` | `MODEL` | `ONE_TO_ONE` | `EmissionsInfo` |

\* Confirm against old `many_to_one` data; flip to `ONE_TO_MANY` if a registration
history is wanted.

## Registration

Add the three descriptor classes to the explicit `PLUGIN_REGISTRY` list in
`registry.py`. `PluginRegistryValidator` then resolves their keys automatically;
provisioners, managers, and structs pick them up with no further wiring.

## Delegation flow — nothing new

These plugins flow through the **exact** Phase 2a paths:

```
AssetCreationOrchestrator.create
  → AssetPluginProvisioner.provision_for_asset
       enabled keys include "vehicle_registration", "smog_record"
       → registry.get(key) → descriptor
       → PluginFactory.provision(owner=asset, descriptor, actor)   # 1 row
```

```
AssetModelFactory.create
  → ModelPluginProvisioner.provision_for_model
       enabled keys include "emissions_info"
       → registry.get(key) → descriptor
       → PluginFactory.provision(owner=model, descriptor, actor)
```

## Cardinality check (the one new behavior to verify)

`smog_record` is the first `ONE_TO_MANY` plugin built on a real table.
`AssetPluginsManager.add("smog_record", data)` must append a new row each call,
while `AssetPluginsManager.add("vehicle_registration", data)` must reject a second
row (descriptor `ONE_TO_ONE`). This exercises the cardinality enforcement that
Phase 2a's `purchase_info`/`model_info` (both one-to-one) could not.

## Old → new

Beyond the renames already captured in
[`../phase_2a_plugin_framework/old_to_new_migration.md`](../phase_2a_plugin_framework/old_to_new_migration.md),
this phase carries the old per-class/per-model detail assignments into seed rows on
the three enablement tables — see [`old_to_new_migration.md`](old_to_new_migration.md).
