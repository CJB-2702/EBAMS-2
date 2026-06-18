# Phase 2a — Asset Plugin Framework

The extension seam. Build the machinery that lets a self-contained **plugin** —
its own typed table, a descriptor, and a provisioning factory — attach to assets
and models, configured per asset class and per model, without the host knowing the
plugin by name. Replaces the original Phase 2 "Asset & Model Details" design (see
[`../decisions.md`](../decisions.md) D4/D5).

## Goal

Stand up the plugin framework end-to-end and prove it with **two reference
plugins** — one asset-target, one model-target — so both provisioning paths are
exercised. Adding the remaining first-party plugins (Phase 2b) must then require
**no change to host models or the orchestrator body**.

## Core concept: descriptor + registry + factory + enablement

- A **plugin descriptor** declares the contract: `key`, `label`, `target`
  (asset/model), `cardinality` (one-to-one / one-to-many), its primary table, and
  its factory.
- An **explicit registry** maps `plugin_key → descriptor` (a named list, **not**
  import-time self-registration — keeps D1's explicit spirit).
- A **factory** provisions the plugin's row(s) for one owner. Today: one primary
  row. The interface is the seam for future multi-table clusters.
- **Enablement tables** declare which plugin keys are switched on for an asset
  class / model. Provisioning reads them on create.

## In scope

- Plugin descriptor base + `target` / `cardinality` enums.
- `app/assets/plugins/` package skeleton; two reference plugin packages
  (`purchase_info` = asset/one-to-one, `model_info` = model/one-to-one).
- The three enablement tables (renamed) and the `plugin_key` contract.
- Abstract primary-table bases (asset / model owner FK).
- Explicit registry + registry validator (unknown key = hard error).
- `PluginFactory` base (provision one primary row, transaction-friendly).
- Provisioning **Handlers** wired into the P2 extension point of
  `AssetCreationOrchestrator` and model creation; idempotent via
  `Asset.plugins_provisioned` / `AssetModel.plugins_provisioned`.
- `AssetPluginsManager` / `ModelPluginsManager` (CRUD on contexts, cardinality-aware).
- `AssetPluginsStruct` / `ModelPluginsStruct` union reads.

## Out of scope

- The remaining concrete plugins (Phase 2b).
- Plugin **rules / validation / derived status** (deferred).
- The asset-page **card UI** and any presentation layer (deferred; framework only).
- Configurations (P3), capabilities (P4).

## Dependencies

- **Phase 1 complete** — contexts + creation orchestrator with the P2 extension
  point; meter/tree/eventing settled.

## Exit criteria

- [ ] A plugin can be added by creating a package (table + descriptor + factory)
      and registering it in one explicit list — no edit to `Asset`/`AssetModel` or
      the orchestrator body.
- [ ] Creating an asset provisions exactly the plugins its class
      (`asset_plugins_by_asset_class`) and model (`asset_plugins_by_model`) enable,
      inside the creation transaction.
- [ ] Creating a model provisions exactly the plugins its asset class enables
      (`model_plugins_by_asset_class`), inside the creation transaction.
- [ ] `plugin_key → descriptor` resolution is centralized and validated; an unknown
      key raises a clear error at provisioning time.
- [ ] Provisioning is idempotent — re-running backfills newly-enabled plugins
      without duplicating, via the `plugins_provisioned` markers.
- [ ] An asset's / model's plugin rows are readable as one union struct.
- [ ] Plugin CRUD goes through the manager; cardinality is enforced from the
      descriptor (`ONE_TO_ONE` rejects a second row).
