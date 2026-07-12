# Phase 3 — Control Layer Plan

## Target additions

```
app/detail_extensions/
├── urls.py                                  # /detail_extensions/ route table (NEW)
├── presentation_layer/
│   ├── entrypoints/
│   │   ├── configuration.py                 # enablement CRUD (real; replaces mock)
│   │   ├── extension_router.py              # target-derived dispatch for the per-extension grammar
│   │   └── aggregate_panel.py               # the 360-panel for one owner
│   └── search/
│       └── enablement_search.py             # reads for the config landing (which extension → where assigned)
├── control_layer/
│   ├── adapters/
│   │   └── enablement_assignment_adaptor.py # AssignmentAdaptor — POST payload → structured toggle input
│   ├── enablement_manager.py                # EnablementManager — assign/unassign verbs (writes)
│   └── guards/
│       └── enablement_assignment_guard.py   # AssignmentPolicy (may this user assign?) + AssignmentValidator
└── templates/detail_extensions/
    ├── configuration/…                      # landing + per-extension assignment editor
    └── panel/…                              # aggregate card strip
```

## Configuration (real enablement CRUD)

- **`EnablementManager`** (control layer; all writes) — domain verbs, not CRUD verbs:
  - `assign_to_class(*, extension_key, asset_class_id, actor)`
  - `unassign_from_class(*, extension_key, asset_class_id, actor)`
  - `assign_to_model(*, extension_key, model_id, actor)` / `unassign_from_model(...)`
  - Routes to `DetailExtensionsByAssetClass` / `DetailExtensionsByModel` /
    `ModelDetailExtensionsByAssetClass` based on the descriptor's `target` (asset vs
    model extension) — resolved via `ExtensionRegistryValidator`.
- **`AssignmentValidator`** (guard) — `extension_key` resolves; the chosen scope matches
  the extension's `target` (an asset-target extension cannot be assigned to a model row,
  etc.); no duplicate (unique constraint mirror).
- **`AssignmentPolicy`** (guard) — may this actor configure assignments? (admin-scoped;
  follows the project RBAC + ownership rules).
- **`AssignmentAdaptor`** — maps the POST/HTMX payload (checkbox grid of
  class/model × extension) to structured assign/unassign calls.

Entrypoint `configuration.py` stays **thin**: parse via adaptor → call `EnablementManager`
verb → render. No writes in the entrypoint (layer rule).

## Per-extension route grammar (the contract — bodies deferred)

**`extension_router`** is the framework's dispatcher. For every per-extension URL it:

1. resolves `<extension-key>` via `ExtensionRegistryValidator` (404 if unknown);
2. derives the owner-type segment from the descriptor's `target`
   (`ASSET → asset/assets`, `MODEL → model/models`) and validates the URL's segment
   matches (404 on mismatch);
3. for owner-scoped routes, checks the extension is **enabled** for that owner
   (404/empty if not);
4. dispatches to the extension's declared entrypoint from its **manifest**
   (`entrypoints_module`) — or, this phase, a **placeholder view** that renders the
   slot with a "page body pending" notice for extensions that have not implemented it.

Routes (from [E6](../decisions.md)):

| Pattern | Resolves to | Status |
| :--- | :--- | :--- |
| `/detail_extensions/configuration/` | `configuration.landing` | **built** |
| `/detail_extensions/configuration/<extension-key>/` | `configuration.assign_editor` | **built** |
| `/detail_extensions/<extension-key>/` | extension summary/index | **slot** (router + placeholder) |
| `/detail_extensions/<extension-key>/<assets\|models>/` | extension search | **slot** |
| `/detail_extensions/<extension-key>/<asset\|model>/<id>/` | owner detail (1:1 lands here) | **slot** |
| `/detail_extensions/<extension-key>/<asset\|model>/<id>/<row-id>/` | single row (1:many) | **slot** |
| `/detail_extensions/<asset\|model>/<id>/?format=htmx-panel` | `aggregate_panel.panel` | **built** |

> `format=` drives density/fragments; never combine density and `htmx-*` in one request
> (project rule). The aggregate panel is an `htmx-panel` fragment; each per-extension
> slot must also satisfy the F5 rule (works on full reload) when its body is built.

## Aggregate panel (built)

- **`aggregate_panel.panel(request, owner_type, owner_id)`** — resolves the owner,
  loads its enabled extensions via `AssetExtensionsStruct` / `ModelExtensionsStruct`
  (Phase 1/2 reads), and renders one **card per enabled extension**. Each card uses the
  descriptor's `label` + reserved `card_template` hint and links into the per-extension
  grammar. Read-only; no writes.

## Delegation flow (assign an extension to a class)

```
POST /detail_extensions/configuration/<extension-key>/
  → AssignmentAdaptor.parse(payload)              # structured toggles
  → AssignmentPolicy.check(actor)                 # may configure?
  → EnablementManager.assign_to_class(extension_key, class_id, actor)
        → AssignmentValidator.check(...)          # target match, no dupe
        → DetailExtensionsByAssetClass.objects.create(...)
  → redirect/HTMX re-render of the assignment editor
```

## Delegation flow (render the 360 panel)

```
GET /detail_extensions/asset/<id>/?format=htmx-panel
  → aggregate_panel.panel
  → AssetExtensionsStruct(asset_id).to_dict()     # {extension_key: [...]}  (enabled only)
  → render card per descriptor (label + card_template hint) → links into <extension-key> grammar
```
