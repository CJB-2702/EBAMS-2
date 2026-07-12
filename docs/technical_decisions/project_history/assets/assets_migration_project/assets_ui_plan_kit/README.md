# Assets UI Plan Kit

A **UI prototyping kit** for the new `assets` sub-application. The goal is a
**mock application with hard-coded data** — no control layer, no real ORM
queries — that lets us *feel* how the migrated assets app will look and flow,
served live at **`localhost/assets`**, in the **style of this repo** (the
`events` app shell) and the **shape of the new migrated models**.

This kit is the **plan to review before building**. It answers the first ask:

> *List out a map of all the new pages / routes that will be built and their
> analogous previous pages.*

## Companion kit

The data shapes and phase boundaries come from the already-written control-layer
kit: [`../asset_control_layer_starter_kit/`](../asset_control_layer_starter_kit/).
This UI kit is **presentation only** and deliberately mirrors its phases so the
two can be built in lockstep.

| Source app (old) | Stack | This app (new) | Stack |
| :--- | :--- | :--- | :--- |
| `/home/cb/REPOS/asset_management` | **Flask** + SQLAlchemy, Bulma | `Django-Starter-Kit` | **Django 6** + HTMX + Bulma |

## What "mock" means here (binding constraints)

1. **No real backend.** Entrypoints return `render()` with **hard-coded Python
   dicts/lists** shaped like the new models. No `Model.objects`, no control
   layer, no auth scoping logic.
2. **New model shape.** Mock data mirrors the fields of the migrated models in
   [`app/assets/models/`](../app/assets/models/) — e.g. `Manufacturer` is split
   out of the old `MakeModel.make`, and access is scoped by **Data Domain**, not
   the old **Major Location**.
3. **New app style.** Every page extends an `asset_base.html` shell cloned from
   [`app/events/templates/events/ev_base.html`](../app/events/templates/events/ev_base.html):
   collapsable sidebar, top nav, page-hero, `pc` cards, sharp corners, Material
   Icons, HTMX-boosted sidebar.
4. **Forms are visual only.** Work Portals POST to a dummy success route or flip
   a visual state; they don't persist.
5. **F5 rule still holds.** Every mock page must render on a full reload.

## Key naming/concept shifts (old → new)

| Old concept | New concept | Notes |
| :--- | :--- | :--- |
| Major Location (access control) | **Data Domain** | List filters & detail "location" card become **domain** |
| `MakeModel` (make + model in one row) | `AssetModel` + `Manufacturer` (M2M) | Manufacturer is its own resource now |
| "Asset Type" (`/asset-types`) | **Asset Class** (`/assets/classes/`) | Same entity, clearer name |
| Asset/Model **Details** (hard-linked tables) | **Plugins** (Phase 2 framework) | Detail tables → per-plugin cards. UI illustrative only |
| Capabilities / Configurations | Same, ported | Phases 4 / 3 |

## Documents in this kit

| Doc | Purpose |
| :--- | :--- |
| [initial_prompt.md](initial_prompt.md) | Verbatim request that started this kit |
| [page_inventory.md](page_inventory.md) | **Every page**, classified (User View / Work Portal / Navigation) + goal |
| [route_map.md](route_map.md) | **The headline deliverable** — new route ↔ old analog ↔ model ↔ mock data |
| [navigation_flow.md](navigation_flow.md) | Sidebar structure, click-flow, and the Asset-360 card anatomy |
| [mock_data_shapes.md](mock_data_shapes.md) | Hard-coded data dicts per model (the fixture shapes) |
| [build_plan.md](build_plan.md) | Phased build order for the mock (mirrors the control kit phases) |

## Review checkpoint

**Nothing is built yet.** Review `route_map.md` + `navigation_flow.md` +
`page_inventory.md` first. Once the page set and flow are approved, building
proceeds per `build_plan.md`.
</content>
</invoke>
