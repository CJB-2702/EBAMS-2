# Phase 2a — Old → New Migration Notes

This phase reshapes both the **old Flask detail code** and the **current Django
detail models** into the plugin framework. Two source surfaces:

## Source — old Flask app

- `app/business/assets/details/asset_details_context.py`
- `app/business/assets/details/make_model_context.py`  (model details)
- `app/business/assets/details/detail_table_context.py`
- `app/business/assets/details/handlers.py`
- `app/business/assets/details/factories/{detail_factory,asset_detail_factory,model_detail_factory}.py`
- `app/business/assets/details/asset_class_details/{asset_details_struct,details_union}.py`
- `app/business/assets/details/model_details/{model_details_struct,details_union}.py`

## Source — current Django models (already built, being reshaped)

- `app/assets/models/details/asset_detail_virtual.py` → `AssetPluginTableVirtual`
- `app/assets/models/details/model_detail_virtual.py` → `ModelPluginTableVirtual`
- `app/assets/models/details/detail_table_templates/{asset_details_from_asset_class,asset_details_from_model_type,model_detail_table_template}.py`
  → the three renamed enablement tables.
- `app/assets/models/core/asset.py` `detail_rows_created` → `plugins_provisioned`.

## Mapping

| Old / current | New | Change |
| :--- | :--- | :--- |
| `AssetDetailsContext(AssetContext)` | `AssetPluginsManager` on `AssetContext` | Inheritance → composition. |
| `MakeModelDetailsContext(MakeModelContext)` | `ModelPluginsManager` on `AssetModelContext` | Same; `MakeModel`→`AssetModel`. |
| `detail_table_context.py` (string→class) | `app/assets/plugins/registry.py` + `PluginRegistryValidator` | Resolution centralized in an **explicit** registry of descriptors, not a string→model dict only. |
| `AssetDetailVirtual` / `ModelDetailVirtual` | `AssetPluginTableVirtual` / `ModelPluginTableVirtual` | Renamed abstract owner-FK bases. |
| `AssetDetailTemplateByAssetClass` | `AssetPluginsByAssetClass` | `detail_table_type`→`plugin_key`; drop `many_to_one`. |
| `AssetDetailTemplateByModelType` | `AssetPluginsByModel` | Same renames. |
| `ModelDetailTableTemplate` (per model) | `ModelPluginsByAssetClass` (per class) | Renames **and** re-scope to asset class (D5). |
| `details/factories/*` | `PluginFactory` base + per-plugin factory seam | Provision from enablement tables; one primary row today, cluster-ready. |
| `*_details_struct.py`, `details_union.py` | `AssetPluginsStruct` / `ModelPluginsStruct` | Registry-driven union behind a loader. |
| `handlers.py` | `AssetPluginProvisioner` / `ModelPluginProvisioner` | The on-create provisioning step; folded factory glue. |
| `Asset.detail_rows_created` | `Asset.plugins_provisioned` (+ new `AssetModel.plugins_provisioned`) | Rename + add model-side marker. |

## Key behavioral notes

- **Provisioning trigger** is the explicit **orchestrator extension point**
  (P1 seam), not old per-context create hooks. Do **not** re-introduce the
  import-time registry/pipeline — discovery here is an explicit list.
- **Cardinality moves** from per-template `many_to_one` to the plugin descriptor
  (D5). The manager reads it from the descriptor, not the enablement row.
- **Idempotency** via `plugins_provisioned` is required on **both** Asset and
  AssetModel — the factory must be safe to re-run (backfill when a plugin is
  enabled later).
- **Canonical `plugin_key` strings:** confirm the exact strings the old templates
  used (old seed/debug data) and encode them in each descriptor's `key` so
  existing-style enablement rows resolve.

## Drop / avoid

- SQLAlchemy idioms and any direct `db.session` commits inside plugin provisioning
  — provisioning is part of the **outer** creation transaction.
- Deep context inheritance chains — managers as context properties.
- A bare string→model dict as the only registry — the registry stores **descriptors**
  (target, cardinality, factory), not just the table class.

## Reference-plugin scope for 2a

Only **two** plugin packages are built this phase to exercise both paths:
`purchase_info` (asset, one-to-one) and `model_info` (model, one-to-one). The other
three concrete tables are ported in **Phase 2b** — their `db_table`s already exist;
2b only rebases them onto the virtual bases and wraps each in a plugin package.
