# Phase 1 — `detail_extensions` app: relocate + rename (clean cut)

Stand up the new app and move the **entire** plugin framework into it under the
`extension` vocabulary, deleting the old packages. This phase changes *where code
lives and what it's called* — not *how provisioning is triggered* (that is Phase 2).

## Goal

`app/detail_extensions/` holds the framework (descriptor, registry, factory, table
contracts), the 3 enablement tables, the 5 concrete extensions (as vertical-slice
packages each with a file manifest), and the framework control layer. The old
`app/assets/plugins/` and `app/assets/control_layer/plugins/` are gone. The project
boots and a full DB rebuild + seed succeeds.

## In scope

- New app `app/detail_extensions/` registered in `INSTALLED_APPS`; `apps.py` skeleton.
- Relocate + rename per [`../migration_map.md`](../migration_map.md) (Phase 1 rows):
  base, registry, enablement models, control layer, concrete extensions.
- `plugin → extension` rename across all moved symbols (see [decisions E8](../decisions.md)).
- Each concrete extension package gains a **file manifest** (`manifest.py`, [E5](../decisions.md));
  the registry validates manifests at startup.
- Rename `Asset.plugins_provisioned` / `AssetModel.plugins_provisioned` →
  `extensions_provisioned` (kept on the assets tables **this phase only**).
- Remove the concrete-table import block from `assets/models/__init__.py`.
- Delete the old packages (clean cut, [E2](../decisions.md)).
- Full DB rebuild + seed.

## Out of scope

- The signal / post-commit inversion — Phase 2. **The orchestrator and model factory
  may still call the relocated provisioner directly this phase** (a transient
  `assets → detail_extensions` import), so creation keeps working while code moves.
- Moving the `.plugins` managers off the asset contexts — Phase 2.
- Moving provisioning state into state tables — Phase 2.
- Any UI work — Phase 3.

## Dependencies

- None beyond the current built framework. This is the first phase.

## Deliverables

- `app/detail_extensions/` package: `base/`, `registry.py`, `models/`, `control_layer/`,
  one sub-package per concrete extension, `apps.py`.
- Updated `assets/models/__init__.py` (import block removed).
- Old `plugins` packages deleted.
- Regenerated migrations; green `seed_dev`.

## Exit criteria

- [ ] `app/detail_extensions/` exists, is in `INSTALLED_APPS`, and imports cleanly.
- [ ] `grep -rn "plugin" app/` returns **zero** hits in first-party code (comments
      included), except where intentionally kept.
- [ ] `app/assets/plugins/` and `app/assets/control_layer/plugins/` no longer exist.
- [ ] `assets/models/__init__.py` imports **no** concrete extension table.
- [ ] Every entry in `EXTENSION_REGISTRY` resolves and passes manifest validation at
      startup; an extension with an incomplete manifest raises a clear error.
- [ ] `python dev_tools/delete_database_rebuild_models.py --seed` completes; the three
      `*_extensions_*` enablement tables and all 5 concrete extension tables exist.
- [ ] Creating an asset/model still provisions its enabled extensions (via the
      transient direct provisioner call) — behavior unchanged from before the move.
