# Phase 1 — Old → New Porting Checklist

Work top-to-bottom. After the schema-affecting steps, do **one** full DB rebuild at the
end of the phase (not per-file). See [`../migration_map.md`](../migration_map.md) for
the complete file table.

## 1. Scaffold the app

- [ ] Create `app/detail_extensions/` with `__init__.py` and `apps.py`
      (`DetailExtensionsConfig`, `default_auto_field = BigAutoField`, empty `ready()`).
- [ ] Add `"app.detail_extensions"` to `INSTALLED_APPS`.

## 2. Move the base + registry

- [ ] `plugin_descriptor.py` → `base/extension_descriptor.py`; rename `AssetPlugin →
      DetailExtension`, `PluginTarget → ExtensionTarget`, `PluginCardinality →
      ExtensionCardinality`. Add the required `manifest` attribute.
- [ ] `plugin_factory.py` → `base/extension_factory.py`; `PluginFactory → ExtensionFactory`.
- [ ] `plugin_table_virtual.py` → `base/table_contract.py`; `AssetPluginTableVirtual →
      AssetExtensionContract`, `ModelPluginTableVirtual → ModelExtensionContract`.
- [ ] NEW `base/manifest.py` → `ExtensionManifest` (declaration only, no logic).
- [ ] `registry.py` → `detail_extensions/registry.py`; `PLUGIN_REGISTRY →
      EXTENSION_REGISTRY`; update imports to the 5 renamed extension classes; add the
      startup manifest-validation pass.

## 3. Move the enablement models

- [ ] `plugins/base/enablement_models.py` → `models/enablement.py`. Rename the three
      classes + `db_table`s + the `plugin_key` field → `extension_key` (per data plan).
- [ ] `models/__init__.py` imports the three enablement tables so the app registers them.

## 4. Move the 5 concrete extensions into vertical slices

For each of `purchase_info`, `model_info`, `vehicle_registration`, `smog_record`,
`emissions_info`:

- [ ] `plugins/<name>/models.py` → `detail_extensions/<name>/models.py`; rebase onto
      `AssetExtensionContract` / `ModelExtensionContract`.
- [ ] `plugins/<name>/plugin.py` → `detail_extensions/<name>/extension.py`; rename the
      descriptor class `<Name>Plugin → <Name>Extension`, subclass `DetailExtension`.
- [ ] NEW `detail_extensions/<name>/manifest.py` (or inline on the descriptor) →
      populate `ExtensionManifest` (`models_module` set; control/template/entrypoints
      reserved/None this phase).
- [ ] `models/__init__.py` (app-level) imports each concrete table for registration —
      **but `assets/models/__init__.py` must NOT.**

## 5. Move the framework control layer

- [ ] `control_layer/plugins/guards/plugin_registry_guard.py` →
      `detail_extensions/control_layer/guards/extension_registry_guard.py`;
      `PluginRegistryValidator → ExtensionRegistryValidator`; add manifest validation.
- [ ] `provisioning/asset_plugin_provisioner.py` + `model_plugin_provisioner.py` →
      `detail_extensions/control_layer/provisioning/...`; rename classes; keep
      `extensions_provisioned` marker logic (renamed field).
- [ ] `managers/*` and `domain_structs/*` → `detail_extensions/control_layer/...`;
      rename classes.

## 6. Rewire assets-side references (minimal, transient)

- [ ] `assets/models/__init__.py` — **delete** the `from app.assets.plugins...` import
      block (enablement + 5 concrete tables). This closes the boundary leak.
- [ ] `assets/models/core/asset.py` + `asset_model.py` — rename the JSON column
      `plugins_provisioned → extensions_provisioned`.
- [ ] `asset_context.py` / `asset_model_context.py` — update the `.plugins` property's
      import to the new manager module path (property itself stays this phase).
- [ ] `asset_creation_orchestrator.py` / `asset_model_factory.py` — update the
      provisioner import to the new path (the **direct call stays** this phase).
- [ ] `asset_struct.py` / `asset_model_struct.py` — update `extensions_provisioned`
      field name.

## 7. Clean cut (E2)

- [ ] Delete `app/assets/plugins/` entirely.
- [ ] Delete `app/assets/control_layer/plugins/` entirely.
- [ ] `grep -rn "plugin" app/` → resolve every remaining hit (rename or remove).

## 8. Rebuild + verify

- [ ] `python dev_tools/delete_database_rebuild_models.py --seed`.
- [ ] Boot the server; create an asset and a model; confirm extension rows are
      provisioned exactly as before (behavior parity).
- [ ] Trip the guard deliberately (a registered extension with a broken manifest) →
      confirm a clear startup error.

## Notes / gotchas

- **Mock display/config left untouched this phase.** `entrypoints/plugins.py` and
  `mock_data.py` still reference the old `plugin` vocabulary in template strings; they
  are deleted in Phase 3. If their imports break during the rename, stub minimally —
  do not invest in them.
- **Template namespace** `assets/templates/assets/plugins/` is moved in Phase 3, not now.
