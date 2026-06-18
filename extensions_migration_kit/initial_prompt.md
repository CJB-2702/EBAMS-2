# Initial Prompt — Extensions Migration Kit

## Originating request (verbatim intent)

> Review `asset_control_layer_starter_kit/phase_2a_plugin_framework/README.md`. I
> previously labeled this concept "plugins" but it may be "extensions" because they
> should have their own sub-interactions / pages.
>
> The enablement/assignment tables (`AssetPluginsByAssetClass`, `AssetPluginsByModel`,
> `ModelPluginsByAssetClass`) feel like they should physically live in the assets
> models — they are extension-assignment tools core to the app. The concrete tables
> (`EmissionsInfo`, `ModelInfo`, `PurchaseInfo`, `SmogRecord`, `VehicleRegistration`)
> feel different — they belong in their own packages.
>
> I want something like `assets/<id>/extensions/extension_name` and a defined
> interface for displaying dynamically installed and assigned extensions on an asset.
>
> The big question: how do I keep the assets application **not dependent** on the
> extensions application? I want assets to just emit a signal that a new asset was
> created, then have the extensions application do its tasks independently.
>
> Because I already built the infrastructure, make a new kit: `extensions_migration_kit`.

This kit operationalizes design decisions **D7** and **D8** recorded in
[`asset_control_layer_starter_kit/decisions.md`](../asset_control_layer_starter_kit/decisions.md).

## Clarifying decisions captured during interrogation

These answers are binding for the kit (see [`decisions.md`](decisions.md) for the
reasoned versions):

1. **UI scope.** Define the **interface / route pattern** every extension's pages must
   conform to (a contract); implement **none** of the per-extension page bodies. Do
   concretely plan the **assignment / configuration UI** (which asset classes and
   models get which extensions). *(→ E6, Phase 3.)*

2. **Clean cut.** Delete `app/assets/plugins/` and `app/assets/control_layer/plugins/`
   after the move. No back-compat shims or re-export stubs. *(→ E2.)*

3. **Framework control stays central, extensions self-describe.** Provisioners,
   managers, structs, registry, and guard live centrally in `detail_extensions`. In
   addition, **every extension package carries a file manifest** declaring its own
   associated files (models, control classes, templates, endpoints). *(→ E4, E5.)*

4. **Signal contract confirmed.** Assets defines and emits `asset_created` and
   `asset_model_created` as the final in-transaction step of creation. The
   `detail_extensions` app is the sole listener and provisions via
   `transaction.on_commit` (eventual consistency). *(→ E3.)*

5. **Seed enablement exists and moves.** The current enablement/assignment seed (today
   expressed through mock data) is relocated and renamed; real persisted enablement
   seed data lands with the Phase 3 config UI. *(→ Phase 1 / Phase 3 migration maps.)*

6. **App root = `detail_extensions`.** Rationale: these are *extended details* of both
   **assets and asset models**, not asset-only — so the neutral root `detail_extensions`
   reads better than `asset_extensions`. URL root `/detail_extensions/`. *(→ E1.)*

### Applied defaults (user approved "looks good", defaults taken)

- **Provisioning marker** moves **off** the `asset` / `asset_model` tables into
  `detail_extensions` state tables, so the assets schema carries no extension state
  (E7). (Cheaper alternative — a renamed `extensions_provisioned` JSON column left on
  the assets tables — was rejected for the cleaner-ignorance default.)
- **Names** (E8): descriptor `DetailExtension`; abstract bases `AssetExtensionContract`
  / `ModelExtensionContract`; enablement tables `detail_extensions_by_asset_class`,
  `detail_extensions_by_model`, `model_detail_extensions_by_asset_class`; contexts
  `AssetDetailExtensionContext` / `ModelDetailExtensionContext`; managers
  `AssetExtensionsManager` / `ModelExtensionsManager`.
- **Three phases**, not folded.

## Owner's requested URL grammar (verbatim, normalized in E6)

```
/detail_extensions/configuration                         configure which assets/models get which extensions
/detail_extensions/<extension-name>                      summary + index
/detail_extensions/<extension-name>/<assets|models>      search page
/detail_extensions/<extension-name>/<asset|model>/<id>   page for one owner
/detail_extensions/<extension-name>/<asset|model>/<id>/<row-id>   page for one row (one-to-many)
```
