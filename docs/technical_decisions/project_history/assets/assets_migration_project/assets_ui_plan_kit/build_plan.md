# Build Plan — Mock App

Order of construction **after** the route map / flow is approved. Mirrors the
control-kit phases so the mock and the real build stay aligned. Each step is
visually verifiable at `localhost/assets`.

## Wiring (once, before any page)

1. Add app to routing: `path("assets/", include("app.assets.urls"))` in
   [`app/config/urls.py`](../app/config/urls.py).
2. Create `app/assets/urls.py` and
   `app/assets/presentation_layer/{__init__,entrypoints,mock_data}.py`.
3. Create `app/assets/templates/assets/asset_base.html` — clone of
   [`ev_base.html`](../app/events/templates/events/ev_base.html) with the
   sidebar from [navigation_flow.md](navigation_flow.md#sidebar-structure) and
   `current_app_group="Assets"`.
4. Confirm `assets` is in `INSTALLED_APPS` and template discovery finds the new
   folder. Add an "Assets" entry to `shared/topnav.html` if needed.

> All entrypoints are plain functions returning `render(...)` with dicts pulled
> from `mock_data.py`. No `@login_not_required` (stays inside the authed app).

## Step 0 — Shell + Dashboard
- `asset_base.html`, `asset_dashboard` page with rollup tiles + recent assets +
  quick links. **Checkpoint:** sidebar nav + hero render in app style.

## Step 1 — Core (Phase 1)
Build list → detail → create/edit for each, reusing one list pattern and one
detail pattern:
- Assets (list, 360 detail, create, edit, images)
- Asset Models (list, detail, create, edit)
- Asset Classes (list, detail, create, edit)
- Manufacturers (list, detail, create, edit)
- Meter History (list)

**Checkpoint:** the main loop (Flow A) and catalog loop (Flow B) click through
end-to-end on hard-coded data. This is the bulk of the "feel".

## Step 2 — Capabilities (Phase 4)
- Definitions list + form; the three assignment hubs (by-class/model/asset).
- Add the **resolved Capabilities card** to Asset/Model/Class detail pages.

**Checkpoint:** Flow C clicks through; capability cards populate.

## Step 3 — Configurations (Phase 3)
- Templates list + builder + detail; Defined Modifications list + detail/edit.
- Asset Configuration view + edit; add **Current Configuration card** to 360.

**Checkpoint:** Flow D clicks through.

## Done = reviewable

When all three steps render, the mock conveys the full shape of the new assets
app without a line of control-layer or ORM code. Feedback then feeds the real
build (control kit + a future real-UI kit).

## Guardrails

- **No DB / ORM / control layer.** If a page "needs" a query, hard-code it.
- **Match the events app exactly** for shell, cards (`pc`), buttons, tags,
  sharp corners, Material Icons.
- **F5 rule** on every page.
- Keep all mock data in `mock_data.py` so shapes are reviewable in one place.
- Don't touch real `app/assets/models/` or migrations — this is presentation
  only.
</content>
