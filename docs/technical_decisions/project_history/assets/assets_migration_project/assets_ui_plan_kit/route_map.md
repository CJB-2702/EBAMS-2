# Route Map — New Pages ↔ Analogous Old Pages

The headline deliverable. Every page the mock will serve, its new Django route
under `/assets/`, the **old Flask page it descends from**, the **new model(s)**
that shape its mock data, and its classification (`Nav` = Navigation Page,
`UV` = User View, `WP` = Work Portal).

**Old path roots** (Flask app `/home/cb/REPOS/asset_management`):
- core routes → `app/presentation/routes/core/` + `templates/core/`
- assets routes → `app/presentation/routes/assets/` + `templates/assets/`

**New URL prefix:** `/assets/` (added to `app/config/urls.py` →
`app/assets/urls.py`). URL names are prefixed `asset_*`, `model_*`, `class_*`, etc.

Legend for "Status": **Port** = direct analog exists · **Rename** = analog
exists under a renamed concept · **New** = no old analog (new model) ·
**Illustrative** = Phase-2 plugins, mocked for feel only.

---

## 0. Hub

| New page | New route | URL name | Old analog | Model(s) | Class | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Assets Dashboard | `/assets/` | `asset_dashboard` | `core/dashboard.html` (asset portion) | counts across all | Nav | Rename |

## 1. Core — Assets *(Phase 1)*

| New page | New route | URL name | Old analog | Model(s) | Class | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Asset List / Browse | `/assets/assets/` | `asset_index` | `GET /assets` · `core/assets/list.html` | `Asset` | Nav/UV | Port |
| Asset Detail (360) | `/assets/assets/<id>/` | `asset_detail` | `GET /assets/<id>` · `core/assets/detail.html` + `assets/view.html` | `Asset` (+ meters, images, caps, config, plugins, parent/child, events) | UV | Port |
| Asset Create | `/assets/assets/create/` | `asset_create` | `core/assets/create.html` | `Asset` | WP | Port |
| Asset Edit | `/assets/assets/<id>/edit/` | `asset_edit` | `core/assets/edit.html` | `Asset` | WP | Port |
| Asset Images Manager | `/assets/assets/<id>/images/` | `asset_images` | `core/assets/images.html` | `AssetImage` | WP | Port |

> **Domain shift:** the old list/detail "Location" filter & card become **Data
> Domain**. Old `major_location` column → `asset.domain`.

## 2. Core — Asset Models *(Phase 1; old `MakeModel`)*

| New page | New route | URL name | Old analog | Model(s) | Class | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Model List | `/assets/models/` | `model_index` | `GET /make-models` · `core/make_models/list.html` | `AssetModel` | Nav/UV | Rename |
| Model Detail | `/assets/models/<id>/` | `model_detail` | `core/make_models/detail.html` | `AssetModel` (+ manufacturers, caps, config templates, plugins, revisions) | UV | Rename |
| Model Create | `/assets/models/create/` | `model_create` | `core/make_models/create.html` | `AssetModel`, `Manufacturer` (M2M), `Domain` (M2M) | WP | Rename |
| Model Edit | `/assets/models/<id>/edit/` | `model_edit` | `core/make_models/edit.html` | `AssetModel` | WP | Rename |

## 3. Core — Asset Classes *(Phase 1; old "Asset Types")*

| New page | New route | URL name | Old analog | Model(s) | Class | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Class List | `/assets/classes/` | `class_index` | `GET /asset-types` · `core/asset_classes/list.html` | `AssetClass` | Nav/UV | Rename |
| Class Detail | `/assets/classes/<id>/` | `class_detail` | `core/asset_classes/detail.html` | `AssetClass` (+ domains, caps, plugin enablement) | UV | Rename |
| Class Create | `/assets/classes/create/` | `class_create` | `core/asset_classes/create.html` | `AssetClass`, `Domain` (M2M) | WP | Rename |
| Class Edit | `/assets/classes/<id>/edit/` | `class_edit` | `core/asset_classes/edit.html` | `AssetClass` | WP | Rename |

## 4. Core — Manufacturers *(Phase 1; NEW — split from `MakeModel.make`)*

| New page | New route | URL name | Old analog | Model(s) | Class | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Manufacturer List | `/assets/manufacturers/` | `manufacturer_index` | — (was a string field) | `Manufacturer` | Nav/UV | **New** |
| Manufacturer Detail | `/assets/manufacturers/<id>/` | `manufacturer_detail` | — | `Manufacturer` (+ models produced) | UV | **New** |
| Manufacturer Create | `/assets/manufacturers/create/` | `manufacturer_create` | — | `Manufacturer` | WP | **New** |
| Manufacturer Edit | `/assets/manufacturers/<id>/edit/` | `manufacturer_edit` | — | `Manufacturer` | WP | **New** |

## 5. Core — Meter History

| New page | New route | URL name | Old analog | Model(s) | Class | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Meter History | `/assets/meter-history/` | `meter_history_index` | `GET /meter-history` · `core/meter_history/list.html` | `MeterHistory` | UV | Port |

## 6. Capabilities *(Phase 4)*

| New page | New route | URL name | Old analog | Model(s) | Class | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Capability Definitions | `/assets/capabilities/definitions/` | `capability_definition_index` | `assets/capabilities/definitions/list.html` | `CapabilityDefinition` | UV/Nav | Port |
| Definition Detail/Form | `/assets/capabilities/definitions/<id>/` | `capability_definition_detail` | `.../definitions/detail.html` + `form.html` | `CapabilityDefinition` | WP | Port |
| Class Capabilities | `/assets/capabilities/by-class/` | `class_capability_index` | `/asset-type-capabilities/` · `asset_class_capabilities/list.html` | `AssetClassCapability` | WP | Rename |
| Model Capabilities | `/assets/capabilities/by-model/` | `model_capability_index` | `/make-model-capabilities/` · `make_model_capabilities/list.html` | `ModelCapability` | WP | Rename |
| Asset Capabilities | `/assets/capabilities/by-asset/` | `asset_capability_index` | `/asset-capabilities/` · `asset_capabilities/list.html` | `AssetCapability` | WP | Port |

> Capabilities also surface **as cards** on the Class / Model / Asset detail
> pages (resolved/inherited view). The list pages above are the management hubs.

## 7. Configurations *(Phase 3)*

| New page | New route | URL name | Old analog | Model(s) | Class | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Config Templates List | `/assets/configurations/templates/` | `config_template_index` | `/template-configurations/` · `configurations/template_list.html` | `ConfigurationTemplate` | Nav/UV | Port |
| Template Builder | `/assets/configurations/templates/builder/` | `config_template_builder` | `configurations/template_builder.html` | `ConfigurationTemplate`, `TemplateChild`, `TemplateModification` | WP | Port |
| Template Detail | `/assets/configurations/templates/<id>/` | `config_template_detail` | `configurations/template_view.html` | `ConfigurationTemplate` (+ children, modifications) | UV | Port |
| Defined Modifications | `/assets/configurations/modifications/` | `defined_modification_index` | `/defined-modifications/` · `configurations/modification_list.html` | `DefinedModification` | UV/WP | Port |
| Modification Detail/Edit | `/assets/configurations/modifications/<id>/` | `defined_modification_detail` | `configurations/modification_view.html` + `modification_edit.html` | `DefinedModification` | WP | Port |
| Asset Configuration View | `/assets/assets/<id>/configuration/` | `asset_configuration_detail` | `asset-configuration-view` · `configurations/asset_configuration_view_portal.html` | `AssetConfiguration`, `ActualModification` | UV | Port |
| Asset Configuration Edit | `/assets/assets/<id>/configuration/edit/` | `asset_configuration_edit` | `configurations/asset_configuration_edit.html` | `AssetConfiguration`, `ActualModification` | WP | Port |

## 8. Plugins *(Phase 2 — Illustrative only)*

The old hard-linked **detail tables** (purchase-info, vehicle-registration,
toyota-warranty, emissions-info, model-info…) become the **plugin framework**.
UI is out of scope in the control kit, so these are mocked purely to convey the
"each plugin = its own card" feel.

| New page | New route | URL name | Old analog | Model(s) | Class | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Plugin card: Purchase Info | (card on `asset_detail`) | — | `assets/detail_tables/detail.html` (purchase-info) | plugin table (mock) | UV | Illustrative |
| Plugin card: Vehicle Registration | (card on `asset_detail`) | — | `detail_tables` (vehicle-registration) | plugin table (mock) | UV | Illustrative |
| Plugin card edit | `/assets/assets/<id>/plugins/<plugin>/edit/` | `asset_plugin_edit` | `detail_tables/edit.html` | plugin table (mock) | WP | Illustrative |
| Class Plugin Enablement | `/assets/classes/<id>/plugins/` | `class_plugin_config` | `detail_template_config/configure_asset_class.html` | `asset_plugins_by_asset_class` (mock) | WP | Illustrative |
| Model Plugin Enablement | `/assets/models/<id>/plugins/` | `model_plugin_config` | `detail_template_config/configure_make_model.html` | `model_plugins_by_asset_class` (mock) | WP | Illustrative |

## Explicitly out of scope (not migrated)

These old pages have **no model in the new `assets` app** and are excluded:
- `assets/technical_library/*` — technical library portal (not migrated).
- `core/events/*` — events live in the **separate `events` app** already built;
  the Asset-360 page links to it via an events card, not re-implemented here.
- `core/locations/*`, `core/users/*`, `core/role_definitions/*`,
  `core/user_roles/*`, `core/user_access/*` — belong to `administration`.
- `supply/*`, `maintenance/*`, `dispatching/*`, `inventory/*` — other domains.

## Count summary

| Group | Pages (routes) |
| :--- | ---: |
| Hub | 1 |
| Core — Assets | 5 |
| Core — Models | 4 |
| Core — Classes | 4 |
| Core — Manufacturers | 4 |
| Core — Meter History | 1 |
| Capabilities | 5 |
| Configurations | 7 |
| Plugins (illustrative) | 5 |
| **Total** | **36** |
</content>
