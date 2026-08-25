# Legacy Maintenance UI Workflows

The end-to-end paths a real user walks in the legacy app, reconstructed from the
routes and the captured screens. Page anatomy lives in
[page_catalog.md](page_catalog.md); this document is about **sequence and gates**.

Nine workflows. Each names its actor, its entry point, every screen in order, and
the state change at each step.

---

## W1 — Build a procedure template from scratch

**Actor:** maintenance manager.
**Entry:** Manager dashboard → *Build Maintenance Templates* → **Create New
Template from Scratch**.

1. `GET /manager/template-builder/new` — creates a builder row, redirects to
   `/manager/template-builder/<id>`.
2. **Builder page.** Fill the *Template Builder Metadata* card (task name,
   estimated duration, description, asset class, make/model) → **Save Metadata**
   (`POST /<id>/metadata`). Build status stays `Initialized` until actions exist.
3. **Add actions** via the embedded Action Creator Portal at the bottom, choosing
   one of five sources per action:
   - *Blank Action* → `POST /<id>/add-blank-action`
   - *From Proto Action* → `POST /<id>/add-action-from-proto/<proto_id>` —
     **carries the proto's parts and tools with it**
   - *From Template Action* → `POST /<id>/add-action-from-template-action/<id>`
   - *From Template* → pick a set, drill into its items via
     `list-template-action-items/<set_id>`, then add chosen items
   - *From Current Build* → clone a step already in this build
4. **Refine each action** in the *Action Editor Panel*: select it in the sidebar,
   edit it in the form (`POST /<id>/action/<idx>/update`), reorder
   (`/action/<idx>/move`), delete (`/action/<idx>/delete`), and manage its
   children:
   - parts — `/action/<idx>/part/add`, `/part/<pidx>/update`, `/part/<pidx>/delete`
   - tools — `/action/<idx>/tool/add`, `/tool/<tidx>/update`, `/tool/<tidx>/delete`
5. **Attachments** — `attachment/upload` (file) or `attachment/add-from-library`
   (pick from the technical library), removable by index.
6. **Commit** — **Create Template from Build** → `POST /<id>/submit`. Real
   `TemplateActionSet` + `TemplateActionItem` + `TemplateActionTool` +
   `TemplatePartDemand` rows are written here and only here. Revisiting the
   builder afterwards lands on `/already-submitted`.
7. Abandon instead → `POST /<id>/delete`.

**The load-bearing detail:** every child is addressed by **position**
(`action_index`, `part_index`, `tool_index`), never by primary key, because
nothing has a PK until commit. The EBAMS-2 session draft must preserve positional
addressing.

### W1a — Variants from the build hub

- **New Template from Existing** — copy an existing set into a fresh builder;
  produces an independent template.
- **New Revision of Existing Template** — copy into a builder that records
  `prior_revision_id` and bumps `revision`. The old revision stays; templates are
  deactivated, never edited in place (`POST /maintenance-template/<id>/active_status`).
- **View your drafts** — `/drafts`, resume an uncommitted builder.

---

## W2 — Publish and retire templates

**Actor:** maintenance manager.

1. `/maintenance/view-templates` — filter by name, status, asset class,
   make/model.
2. **View** a template → template detail. Read the per-step tools and safety
   notes and the three roll-ups (all parts / all tools / attachments).
3. **Deactivate** (header button) → `POST /maintenance-template/<id>/active_status`.
   Deactivation hides the template from the create-assign and plan pickers while
   leaving existing events and plans that reference it intact.

Templates are never hard-edited once used. Change = new revision (W1a).

---

## W3 — Maintain the proto action library

**Actor:** maintenance manager / senior technician.
**Entry:** Manager dashboard → *Build Maintenance Templates* → **Create Proto
Action** or **View All Proto Actions**.

1. `/proto-actions/list` — search by name/description/**instructions**, filter by
   required, sort.
2. `/proto-actions/create` — the two-column form: identity + instructions on the
   left, properties (required toggle, duration, billable hours, minimum staff,
   required skills) on the right, and two repeaters at the bottom for parts and
   tools.
3. `/proto-actions/<id>/view` — read the detail and, critically, the
   **"Referenced By Template Action Items"** card, which lists every template
   step derived from this proto with a link to its template.

**Why the library exists:** proto actions are the *reusable* rung between "typed
free-hand into one template" and "a whole template". A proto carries its own
parts, tools, skills and safety notes, so pulling it into a template or an event
(W1 step 3, W5 step 2) drags all of that along. The template detail page even
nags about it: *"It's recommended that common actions are linked to action
prototypes."*

See [proto_vs_template_actions.md](proto_vs_template_actions.md) for the
three-tier model.

---

## W4 — Set up recurring maintenance and harvest due assets

**Actor:** maintenance manager.

1. `/manager/maintenance-plans` — the plan table.
2. **⊕ Create Maintenance Plan** → the three-fieldset form:
   - *Basic Information* — name, description, asset class (required), model
     (blank = all models of that class), status.
   - *Maintenance Template* — type a term, click **Search**, pick a template from
     the returned list. Deliberately **click-to-search**, not live filtering.
   - *Frequency Configuration* — pick a frequency type; the relevant delta fields
     appear (`Delta Days` for calendar plans, `Delta Meter 1-4` for meter plans).
   Submit is disabled until the form validates.
3. `/maintenance-plan/<id>/view` — plan info, frequency config, and the linked
   template action set expanded inline as a step table.
4. **📅 Plan Maintenance** → `/maintenance-plan/<id>/plan` — the *Assets Needing
   Maintenance* worklist. For each due asset, `POST /create-event` instantiates a
   maintenance event from the plan's template.
5. **✎ Edit Plan** → the same form pre-populated.

**Automation:** `MaintenancePlanner.plan_all_active_plans()` also runs on app
startup and creates due events unattended (visible in the legacy boot log:
"Planning maintenance for 3 active plans … 0 due result(s), 0 event(s) created").
The `/plan` page is the manual override, not the only path.

---

## W5 — Create an event and assign it to a technician

**Actor:** maintenance manager.
**Entry:** Manager dashboard → **Create & Assign**.

1. `/manager/create-assign` — three stacked search dropdowns in one card:
   1. **Template** (live filter; `api/template/<id>/summary` populates a preview)
   2. **Asset** (live filter, shows serial)
   3. **Technician** (live filter, **shows each technician's current active
      load**) — optional at this step
2. **⊘ Create & Assign Event** → `POST /create-assign/create`. Instantiates the
   event and all its actions/parts/tools from the template, and assigns it if a
   technician was chosen.
3. Skipped the technician? The event lands in
   `/manager/create-assign/unassigned`. Filter by asset class / status /
   priority, check rows (or **Select All**), pick one technician in the *Bulk
   Assign* card, add optional shared notes, submit → `POST
   /unassigned/bulk-assign`.
4. **Reassign** an already-assigned event from
   `/maintenance-event/<id>/assign` — the Help card on the create-assign portal
   says so explicitly.

---

## W6 — Perform maintenance (the technician's day)

**Actor:** technician.
**Entry:** Technician dashboard → *Assigned Events* → an event's work portal, or
`/technician/most-recent-event` which jumps straight to the latest one.

1. `/technician/dashboard` — three counters (Assigned Work, In Progress,
   Completed Today), a quick asset lookup, the assigned-events list, recently
   interacted with, and planned-this-week.
2. `/maintenance-event/<id>/work` — the work portal.
3. **Per action, in sequence:**
   - **▶ Start** → `POST /action/<id>/update-status` (`In Progress`, stamps start
     time)
   - **✎ Edit** → `POST /action/<id>/update` (notes, findings)
   - **⊕ Add Part** → `POST /action/<id>/part-demand/create` — raises a new part
     demand mid-job
   - existing demands on the step: **✓ Issue** (`part-demand/<id>/issue`), edit
     (`update` / `update-issue`), **✕ Cancel** (`cancel`), and `undo`
   - tools: `action/<id>/tool/create`, `tool/<tid>/update`, `tool/<tid>/delete`
   - complete the step → `update-status`, and log time via
     `action/<id>/update-billable-hours`
   The status card's progress bar and Total / In Progress / Complete counters
   update as steps advance.
4. **Interruptions** — two distinct concepts, two buttons, two record types:
   - **⏸ Place in Blocked Status** → `POST /<event_id>/blocker/create`. The work
     itself is stopped (waiting on a part, a bay, a decision). Ended via
     `blocked_status/<id>/end`, editable via `blocked_status/<id>/update`.
     Blockers carry a billable-hours impact.
   - **⚠ Add Capability Limitation** → `POST /<event_id>/limitation/create`. The
     *asset* is degraded but the work may continue. Closed via
     `limitation/<id>/close`. Surfaced fleet-wide through the
     `/widgets/limitations/<asset_id>` and `/widgets/blockers/<asset_id>`
     fragments, which other apps embed.
5. **Discussion** — the *Event Activity* card's Comments / Attachments /
   Metadata tabs; `technician/continue-discussion` returns to the last thread.
6. **⊘ Mark Complete** → `POST /<event_id>/complete`, gated by a confirmation
   modal (`complete_maintenance.html`) and by a completion guard — actions must be
   resolved and the event must not be blocked.

---

## W7 — Amend an event's plan mid-flight

**Actor:** manager (or technician with rights).
**Entry:** work portal → *Quick Actions* → **Edit Event**.

1. `/maintenance-event/<id>/edit` — event metadata form, limitations card,
   blockers card, the three-pane action editor, and the Action Creator Portal.
2. **Reschedule / re-time** — `update-datetime`, `update-billable-hours`.
3. **Restructure the action list** — add a step from any of the five sources
   (`create-blank-action`, `create-from-proto-action`,
   `create-from-template-action`, `create-from-current-action`), reorder with
   `action/<id>/move-up` / `move-down`, delete with `action/<id>/delete`.
4. Save → `POST /<id>/edit`.

Note the asymmetry: **events** are edited freely in place; **templates** are
never edited, only revised (W2). Live work is mutable, the library is immutable.

---

## W8 — Approve, substitute, and issue part demands

**Actor:** maintenance manager, then supply.
**Entry:** Manager dashboard → **Part Demands** (the yellow *Pending Part
Demands* tile is the prompt).

1. `/manager/part-demands` — filter by part id, description, approval status, and
   four created/updated date bounds, plus a collapsed **Maintenance Event
   Filters** tier. Sort, apply, clear.
2. **Per row:** eye (detail), green check (`manager-approve`), red ✕
   (`manager-reject`).
3. **In bulk** on checked rows: `bulk-approve`, `bulk-reject`, and
   **`bulk-change-part`** — substitute the requested part across many demands at
   once, the manager's answer to "we don't stock that, use this instead".
4. `/part_demand/<id>/view` — the detail page. The *Workflow Information* card
   shows the **two independent gates**: `Maintenance Approval` and
   `Supply Approval`. Maintenance approving does not issue anything.
5. **Issuing** happens against the demand (`issue`, `update-issue`) either from
   the demand page or inline in the work portal's per-step *Parts Required*
   panel. `undo` reverses the last transition; `cancel` kills the demand.
6. **A second approval surface exists**: the work portal's right-hand
   ***Part Demand Manager Approval*** card approves that event's demands in place,
   without visiting the portal. Both surfaces hit the same POST endpoints.

Demands reaching this queue are **not all maintenance-sourced** — dispatching
demands appear with `N/A` in the event/asset/location columns.

---

## W9 — Fleet oversight

**Actor:** fleet admin. `/maintenance/fleet/dashboard` shows Total Assets,
Assets Due, Overdue, Active Maintenance and then an explicit
"will be implemented here" placeholder. **This workflow was never built.**

---

## Cross-cutting UI mechanics to carry over

| Mechanic | Where it appears | Note |
| :--- | :--- | :--- |
| **Search dropdown with live results and a "N matches" footer** | create-assign (×3), bulk assign, assign portal, action creator tabs | Maps to EBAMS-2 `search_dropdown` component |
| **Click-to-search picker** (input + Search button + result list) | plan create/edit template picker | Deliberately different from the live dropdowns |
| **Technician load in the picker** (`0 active`) | every technician picker | Assignment decision support, not decoration |
| **Five-source action creator** | template builder, event edit, standalone | The most reused composite in the module |
| **Positional addressing of draft children** | template builder | Survives the session-memory swap |
| **Roll-up cards** (all parts / all tools / attachments, with the owning action named) | template detail, proto detail | Answers "what do I need to bring" |
| **Yellow safety-notes callout** | proto detail, template detail, work portal action rows | Propagates proto → template → live action |
| **Reverse-reference card** | proto detail ("Referenced By Template Action Items") | Impact analysis before editing |
| **Dual approval gates** | part demand detail | Maintenance and supply are independent |
| **Two interruption types** | work portal | Blocker stops work; limitation degrades the asset |
| **Always-rendered empty states** | everywhere | Already matches EBAMS-2 rule #5 |
| **Embeddable event fragments** | `/event-components/<slug>/full/<event_id>` and `/goto_button/<event_id>` | Other apps embed maintenance events this way |
| **Asset widget fragments** | `/widgets/limitations/<asset_id>`, `/widgets/blockers/<asset_id>` | Asset pages show maintenance state |
