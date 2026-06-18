# Phase 2b — Old → New Migration Notes

The framework renames/reshapes are all in
[`../phase_2a_plugin_framework/old_to_new_migration.md`](../phase_2a_plugin_framework/old_to_new_migration.md).
This phase is the mechanical relocation of three concrete tables and the carry-over
of their enablement config.

## Source (current Django models, relocated)

| Current file | New home | Change |
| :--- | :--- | :--- |
| `app/assets/models/details/asset_class_details/vehicle_registration.py` | `app/assets/plugins/vehicle_registration/models.py` | Rebase on `AssetPluginTableVirtual`; keep `db_table="vehicle_registration"`. |
| `app/assets/models/details/asset_class_details/smog_record.py` | `app/assets/plugins/smog_record/models.py` | Rebase; keep `db_table="smog_record"`. |
| `app/assets/models/details/model_details/emissions_info.py` | `app/assets/plugins/emissions_info/models.py` | Rebase on `ModelPluginTableVirtual`; keep `db_table="emissions_info"`. |

After relocation, `app/assets/models/details/` should contain **no detail tables**
(the two reference plugins moved in 2a; these three in 2b). Remove the now-empty
`asset_class_details/` and `model_details/` packages and the old virtual-base files
if fully superseded by the 2a renamed bases.

## Source (old Flask app)

The old per-class/per-model detail assignments (`details/asset_class_details/*`,
`details/model_details/*` seed/config) become **enablement rows**:

| Old assignment | New row |
| :--- | :--- |
| asset-class → `vehicle_registration` detail | `asset_plugins_by_asset_class(asset_class, "vehicle_registration")` |
| asset-class → `smog_record` detail | `asset_plugins_by_asset_class(asset_class, "smog_record")` |
| model/class → `emissions_info` detail | `model_plugins_by_asset_class(asset_class, "emissions_info")` |

## Key notes

- **Cardinality** is set on the descriptor, not carried from the old
  `many_to_one` template flag. `smog_record` → `ONE_TO_MANY`; the others
  `ONE_TO_ONE` (confirm `vehicle_registration` against old data).
- **Canonical keys.** The `plugin_key` strings (`vehicle_registration`,
  `smog_record`, `emissions_info`) must match whatever the old templates used so
  carried-over enablement resolves. Confirm against old seed/debug data — the one
  remaining open item from the framework migration notes.
- **Schema reset.** Relocating a model and changing its base is a schema-affecting
  change; run the full DB reset (`/db-rebuild`) per the repo migration strategy,
  then re-seed enablement rows.

## Drop / avoid

- Do **not** add any framework code here. If a plugin needs behavior the base
  factory/descriptor can't express (e.g. a cluster), that is a Phase 2a extension,
  not a 2b workaround.
- Do not keep duplicate model definitions in both `models/details/` and the plugin
  package — relocate, don't copy.
