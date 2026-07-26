# Phase 1 — Control Layer Plan

## Target tree (after the move)

```
app/detail_extensions/
├── apps.py                              # DetailExtensionsConfig (ready() skeleton; receivers wired in P2)
├── registry.py                          # EXTENSION_REGISTRY (explicit list) + lookups + manifest validation
├── base/
│   ├── extension_descriptor.py          # DetailExtension, ExtensionTarget, ExtensionCardinality
│   ├── extension_factory.py             # ExtensionFactory (base provision; the extension seam)
│   ├── table_contract.py                # AssetExtensionContract, ModelExtensionContract (abstract)
│   └── manifest.py                       # ExtensionManifest (the per-extension file declaration, E5)
├── models/
│   ├── __init__.py                       # registers enablement tables with the app
│   └── enablement.py                     # DetailExtensionsByAssetClass / ByModel / ModelDetailExtensionsByAssetClass
├── control_layer/
│   ├── provisioning/
│   │   ├── asset_extension_provisioner.py   # AssetExtensionProvisioner (Handler)
│   │   └── model_extension_provisioner.py   # ModelExtensionProvisioner (Handler)
│   ├── managers/
│   │   ├── asset_extensions_manager.py      # AssetExtensionsManager
│   │   └── model_extensions_manager.py      # ModelExtensionsManager
│   ├── domain_structs/
│   │   ├── asset_extensions_struct.py       # AssetExtensionsStruct (union read)
│   │   └── model_extensions_struct.py       # ModelExtensionsStruct (union read)
│   └── guards/
│       └── extension_registry_guard.py      # ExtensionRegistryValidator
├── purchase_info/                       # vertical slice — asset / one-to-one
│   ├── models.py                        # PurchaseInfo(AssetExtensionContract)
│   ├── extension.py                     # PurchaseInfoExtension(DetailExtension)
│   └── manifest.py                      # PurchaseInfoExtension.manifest contents (E5)
├── model_info/                          # model / one-to-one
├── vehicle_registration/                # asset / one-to-one
├── smog_record/                         # asset / one-to-many
└── emissions_info/                      # asset / one-to-one
```

> **Layering.** Extension *packages* (table + descriptor + factory + manifest) and the
> framework *coordination* (provisioners, managers, structs, guard, registry) now both
> live in `detail_extensions`. The host (`assets`) imports **nothing** from here except,
> transiently this phase, the two provisioners (severed in Phase 2).

## The extension contract — `DetailExtension`

Renamed from `AssetPlugin`; same declarative, class-attribute shape. Minimum contract
unchanged: `key`, `label`, `target` (`ExtensionTarget.ASSET|MODEL`), `cardinality`
(`ExtensionCardinality.ONE_TO_ONE|ONE_TO_MANY`), `primary_model`, `factory`. Reserved
seams (`card_template`) carry over for the Phase 3 contract.

**New required attribute — `manifest: ExtensionManifest`** ([E5](../decisions.md)).

## `ExtensionManifest` (new, E5)

A small declarative struct (in `base/manifest.py`) each extension sets, enumerating its
own files/modules:

| Field | Meaning |
| :--- | :--- |
| `models_module` | dotted path to the slice's `models.py` |
| `control_modules` | list of dotted paths to the slice's control classes (empty for the 5 references this phase) |
| `template_dir` | the slice's template directory (reserved for Phase 3 bodies) |
| `entrypoints_module` | the slice's entrypoints module (reserved for Phase 3) |
| `urls_module` | the slice's urls module (reserved for Phase 3) |

It is a **declaration**, not behavior — no logic on it. The registry validates it
exists and its declared modules import (or are explicitly marked reserved/None).

## Registry + Guard (moved + renamed)

- **`registry.py`** — `EXTENSION_REGISTRY` is the explicit list of `DetailExtension`
  subclasses assembled into `{key: descriptor}`, plus `get(key)` and
  `descriptors_for_target(target)`. Adds a startup pass that calls the guard to
  validate **manifest completeness** for every registered extension.
- **`ExtensionRegistryValidator`** (`guards/extension_registry_guard.py`, was
  `PluginRegistryValidator`) — `resolve(extension_key) -> DetailExtension | raise`.
  Extended to also assert each descriptor's `manifest` is present and well-formed
  (unknown key **and** missing/invalid manifest are both hard errors).

## Provisioners (moved + renamed; logic unchanged this phase)

- **`AssetExtensionProvisioner.provision_for_asset(*, asset, actor)`** (was
  `AssetPluginProvisioner`) — gather enabled keys from `DetailExtensionsByAssetClass`
  + `DetailExtensionsByModel`, skip keys already in `asset.extensions_provisioned`,
  resolve each via `ExtensionRegistryValidator`, call `descriptor.factory.provision(...)`,
  append the key. Still reads/writes `asset.extensions_provisioned` **this phase**
  (relocated to the state table in Phase 2).
- **`ModelExtensionProvisioner.provision_for_model(*, model, actor)`** — same against
  `ModelDetailExtensionsByAssetClass`, marking `model.extensions_provisioned`.

## Managers + Structs (moved + renamed; still reached via the asset contexts this phase)

- **`AssetExtensionsManager`** / **`ModelExtensionsManager`** — CRUD + read; cardinality
  enforced from the descriptor. Still exposed as `AssetContext.plugins` /
  `AssetModelContext.plugins` **this phase** (the property import is updated to the new
  module path; the property is *removed* from the asset contexts in Phase 2).
- **`AssetExtensionsStruct`** / **`ModelExtensionsStruct`** — union reads over
  `descriptors_for_target(...)`, `to_dict()` as `{extension_key: [rows]}`.

## Transient orchestrator wiring (severed in Phase 2)

`AssetCreationOrchestrator` and `AssetModelFactory` keep calling the relocated
provisioners directly this phase:

```python
# transient — replaced by signal emission in Phase 2
AssetExtensionProvisioner.provision_for_asset(asset=asset, actor=actor)
```

This is the one tolerated `assets → detail_extensions` import. It exists only so the
project keeps booting and creating assets while the files relocate; Phase 2 deletes it.

## Delegation flow (provision on create — unchanged behavior, new names)

```
AssetCreationOrchestrator.create  (atomic)
  → AssetFactory.create → Asset
  → AssetExtensionProvisioner.provision_for_asset      # transient direct call (P1)
        enabled keys = DetailExtensionsByAssetClass(class) + DetailExtensionsByModel(model)
        for key not in asset.extensions_provisioned:
          → ExtensionRegistryValidator.resolve(key) → descriptor
          → descriptor.factory.provision(owner=asset, descriptor, actor)
          → asset.extensions_provisioned.append(key)
```
