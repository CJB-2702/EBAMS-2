# Phase 2 — Control Layer Plan

## The signal seam (assets-side — the only assets→world surface)

`app/assets/signals.py` (NEW):

```python
from django.dispatch import Signal

# kwargs: asset (Asset)        — sent as the final in-transaction step of asset creation
asset_created = Signal()
# kwargs: model (AssetModel)   — sent as the final in-transaction step of model creation
asset_model_created = Signal()
```

**Emission points** (assets owns these; importing a `Signal` is not a dependency on any
listener):

- `AssetCreationOrchestrator.create` — after meter/tree/eventing, as the **last
  statement inside `transaction.atomic()`**:
  ```python
  asset_created.send(sender=Asset, asset=asset)
  ```
  Remove the transient `AssetExtensionProvisioner.provision_for_asset(...)` call and its
  import.
- `AssetModelFactory.create` — after the model row + its create-steps:
  ```python
  asset_model_created.send(sender=AssetModel, model=model)
  ```
  Remove the transient `ModelExtensionProvisioner` call + import.

> **Why fire inside the transaction but provision after commit:** sending inside the
> atomic block lets the receiver call `transaction.on_commit`, which Django queues
> against the *current* transaction and runs only if it commits. Net effect: no
> provisioning for a rolled-back asset; provisioning immediately after a successful one.
> Do **not** use Django's `post_save` — it fires before the orchestrator's later steps,
> so the owner would not be fully built.

## Receiver wiring (`detail_extensions` — the listener)

`detail_extensions/apps.py`:

```python
class DetailExtensionsConfig(AppConfig):
    name = "app.detail_extensions"

    def ready(self):
        from app.detail_extensions.control_layer.provisioning import receivers  # noqa
        receivers.connect()
```

`detail_extensions/control_layer/provisioning/receivers.py` (NEW):

- `connect()` — `asset_created.connect(on_asset_created)`,
  `asset_model_created.connect(on_asset_model_created)`.
- `on_asset_created(sender, asset, **kwargs)` —
  `transaction.on_commit(lambda: AssetExtensionProvisioner.provision_for_asset(asset_id=asset.pk, actor=...))`.
- `on_asset_model_created(sender, model, **kwargs)` — symmetric.

> Receivers are **thin** — they only schedule. All logic stays in the provisioner
> Handler. Pass the **pk**, not the instance, into the `on_commit` closure, and re-fetch
> inside the post-commit transaction (the instance's transaction has closed).

## Provisioner reshape (marker → state table, E7)

`AssetExtensionProvisioner.provision_for_asset(*, asset_id, actor)` (Handler):

1. Re-fetch the asset (post-commit, fresh transaction).
2. Load-or-create `AssetExtensionProvisioningState(asset)`; read `provisioned_keys`.
3. Enabled keys = `DetailExtensionsByAssetClass(asset.asset_class)` +
   `DetailExtensionsByModel(asset.model)`.
4. For each key not in `provisioned_keys`: `ExtensionRegistryValidator.resolve(key)` →
   `descriptor.factory.provision(owner=asset, descriptor=descriptor, actor=actor)`;
   append the key.
5. Save `provisioned_keys` back to the state row. **Idempotent / backfill-safe.**
6. Wrap steps 2–5 in `transaction.atomic()` (its own post-commit transaction). A
   failure here is logged and isolated — it does **not** touch the already-committed
   asset.

`ModelExtensionProvisioner.provision_for_model(*, model_id, actor)` — symmetric against
`ModelDetailExtensionsByAssetClass` + `ModelExtensionProvisioningState`.

## Read access moves off the asset contexts

NEW Contexts in `detail_extensions/control_layer/`:

- **`AssetDetailExtensionContext(asset_id)`** — `from_struct()`, and hosts
  `AssetExtensionsManager` as its `.extensions` collaborator (replaces
  `AssetContext.plugins`). Verbs: `list()`, `get(extension_key)`, `add(...)`,
  `update(...)`, `remove(...)` — cardinality enforced from the descriptor.
- **`ModelDetailExtensionContext(model_id)`** — symmetric with `ModelExtensionsManager`.

**Remove** from `assets`: the `.plugins` property and its import on `AssetContext` and
`AssetModelContext`; the `extensions_provisioned` field from `AssetStruct` /
`AssetModelStruct`.

## Delegation flow (provision on create — post-commit)

```
AssetCreationOrchestrator.create  (atomic)
  → AssetFactory.create → Asset
  → … meter / tree / eventing …
  → asset_created.send(asset=asset)            # last in-txn statement
                                               # assets knows nothing more
        │  (detail_extensions receiver, registered in ready())
        └─ transaction.on_commit:
             AssetExtensionProvisioner.provision_for_asset(asset_id)   # NEW txn, post-commit
               state = AssetExtensionProvisioningState.get_or_create(asset)
               for key in enabled - state.provisioned_keys:
                 → ExtensionRegistryValidator.resolve(key) → descriptor
                 → descriptor.factory.provision(owner=asset, descriptor, actor)
                 → state.provisioned_keys.append(key)
               state.save()
```

## Delegation flow (read an owner's extensions — new entry point)

```
AssetDetailExtensionContext(asset_id).extensions.list()
  → AssetExtensionsManager
  → AssetExtensionsStruct(asset_id)
       for descriptor in descriptors_for_target(ASSET):
         rows = descriptor.primary_model.objects.filter(asset_id=…)
       → to_dict()   # {extension_key: [...]}
```

## Verification hooks

- `grep -rn "detail_extensions" app/assets/` → **empty**.
- A factory that raises in provisioning leaves the asset committed (creation unaffected).
- The `on_commit` receiver fires only after a successful create (none on rollback).
