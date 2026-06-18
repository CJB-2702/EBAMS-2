# Migration Map — plugin → `detail_extensions`

Every existing plugin-related file → its new home, rename, or deletion. This is the
execution spine: working through it top-to-bottom, with the phase column as the order,
completes the migration. New app root: **`app/detail_extensions/`**.

Legend: **MOVE+RENAME** = relocate and rename symbols · **RESHAPE** = logic changes ·
**DELETE** = removed after relocation (E2 clean cut) · **NEW** = created by this kit.

## Framework data + base (`app/assets/plugins/` → `app/detail_extensions/`)

| Old file | New file | Action | Phase |
| :--- | :--- | :--- | :--- |
| `plugins/base/plugin_descriptor.py` | `detail_extensions/base/extension_descriptor.py` | MOVE+RENAME → `DetailExtension`, `ExtensionTarget`, `ExtensionCardinality` | 1 |
| `plugins/base/plugin_factory.py` | `detail_extensions/base/extension_factory.py` | MOVE+RENAME → `ExtensionFactory` | 1 |
| `plugins/base/plugin_table_virtual.py` | `detail_extensions/base/table_contract.py` | MOVE+RENAME → `AssetExtensionContract`, `ModelExtensionContract` | 1 |
| `plugins/base/enablement_models.py` | `detail_extensions/models/enablement.py` | MOVE+RENAME → 3 tables renamed (see data plan P1) | 1 |
| `plugins/registry.py` | `detail_extensions/registry.py` | MOVE+RENAME → `EXTENSION_REGISTRY`, manifest validation (E5) | 1 |
| `plugins/__init__.py`, `plugins/base/__init__.py` | (new package `__init__`s) | MOVE | 1 |

## Concrete plugins → vertical-slice extension packages (each gets a manifest, E5)

| Old package | New package | Action | Phase |
| :--- | :--- | :--- | :--- |
| `plugins/purchase_info/` (`models.py`, `plugin.py`) | `detail_extensions/purchase_info/` (`models.py`, `extension.py`, `manifest.py`) | MOVE+RENAME → `PurchaseInfo(AssetExtensionContract)`, `PurchaseInfoExtension(DetailExtension)` | 1 |
| `plugins/model_info/` | `detail_extensions/model_info/` | MOVE+RENAME (model-target) | 1 |
| `plugins/vehicle_registration/` | `detail_extensions/vehicle_registration/` | MOVE+RENAME | 1 |
| `plugins/smog_record/` | `detail_extensions/smog_record/` | MOVE+RENAME (one-to-many) | 1 |
| `plugins/emissions_info/` | `detail_extensions/emissions_info/` | MOVE+RENAME | 1 |

## Framework control layer (`app/assets/control_layer/plugins/` → `detail_extensions/control_layer/`)

| Old file | New file | Action | Phase |
| :--- | :--- | :--- | :--- |
| `control_layer/plugins/guards/plugin_registry_guard.py` | `detail_extensions/control_layer/guards/extension_registry_guard.py` | MOVE+RENAME → `ExtensionRegistryValidator` | 1 |
| `control_layer/plugins/provisioning/asset_plugin_provisioner.py` | `detail_extensions/control_layer/provisioning/asset_extension_provisioner.py` | MOVE+RENAME → `AssetExtensionProvisioner`; RESHAPE marker source in P2 | 1 → reshape 2 |
| `control_layer/plugins/provisioning/model_plugin_provisioner.py` | `detail_extensions/control_layer/provisioning/model_extension_provisioner.py` | MOVE+RENAME → `ModelExtensionProvisioner` | 1 → reshape 2 |
| `control_layer/plugins/managers/asset_plugins_manager.py` | `detail_extensions/control_layer/managers/asset_extensions_manager.py` | MOVE+RENAME → `AssetExtensionsManager` | 1 |
| `control_layer/plugins/managers/model_plugins_manager.py` | `detail_extensions/control_layer/managers/model_extensions_manager.py` | MOVE+RENAME → `ModelExtensionsManager` | 1 |
| `control_layer/plugins/domain_structs/asset_plugins_struct.py` | `detail_extensions/control_layer/domain_structs/asset_extensions_struct.py` | MOVE+RENAME → `AssetExtensionsStruct` | 1 |
| `control_layer/plugins/domain_structs/model_plugins_struct.py` | `detail_extensions/control_layer/domain_structs/model_extensions_struct.py` | MOVE+RENAME → `ModelExtensionsStruct` | 1 |
| — | `detail_extensions/control_layer/asset_detail_extension_context.py` | NEW → `AssetDetailExtensionContext(asset_id)` (replaces `AssetContext.plugins`) | 2 |
| — | `detail_extensions/control_layer/model_detail_extension_context.py` | NEW → `ModelDetailExtensionContext(model_id)` | 2 |

## Assets-side wiring (the dependency edge)

| Old location | Change | Action | Phase |
| :--- | :--- | :--- | :--- |
| `assets/models/__init__.py` | Remove the `from app.assets.plugins...` import block (lines importing enablement + 5 concrete tables) | RESHAPE | 1 |
| `assets/models/core/asset.py` `plugins_provisioned` | Rename → `extensions_provisioned` (P1), then **delete the column** (P2, → state table E7) | RESHAPE | 1 → delete 2 |
| `assets/models/core/asset_model.py` `plugins_provisioned` | Same as above | RESHAPE | 1 → delete 2 |
| `assets/control_layer/asset_context.py` `.plugins` property + import | **Remove** — managers move to `AssetDetailExtensionContext` | RESHAPE | 2 |
| `assets/control_layer/asset_model_context.py` `.plugins` property + import | **Remove** | RESHAPE | 2 |
| `assets/control_layer/orchestrators/asset_creation_orchestrator.py` | Replace direct `AssetPluginProvisioner` call with `asset_created.send(...)` (final in-txn step) | RESHAPE | 1 (transient call) → 2 (signal) |
| `assets/control_layer/factories/asset_model_factory.py` | Replace direct `ModelPluginProvisioner` call with `asset_model_created.send(...)` | RESHAPE | 1 (transient) → 2 (signal) |
| `assets/control_layer/domain_structs/asset_struct.py` / `asset_model_struct.py` | Remove `plugins_provisioned` field from struct payload | RESHAPE | 2 |
| — | `app/assets/signals.py` → `asset_created`, `asset_model_created` | NEW | 2 |

## Presentation (mock display/config → real)

| Old location | Change | Action | Phase |
| :--- | :--- | :--- | :--- |
| `assets/presentation_layer/entrypoints/plugins.py` (mock) | Superseded by real config entrypoints in `detail_extensions` | DELETE | 3 |
| `assets/presentation_layer/mock_data.py` (plugin parts) | Superseded by real reads | DELETE (plugin parts) | 3 |
| `assets/urls.py` plugin routes (`asset_plugin_edit`, `class_plugin_config`, `model_plugin_config`) | Removed; routes move under `/detail_extensions/` | RESHAPE | 3 |
| `assets/templates/assets/plugins/*` | Move/replace under `detail_extensions/templates/` | MOVE+RENAME | 3 |
| — | `detail_extensions/presentation_layer/entrypoints/configuration.py` | NEW → real enablement CRUD | 3 |
| — | `detail_extensions/presentation_layer/entrypoints/extension_router.py` | NEW → target-derived route dispatch (contract) | 3 |
| — | `detail_extensions/urls.py` + include in `config/urls.py` | NEW | 3 |

## App registration + config

| Item | Change | Phase |
| :--- | :--- | :--- |
| `app/detail_extensions/apps.py` | NEW — `ready()` connects `asset_created`/`asset_model_created` receivers | 1 (skeleton) → 2 (wire receivers) |
| `config/settings` `INSTALLED_APPS` | Add `app.detail_extensions` | 1 |
| `config/urls.py` | Include `detail_extensions.urls` | 3 |
| `assets/migrations/0001_initial.py` | Regenerated by full DB rebuild after each schema phase (P1, P2) | 1, 2 |

## Provisioning state (E7)

| Item | Change | Phase |
| :--- | :--- | :--- |
| — | `detail_extensions/models/provisioning_state.py` → `AssetExtensionProvisioningState`, `ModelExtensionProvisioningState` | NEW (2) |
| `asset.extensions_provisioned` / `asset_model.extensions_provisioned` | Deleted; logic reads/writes the state tables | RESHAPE (2) |

## Seed

| Item | Change | Phase |
| :--- | :--- | :--- |
| Mock enablement data (`mock_data.py`) | Replaced by real persisted enablement seed for the new tables | 3 |
