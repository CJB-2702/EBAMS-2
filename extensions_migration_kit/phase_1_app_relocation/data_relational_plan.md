# Phase 1 — Data & Relational Plan

*Relocates the existing plugin schema into `app/detail_extensions/` under the
`extension` vocabulary. No relational shape changes this phase — only table moves,
renames, and the marker rename. Audit columns (`created_at/updated_at/created_by_id/
updated_by_id`) are on every table via the standard mixin and omitted below. Tables FK
into `assets` — the allowed one-way direction (`detail_extensions → assets`).*

## Owner markers (assets-side, this phase only)

| Table | Change |
| :--- | :--- |
| `asset` | Rename `plugins_provisioned` → `extensions_provisioned` (JSON list). **Stays on the table through Phase 1; relocated to a state table in Phase 2** ([E7](../decisions.md)). |
| `asset_model` | Same rename. |

## Abstract primary-table bases (moved + renamed)

| New abstract base | Owner FK | Was |
| :--- | :--- | :--- |
| `AssetExtensionContract` | `asset` → `assets.Asset` | `AssetPluginTableVirtual` |
| `ModelExtensionContract` | `model` → `assets.AssetModel` | `ModelPluginTableVirtual` |

Still `abstract = True`; each concrete extension table subclasses one of these and
inherits the owner FK + audit columns.

## Enablement tables (moved + renamed; relational shape unchanged)

| New table class | `db_table` | Key fields | Was |
| :--- | :--- | :--- | :--- |
| `DetailExtensionsByAssetClass` | `detail_extensions_by_asset_class` | `asset_class` FK, `extension_key`; unique(class, key) | `AssetPluginsByAssetClass` |
| `DetailExtensionsByModel` | `detail_extensions_by_model` | `model` FK, `extension_key`; unique(model, key) | `AssetPluginsByModel` |
| `ModelDetailExtensionsByAssetClass` | `model_detail_extensions_by_asset_class` | `asset_class` FK, `extension_key`; unique(class, key) | `ModelPluginsByAssetClass` |

Field rename inside all three: `plugin_key` → **`extension_key`** (string, resolved
through the code registry, not the DB).

## Concrete extension tables (moved into vertical-slice packages)

Owner-FK direction is unchanged; only the package and base-class name change.

| Table | `db_table` | Base | Target / cardinality |
| :--- | :--- | :--- | :--- |
| `PurchaseInfo` | `purchase_info` | `AssetExtensionContract` | asset / one-to-one |
| `VehicleRegistration` | `vehicle_registration` | `AssetExtensionContract` | asset / one-to-one |
| `SmogRecord` | `smog_record` | `AssetExtensionContract` | asset / **one-to-many** |
| `EmissionsInfo` | `emissions_info` | `AssetExtensionContract` | asset / one-to-one |
| `ModelInfo` | `model_info` | `ModelExtensionContract` | model / one-to-one |

*(Cardinality is not stored — it is a class attribute on each extension's descriptor,
per D5. Listed here only to show the spread the move must preserve.)*

## Relational flow (unchanged shape, new names)

```
AssetClass ─< DetailExtensionsByAssetClass ┐
AssetModel ─< DetailExtensionsByModel       ┘─(extension_key)→ registry → asset extension table ─FK▶ Asset
AssetClass ─< ModelDetailExtensionsByAssetClass ──(extension_key)→ registry → model extension table ─FK▶ AssetModel
```

## What does NOT change this phase

- No new tables (provisioning-state tables arrive in Phase 2).
- No FK redirection — every extension table still points at `assets.Asset` /
  `assets.AssetModel`.
- The `extension_key` string values themselves are preserved (the seed/enablement data
  keeps resolving), so a re-seed reproduces the same enablement.
