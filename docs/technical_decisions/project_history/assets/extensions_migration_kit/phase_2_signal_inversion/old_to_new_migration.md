# Phase 2 — Old → New Porting Checklist

One full DB rebuild at the end (the column drop + new tables are schema changes).

## 1. Define + emit the signals (assets-side)

- [ ] NEW `app/assets/signals.py` → `asset_created`, `asset_model_created`.
- [ ] `AssetCreationOrchestrator.create` — add `asset_created.send(sender=Asset,
      asset=asset)` as the **last statement inside** `transaction.atomic()`; **delete**
      the transient `AssetExtensionProvisioner` call + import.
- [ ] `AssetModelFactory.create` — add `asset_model_created.send(...)`; delete the
      transient `ModelExtensionProvisioner` call + import.
- [ ] Confirm emission is **after** meter/tree/eventing (owner fully built).

## 2. Wire receivers (detail_extensions-side)

- [ ] NEW `detail_extensions/control_layer/provisioning/receivers.py` with `connect()`
      + `on_asset_created` / `on_asset_model_created`, each scheduling
      `transaction.on_commit(...)` with the owner **pk** (not instance).
- [ ] `detail_extensions/apps.py` `ready()` imports and calls `receivers.connect()`.

## 3. Provisioning state (E7)

- [ ] NEW `detail_extensions/models/provisioning_state.py` →
      `AssetExtensionProvisioningState`, `ModelExtensionProvisioningState`; register in
      `models/__init__.py`.
- [ ] Reshape both provisioners: signature `(*, asset_id|model_id, actor)`; re-fetch
      owner; read/write `provisioned_keys` on the state row; wrap in its own
      `transaction.atomic()`.
- [ ] Remove the `extensions_provisioned` JSON column from `assets/models/core/asset.py`
      and `asset_model.py`.

## 4. Move read access off the asset contexts

- [ ] NEW `AssetDetailExtensionContext`, `ModelDetailExtensionContext` in
      `detail_extensions/control_layer/`, hosting the moved managers.
- [ ] **Remove** the `.plugins` property + import from `AssetContext` /
      `AssetModelContext`.
- [ ] Update any caller of `AssetContext(...).plugins` to
      `AssetDetailExtensionContext(...).extensions`.
- [ ] Remove `extensions_provisioned` from `AssetStruct` / `AssetModelStruct`
      `to_dict()` payloads.

## 5. Rebuild + verify

- [ ] `python dev_tools/delete_database_rebuild_models.py --seed`.
- [ ] `grep -rn "detail_extensions" app/assets/` → **empty**. (The dependency is severed.)
- [ ] Create an asset → row commits; receiver fires post-commit; state table records keys.
- [ ] Force a factory error → asset still created; provisioning failure isolated/logged.
- [ ] Enable a new extension on a class, re-run provisioning for an existing asset →
      only the missing row is added (idempotent).

## Notes / gotchas

- **Instance vs pk in `on_commit`.** The closure runs after the transaction closes;
  capture `asset.pk` and re-query inside the provisioner, never the stale instance.
- **Test signal connection.** In tests, `ready()` runs once; if a test needs to assert
  provisioning, trigger a real create or call the provisioner directly. Document this in
  the test module.
- **`actor` in a post-commit context.** The request user may not be available
  post-commit; pass the actor id through the signal kwargs or resolve a system actor.
  Decide and record (carry-over open question from the brainstorming session).
