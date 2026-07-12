---
type: "Technical Decision"
title: "Phase 2a — Data & Relational Plan"
description: "framework."
tags: [technical-decisions, technical-decision, project-history, asset-control-layer-starter-kit, phase-2a-plugin-framework]
context_tier: 2
---

# Phase 2a — Data & Relational Plan

*Reshapes the existing detail schema (`app/assets/models/details/`) into the plugin
framework. Audit columns (`created_at/updated_at/created_by_id/updated_by_id`) are
on every table via the standard mixin and omitted below.*

## Owner markers (host changes)

| Table | Change |
| :--- | :--- |
| `asset` | Rename `detail_rows_created` → `plugins_provisioned` (JSON list of provisioned `plugin_key`s). |
| `asset_model` | **Add** `plugins_provisioned` (JSON list) — model provisioning needs its own idempotency marker. |

## Primary-table bases (abstract)

| Abstract base | Owner FK | Purpose |
| :--- | :--- | :--- |
| `AssetPluginTableVirtual` | `asset` → Asset | Base for every **asset-target** plugin's primary table. |
| `ModelPluginTableVirtual` | `model` → AssetModel | Base for every **model-target** plugin's primary table. |

*(These are the renamed `AssetDetailVirtual` / `ModelDetailVirtual`. Still abstract;
each concrete plugin table subclasses one of them and gets the owner FK.)*

## Reference plugin tables (two, to prove both paths)

Asset-target (subclass `AssetPluginTableVirtual`):

| Table | `db_table` | Notable fields |
| :--- | :--- | :--- |
| `PurchaseInfo` | `purchase_info` | purchase_date, purchase_price, vendor, po_number |

Model-target (subclass `ModelPluginTableVirtual`):

| Table | `db_table` | Notable fields |
| :--- | :--- | :--- |
| `ModelInfo` | `model_info` | engine_type, horsepower, weight_kg, dimensions |

*(The remaining concrete tables — `vehicle_registration`, `smog_record`,
`emissions_info` — are ported in Phase 2b. Their tables already exist; 2b moves
them onto the new bases and into plugin packages.)*

## Enablement tables (renamed; declare which plugins are switched on)

| Table | `db_table` | Key fields | Scope |
| :--- | :--- | :--- | :--- |
| `AssetPluginsByAssetClass` | `asset_plugins_by_asset_class` | `asset_class` FK, `plugin_key`; unique(class, key) | Asset plugins every asset of a class gets. |
| `AssetPluginsByModel` | `asset_plugins_by_model` | `model` FK, `plugin_key`; unique(model, key) | Extra asset plugins for a specific model. |
| `ModelPluginsByAssetClass` | `model_plugins_by_asset_class` | `asset_class` FK, `plugin_key`; unique(class, key) | Model plugins every model of a class gets. |

Changes from the old template tables:
- `detail_table_type` → **`plugin_key`** (string; resolves via the registry).
- **`many_to_one` removed** — cardinality now lives on the plugin descriptor
  ([D5](../decisions.md)), so enablement rows are pure on/off switches.
- Third table re-scoped from per-model to **per asset class** (D5).

## The `plugin_key` contract

`plugin_key` is a **string** on every enablement row. It must resolve, through the
**code registry** (not the DB), to exactly one plugin descriptor — which carries
the concrete table class, target, cardinality, and factory. An unknown `plugin_key`
is a **hard error surfaced at provisioning time**. Canonical strings are confirmed
against old seed/template data.

## Relational flow

```
AssetClass ─< AssetPluginsByAssetClass ┐
AssetModel ─< AssetPluginsByModel       ┘─(plugin_key)→ registry → asset plugin table ─FK▶ Asset
AssetClass ─< ModelPluginsByAssetClass ───(plugin_key)→ registry → model plugin table ─FK▶ AssetModel
```

`plugins_provisioned` (JSON, on Asset and AssetModel) records which `plugin_key`s
have already been provisioned, so provisioning is **idempotent** and a later
enablement addition can backfill without duplicating.

## Cardinality

Cardinality is **not** stored on these tables. It is a class attribute on the
plugin descriptor (`ONE_TO_ONE` / `ONE_TO_MANY`). When `ONE_TO_MANY`, multiple
rows of that plugin's table are allowed for one owner (a history); otherwise a
single row is created/expected.
