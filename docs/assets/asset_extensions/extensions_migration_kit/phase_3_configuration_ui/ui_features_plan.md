# Phase 3 — UI Features & Page Inventory

Pages classified as **User View** (read/detail), **Work Portal** (action/forms), or
**Navigation Page** (hub/router). Per-extension *body* pages are listed as **deferred
slots** — the routing/contract is built, the content is not.

## Built this phase

| Page | URL | Classification | Goal |
| :--- | :--- | :--- | :--- |
| **Configuration landing** | `/detail_extensions/configuration/` | Navigation Page | List every registered extension with where it's assigned (which classes/models); link to each extension's assignment editor. The catalog + status hub. |
| **Assignment editor** | `/detail_extensions/configuration/<extension-key>/` | Work Portal | Toggle an extension on/off across asset classes (and models, for asset-target). Persists to the enablement tables. Replaces the mock. |
| **Aggregate detail panel** | `/detail_extensions/<asset\|model>/<id>/?format=htmx-panel` | User View | A compact card strip on the owner's 360 page showing every enabled extension as a card, each linking into that extension's area. HTMX-loaded; F5-safe. |

## Contract defined, body deferred (slots)

These resolve through `extension_router` (key validation, target-derived segments,
enablement check) and render a **placeholder** until each extension implements its body.

| Slot | URL | Intended classification | Intended goal |
| :--- | :--- | :--- | :--- |
| **Extension summary / index** | `/detail_extensions/<extension-key>/` | Navigation Page | Overview of one extension type across the system + entry to its search. |
| **Extension search** | `/detail_extensions/<extension-key>/<assets\|models>/` | User View | Searchable list of all owners carrying this extension (plural segment from `target`). |
| **Owner detail** | `/detail_extensions/<extension-key>/<asset\|model>/<id>/` | User View / Work Portal | The extension's page for one owner. For `ONE_TO_ONE`, the record lands/edits here. |
| **Single row** | `/detail_extensions/<extension-key>/<asset\|model>/<id>/<row-id>/` | User View / Work Portal | One entry of a `ONE_TO_MANY` extension (e.g. one smog test in the history). |

## Interface rules every extension body must honor (the contract)

- **Single canonical URL + `format=`** for density (`condensed`/`medium`/`large`) and
  HTMX fragments (`htmx-*`); never combine density and `htmx-*` in one request.
- **F5 rule** — each slot works on a plain full-page reload; HTMX layers on top.
- **Target-derived segments** — singular/plural and `asset`/`model` come from the
  descriptor's `target`; bodies must not hardcode them.
- **Cardinality-aware** — `ONE_TO_ONE` extensions terminate at the owner-detail slot;
  `ONE_TO_MANY` use the owner-detail slot as a list and the single-row slot as the item.
- **Bulma + sharp corners** — house style (radius 0, no pills); cards in the aggregate
  panel follow `COMMON_UI_COMPONENTS` + `form_style_guide`.

## Removed this phase

| Removed | Replaced by |
| :--- | :--- |
| Mock `entrypoints/plugins.py` (`asset_plugin_edit`, `class_plugin_config`, `model_plugin_config`) | Real `configuration.py` + `extension_router` |
| Mock `mock_data.py` (plugin parts) | Real reads (`AssetExtensionsStruct`, enablement search) |
| `assets/urls.py` plugin routes + `assets/templates/assets/plugins/*` | `detail_extensions/urls.py` + `detail_extensions/templates/` |
