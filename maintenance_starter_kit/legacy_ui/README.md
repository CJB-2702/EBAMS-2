# Legacy Maintenance UI Capture

A faithful record of the **legacy Flask maintenance UI** — every route, every
page's layout and features, every workflow — captured so the EBAMS-2 port can be
checked against what actually existed rather than against memory.

Produced 2026-08-17 in response to the reported gaps: missing part-demand portal,
missing create & assign portal, template and plan pages that didn't match, no
proto actions, no technician view, and the request to merge the manager /
technician / fleet portals into the index.

## Documents

| Document | What it answers |
| :--- | :--- |
| [route_inventory.md](route_inventory.md) | Every legacy HTTP route, its blueprint prefix, its purpose, and its screenshot. Includes which registrations are dead. |
| [page_catalog.md](page_catalog.md) | Per-page anatomy — chrome, cards in layout order, every control and its endpoint. 25 entries. |
| [ui_workflows.md](ui_workflows.md) | The nine end-to-end workflows with their sequences and gates, plus a table of cross-cutting UI mechanics. |
| [proto_vs_template_actions.md](proto_vs_template_actions.md) | The three action tiers (proto / template / live), what copies down between them, and what the port dropped. |
| [gap_analysis.md](gap_analysis.md) | Each reported gap verified against the code, the gaps verification turned up, the merged-index proposal, and a 19-row missing-surface table. |
| [screenshots/](screenshots/) | 44 full-page PNGs at 1600px wide, plus `_manifest.json` / `_manifest_batch2.json` recording each page's path, HTTP status, final URL, `<title>`, and a body-text excerpt. |

## Headline findings

- **The gap is almost entirely presentation-layer.** The control layer is largely
  ported already — every manager, context, factory, planner and guard the missing
  pages need exists in `app/maintenance/control_layer/`. What is missing is
  routes, entrypoints and templates.
- **19 surfaces are missing or thin.** The largest single omission is the
  **event work portal** (`/maintenance-event/<id>/work`) — the technician's main
  screen, and the busiest page in the legacy module.
- **Proto actions were ported as models but not as a UI.** No detail page, no
  reverse-reference card, and no "From Proto Action" tab, which is the only path
  by which a proto action reaches real work.
- **Some legacy pages should not be ported:** the Fleet portal body (a
  placeholder), three duplicate/vestigial event ledgers, nine dead blueprint
  registrations with orphaned templates, six routeless technician templates, and
  two "Debug:" buttons on the template builder.

## Reproducing the screenshots

The legacy app runs locally against its own committed SQLite database.

```bash
# 1. Back up the legacy DB first — the app seeds on boot and ./run calls z_clear_data.py
cp ~/REPOS/asset_management/instance/asset_management.db /tmp/old_db_backup.db

# 2. Start the legacy Flask app directly (NOT ./run, which wipes data)
cd ~/REPOS/asset_management
nohup ./venv/bin/python3 app.py > /tmp/oldapp.log 2>&1 &
# serves on http://127.0.0.1:5000 — FLASK_PORT in .env wins over the environment

# 3. Capture, from the ebams2 venv (playwright + chromium are installed there)
cd ~/REPOS/ebams2
./venv/bin/python maintenance_starter_kit/legacy_ui/capture_screenshots.py \
    maintenance_starter_kit/legacy_ui/screenshots
./venv/bin/python maintenance_starter_kit/legacy_ui/capture_screenshots_batch2.py \
    maintenance_starter_kit/legacy_ui/screenshots
```

Login is `admin` / `admin987654321!` (from `asset_management/.env`;
`ADMIN_USER_PASSWORD`). Every page in both scripts returned HTTP 200.

### Seed data the screenshots use

| Entity | IDs | Note |
| :--- | :--- | :--- |
| Maintenance events | `events.id` **21**, **22** | Event routes key on `events.id`, not `maintenance_action_sets.id` |
| Template action sets | 1 (Toyota Corolla Oil Change, 3 actions), 2 (Brake Inspection, 2 actions) | |
| Maintenance plans | 1, 2 (Corolla oil change — days / meter1), 3 (Truck Brake Inspection — days) | |
| Part demands | 1, 2 (dispatching-sourced, no event) · 3, 4 (maintenance, event 21) | The mix is deliberate — the approval queue shows both |
| Proto actions | 1–5 | |
| Template builder | builder 1, created by visiting `/new` during capture | |

### Known capture artifacts

- On `05_manager_create_assign.png` and `07_…_unassigned.png` the search
  dropdowns render **open and overlapping**, because they pre-populate on load.
  Live, only the focused one is open.
- `06_manager_create_assign_create.png` and
  `39_technician_most_recent_event.png` are **redirect landings** — `GET` on those
  routes bounces to the portal / dashboard. Kept for completeness.
- `/maintenance-event/<id>/edit` reports `<title>` "Action Creator Portal"; the
  legacy page inherits the embedded portal's title. That is a legacy bug, not a
  capture error.
