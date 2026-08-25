Add time tracking fields to the maintenance event edit portal.

  PAGE: http://localhost:8000/maintenance/event/111/edit
  (route: `maintenance/event/<int:pk>/edit`, view: `maintenance_edit`)

## What's missing

The event edit portal (and the read-only/work views that share its data)
currently has no explicit place to capture:

- Planned Start
- Actual Start
- Actual End
- Expected Labor Hours
- Actual Labor Hours

The legacy app already surfaces **Planned Start / Actual Start / Actual End**
on this page — see `maintenance_starter_kit/legacy_ui/page_catalog.md`,
section "21. Maintenance event — edit portal" (and the read-only view, section
20), plus screenshots `27_event_21_edit.png` and `36_event_22_edit.png`. Read
those first. Labor hours (expected vs actual) is a new field pair, not a
legacy port — there is no legacy equivalent, so design it fresh in the style
of the existing cards.

## What already exists — read before adding anything

Before adding new columns, confirm what's already on the model so nothing is
duplicated:

- `app/events/models/event.py` — `Event.event_start` / `Event.event_end`
  (generic event-level timestamps, not maintenance-specific "planned" vs
  "actual").
- `app/events/models/details/maintenance.py` — `MaintenanceDetail` currently
  has `actual_billable_hours` (a technician-recorded total, reconciled
  against child `Action.billable_hours` by
  `maintenance.BillableHoursManager`) but **no planned/actual start-end pair
  and no expected-labor-hours field**. Read the comment block above
  `actual_billable_hours` (lines 42-52) — it explains how billable hours,
  elapsed duration, and the template's `labor_hours` budget are three
  independent numbers today. Your new fields need to fit into that same
  mental model without silently conflating with it.
- `app/maintenance/models/abstract_mixins.py` — `labor_hours` on
  `AbstractActionSet` (the template-level budget: `TemplateActionSet` and
  `AbstractActionSet` per-step share). This is the natural source for a
  default/expected value, not a field to duplicate meaning with.
- `app/maintenance/models/action.py` — per-action `start_time` / `end_time`
  and `billable_hours`, if present — check whether an event-level actual
  start/end should simply be derived from these (min/max across actions)
  rather than captured independently. Decide and state the answer, don't
  silently do both.

## Questions to resolve as part of the plan (don't guess silently)

1. **Where do the new fields live?** Straight columns on `MaintenanceDetail`
   is the obvious answer given the existing pattern (`actual_billable_hours`
   lives there), but confirm against `harness/Architecture/patterns/model_patterns.md`
   — no business logic on models, audit columns already present via
   `AuditFieldsMixin`.
2. **Expected Labor Hours — captured per-event or derived from
   `template_action_set.labor_hours`?** If a plan is instantiated from a
   template, the template already carries a labor-hours budget. Decide
   whether "Expected Labor Hours" on the event is: (a) a copy taken at
   creation time (like `ActionFactory` copies template values onto actions
   today — see the comment in `abstract_mixins.py`), (b) a live read-through
   to the template, or (c) an independently editable override. State which,
   and why.
3. **Actual Start / Actual End — manual fields or derived?** Check whether
   these should be settable directly on the edit form, or auto-stamped by
   existing state-machine transitions (e.g. "Start" action / "Mark Complete"
   guard in `maintenance/control_layer/guards/maintenance_completion_guard.py`).
   If auto-stamped, the edit form should show them read-only with a note, not
   present them as freely editable — don't let the UI promise something the
   control layer doesn't enforce.
4. **Actual Labor Hours vs. `actual_billable_hours`** — are these the same
   concept renamed, or genuinely different (e.g. billable = what gets
   invoiced, actual labor = total time spent including non-billable work)?
   If they're the same concept, don't add a second field — rename/reuse
   instead. If they differ, say how, in a code comment matching the existing
   one at `maintenance.py:42-52`.

## Constraints

- `.claude/CLAUDE.md` — schema change means a **full `python refresh_project.py`
  reset**, not an incremental migration. Say so before running it, and confirm
  before wiping the dev DB.
- `harness/Architecture/` layer rules — the edit form's write path goes
  through the control layer (`maintenance/control_layer/`), never straight
  from the entrypoint. If validation is needed (e.g. actual_end >=
  actual_start), it belongs in a `_guard.py` or existing adapter, not inline
  in the view.
- `harness/UX_UI/form_style_guide.md` — match the existing 2-column grid
  layout already used in the "Maintenance Event Details" / "Event
  Information" cards (per the legacy catalog entry above) rather than
  inventing a new card pattern.
- The F5 rule — new fields must survive a plain full-page reload, same as
  everything else on this page.
- Update the seed command (`app/maintenance/management/commands/seed_maintenance_dev.py`)
  so dev data exercises the new fields (some populated, some blank, to check
  the empty-state rendering).

## Definition of done

- [ ] New field(s) added to `MaintenanceDetail` (or wherever the plan lands),
      with a clear one-line comment on each stating what it means and how it
      relates to `actual_billable_hours` / template `labor_hours`
- [ ] Full `refresh_project.py` reset run, migrations regenerated clean
- [ ] Edit portal (`/maintenance/event/<pk>/edit`) shows and can set the
      applicable fields (respecting the manual-vs-derived decision above)
- [ ] Read-only view and work portal reflect the same values consistently
- [ ] Seed data exercises populated and blank states
- [ ] `./venv/bin/python manage.py check` passes
- [ ] Tests for any new control-layer verb or guard added

## Report back

State the four resolved questions above explicitly before touching code —
this is a plan-first task, not straight-to-implementation. Then a short list
of what changed, what was skipped and why, and anything you're unsure about.
