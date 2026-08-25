# Legacy Maintenance Page Catalog

Faithful, screenshot-backed anatomy of every legacy maintenance page. Each entry
gives the legacy URL, the captured screenshot, the page chrome, the cards in
layout order, and every action the page can fire.

Read this alongside [route_inventory.md](route_inventory.md) (the HTTP surface)
and [gap_analysis.md](gap_analysis.md) (what EBAMS-2 is missing).

**Shared page chrome on every page:** dark top navbar (`EBAMS` wordmark, hamburger,
portal tabs `Events · Dispatching · Maintenance · Inventory · Assets · Core`,
global searchbar with a scope dropdown, user menu), a page header with an icon +
title + one-line subtitle on the left and a "Back to …" button on the right, and
a footer with copyright plus `Help` / `About`. The legacy visual language is
rounded Bootstrap-ish cards with colored left accent bars and heavy use of
colored stat tiles.

---

## 1. Maintenance hub — portal chooser

- **URL:** `/maintenance/` , `/maintenance/index`
- **Screenshot:** `00_maintenance_index.png`
- **Title:** "Maintenance Portal" / "Choose your portal based on your role"

Layout, top to bottom:

1. **Centered hero** — crossed-tools icon + "Maintenance Portal" + subtitle.
2. **Full-width feature card** — calendar icon, "View Maintenance Events",
   "Browse and filter all maintenance events with comprehensive search,
   filtering, and enhanced data views.", full-width yellow **View Events Portal**
   button → `/maintenance/view-events`.
3. **Three equal role cards** in a row:
   - *Technician Portal* — "View assigned work, complete actions, request parts,
     and track your maintenance history." → blue **Go to Technician Portal**.
   - *Manager Portal* — "Create templates, manage plans, assign work to
     technicians, and approve part requests." → green **Go to Manager Portal**.
   - *Fleet/Admin Portal* — "Fleet-wide dashboard, analytics, comprehensive
     maintenance data views, and reporting." → cyan **Go to Fleet Portal**.
   Only the Manager and Fleet cards carry icons; the Technician card has none —
   an inconsistency, not a design choice.
4. **Maintenance Overview strip** — 4 inline counters: Total Events (blue),
   Completed (green), In Progress (yellow), Planned (cyan).

This is the page the user wants **merged** with the three portal dashboards.
See [gap_analysis.md § Merged index](gap_analysis.md#7-merged-index-manager--technician--fleet-into-one-hub).

---

## 2. Manager dashboard

- **URL:** `/maintenance/manager/dashboard`
- **Screenshot:** `01_manager_dashboard.png`
- **Title:** "Manager Portal" / "Plan, schedule, and manage maintenance operations"

1. **4 stat tiles:** Total Events, Active Maintenance, Pending Part Demands
   (yellow — the count that drives the approval queue), Active Templates.
2. **"Maintenance Workflows"** section label, then a 2×2 grid of workflow cards,
   each with a colored left accent bar, icon, title, description, and one or more
   buttons:
   - **Create & Assign** (green accent) — "Create maintenance events from
     templates and assign them to assets and technicians." → one green button.
   - **Part Demands** (yellow accent) — "View and approve part demands with
     filters and bulk actions for efficient management." → one yellow button.
   - **Build Maintenance Templates** (cyan accent) — five buttons:
     *View Templates*, *Build Templates*, *View Proto Actions*,
     *Create Proto Action*, and a muted *Legacy View Maintenance*.
   - **Plan Maintenance** (indigo accent) — "Create maintenance plans, schedule
     events, and manage assets due for maintenance." → one indigo button.

The Build card is the only card with a button cluster; it is the launchpad for
both the template library and the **proto action** library.

---

## 3. Part demand approval portal ⚠️ missing in EBAMS-2

- **URL:** `/maintenance/manager/part-demands`
- **Screenshot:** `02_manager_part_demands.png`
- **Title:** "Part Demand Approvals" / "Filter by approval status and approve or
  reject part demands for maintenance events"

1. **Filters card** (very wide, three rows):
   - Row 1: `Part ID` (text), `Part Description` (text), `Approval status`
     (select, default "All approval statuses").
   - Row 2: four date inputs — `Created From`, `Created To`,
     `Last Updated From`, `Last Updated To`.
   - Row 3: a **collapsed disclosure** "⚒ Maintenance Event Filters" — a second
     tier of filters scoped to the owning event (asset, status, priority,
     assignee).
   - Footer row: `Sort By` select (default "Default") on the left; **Apply
     Filters** (blue) and **Clear** (outline) on the right.
2. **Results table card** with a header checkbox for select-all and columns:
   `☐ · ID · Part · Quantity · Price · Status · Priority · Maintenance Event ·
   Asset · Location · Assigned To · Requested By · Actions`.
   - `Part` shows part number in bold over the description.
   - `Price` shows unit price in bold over `Total: $x`.
   - `Status` and `Priority` render as pills (grey `Planned`, cyan `Medium`).
   - `Maintenance Event` shows `Event #21` over the task name; demands not
     attached to a maintenance event show `N/A` in that column *and* in Asset and
     Location (dispatching-sourced demands appear here too).
   - `Actions` is a three-button group per row: cyan **eye** (view detail),
     green **check** (approve), red **✕** (reject).
3. **Bulk actions** operate on the checked rows via
   `bulk-approve` / `bulk-reject` / `bulk-change-part`. `bulk-change-part` lets a
   manager substitute the part on many demands at once — the least obvious and
   most valuable feature on this page.

---

## 4. Part demand detail ⚠️ missing in EBAMS-2

- **URL:** `/maintenance/part_demand/<id>/view` (also `/part-demand/<id>`)
- **Screenshots:** `03_part_demand_1_view.png` (unlinked demand),
  `04_part_demand_3_view.png` and `43_part_demand_4_view.png` (linked to an event)
- **Title:** "Part Demand Details" / `<part number> - <description>`

1. **Breadcrumb** — `Maintenance / Part Demand #1`.
2. **Header** with a **View Lifecycle** outline button on the right.
3. **Status banner card** with a colored left bar: `STATUS` in large colored type
   on the left, then `PRIORITY` and `QUANTITY REQUIRED` right-aligned.
4. **Two side-by-side cards:**
   - *Part Information* — Part Number, Category, Description, Manufacturer, Unit
     of Measure (2-column definition grid).
   - *Maintenance Context* — `ACTION` and `MAINTENANCE EVENT` sub-labels. When
     the demand has no maintenance link, this card renders explicit italic
     explanations rather than hiding: *"This part demand is not linked to a
     maintenance action (e.g. it may be Dispatching or General)."* and *"No
     associated maintenance event found."* This is exactly the always-render
     empty-state behaviour EBAMS-2 rule #5 requires.
5. **Workflow Information card** — three columns: `Requested By`,
   `Maintenance Approval`, `Supply Approval`, each rendering the state in colored
   type (yellow `Pending`). **The dual approval gate is the point of this page:**
   maintenance approval and supply approval are separate.

Row actions (`issue`, `update-issue`, `cancel`, `undo`, `update`,
`manager-approve`, `manager-reject`) are POSTs available from this page and from
the approval portal and work portal.

---

## 5. Create & assign portal ⚠️ missing entirely in EBAMS-2

- **URL:** `/maintenance/manager/create-assign`
- **Screenshot:** `05_manager_create_assign.png`
- **Title:** "Create & Assign" / "Create maintenance events from templates and
  assign them to assets and technicians"
- Header buttons: **View Unassigned Events**, **Back to Dashboard**.

Two-column layout, ~2:1.

**Left column — one green-headed card "⊕ Create Maintenance Event"** containing
three stacked sub-cards, each a **search-dropdown** (type-to-filter, results
render inline with a "N matches" footer row):

1. *Select Template* — sub-card header with a **View All Templates** link on the
   right; `Template *` search input; results show `<name> (Rev. 1.0)`.
2. *Asset* — `Asset *` search input; results show `<name> (<serial>)`.
3. *Technician* — `Search technicians...`; each result row shows the username on
   the left and its current load (`0 active`) right-aligned. **The active-load
   count in the picker is the feature that makes this an assignment tool rather
   than a plain select.**

Card footer: **Cancel** (outline) left, **⊘ Create & Assign Event** (green) right.

Selecting a template fires `api/template/<id>/summary` to populate a preview.

**Right column:**
- *⚡ Quick Actions* card (green header) — *View Unassigned Events* (emphasised),
  *View Events*, *View Templates*, *Build Templates*.
- *ⓘ Help* card (cyan header) — three labelled paragraphs: **Creating Events**,
  **Unassigned Events**, **Reassigning** ("Use the individual event pages to
  reassign events to different technicians").

`GET /create-assign/create` simply redirects back to the portal; only POST creates.

---

## 6. Unassigned events queue ⚠️ missing in EBAMS-2

- **URL:** `/maintenance/manager/create-assign/unassigned`
- **Screenshot:** `07_manager_create_assign_unassigned.png`
- **Title:** "Unassigned Events" / "View and assign maintenance events that
  haven't been assigned to technicians"

1. **Filter bar card** — `Asset Class`, `Status`, `Priority` selects + blue
   **Filter** button + **Clear**.
2. **Yellow-headed results card** "Unassigned Events (2)" with a **Select All**
   button in the header. Columns: `☐ · Event ID · Task Name · Asset · Status ·
   Priority · Planned Start · Created · Actions`. Event ID and Asset are links.
   Actions: yellow **assign-user** icon + outline **eye** icon.
3. **Yellow-tinted "Bulk Assign Selected Events" card** — `Assign to Technician *`
   search dropdown (same active-load rows as the create portal) on the left and
   `Assignment Notes (Optional)` free text on the right, applied to every checked
   row on submit.

---

## 7. Build maintenance templates hub ⚠️ partially represented in EBAMS-2

- **URL:** `/maintenance/manager/build-maintenance-templates`
- **Screenshot:** `08_manager_build_maintenance_templates.png`
- **Title:** "Build Maintenance Templates" / "Create and manage maintenance
  templates, action sets, and prototype actions"

1. **Primary button row** (four buttons, full-size, side by side):
   **⊕ Create New Template from Scratch** (blue) ·
   **View your drafts** (grey) ·
   **View All Proto Actions** (cyan) ·
   **⊞ Create Proto Action** (green).
2. **"From Existing Templates" card:**
   - Two secondary buttons: **New Template from Existing** (copy) and
     **New Revision of Existing Template** (revision chain). These are *two
     distinct semantics* — a copy starts a fresh template, a revision links
     `prior_revision_id` and bumps `revision`.
   - **Filters** sub-block: `Template name` (text), `Make Model` (select),
     `Asset Class` (select), `Template ID` (number spinner), then **Apply
     Filters** / **Clear Filters**.
   - **Two-pane picker**, ~40/60:
     - *List of Template Action Sets* `[2]` — selectable rows showing name, a
       `Rev: 1.0` pill, an `ID: n` pill right-aligned, description, and
       `≡ N actions`.
     - *Preview* — empty state "Click on a template from the list to preview its
       actions, part demands, and tools." Populated by HTMX on row click.

This page is the single entry point to **five** creation paths: scratch, from
existing, new revision, drafts, and proto action creation.

---

## 8. Procedure template detail ⚠️ EBAMS-2 version does not capture this

- **URL:** `/maintenance/maintenance-template/<id>/view`
- **Screenshots:** `09_maintenance_template_2_view.png` (2 actions),
  `10_maintenance_template_1_view.png` (3 actions)
- **Title:** `<task name>` / `<description>`
- Header buttons: **⊙ Deactivate** (yellow outline — toggles
  `active_status`), **Back to View Templates**.

1. **4 stat tiles** with colored left accent bars: `Status` (Active pill),
   `Revision` (1.0), `Action Items` (2), `Parts Required` (0).
2. **Two-column body, ~60/40.**

**Left column:**
- *ⓘ Template Details* — 2-column definition grid: Task Name, Estimated Duration
  (`0.75 hours (estimated)`), Description, Staff Count, Revision, Parts Cost,
  Is Active (pill), Labor Hours, Asset Class, Safety Review (yellow `Required`
  pill), Make / Model.
- *≡ Template Action Items (N)* — one block per step, in sequence:
  - `#1` sequence pill + action name;
  - description line;
  - a metric strip: `🕐 Est: 0.33h · ▭ Billable: 0.33h · 👥 Staff: 1`;
  - a **yellow safety-notes callout** "⚠ Safety Notes: …" when present;
  - a grey **"⚒ Tools Required"** sub-panel listing tool pills (`Jack x1`,
    `Jack Stands x2`);
  - a parts sub-panel when the step has part demands.

**Right column (stacked cards):**
- *📄 Template Information* — Template ID, Revision, Status, Created,
  Created By.
- *📊 Summary* — Total Action Items, Total Parts, Total Tools, Total
  Attachments, Total Estimated Duration (rolled up: `1.33 hours` — the sum of
  the steps, distinct from the header's `0.75` labor hours), Labor Hours.
- *📦 All Parts Required* `[0]` — cyan header, roll-up across all steps, empty
  state "No parts required for this template".
- *⚒ All Tools Required* `[2]` — roll-up with the tool pill on the left and the
  **owning action name** right-aligned, so you can see which step needs it.
- *📎 Attachments* `[0]` — empty state "No attachments for this template".
- **Yellow recommendation callout:** "⚠ **Recommendation:** It's recommended that
  common actions are linked to action prototypes." — an advisory nudge toward
  proto actions, rendered on templates whose steps are ad-hoc.

The three roll-up cards (parts / tools / attachments) and the per-step tool and
safety sub-panels are what the current EBAMS-2 `template_detail.html` is missing.

---

## 9. Template library browse

- **URL:** `/maintenance/view-templates`
- **Screenshot:** `11_view_templates.png`
- **Title:** "Maintenance Templates" / "View and filter maintenance templates"

1. **Filters card** — `Search Templates` (text), `Status`, `Asset Class`,
   `Make / Model` selects, blue **Apply**.
2. **Count strip** — "Showing 2 of 2 templates".
3. **Result cards**, one per template, with a blue left accent bar: title +
   `v1.0` pill + `Active` pill + `N actions` pill; description; a footer metric
   line `🕐 0.75h · 📅 Created 2026-08-09`; blue **View** button right-aligned.

---

## 10. Proto action library ⚠️ no proto actions in EBAMS-2 UI

- **URL:** `/maintenance/proto-actions/list`
- **Screenshot:** `12_proto_actions_list.png`
- **Title:** "Proto Actions" / "Reusable action templates for maintenance
  procedures"
- Header buttons: **⊕ Create Proto Action** (blue), **Back to Build**.

1. **Search bar card** — `Search` (name, description, or instructions),
   `Required` select (All), `Sort By` (Name), `Order` (Ascending), blue
   **Search**.
2. **"Proto Actions" heading + `5 total` pill.**
3. **Three-column card grid.** Each card: action name as a blue link, a yellow
   `Required` pill top-right, description, a badge strip (`🕐 0.25h` blue,
   `⚒ 1 tools` dark, `📦 1 parts` green), then a footer row with the created date
   and an outline **View** button. The currently-hovered/selected card gets a
   cyan left accent bar.

---

## 11. Proto action detail ⚠️ missing in EBAMS-2

- **URL:** `/maintenance/proto-actions/<id>/view`
- **Screenshots:** `13_proto_action_1_view.png`, `42_proto_action_4_view.png`
- **Title:** `<action name>` / `<description>`

1. **4 stat tiles:** `Required` (Yes), `Revision`, `Parts Required`,
   `Tools Required`.
2. **Left column:**
   - *ⓘ Proto Action Details* — Action Name, Estimated Duration, Description,
     Expected Billable Hours, Revision, Minimum Staff Count, Is Required (pill),
     and **Safety Notes rendered in yellow body type**.
   - *📦 Parts Required* `[0]` (cyan header) — pills, or "No parts required for
     this proto action".
   - *⚒ Tools Required* `[1]` — tool pills (`Oil Drain Pan x1`).
   - ***🔗 Referenced By Template Action Items (N)*** — one row per template
     action derived from this proto: `<action name> (from <template name>)`,
     description, and a green outline **View Template** button. **This reverse-
     reference card is the core value of the proto library** — it answers "what
     breaks if I change this?"
3. **Right column:** *📦 Proto Action Information* (Proto Action ID, Revision,
   Required pill, Created, Created By) and *📊 Summary* (Parts Required, Tools
   Required, **Referenced By Templates**, Estimated Duration, Expected Billable
   Hours, Minimum Staff).

---

## 12. Create proto action ⚠️ EBAMS-2 has a thin version

- **URL:** `/maintenance/proto-actions/create`
- **Screenshot:** `14_proto_action_create.png`
- **Title:** "Create Proto Action" / "Create a reusable action template for
  maintenance procedures"

Two-column form, ~65/35, with cyan underlined card headers.

**Left column:**
- *ⓘ Basic Information* — `Action Name *` (placeholder "e.g., Replace Engine Oil,
  Inspect Brakes", help "A clear, descriptive name for this action"),
  `Description` textarea, `Revision` ("e.g., 1.0, A, 2023-v1", help "Optional
  version identifier for tracking changes").
- *≡ Instructions* — `Detailed Instructions` (large textarea, "Step-by-step
  instructions for completing this action..."), `Instructions Format` select
  (default **Plain Text**), `Safety Notes` textarea with a yellow help line
  "⚠ Critical safety information for technicians", `Additional Notes` textarea.

**Right column:**
- *⚙ Action Properties* — a **toggle switch** `Required Action` (on by default,
  "Mark if this action must be completed"), `Estimated Duration (hours)`,
  `Expected Billable Hours`, `Minimum Staff Required` (default 1),
  `Required Skills` textarea ("e.g., Hydraulic Systems Certified, Welding").
- *💡 Next Steps* card (cyan) — "After creating this proto action, you can:
  Attach reference documents · Use it in maintenance templates".

**Full-width bottom row — two repeater cards side by side:**
- *📦 Parts Required* — "Add parts needed for this action. Leave part unselected
  to skip a row." Each row: `Part` select, `Qty` (default 1), `Expected cost`
  (Optional), `Notes` (Optional), an **`Optional part`** checkbox, and a red
  **Remove**. An outline **⊕ Add Part** appends a row.
- *⚒ Tools Required* — same shape: `Tool` select, `Qty`, `Notes`, a
  **`Required`** checkbox (checked by default), **Remove**, and **⊕ Add Tool**.

Footer: **Cancel** left, **⊘ Create Proto Action** (blue) right.

Note the inverted checkbox polarity between the two repeaters — parts opt *into*
being optional, tools opt *out* of being required.

---

## 13. Maintenance plans list

- **URL:** `/maintenance/manager/maintenance-plans`
- **Screenshot:** `15_manager_maintenance_plans.png`
- **Title:** "Maintenance Plans", header button **⊕ Create Maintenance Plan**.

Single card "Maintenance Plans (3 total)" with columns `ID · Name · Asset Class ·
Model · Frequency Type · Template · Status · Created · Actions`. ID renders in
pink monospace. `Model` shows a muted "All Models" when unscoped. `Frequency
Type` is a cyan pill (`days`, `meter1`). `Template` is a link to the template
detail. Actions: outline **eye** + outline **pencil**.

---

## 14. Maintenance plan detail ⚠️ EBAMS-2 version looks nothing like this

- **URL:** `/maintenance/maintenance-plan/<id>/view`
- **Screenshots:** `16_maintenance_plan_3_view.png`, `40_maintenance_plan_1_view.png`
- **Title:** `<plan name>` (large, no icon, no subtitle)
- Header buttons: **📅 Plan Maintenance** (blue), **✎ Edit Plan** (grey),
  **Back to Plans** (muted).

1. **Two side-by-side cards:**
   - *Plan Information* — ID (pink monospace), Name, Description, Status (green
     `Active` pill), **Asset Class ID** rendered as `1 (Vehicle)` — the raw id in
     pink followed by the resolved label, **Model ID** (`All Models` muted when
     unscoped), **Template Action Set ID** as `2 (Brake Inspection Procedure)`,
     Created (`… by system`), Created By ID (`N/A` in pink monospace).
   - *Frequency Configuration* — Frequency Type (cyan pill `days`),
     `Delta Days` (90.0), then **`Delta Meter 1` through `Delta Meter 4`** each
     showing `-` when unset, Last Updated, Updated By ID.
2. **Full-width card "Template Action Set: `<template name>`"** — an inline
   expansion of the linked template so the plan can be understood without
   navigating away:
   - a 2-column header grid: Task Name, Action Items (blue count pill),
     Description, Status (green pill), Estimated Hours;
   - a table of the template's steps: `Order` (grey `#1` pill) · `Action Name`
     (bold) · `Description` · `Required` (green pill) · `Estimated Duration`.

The four `Delta Meter` slots and the embedded template action set table are the
two features most obviously absent from the current EBAMS-2 plan page.

---

## 15. Create maintenance plan ⚠️ EBAMS-2 version looks nothing like this

- **URL:** `/maintenance/maintenance-plan/create`
- **Screenshot:** `17_maintenance_plan_create.png`
- **Title:** "Create Maintenance Plan", header button **Back to Plans**.

One centred card, "Maintenance Plan Information", divided by hairlines into
three labelled fieldsets:

1. **Basic Information** — `Plan Name *`, `Description` (textarea),
   `Asset Class *` select ("Select Asset Class") beside `Model` select ("All
   Models", help "Leave blank to apply to all models of the selected asset
   type."), `Status *` select (default Active).
2. **Maintenance Template** — `Template Action Set *` with a text input plus an
   adjacent blue **🔍 Search** button and help "Enter search term and click
   Search to filter templates". Below it, a **selectable result list**: each row
   shows the template name, its description, and a blue `N actions` pill
   right-aligned. This is a click-to-search picker, **not** a live-as-you-type
   dropdown — a deliberate difference from the create-assign searchbars.
3. **Frequency Configuration** — `Frequency Type *` select ("Select Frequency
   Type"). The delta fields (`Delta Days`, `Delta Meter 1-4`) are revealed
   conditionally by the chosen frequency type.

Footer: **⊘ Cancel** left, **⊘ Create Maintenance Plan** (blue, **disabled until
valid**) right. `18_maintenance_plan_3_edit.png` is the same card pre-populated.

---

## 16. Plan maintenance — due-asset worklist ⚠️ missing in EBAMS-2

- **URL:** `/maintenance/maintenance-plan/<id>/plan`
- **Screenshots:** `19_maintenance_plan_3_plan.png`, `41_maintenance_plan_1_plan.png`
- **Title:** "Plan Maintenance: `<plan name>`", header button **Back to Plan**.

1. **Plan Summary card** — 2 columns: Plan ID, Template (name), Frequency Type
   (pill), Status, **Assets Needing Maintenance** (blue count pill).
2. **Plan Information** and **Frequency Configuration** cards — identical to the
   plan detail page.
3. **Assets Needing Maintenance card** — a cyan info callout
   "ⓘ No assets currently need maintenance for this plan." when empty; otherwise
   the due-asset rows, each able to POST `create-event` to instantiate a
   maintenance event from the plan's template.

This page is the manual counterpart to `MaintenancePlanner.plan_all_active_plans()`,
which the legacy app also runs automatically at startup.

---

## 17. Technician dashboard ⚠️ missing entirely in EBAMS-2

- **URL:** `/maintenance/technician/dashboard`
- **Screenshot:** `20_technician_dashboard.png`
- **Title:** "Technician Portal" / "View assigned work, complete actions, and
  track your maintenance history", header button **Back to Portals**.

1. **3 stat tiles:** `Assigned Work` (blue), `In Progress` (green),
   `Completed Today` (yellow).
2. **Row of three unequal cards:**
   - *🔍 Quick Asset Lookup* (wide) — "Search assets by name or serial
     number..." with help "Search for assets to view their maintenance history".
   - *View Events by Your Location* — a **disabled grey tile** with a location
     pin, plus the explanation "Complete an event to see location-based events".
     The tile enables once the technician has a completed event to derive a
     location from.
   - *Event Viewer Dashboard* — a cyan tile linking to the event ledger.
3. **Two side-by-side list cards**, each with a **View All** button in the
   header: *≡ Assigned Events* and *💬 Recently Interacted With* (the latter
   backed by `technician/continue-discussion`).
4. **Full-width *📅 Planned This Week*** card with its own **View All**.

All three list cards render as empty bodies when there is nothing to show —
faithful to EBAMS-2 rule #5 already.

---

## 18. Fleet / admin dashboard (stub)

- **URL:** `/maintenance/fleet/dashboard`
- **Screenshot:** `21_fleet_dashboard.png`

4 stat tiles with colored accent bars — `Total Assets` (blue), `Assets Due`
(yellow), `Overdue` (red), `Active Maintenance` (cyan) — over a single large
placeholder card reading "Fleet/Admin Portal · Fleet-wide maintenance oversight
will be implemented here · Features: Fleet dashboard, analytics, comprehensive
data views, reporting."

**Only the stat tiles were ever built.** When merging portals into the index,
this contributes four numbers and nothing else.

---

## 19. Maintenance event — work portal

- **URL:** `/maintenance/maintenance-event/<event_id>/work`
- **Screenshots:** `28_event_21_work.png`, `37_event_22_work.png`
- **Title:** `<task name>` / `Asset: <asset link> (<serial>)`, header button
  **Back to View**.

This is the busiest page in the legacy module and the technician's main screen.

1. **"⚒ Maintenance Status" card** (cyan header, status pill right-aligned),
   split into two halves:
   - Left: `Completion Progress` label with the percentage right-aligned, a
     progress bar, and three mini counters (`Total`, `In Progress`, `Complete`).
   - Right: three action buttons — **⊘ Mark Complete** (muted green, gated),
     **⏸ Place in Blocked Status** (yellow), **⚠ Add Capability Limitation**
     (red).
2. **Left column:**
   - *ⓘ Maintenance Event Details* — 2-column grid: Task Name, Planned Start,
     Description, Actual Start, Asset (link), Actual End, **Template Source**
     (which template the event was instantiated from), Estimated Duration.
   - *≡ Maintenance Actions (N)* — the work list. Per step:
     - `#1` pill + action name + a status pill (`Not Started`);
     - description; `🕐 Est: 0.25h`;
     - a **yellow safety-notes callout** when present;
     - a **right-hand vertical button stack**: cyan **▶ Start**, outline
       **✎ Edit**, outline **⊕ Add Part**;
     - a cyan **"📦 Parts Required"** sub-panel per step, each demand row showing
       a part pill (`Oil Filter x1.0`), an issue-status pill (`Not Issued`), and
       three buttons: green **✓ Issue**, an outline **edit** icon, red
       **✕ Cancel**.
   - *📈 Event Activity* card with the event type and timestamp right-aligned in
     the header, and a **three-tab strip**: `Comments (N)` · `Attachments` ·
     `Metadata`; inside Comments, two disclosures — **Show / Hide Comments** and
     **⊕ Add comment**.
3. **Right column (stacked):**
   - *⚡ Quick Actions* — **View Event**, **Edit Event**.
   - *ⓘ Event Information* — Status, Priority, Planned Start, Actual Start,
     Estimated Duration (all as pills or values).
   - *📎 Template Attachments* — "From template: `<link>`" plus the attachment
     list or "No attachments for this template".
   - *📊 Summary* — Total Actions, Completed, In Progress, Total Parts, Total Tools.
   - ***⚒ Part Demand Manager Approval*** `[2]` — an in-page approval queue
     scoped to this event. Each row: part name + qty, an `Approval: Planned` pill
     and an `Issue: Not Issued` pill, the owning action name (`≡ Replace Oil
     Filter`), and green **✓** / red **✕** buttons. **A manager can approve this
     event's demands without leaving the work portal.**
   - *🕐 Blockers (N)* — "No blockers recorded" empty state.
   - *🕐 Capability Limitations (N)* — "No capability limitations recorded".

Modals used by this page live in
`templates/maintenance/base/work_maintenance_components/modals/`:
`action_status`, `edit_action`, `part_demand`, `create_blocked`,
`create_limitation`, `close_limitation`, `complete_maintenance`.

---

## 20. Maintenance event — read-only view

- **URL:** `/maintenance/maintenance-event/<event_id>/view`
- **Screenshots:** `26_event_21_view.png`, `30_event_22_view.png`

The same card inventory as the work portal with every mutating control removed:
status header without the three action buttons, event details, the action list as
static rows with their parts and tools, and the right-hand information / summary /
blockers / limitations stack. This is the "what happened" page.

---

## 21. Maintenance event — edit portal

- **URL:** `/maintenance/maintenance-event/<event_id>/edit`
- **Screenshots:** `27_event_21_edit.png`, `36_event_22_edit.png`
- **Page title element:** "Action Creator Portal" (the `<title>` is wrong on this
  page — it inherits the embedded portal's title).

Composition, from `templates/maintenance/base/edit_maintenance_components/`:

1. `event_header.html` — event identity strip.
2. `event_details_form.html` — editable event metadata (datetime, billable hours,
   priority, description) posting to `update-datetime` and
   `update-billable-hours`.
3. `limitations_card.html` + `limitation_modals.html` — asset limitation list
   with create/close modals.
4. `blockers_card.html` + `blocker_modals.html` — blocker list with
   create/end/update modals.
5. **`action_editor_panel/`** — a three-pane editor:
   - `actions_list_sidebar.html` — the ordered action list, click to select,
     with move-up / move-down / delete;
   - `action_edit_form.html` — the selected action's form;
   - `part_demands_section.html` and `tools_section.html` — the selected action's
     part and tool repeaters.
6. **The embedded Action Creator Portal** (see next entry) at the bottom of the
   page, posting to `create-blank-action`, `create-from-proto-action`,
   `create-from-template-action`, `create-from-current-action`.

---

## 22. Action creator portal — the five-tab action source picker

- **Standalone URL:** `/maintenance/action-creator-portal/<maintenance_action_set_id>`
- **Embedded URLs:** bottom of the event edit portal; bottom of the template
  builder (`/manager/template-builder/<id>/action-creator-portal`)
- **Screenshots:** `33_action_creator_portal_set1.png`,
  `35_template_builder_1_action_creator.png`, and in context inside
  `34_template_builder_1_edit.png`

A cyan-headed card "⊕ Action Creator Portal" with a **five-tab strip**:

| Tab | Panel | Behaviour |
| :--- | :--- | :--- |
| **From Template** | "📄 Select Template Action Set" — `Search Templates` input, help "Searching template action sets and their action items", then a **Template Action Sets** list (name, description, blue `N actions` pill) | Pick a whole set, then drill into `list-template-action-items/<set_id>` to choose steps |
| **From Template Action** | search over individual `TemplateActionItem` rows | Copies one template step |
| **From Proto Action** | search over the proto action library | Copies a proto step; carries its parts and tools |
| **From Current Build** | list of steps already in the current build/event | Clone an existing step |
| **Blank Action** | empty form | Ad-hoc step |

The same five tabs appear in all three hosts; only the POST target changes. This
is the single most reused composite component in the legacy maintenance UI.

---

## 23. Template builder

- **URL:** `/maintenance/manager/template-builder/<builder_id>`
  (reached via `/new`, which creates the row then redirects)
- **Screenshots:** `34_template_builder_1_edit.png`, `32_template_builder_new.png`
- **Header:** a **purple gradient banner** "⚒ Edit Template Builder" with a
  status pill (`Initialized`) and a build-type label (`New Template`) beneath it,
  and **Back to Build Templates** on the right.

1. **Green commit banner** — "ⓘ **Ready to create your template?** Once you're
   satisfied with your template builder, click below to create the final
   template." with a large green **⊘ Create Template from Build** button on the
   right. Always visible, at the top, before the form.
2. **Two-column body.**

**Left — *ⓘ Template Builder Metadata* card:**
`Builder ID` (read-only, greyed), `Task Name *`, `Estimated Duration (hours)`,
`Description` (textarea, "Describe this maintenance template..."), `Asset Class`
select (`— Any —`), `Make / Model` select (`— Any —`), `Revision` (read-only,
`0`), a **▸ Additional Details** disclosure, then **💾 Save Metadata** (blue) and
**Cancel**.

**Right — three stacked cards:**
- *ⓘ Builder Summary* — Builder ID (`#1` cyan pill), Build Status (`Initialized`
  green pill), Build Type (`—`), Total Actions (`0` blue pill).
- *📎 Template Attachments* `[0]` — "No attachments yet." plus two disclosures:
  **▸ ⬆ Upload Attachment** (green tint) and **▸ 📖 Select from Technical
  Library** (cyan tint).

3. **Full-width "✎ ACTION EDITOR PANEL"** — three panes: *≡ Action Details*
   (the action list, empty here), *✎ Action Form Details* ("Select an action from
   the list to edit it."), and a third pane carrying the empty state "No actions
   available. Use the Action Creator Portal below to add actions."
4. **Two debug/utility buttons** outside any card: "Debug: Open Action Creator
   Portal in New Tab" and "↻ Reload Action Creator Portal". These are dev
   scaffolding — **do not port them.**
5. **The embedded Action Creator Portal** (entry 22) at the bottom.

`/drafts` (`31_template_builder_drafts.png`) lists in-progress builder rows.
Under the EBAMS-2 session-memory decision, "drafts" becomes at most **one**
draft per session, so the drafts list collapses into "resume your draft" —
see [gap_analysis.md](gap_analysis.md#6-template-builder-under-session-memory).

---

## 24. Event assign portal

- **URL:** `/maintenance/maintenance-event/<event_id>/assign`
- **Screenshots:** `29_event_21_assign.png`, `38_event_22_assign.png`
- **Title:** "Assign Event - Maintenance"

Single-purpose page: event identity summary plus a technician search dropdown
(the same active-load rows as create-assign) and a submit. `GET /api/technicians`
backs the picker. This is the "reassign" path the create-assign Help card points
users to.

---

## 25. Event ledgers

Three near-duplicate list pages exist, all showing maintenance events with
filters:

| Page | URL | Screenshot | Notes |
| :--- | :--- | :--- | :--- |
| Cross-role ledger | `/maintenance/view-events` | `25_view_events.png` | The one the hub's yellow button points at |
| Manager ledger | `/maintenance/manager/view-maintenance` | `22_manager_view_maintenance.png` | Reached only via the muted "Legacy View Maintenance" button |
| Manager plan landing | `/maintenance/manager/plan-maintenance` | `23_manager_plan_maintenance.png` | Thin landing that forwards into the plan list |
| Assign & monitor landing | `/maintenance/manager/assign-monitor` | `24_manager_assign_monitor.png` | Thin landing, overlaps create-assign |

**Recommendation:** port one ledger. The manager duplicate was already labelled
"Legacy" by the previous author, and `plan-maintenance` / `assign-monitor` are
vestigial landings whose jobs are done better by the plan list and the
create-assign portal.
