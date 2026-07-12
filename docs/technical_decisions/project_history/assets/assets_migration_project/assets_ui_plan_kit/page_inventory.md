# Page Inventory — Classified

Per [`docs/starter_kit_process/how_to_plan_ui_features.md`](../docs/starter_kit_process/how_to_plan_ui_features.md),
every page is classified and given a primary goal.

- **Navigation Page** — dashboards/hubs that orient and route.
- **User View** — read-only / detail screens presenting information.
- **Work Portal** — action-oriented forms / workflows.

(Pages that are both a browse-list and an entrypoint are tagged **Navigation /
User View**.)

---

## Navigation Pages

| Page | Goal |
| :--- | :--- |
| **Assets Dashboard** (`/assets/`) | High-level overview: total assets / models / classes, capability-status rollup, recent assets, quick links into each management hub. Scoped wording uses **Data Domain**. |
| **Asset List** | Browse + search + filter (by domain, class, status) all assets; entry to each Asset-360. |
| **Model List** | Browse asset models; entry to model detail and create. |
| **Class List** | Browse asset classes; entry to class detail and config. |
| **Manufacturer List** | Browse manufacturers; entry to detail and create. |
| **Config Templates List** | Browse configuration templates; entry to builder/detail. |
| **Capability Definitions** | Catalog of capability definitions; entry to the three assignment hubs. |

## User Views

| Page | Goal |
| :--- | :--- |
| **Asset Detail (360)** | Single source of truth for one asset: identity, status, meters, image carousel, resolved capabilities, current configuration, plugin cards, parent/child tree, linked events. |
| **Model Detail** | One model's spec: identity, manufacturers, revisions, inherited/declared capabilities, configuration templates, enabled plugins. |
| **Class Detail** | One class: description, data domains, declared capabilities, plugin enablement summary. |
| **Manufacturer Detail** | One manufacturer: identity, website, list of models produced. |
| **Meter History** | Chronological meter readings across assets. |
| **Config Template Detail** | A template's modifications + child-model declarations (the BOM). |
| **Asset Configuration View** | An asset's as-built configuration: applied modifications, verification status. |
| **Plugin cards** (Purchase Info, Vehicle Registration) | Read view of one plugin's data on the Asset-360 page. |

## Work Portals

| Page | Goal |
| :--- | :--- |
| **Asset Create / Edit** | Capture/modify an asset (class → model → identity, domain, meters, parent). |
| **Model Create / Edit** | Capture/modify a model (class, manufacturers, domains, meter units, revision). |
| **Class Create / Edit** | Capture/modify a class (name, category, domains, restrict-to-domain-set). |
| **Manufacturer Create / Edit** | Capture/modify a manufacturer. |
| **Capability Definition Form** | Create/edit a capability definition. |
| **Class / Model / Asset Capability hubs** | Assign capabilities to a class / model / asset (and toggle active). |
| **Config Template Builder** | Compose a template from modifications + child models. |
| **Defined Modifications List + Detail/Edit** | CRUD the modification catalog. |
| **Asset Configuration Edit** | Record applied modifications + set verification status. |
| **Class / Model Plugin Enablement** | Toggle which plugins are enabled per class/model *(illustrative)*. |
| **Plugin card edit** | Edit one plugin's data *(illustrative)*. |

---

## Card inventory (composed views, not separate routes)

The Asset-360 and Model/Class detail pages are **compositions of cards**. These
are not their own routes but must be mocked to convey the feel. See
[navigation_flow.md](navigation_flow.md#asset-360-card-anatomy).

| Detail page | Cards |
| :--- | :--- |
| Asset-360 | Identity/Status · Meters · Asset Images Manager (view fragment / edit fragment: Upload, reorder, set-primary, delete) · Capabilities (resolved) · Current Configuration · Plugin cards (1–2) · Related Assets (parent/child) · Events (link to events app) |
| Model Detail | Identity · Manufacturers · Capabilities · Configuration Templates · Revisions · Enabled Plugins |
| Class Detail | Identity · Data Domains · Capabilities · Plugin Enablement |
</content>
