# Legacy Maintenance Route Inventory

Complete HTTP surface of the legacy Flask maintenance module, harvested from
`/home/cb/REPOS/asset_management/app/presentation/routes/maintenance/` and its
blueprint registrations in `app/presentation/routes/__init__.py`.

Production host prefix on the live system is `https://ebamscore.com`. Every path
below is reproducible locally at `http://127.0.0.1:5000` (see
[README.md](README.md) for how to run the legacy app).

## Blueprint prefixes

| Blueprint | Source | URL prefix |
| :--- | :--- | :--- |
| `maintenance` | `main.py` | `/maintenance` |
| `maintenance_event_view` | `core/view_portal.py` | `/maintenance/maintenance-event` |
| `maintenance_event_edit` | `core/edit_portal.py` | `/maintenance/maintenance-event` |
| `maintenance_event_work` | `core/work_portal.py` | `/maintenance/maintenance-event` |
| `maintenance_event_assign` | `core/assign_portal.py` | `/maintenance/maintenance-event` |
| `maintenance_event_mgmt` | `core/maintenance_management.py` | `/maintenance/maintenance-event` |
| `manager_portal` | `user_views/manager/main.py` | `/maintenance/manager` |
| `technician_portal` | `user_views/technician/main.py` | `/maintenance/technician` |
| `fleet_portal` | `user_views/fleet/fleet.py` | `/maintenance/fleet` |
| `maintenance_plan` | `planning/maintenance_plan_routes.py` | `/maintenance` (registered with prefix) |
| `proto_action_portal` | `proto_action_portal.py` | `/maintenance/proto-actions` |
| `action_creator_portal` | `action_creator_portal.py` | `/maintenance/action-creator-portal` |
| `template_builder` | `templates/template_builder.py` | `/maintenance/manager/template-builder` |
| `maintenance_searchutils` | `search_utils.py` | `/maintenance/searchutils` |

Five blueprints listed in `routes/__init__.py` (`maintenance_plans`,
`maintenance_action_sets`, `actions`, `part_demands`, `blockers`,
`template_actions`, `proto_action_items`, `template_part_demands`,
`template_action_tools`) fail to import — the modules do not exist. They are
dead registrations, **not** part of the surface to port. Templates exist for
some of them under `templates/maintenance/maintenance_templates/*/list.html` and
`detail.html` but are unreachable.

---

## 1. Hub and shared pages (`main.py`)

| Method | Path | Purpose | Screenshot |
| :--- | :--- | :--- | :--- |
| GET | `/maintenance/` , `/maintenance/index` | Portal chooser hub — role card grid + overview stats | `00_maintenance_index.png` |
| GET | `/maintenance/view-events` | Cross-role maintenance event ledger with filters | `25_view_events.png` |
| GET | `/maintenance/view-templates` | Procedure template library (read-only browse) | `11_view_templates.png` |
| GET | `/maintenance/maintenance-template/<id>` , `/view` | Procedure template detail | `09_maintenance_template_2_view.png`, `10_…_1_view.png` |
| POST | `/maintenance/maintenance-template/<id>/active_status` | Activate / deactivate a template | — |
| GET | `/maintenance/proto-actions/<id>` , `/view` | Proto action detail | `13_proto_action_1_view.png`, `42_proto_action_4_view.png` |
| GET | `/maintenance/widgets/limitations/<asset_id>` | HTMX fragment: active asset limitations | — |
| GET | `/maintenance/widgets/blockers/<asset_id>` | HTMX fragment: active blockers | — |
| GET | `/maintenance/event-components/<slug>/full/<event_id>` | HTMX fragment: embeddable event card | — |
| GET | `/maintenance/event-components/<slug>/goto_button/<event_id>` | HTMX fragment: "go to event" button | — |

## 2. Manager portal (`user_views/manager/`)

| Method | Path | Purpose | Screenshot |
| :--- | :--- | :--- | :--- |
| GET | `/maintenance/manager/` , `/dashboard` | Manager landing — 4 stat tiles + 4 workflow cards | `01_manager_dashboard.png` |
| GET | `/maintenance/manager/part-demands` | **Part demand approval portal** — filters, table, bulk actions | `02_manager_part_demands.png` |
| POST | `/maintenance/manager/part-demands/approve` | Approve one demand | — |
| POST | `/maintenance/manager/part-demands/reject` | Reject one demand | — |
| POST | `/maintenance/manager/part-demands/bulk-approve` | Approve checked demands | — |
| POST | `/maintenance/manager/part-demands/bulk-reject` | Reject checked demands | — |
| POST | `/maintenance/manager/part-demands/bulk-change-part` | Substitute the part on checked demands | — |
| GET | `/maintenance/manager/create-assign` | **Create & assign portal** — 3-searchbar create card | `05_manager_create_assign.png` |
| GET/POST | `/maintenance/manager/create-assign/create` | Create+assign submit (GET redirects to portal) | `06_…_create.png` (redirect) |
| GET | `/maintenance/manager/create-assign/unassigned` | Unassigned event queue + bulk assign | `07_…_unassigned.png` |
| POST | `/maintenance/manager/create-assign/unassigned/bulk-assign` | Assign checked events to one technician | — |
| GET | `/maintenance/manager/create-assign/search-bars/templates` | HTMX searchbar results — templates | — |
| GET | `/maintenance/manager/create-assign/search-bars/assets` | HTMX searchbar results — assets | — |
| GET | `/maintenance/manager/create-assign/search-bars/assignment` | HTMX searchbar results — technicians (+ active load) | — |
| GET | `/maintenance/manager/create-assign/api/template/<id>/summary` | JSON template summary for the preview panel | — |
| GET | `/maintenance/manager/build-maintenance-templates` | **Template build hub** — 4 entry buttons, filters, list+preview | `08_manager_build_maintenance_templates.png` |
| GET | `/maintenance/manager/view-maintenance` | Legacy manager event ledger | `22_manager_view_maintenance.png` |
| GET | `/maintenance/manager/plan-maintenance` | Plan-maintenance landing | `23_manager_plan_maintenance.png` |
| GET | `/maintenance/manager/assign-monitor` | Assign & monitor landing | `24_manager_assign_monitor.png` |

## 3. Technician portal (`user_views/technician/main.py`)

| Method | Path | Purpose | Screenshot |
| :--- | :--- | :--- | :--- |
| GET | `/maintenance/technician/` , `/dashboard` | **Technician dashboard** — 3 stat tiles, asset lookup, assigned/recent/planned cards | `20_technician_dashboard.png` |
| GET | `/maintenance/technician/most-recent-event` | Jump to the technician's latest event (redirects) | `39_…` (redirect) |
| GET | `/maintenance/technician/continue-discussion` | Resume the last discussion thread | — |

Templates `action_detail.html`, `add_delay.html`, `delays.html`, `history.html`,
`request_parts.html`, `work_detail.html` exist under
`templates/maintenance/user_views/technician/` but **have no routes** — dead code.

## 4. Fleet / admin portal (`user_views/fleet/fleet.py`)

| Method | Path | Purpose | Screenshot |
| :--- | :--- | :--- | :--- |
| GET | `/maintenance/fleet/` , `/dashboard` | 4 stat tiles + "will be implemented here" placeholder | `21_fleet_dashboard.png` |

This portal is a **stub**. Only the stat tiles are real.

## 5. Maintenance event portals (`core/`)

| Method | Path | Purpose | Screenshot |
| :--- | :--- | :--- | :--- |
| GET | `/maintenance/maintenance-event/<event_id>` , `/`, `/view` | Read-only event detail | `26_event_21_view.png`, `30_event_22_view.png` |
| GET | `/maintenance/maintenance-event/<event_id>/edit` | Edit portal — metadata + action editor + action creator portal | `27_event_21_edit.png`, `36_event_22_edit.png` |
| POST | `/maintenance/maintenance-event/<event_id>/edit` | Save edit portal | — |
| GET | `/maintenance/maintenance-event/<event_id>/work` | Work portal — perform maintenance | `28_event_21_work.png`, `37_event_22_work.png` |
| GET/POST | `/maintenance/maintenance-event/<event_id>/assign` | Assign portal — pick technician | `29_event_21_assign.png`, `38_event_22_assign.png` |
| POST | `/maintenance/maintenance-event/<event_id>/complete` | Complete the event | — |
| POST | `/maintenance/maintenance-event/<event_id>/update-datetime` | Reschedule | — |
| POST | `/maintenance/maintenance-event/<event_id>/update-billable-hours` | Set event billable hours | — |
| POST | `/maintenance/maintenance-event/<event_id>/blocker/create` | Raise a work blocker | — |
| POST | `/maintenance/maintenance-event/<event_id>/limitation/create` | Raise an asset limitation | — |
| POST | `/maintenance/maintenance-event/<event_id>/create-blank-action` | Add empty action step | — |
| POST | `/maintenance/maintenance-event/<event_id>/create-from-proto-action` | Add step from proto action | — |
| POST | `/maintenance/maintenance-event/<event_id>/create-from-template-action` | Add step from template action | — |
| POST | `/maintenance/maintenance-event/<event_id>/create-from-current-action` | Clone an existing step | — |
| GET | `/maintenance/maintenance-event/static/js/edit_maintenance.js` | Route-served JS asset | — |

### Action-scoped operations (`core/action_managment.py`, `tool.py`)

All under `/maintenance`, all POST, all keyed by `action_id` (not event):

`action/create` · `action/<id>/update` · `action/<id>/update-status` ·
`action/<id>/update-billable-hours` · `action/<id>/delete` · `action/<id>/move-up` ·
`action/<id>/move-down` · `action/<id>/part-demand/create` · `action/<id>/tool/create` ·
`action/<id>/tool/<tool_id>/update` · `action/<id>/tool/<tool_id>/delete`

### Part demand operations (`core/part_demand.py`)

| Method | Path | Purpose | Screenshot |
| :--- | :--- | :--- | :--- |
| GET | `/maintenance/part-demand/<id>` , `/part_demand/<id>/view` | **Part demand detail** | `03_part_demand_1_view.png`, `04_…_3_view.png`, `43_…_4_view.png` |
| POST | `/maintenance/part-demand/<id>/manager-approve` | Maintenance-side approval | — |
| POST | `/maintenance/part-demand/<id>/manager-reject` | Maintenance-side rejection | — |
| POST | `/maintenance/part-demand/<id>/issue` | Issue parts | — |
| POST | `/maintenance/part-demand/<id>/update-issue` | Amend an issue | — |
| POST | `/maintenance/part-demand/<id>/cancel` | Cancel demand | — |
| POST | `/maintenance/part-demand/<id>/undo` | Undo last state change | — |
| POST | `/maintenance/part-demand/<id>/update` | Edit quantity / priority / notes | — |

Note the **two URL spellings**: `part-demand` (hyphen) for the action verbs and
`part_demand` (underscore) for the `…/view` alias. The user's reported URL
`https://ebamscore.com/maintenance/part_demand/1/view` uses the underscore form.

### Blocker and limitation operations

| Method | Path | Purpose |
| :--- | :--- | :--- |
| POST | `/maintenance/blocked_status/<id>/end` | End a blocker |
| POST | `/maintenance/blocked_status/<id>/update` | Edit a blocker |
| POST | `/maintenance/limitation/<id>/close` | Close an asset limitation |

## 6. Proto action library (`proto_action_portal.py`)

| Method | Path | Purpose | Screenshot |
| :--- | :--- | :--- | :--- |
| GET | `/maintenance/proto-actions/` , `/list` | Proto action card grid + search/sort | `12_proto_actions_list.png` |
| GET/POST | `/maintenance/proto-actions/create` | Create proto action (2-column form + parts/tools repeaters) | `14_proto_action_create.png` |
| GET | `/maintenance/proto-actions/<id>/view` | Proto action detail (via `main.py`) | `13_proto_action_1_view.png` |

## 7. Action creator portal (`action_creator_portal.py`)

| Method | Path | Purpose | Screenshot |
| :--- | :--- | :--- | :--- |
| GET | `/maintenance/action-creator-portal/<maintenance_action_set_id>` | Standalone 5-tab action creator | `33_action_creator_portal_set1.png` |
| GET | `/maintenance/action-creator-portal/search-template-action-sets` | HTMX tab results | — |
| GET | `/maintenance/action-creator-portal/search-template-actions` | HTMX tab results | — |
| GET | `/maintenance/action-creator-portal/search-proto-actions` | HTMX tab results | — |
| GET | `/maintenance/action-creator-portal/list-template-action-items/<set_id>` | HTMX drill-down list | — |

The same portal is embedded (identical tab set, different POST targets) in the
event edit portal and the template builder.

## 8. Template builder (`templates/template_builder.py`)

Prefix `/maintenance/manager/template-builder`.

| Method | Path | Purpose | Screenshot |
| :--- | :--- | :--- | :--- |
| GET | `/new` | Create a builder row and redirect to `/<builder_id>` | `32_template_builder_new.png` |
| GET | `/<builder_id>` | **Builder edit page** — metadata card, summary, attachments, action editor panel, embedded action creator portal | `34_template_builder_1_edit.png` |
| GET | `/drafts` | Draft list | `31_template_builder_drafts.png` |
| GET | `/<builder_id>/already-submitted` | Guard page for a committed builder | — |
| GET | `/<builder_id>/action-creator-portal` | Embedded action creator portal fragment | `35_template_builder_1_action_creator.png` |
| GET | `/<builder_id>/actions-list` | HTMX action sidebar |  — |
| GET | `/<builder_id>/get-action-dict/<action_index>` | JSON for the action form | — |
| POST | `/<builder_id>/metadata` | Save metadata card | — |
| POST | `/<builder_id>/add-blank-action` | Add empty action | — |
| POST | `/<builder_id>/add-action-from-proto/<proto_id>` | Add from proto action | — |
| POST | `/<builder_id>/add-action-from-template-action/<template_action_id>` | Add from template action | — |
| POST | `/<builder_id>/add-action-from-json` | Add from a JSON blob | — |
| POST/PUT | `/<builder_id>/action/add` | Add action (form) | — |
| POST | `/<builder_id>/action/<idx>/update` | Update action at index | — |
| POST | `/<builder_id>/action/<idx>/delete` | Delete action at index | — |
| POST | `/<builder_id>/action/<idx>/move` | Reorder action | — |
| POST | `/<builder_id>/action/<idx>/part/add` | Add part requirement | — |
| POST | `/<builder_id>/action/<idx>/part/<pidx>/update` , `/delete` | Edit / remove part requirement | — |
| POST | `/<builder_id>/action/<idx>/tool/add` | Add tool requirement | — |
| POST | `/<builder_id>/action/<idx>/tool/<tidx>/update` , `/delete` | Edit / remove tool requirement | — |
| POST | `/<builder_id>/attachment/upload` | Upload attachment | — |
| POST | `/<builder_id>/attachment/add-from-library` | Attach from technical library | — |
| POST | `/<builder_id>/attachment/<idx>/remove` | Remove attachment | — |
| POST | `/<builder_id>/submit` | **Commit builder → real `TemplateActionSet`** | — |
| POST | `/<builder_id>/delete` | Discard builder | — |
| GET | `/search-template-action-sets` , `/search-template-actions` , `/search-proto-actions` , `/list-template-action-items/<id>` | Embedded action creator HTMX endpoints | — |

Every `<builder_id>`-keyed route is what the EBAMS-2 port replaces with
`request.session['template_builder_draft']` (see decision 6 in
[../porting_mapping_plan.md](../porting_mapping_plan.md)). The **indices**
(`action_index`, `part_index`, `tool_index`) are the important shape to carry
over: the legacy builder addresses draft children positionally, not by PK.

## 9. Maintenance plans (`planning/maintenance_plan_routes.py`)

| Method | Path | Purpose | Screenshot |
| :--- | :--- | :--- | :--- |
| GET | `/maintenance/manager/maintenance-plans` | Plan list table | `15_manager_maintenance_plans.png` |
| GET | `/maintenance/maintenance-plan/<id>/view` | **Plan detail** — plan info + frequency config + template action set expansion | `16_maintenance_plan_3_view.png`, `40_…_1_view.png` |
| GET/POST | `/maintenance/maintenance-plan/create` | **Create plan** — single card, 3 fieldsets | `17_maintenance_plan_create.png` |
| GET/POST | `/maintenance/maintenance-plan/<id>/edit` | Edit plan | `18_maintenance_plan_3_edit.png` |
| GET | `/maintenance/maintenance-plan/<id>/plan` | **Plan Maintenance** — assets needing maintenance under this plan | `19_maintenance_plan_3_plan.png`, `41_…_1_plan.png` |
| POST | `/maintenance/maintenance-plan/<id>/create-event` | Generate an event for a due asset | — |
| GET | `/maintenance/search-template-action-sets` | HTMX template searchbar for the plan form | — |
| GET | `/maintenance/preview-template-action-set/<id>` | HTMX template preview panel | — |

## 10. Search utilities (`search_utils.py`)

| Method | Path | Purpose |
| :--- | :--- | :--- |
| GET | `/maintenance/searchutils/template-action-set` | Shared template searchbar results |
| GET | `/maintenance/searchutils/proto-action` | Shared proto action searchbar results |
