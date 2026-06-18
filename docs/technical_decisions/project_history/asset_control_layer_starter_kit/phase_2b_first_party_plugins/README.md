# Phase 2b — First-Party Plugins

Port the remaining concrete details onto the Phase 2a framework as plugin packages.
This phase writes **no framework code** — if it needs to, 2a was incomplete. It is
the proof that adding a plugin is a repeatable, low-ceremony act.

## Goal

Turn the three remaining detail tables into plugin packages and register them, so
the full original detail set is provisioned through the plugin framework — with
zero changes to host models or the orchestrator body.

## Plugins to port

| Plugin key | Target | Cardinality | `db_table` (exists) | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `vehicle_registration` | Asset | one-to-one* | `vehicle_registration` | *Confirm vs. old `many_to_one`; old data decides single vs. history. |
| `smog_record` | Asset | one-to-many | `smog_record` | History of tests — the reference **one-to-many** plugin. |
| `emissions_info` | Model | one-to-one | `emissions_info` | Model-target. |

*(`purchase_info` and `model_info` were already built in 2a as reference plugins.)*

## Per-plugin work (identical shape each)

1. Create `app/assets/plugins/<key>/` with `models.py` (rebased on
   `AssetPluginTableVirtual` / `ModelPluginTableVirtual`), `plugin.py` (the
   descriptor), and `factory.py` only if it needs non-default provisioning.
2. Move the existing table out of `app/assets/models/details/` into the package,
   keeping its `db_table` so the schema is stable.
3. Add the descriptor class to `PLUGIN_REGISTRY` (one line).
4. Seed enablement rows (`asset_plugins_by_asset_class` / `_by_model` /
   `model_plugins_by_asset_class`) using the canonical `plugin_key`.

## In scope

- Three plugin packages + their registry entries.
- Seed/enablement rows mapping the old class/model→detail config onto plugin keys.
- The `smog_record` one-to-many path (validates cardinality enforcement end-to-end).

## Out of scope

- Any framework change (belongs in 2a).
- Plugin rules / validation / cards (deferred).
- Configurations (P3), capabilities (P4).

## Dependencies

- **Phase 2a complete** — framework, registry, factory seam, provisioners,
  managers, structs, and the two reference plugins all working.

## Exit criteria

- [ ] All five original detail types are plugin packages discovered via
      `PLUGIN_REGISTRY`; `app/assets/models/details/` no longer holds detail tables.
- [ ] Creating an asset of a class/model whose enablement rows name these keys
      provisions exactly those plugin rows in the creation transaction.
- [ ] `smog_record` allows multiple rows per asset; the one-to-one plugins reject a
      second row through the manager.
- [ ] No file under `app/assets/control_layer/plugins/` or `app/assets/plugins/base/`
      was edited to add these three plugins (framework untouched).
- [ ] `AssetPluginsStruct` / `ModelPluginsStruct` return all five plugin types in
      their unions.
