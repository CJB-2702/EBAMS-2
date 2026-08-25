# Gap Analysis: Legacy Maintenance UI vs Current EBAMS-2 Port

Every gap the user reported, verified against the code, plus the ones the
verification turned up. Legacy anatomy is in [page_catalog.md](page_catalog.md);
legacy sequences are in [ui_workflows.md](ui_workflows.md).

## What EBAMS-2 has today

`app/maintenance/urls.py` — 12 routes:

```
events · events/create · event/<pk>
event/<id>/actions · action/<id> · action/<id>/reorder
templates · template/<pk>
templates/builder · templates/builder/update · templates/builder/commit
proto-actions · proto-actions/create
plans · plans/create · plan/<pk>
```

`app/maintenance/templates/maintenance/` — index, create, detail, template_index,
template_detail, template_builder, proto/{index,create}, planning/{index,detail,create},
and five components.

Nav (`app/public_app/templates/shared/topnav.html`, Maintenance popover) — three
groups: **Work** (All Maintenance Events, New Maintenance Event), **Planning**
(Recurring Plans), **Library** (Procedure Templates, Proto Actions). Five links.

The control layer, by contrast, is largely ported already — `MaintenanceContext`,
`ActionContext`, `PartDemandManager`, `MaintenanceAssignmentManager`,
`MaintenanceBlockerManager`, `AssetLimitationManager`, `BillableHoursManager`,
`MaintenancePlanner`, `MaintenancePlanContext`, `ActionFactory`,
`MaintenanceFactory`, `TemplateBuilderSessionAdapter` and a completion guard all
exist. **The gap is almost entirely presentation-layer.** Most of what follows is
templates, entrypoints and URLs over control code that is already written.

---

## 1. Part demand portal and detail — not built, not in nav

**Reported:** *"Pages I am not seeing in the sidenav bar — maintenance facing
demand portal … /maintenance/manager/part-demands … /maintenance/part_demand/1/view
+ actions"*

**Verified:** no route, no template, no nav entry. `PartDemandManager` exists in
the control layer, so the write side is available.

Missing:

| Legacy | What to build |
| :--- | :--- | 
| `/manager/part-demands` (`02_manager_part_demands.png`) | Approval queue: 3+4 filter grid, collapsed *Maintenance Event Filters* tier, sort, 13-column table with select-all, per-row eye/approve/reject |
| `bulk-approve`, `bulk-reject`, **`bulk-change-part`** | Bulk endpoints over the checked set. `bulk-change-part` (substitute the part across many demands) has no equivalent anywhere in EBAMS-2 |
| `/part_demand/<id>/view` (`03_…`, `04_…`, `43_…`) | Detail page: status banner, Part Information, **Maintenance Context** (with its two explicit italic empty states), **Workflow Information** with the *two independent gates* — Maintenance Approval and Supply Approval |
| `manager-approve`, `manager-reject`, `issue`, `update-issue`, `cancel`, `undo`, `update` | Seven POST verbs |
| Work-portal *Part Demand Manager Approval* card | Second approval surface, in-page on the event |

**Watch:** the queue carries demands from **dispatching** too (they show `N/A` in
the event / asset / location columns). Scope this against
`procurement.PartDemand` via `MaintenanceDemandLink`, not by assuming every row
has a maintenance parent.

**Nav:** add a **Parts** group to the Maintenance popover.

## 2. Create & assign portal — not built

**Reported:** *"there is no create and assign portal"*

**Verified:** `maintenance_create` + `create.html` exist, but they are a plain
create form. The legacy portal is a different thing.

Missing:

| Legacy | What to build |
| :--- | :--- |
| `/manager/create-assign` (`05_…`) | One card, three stacked **live search dropdowns** — Template, Asset, Technician — plus a Quick Actions card and a Help card |
| Technician picker showing `N active` | Load-aware assignment. `MaintenanceAssignmentManager` exists; the UI does not |
| `api/template/<id>/summary` | Template preview on selection |
| `/create-assign/unassigned` (`07_…`) | Unassigned queue: asset-class/status/priority filters, select-all table, **Bulk Assign** card with a technician dropdown + shared notes |
| `unassigned/bulk-assign` | Bulk assignment endpoint |
| `/maintenance-event/<id>/assign` (`29_…`, `38_…`) | Single-event reassign page — the path the Help card sends users to |

Per [harness/UX_UI/design_patterns/modals.md](../../harness/UX_UI/design_patterns/modals.md),
assignment must **not** go in a modal; the legacy in-page card pair is already the
right shape.

## 3. Template pages — layout and features not captured

**Reported:** *"view templates pages both did not adequately capture the layout
and features of their pages"* — `/maintenance-template/2/view` and
`/manager/build-maintenance-templates`.

**Template detail** (`09_…`, `10_…`) — EBAMS-2 `template_detail.html` is missing:

- the 4 stat tiles (Status, Revision, Action Items, Parts Required);
- the 2-column *Template Details* grid (staff count, parts cost, labor hours,
  **Safety Review Required** pill, asset class, make/model);
- per action step: the `🕐 Est / ▭ Billable / 👥 Staff` metric strip, the
  **yellow safety-notes callout**, the grey **Tools Required** sub-panel with
  quantity pills, and the parts sub-panel;
- right column: *Template Information*, *Summary* (note **Total Estimated
  Duration** rolls the steps up to `1.33h` while the header's labor hours reads
  `0.75` — two different numbers, both shown), *All Parts Required*,
  ***All Tools Required* with the owning action named per row**, *Attachments*;
- the **Deactivate** header action (`active_status`);
- the advisory callout recommending proto-action linkage.

**Build hub** (`08_…`) — **no equivalent page exists at all.** It is the single
entry point to five creation paths:

1. Create New Template from Scratch
2. **New Template from Existing** (copy)
3. **New Revision of Existing Template** (revision chain — `prior_revision_id`,
   bumped `revision`)
4. View your drafts
5. Create Proto Action / View All Proto Actions

Plus a 4-field filter row and a **two-pane list + HTMX preview** picker. Items 2
and 3 are distinct semantics and neither exists in EBAMS-2.

## 4. Proto actions — only the middle tier was ported

**Reported:** *"there is no reference of proto actions just template actions.
copy over these items"*

Full treatment in [proto_vs_template_actions.md](proto_vs_template_actions.md).
Short form — missing: **proto detail route + page** (including the *Referenced By
Template Action Items* reverse-reference card), the **From Proto Action** tab in
the action source picker, the proto search endpoints, the proto badges and
instruction-text search on the list page, and a decision on proto attachments and
proto revisioning.

## 5. Maintenance plan pages — wrong shape

**Reported:** *"the maintenance plans page looks nothing like the old page"* —
`/maintenance-plan/3/view` and `/maintenance-plan/create`.

**Plan detail** (`16_…`, `40_…`) is missing:

- the ID-plus-label rendering convention (`Asset Class ID: 1 (Vehicle)`,
  `Template Action Set ID: 2 (Brake Inspection Procedure)`);
- **`Delta Meter 1` through `Delta Meter 4`**, each shown with `-` when unset —
  four meter thresholds, not one;
- the full-width **"Template Action Set: `<name>`"** card that expands the linked
  template inline as a step table;
- the header actions **Plan Maintenance** and **Edit Plan**.

**Plan create** (`17_…`) is missing:

- the three hairline-separated fieldsets (Basic Information / Maintenance
  Template / Frequency Configuration);
- the **click-to-search** template picker (input + Search button + selectable
  result list with `N actions` pills) — deliberately *not* a live dropdown;
- the "Leave blank to apply to all models of the selected asset type." helper;
- conditional reveal of delta fields by frequency type;
- submit disabled until valid.

**Missing outright:** `/maintenance-plan/<id>/edit` and
**`/maintenance-plan/<id>/plan`** (`19_…`, `41_…`) — the *Assets Needing
Maintenance* worklist with per-asset `create-event`. `MaintenancePlanner` and
`MaintenancePlanContext` are already ported; only the page is absent.

## 6. Technician view — not built

**Reported:** *"there is no technician view page"* — `/maintenance/technician/dashboard`

**Verified:** no route, no template, no nav entry.

Missing (`20_technician_dashboard.png`): three counters (Assigned Work, In
Progress, Completed Today), **Quick Asset Lookup**, the **disabled**
*View Events by Your Location* tile with its "Complete an event to see
location-based events" explanation, an Event Viewer link, and three list cards
with **View All** — *Assigned Events*, *Recently Interacted With*,
*Planned This Week*. Plus `most-recent-event` (jump to latest) and
`continue-discussion`.

**Also missing: the work portal itself.** `28_event_21_work.png` is the
technician's actual screen and EBAMS-2 has no `/work` route — no progress bar,
no per-step Start / Edit / Add Part stack, no per-step parts panel with
Issue / edit / Cancel, no **Mark Complete** / **Place in Blocked Status** /
**Add Capability Limitation** buttons, no Event Activity tabs. This is the single
largest missing page in the port; the completion guard, blocker manager and
limitation manager it needs are all already written.

The legacy technician templates `action_detail.html`, `add_delay.html`,
`delays.html`, `history.html`, `request_parts.html`, `work_detail.html` are
**dead** — no routes reference them. Do not port them.

## 7. Merged index: manager + technician + fleet into one hub

**Requested:** *"pages I want to merge manager technician and admin portals into
the index home"*

The legacy hub (`00_maintenance_index.png`) is a **role chooser** — three cards
that each navigate to a dashboard. Merging means the four screens
(`00_`, `01_`, `20_`, `21_`) collapse into one page. Recommended composition:

1. **Page header** — "Maintenance" + subtitle. No role chooser.
2. **One stat strip** — the union of all four screens, deduplicated:
   Total Events · Active Maintenance · Planned · Completed ·
   **Pending Part Demands** · Active Templates · Assets Due · Overdue.
   (Fleet contributes only Assets Due and Overdue; its page body was a "will be
   implemented here" placeholder and should not be ported.)
3. **"My Work" band** — the technician content, shown to any user with assigned
   work: Assigned Work / In Progress / Completed Today counters, *Assigned
   Events*, *Planned This Week*, *Recently Interacted With*, Quick Asset Lookup.
4. **"Manage" band** — the four manager workflow cards: Create & Assign ·
   Part Demands · Build Templates (button cluster: View Templates, Build
   Templates, View Proto Actions, Create Proto Action) · Plan Maintenance.
5. **Ledger link** — one prominent link to the event list.

Decisions to make before building:

- **Visibility.** Legacy gated by portal choice, not permission. In EBAMS-2 the
  bands should be permission-driven. `presentation_layer/tools/maintenance_access.py`
  already exists — check whether it can drive band visibility as-is.
- **Empty bands.** Rule #5 says a card renders even when empty. A whole *band*
  belonging to a role the user does not hold is the "feature doesn't apply"
  exception — omit it. An empty *card* inside a band the user does hold renders
  with "None."
- **Drop:** the Fleet placeholder body, the three role-chooser cards, the muted
  "Legacy View Maintenance" button, and the two "Debug:" buttons on the template
  builder.
- **Nav consequence:** with the portals merged, the Maintenance popover should
  gain **Parts** (Part Demand Queue) and **Work** entries (Create & Assign,
  Unassigned Events) and keep one Dashboard link to the merged index.

## 8. Template builder under session memory

Not user-reported; a consequence of decision 6 in
[../porting_mapping_plan.md](../porting_mapping_plan.md).

`template_builder.html` and the three builder routes exist. Against the legacy
builder (`34_template_builder_1_edit.png`, 30 routes) verify:

- **Positional addressing.** Legacy addresses draft children by
  `action_index` / `part_index` / `tool_index` because nothing has a PK before
  commit. `TemplateBuilderSessionAdapter` must keep that shape.
- **The commit banner** sits at the **top** of the page, above the form, always
  visible.
- **Builder Summary** card — status, build type, total actions.
- **Attachments** — upload *and* "Select from Technical Library", staged in
  session and converted to `events.Attachment` on commit only.
- **The three-pane Action Editor Panel** — list / form / children.
- **The five-tab Action Creator Portal** at the bottom.
- **`/drafts` collapses.** One session, one draft: "Resume your draft" plus
  "Discard". Decide what happens when a manager wants two drafts at once — this
  is a genuine capability regression from the DB-backed builder and should be an
  explicit, recorded choice, not an accident.
- **`already-submitted` guard** — revisiting a committed draft.
- Do **not** port the two "Debug:" buttons.

## 9. Event edit portal and the action creator portal

`action_create` / `action_update` / `action_reorder` exist as endpoints, but there
is no edit-portal page (`27_event_21_edit.png`, `36_event_22_edit.png`) — no
metadata form, no limitations card, no blockers card, no three-pane action editor,
and no five-source action picker for live events (`create-blank-action`,
`create-from-proto-action`, `create-from-template-action`,
`create-from-current-action`).

The **Action Creator Portal** is the same component in three hosts — template
builder, event edit portal, and standalone. Build it once as a reusable partial
parameterised by POST target.

## 10. Duplicate ledgers and vestigial landings — do not port

Legacy has four overlapping list/landing pages: `/view-events` (`25_…`),
`/manager/view-maintenance` (`22_…`, already labelled "Legacy" by the previous
author), `/manager/plan-maintenance` (`23_…`) and `/manager/assign-monitor`
(`24_…`). Port **one** ledger — EBAMS-2's existing `maintenance_index` — and drop
the rest; `plan-maintenance` and `assign-monitor` are thin landings whose jobs are
done better by the plan list and the create-assign portal.

Also dead in the legacy app and not to be ported: the nine failed blueprint
registrations in `routes/__init__.py` and their orphaned CRUD templates under
`templates/maintenance/maintenance_templates/*/`, and the six routeless
technician templates.

---

## Missing-surface summary

| # | Surface | Route | Template | Control layer ready? |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Part demand approval queue | ✗ | ✗ | ✓ `PartDemandManager` |
| 2 | Part demand detail + 7 verbs | ✗ | ✗ | ✓ |
| 3 | Create & assign portal | ✗ | ✗ | ✓ `MaintenanceAssignmentManager` |
| 4 | Unassigned queue + bulk assign | ✗ | ✗ | ✓ |
| 5 | Single-event assign page | ✗ | ✗ | ✓ |
| 6 | Build-templates hub (5 paths) | ✗ | ✗ | ✓ `TemplateMaintenanceContext` |
| 7 | Template detail — full anatomy | ✓ | partial | ✓ |
| 8 | Proto action detail + reverse refs | ✗ | ✗ | — |
| 9 | Action Creator Portal (5 tabs, 3 hosts) | ✗ | ✗ | ✓ `ActionFactory` |
| 10 | Plan detail — full anatomy | ✓ | partial | ✓ |
| 11 | Plan create — 3 fieldsets, click-to-search | ✓ | partial | ✓ |
| 12 | Plan edit | ✗ | ✗ | ✓ |
| 13 | Plan → assets-needing-maintenance worklist | ✗ | ✗ | ✓ `MaintenancePlanner` |
| 14 | **Event work portal** | ✗ | ✗ | ✓ + completion guard |
| 15 | Event edit portal | partial | ✗ | ✓ |
| 16 | Technician dashboard | ✗ | ✗ | ✓ |
| 17 | Merged index hub | ✓ | needs rebuild | ✓ `maintenance_access` |
| 18 | Blocker / limitation UI + asset widgets | ✗ | ✗ | ✓ both managers |
| 19 | Embeddable event fragments | ✗ | ✗ | ✓ |
