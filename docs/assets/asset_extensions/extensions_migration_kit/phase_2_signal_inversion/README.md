# Phase 2 — Invert the dependency: signal-driven post-commit provisioning

Flip the single remaining `assets → detail_extensions` edge. After this phase the
assets app has **zero** knowledge that extensions exist; provisioning happens because
`detail_extensions` *listens*, not because assets *calls*.

## Goal

Asset and model creation emit a signal; `detail_extensions` receives it and provisions
its extensions **after the creation transaction commits**. The `.plugins` accessor
leaves the asset contexts, and provisioning state leaves the assets tables. Executes
[D8](../../asset_control_layer_starter_kit/decisions.md) / [E3](../decisions.md) / [E7](../decisions.md).

## In scope

- NEW `app/assets/signals.py` → `asset_created`, `asset_model_created`
  (`django.dispatch.Signal`).
- Emit each signal as the **final in-transaction step** of creation
  (`AssetCreationOrchestrator`, `AssetModelFactory`) — after meter/tree/eventing.
- Remove the direct provisioner calls from assets (the transient P1 import).
- `detail_extensions/apps.py` `ready()` connects one receiver per signal; each
  schedules provisioning via `transaction.on_commit`.
- NEW `AssetDetailExtensionContext` / `ModelDetailExtensionContext` in `detail_extensions`,
  hosting the (moved) `AssetExtensionsManager` / `ModelExtensionsManager`.
- Remove the `.plugins` property + imports from `AssetContext` / `AssetModelContext`.
- NEW provisioning-state tables ([E7](../decisions.md)); **delete** the
  `extensions_provisioned` columns from `asset` / `asset_model`; provisioner reads/writes
  the state tables.
- Remove `extensions_provisioned` from `AssetStruct` / `AssetModelStruct`.
- Full DB rebuild + seed.

## Out of scope

- Any UI — Phase 3.
- Changing *which* extensions are enabled or the descriptor contract.

## Dependencies

- **Phase 1 complete** — all code relocated and renamed; the only assets→extensions
  link left is the transient provisioner call this phase removes.

## Deliverables

- `app/assets/signals.py`; emission wired into the two creation paths.
- Receivers in `detail_extensions/apps.py` + a provisioning receiver module.
- The two new contexts; `.plugins` removed from the asset contexts.
- Provisioning-state tables; markers dropped from assets.
- Regenerated migrations; green `seed_dev`.

## Exit criteria

- [ ] `grep -rn "detail_extensions" app/assets/` returns **zero** results — assets
      imports nothing from the extensions app.
- [ ] `grep -rn "extension" app/assets/` returns only the **signal definitions/sends**
      in `signals.py` + the two creation paths — no extension *models, managers, or
      provisioners* referenced.
- [ ] `asset` and `asset_model` tables have **no** `extensions_provisioned` column.
- [ ] Creating an asset commits successfully **even if** an extension factory raises;
      the asset exists and the failure is isolated to provisioning (does not roll back
      creation).
- [ ] On a normal create, extension rows appear **after** commit (verifiable: a
      breakpoint/log in the receiver fires post-commit) and the state table records the
      provisioned keys.
- [ ] Re-running provisioning (backfill) for an owner with newly-enabled extensions
      adds only the missing rows — idempotent via the state table.
- [ ] Reading an owner's extensions goes through `AssetDetailExtensionContext` /
      `ModelDetailExtensionContext`, not through `AssetContext`.
