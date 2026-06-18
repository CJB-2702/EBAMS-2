# Phase 2 — Data & Relational Plan

*Adds the provisioning-state tables in `detail_extensions` and removes the
provisioning markers from the assets tables ([E7](../decisions.md)). No change to the
enablement tables or the concrete extension tables. Audit columns omitted.*

## Removed (assets-side)

| Table | Change |
| :--- | :--- |
| `asset` | **Drop** the `extensions_provisioned` JSON column. |
| `asset_model` | **Drop** the `extensions_provisioned` JSON column. |

After this, the `asset` / `asset_model` schemas carry **no** extension state — the
ignorance goal is complete at the data layer too.

## Added (`detail_extensions` provisioning state)

| New table class | `db_table` | Fields | Purpose |
| :--- | :--- | :--- | :--- |
| `AssetExtensionProvisioningState` | `asset_extension_provisioning_state` | `asset` **OneToOne** → `assets.Asset`; `provisioned_keys` JSON list | Records which `extension_key`s have been provisioned for an asset. |
| `ModelExtensionProvisioningState` | `model_extension_provisioning_state` | `model` **OneToOne** → `assets.AssetModel`; `provisioned_keys` JSON list | Same, for a model. |

- **One row per owner** (OneToOne). Created lazily by the provisioner on first
  provisioning; absence = "never provisioned."
- FK direction is `detail_extensions → assets` — the allowed one-way dependency.
- **Why a durable marker is still needed:** a `ONE_TO_MANY` extension (e.g. smog
  history) with zero rows is a *valid* provisioned state; row-existence alone cannot
  distinguish "provisioned, empty" from "never provisioned." The key list disambiguates
  and keeps backfill idempotent.

## Relational flow (state added; enablement unchanged)

```
Asset      ─1:1─ AssetExtensionProvisioningState  (provisioned_keys: [extension_key, …])
AssetModel ─1:1─ ModelExtensionProvisioningState

AssetClass ─< DetailExtensionsByAssetClass ┐
AssetModel ─< DetailExtensionsByModel       ┘─(extension_key)→ registry → asset extension table ─FK▶ Asset
AssetClass ─< ModelDetailExtensionsByAssetClass ──(extension_key)→ registry → model extension table ─FK▶ AssetModel
```

## What does NOT change

- Enablement tables and concrete extension tables are untouched (relocated in Phase 1).
- `extension_key` strings and seed enablement are preserved.
