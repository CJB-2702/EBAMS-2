# Phase 3 — Data & Relational Plan

*No new tables. This phase is UI + routing over the models already in place from
Phases 1–2, plus real seed data. Listed here for completeness of what the UI
reads/writes.*

## Tables the configuration UI writes (enablement — from Phase 1)

| Table | Written by config UI | Operation |
| :--- | :--- | :--- |
| `DetailExtensionsByAssetClass` (`detail_extensions_by_asset_class`) | Assign asset extension to a class | create / delete row `(asset_class, extension_key)` |
| `DetailExtensionsByModel` (`detail_extensions_by_model`) | Assign asset extension to a model | create / delete row `(model, extension_key)` |
| `ModelDetailExtensionsByAssetClass` (`model_detail_extensions_by_asset_class`) | Assign model extension to a class | create / delete row `(asset_class, extension_key)` |

Each row is a pure on/off switch (unique constraint per Phase 1). Toggling on adds a
row; toggling off removes it. Existing assets are not retro-provisioned by the toggle
itself — a backfill run (Phase 2 provisioner, idempotent) applies it.

## Tables the UI reads (no writes)

| Table | Read for |
| :--- | :--- |
| `assets.AssetClass` | class picker + labels (read-only) |
| `assets.AssetModel` | model picker + labels (read-only) |
| concrete extension tables (e.g. `purchase_info`) | the aggregate panel card summaries / per-extension routing (bodies deferred) |
| `AssetExtensionProvisioningState` / `ModelExtensionProvisioningState` (Phase 2) | showing whether an owner has been provisioned for an extension |
| `EXTENSION_REGISTRY` (code, not DB) | the catalog of assignable extensions + each `target`/`cardinality`/`label` |

## Relational context (unchanged; for reference)

```
AssetClass ─< DetailExtensionsByAssetClass ┐
AssetModel ─< DetailExtensionsByModel       ┘─(extension_key)→ registry → asset extension table ─FK▶ Asset
AssetClass ─< ModelDetailExtensionsByAssetClass ──(extension_key)→ registry → model extension table ─FK▶ AssetModel

Asset ─1:1─ AssetExtensionProvisioningState
AssetModel ─1:1─ ModelExtensionProvisioningState
```

## Seed (real, replaces mock)

Real enablement rows for the dev dataset — which classes/models switch on which
extensions — created idempotently in the seed (`get_or_create`), reproducing the
previously-mock assignment set against the new tables.
