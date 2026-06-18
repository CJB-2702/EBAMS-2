# Decisions — Extensions Migration Kit

Decision log for this migration. These build on **D7** and **D8** from
[`asset_control_layer_starter_kit/decisions.md`](../asset_control_layer_starter_kit/decisions.md),
which established the rename and the signal-driven design at the concept level. The
`E#` decisions here are the *execution-level* choices for the migration itself.

---

## E1 — App name `detail_extensions` (not `asset_extensions`)

**Status:** Accepted

The framework attaches to **both** `Asset` and `AssetModel`, and the units are
"extended details" of those owners. A neutral root reads better than an asset-only
one. New Django app `app/detail_extensions/`, app label `detail_extensions`, URL root
`/detail_extensions/`. The user's phrasing — "extended details of both assets and
asset models" — is the naming source.

---

## E2 — Clean cut, no shims

**Status:** Accepted

`app/assets/plugins/` and `app/assets/control_layer/plugins/` are **deleted** once
their contents are relocated. No re-export stubs, no back-compat `plugins` aliases.
Justified because nothing outside the assets app imports them and dev does a full DB
rebuild, so there is no external or data consumer to protect. Greppability wins: after
the migration, `grep -r plugin app/` should return nothing in first-party code.

---

## E3 — Provisioning is signal-driven and post-commit (executes D8)

**Status:** Accepted (executes D8)

`app/assets/signals.py` defines `asset_created` and `asset_model_created`
(`django.dispatch.Signal`). The asset creation orchestrator and the model factory each
`send()` their signal as the **last in-transaction step** of creation — after the row
and its sibling create-steps (meter, tree, eventing) are settled, so listeners see a
fully-built owner. `detail_extensions` connects **one** receiver per signal in
`apps.py` `ready()`; each receiver schedules the actual provisioning with
`transaction.on_commit(...)`. The owner therefore commits first; extension rows are
created in a **separate** post-commit transaction.

**Why the signal lives in `assets`, not `detail_extensions`.** A `Signal` object is
part of the *emitter's* public surface ("events I announce"). Assets defining and
sending it creates **no** dependency on extensions — assets imports no receiver.
`detail_extensions` imports the signal from assets to connect to it; that is the
allowed direction (`detail_extensions → assets`).

**Why post-commit, not in-transaction.** Chosen on the consistency↔independence
spectrum (D8): a broken extension must never roll back asset creation, and an asset is
valid standalone. The temporary "owner exists, extensions not yet provisioned" window
is made safe by idempotent provisioning (E7).

---

## E4 — Framework control stays central

**Status:** Accepted

Provisioners, managers, structs, the registry, and the registry guard are
**framework-level** concerns, not per-extension. They live centrally:
`detail_extensions/control_layer/` + `detail_extensions/base/` + `registry.py`. A
concrete extension package owns only its **model + descriptor + factory + its own
templates/entrypoints**. This keeps the seam in one place while letting each extension
remain a self-contained slice.

---

## E5 — Each extension declares a file manifest

**Status:** Accepted

Beyond the descriptor's behavioral attributes, every extension declares an
**`ExtensionManifest`** — an explicit list of its own associated files/modules
(`models`, `control` classes, `templates` dir, `entrypoints`/`urls` module). The
central registry **validates** each registered extension's manifest at startup.

**Why.** (a) It makes each extension genuinely self-describing, so the central router
can wire a target-derived URL include per extension without hardcoding paths; (b) it
documents the slice's surface in one place; (c) it is the pre-condition for an
extension to later **graduate to its own Django app** (D7's stated future option) —
the manifest already enumerates everything that would move.

---

## E6 — UI: route-pattern contract + concrete config UI; per-extension bodies deferred

**Status:** Accepted

Two distinct UI deliverables, only one of which is implemented now:

- **Implemented (Phase 3):** the **assignment/configuration UI** under
  `/detail_extensions/configuration/` — CRUD over the three enablement tables (assign
  an extension to asset classes / models). This **replaces** the current *mock*
  config entrypoints (`entrypoints/plugins.py`, `mock_data.py`).
- **Specified only (interface contract):** the per-extension URL grammar and the
  aggregate 360-panel. The framework owns the **routing** (singular/plural and
  `asset`/`model` segments are derived from the extension's `target`); each extension
  supplies the **page body**, which is **out of scope for this kit**.

Normalized grammar (from the owner's request, aligned to the `format=` + F5 rules):

```
/detail_extensions/configuration/                                   landing
/detail_extensions/configuration/<extension-key>/                   assign to classes/models
/detail_extensions/<extension-key>/                                 summary + index        [body deferred]
/detail_extensions/<extension-key>/<assets|models>/                 search                 [body deferred]
/detail_extensions/<extension-key>/<asset|model>/<id>/              owner detail (1:1 lands here) [body deferred]
/detail_extensions/<extension-key>/<asset|model>/<id>/<row-id>/     single row (1:many)    [body deferred]
/detail_extensions/<asset|model>/<id>/?format=htmx-panel            aggregate 360 panel    [contract]
```

---

## E7 — Provisioning state moves off the assets tables

**Status:** Accepted (default approved)

The `plugins_provisioned` JSON markers are **removed** from `asset` and `asset_model`.
Provisioning state is tracked inside `detail_extensions` via small state tables
(`AssetExtensionProvisioningState`, `ModelExtensionProvisioningState`: one row per
owner, a JSON list of provisioned `extension_key`s). Reasons: (a) the assets schema
then carries **zero** extension state, completing the ignorance goal of E3/D8; (b) a
durable marker is still required because a `ONE_TO_MANY` extension with an empty
history is indistinguishable from "never provisioned" by row-existence alone, so the
marker cannot simply be inferred.

**Phasing:** the rename `plugins_provisioned → extensions_provisioned` stays on the
assets tables through **Phase 1** (minimal change while code moves) and is **relocated
into the state tables in Phase 2**, alongside severing the dependency — because Phase 2
is where "assets carries no extension state" must become true.

---

## E8 — Canonical names

**Status:** Accepted

| Old (`plugin`) | New (`extension`) |
| :--- | :--- |
| `AssetPlugin` (descriptor) | `DetailExtension` |
| `PluginTarget` / `PluginCardinality` | `ExtensionTarget` / `ExtensionCardinality` |
| `PluginFactory` | `ExtensionFactory` |
| `AssetPluginTableVirtual` / `ModelPluginTableVirtual` | `AssetExtensionContract` / `ModelExtensionContract` |
| `registry.PLUGIN_REGISTRY` | `registry.EXTENSION_REGISTRY` |
| `PluginRegistryValidator` | `ExtensionRegistryValidator` |
| `AssetPluginProvisioner` / `ModelPluginProvisioner` | `AssetExtensionProvisioner` / `ModelExtensionProvisioner` |
| `AssetPluginsManager` / `ModelPluginsManager` | `AssetExtensionsManager` / `ModelExtensionsManager` |
| `AssetPluginsStruct` / `ModelPluginsStruct` | `AssetExtensionsStruct` / `ModelExtensionsStruct` |
| `AssetContext.plugins` / `AssetModelContext.plugins` | `AssetDetailExtensionContext` / `ModelDetailExtensionContext` (separate contexts in the new app) |
| `asset_plugins_by_asset_class` | `detail_extensions_by_asset_class` |
| `asset_plugins_by_model` | `detail_extensions_by_model` |
| `model_plugins_by_asset_class` | `model_detail_extensions_by_asset_class` |
| `plugin_key` | `extension_key` |
| `plugins_provisioned` (column) | provisioning state tables (E7) |
