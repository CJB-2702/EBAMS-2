# Phase 2b — Data & Relational Plan

*No new framework schema. Three existing detail tables are rebased onto the Phase
2a virtual bases and relocated into plugin packages, keeping their `db_table` names.
Audit columns omitted (standard mixin).*

## Plugin tables ported

Asset-target (subclass `AssetPluginTableVirtual` → `asset` FK):

| Table | `db_table` | Notable fields | Cardinality |
| :--- | :--- | :--- | :--- |
| `VehicleRegistration` | `vehicle_registration` | plate_number, registration_expiry, state_province, vin_number | one-to-one* |
| `SmogRecord` | `smog_record` | test_date, test_result, test_station, certificate_number, expiry_date | one-to-many |

Model-target (subclass `ModelPluginTableVirtual` → `model` FK):

| Table | `db_table` | Notable fields | Cardinality |
| :--- | :--- | :--- | :--- |
| `EmissionsInfo` | `emissions_info` | emissions_standard, tier_level, co2_rating, certified_year | one-to-one |

\* `vehicle_registration` cardinality: confirm against old seed/`many_to_one` data.
If a registration history is wanted, set the descriptor to `ONE_TO_MANY`; the table
is unchanged either way (cardinality is a descriptor attribute, [D5](../decisions.md)).

## What does **not** change

- The owner FK comes from the rebased virtual base — no new FK fields.
- `db_table` names are preserved, so this is a model-location/inheritance change,
  not a table rename. (Full DB reset per repo migration strategy still applies.)
- No new enablement tables — these plugins are switched on by inserting rows into
  the Phase 2a tables (`asset_plugins_by_asset_class`, `asset_plugins_by_model`,
  `model_plugins_by_asset_class`) with the matching `plugin_key`.

## Enablement (seed shape)

| Plugin key | Enabled via | Scope example |
| :--- | :--- | :--- |
| `vehicle_registration` | `asset_plugins_by_asset_class` | light-vehicle classes |
| `smog_record` | `asset_plugins_by_asset_class` | emissions-tested classes |
| `emissions_info` | `model_plugins_by_asset_class` | emissions-tested classes |

Exact class assignments come from the old seed/template data (carried as an open
item — confirm canonical `plugin_key` strings and class mappings).

## Relational flow (unchanged from 2a)

```
AssetClass ─< asset_plugins_by_asset_class ─(plugin_key)→ registry → vehicle_registration / smog_record ─FK▶ Asset
AssetClass ─< model_plugins_by_asset_class ─(plugin_key)→ registry → emissions_info ─FK▶ AssetModel
```
