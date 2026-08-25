# 03 — Dispatching rebuild: reservation first, dispatch as an enhancement

**Status:** design pending, build targeted for tomorrow
**Current state in this repo:** no `app/dispatching/` exists. What *does* exist:
`events.EventType.DISPATCHING`, an `events.models.details.DispatchingDetail`
stub (two fields, multi-table inheritance from `Event`), and
`procurement.DemandSourceModule.DISPATCHING`. The seams were left open; nothing
is built.
**Legacy source:** `/home/cb/REPOS/asset_management/app/{data,business,intermediate,presentation}/dispatching/`

---

## 1. The core insight, and why it's right

From the note:

> *previously i just had a check in check out system then added a bunch of
> infrastructure (group dispatches, capability requirements, etc.) but honestly
> most of the time the business wants to just reserve an asset without doing
> all that work.*

This is correct, and the legacy schema shows exactly how it went wrong. Legacy
splits one user intention across **two tables joined by a hand-rolled
polymorphic pointer**:

- `DispatchRequest` — the *intent*. Who, for whom, desired window, asset class,
  location, `workflow_status` (Requested → Submitted → UnderReview →
  FixesRequested → Planned → Resolved → Cancelled).
- `StandardDispatch` — the *outcome*. Assigned asset, assigned person,
  scheduled/actual window, `resolution_status` (Planned → Complete →
  Cancelled).
- Joined by `active_outcome_type` + `active_outcome_row_id` — a type string and
  a bare integer, with no FK behind it.

That split exists for exactly one reason: a request could resolve into
something *other* than a dispatch — a contract, a reimbursement, or a
rejection. Look at what supporting that costs in the legacy tree:

```
policies/  active_pointer.py  outcome_uniqueness.py  intent_lock.py
           manifest_uniqueness.py  double_booking.py  dispatch_status_validation.py
           asset_dispatchability.py  parts_availability.py
alternative_outcomes/  contract_handler.py  reimbursement_handler.py  reject_handler.py
```

Three of those eight policies (`active_pointer`, `outcome_uniqueness`,
`intent_lock`) exist **only to keep the untyped pointer honest**. They enforce
nothing a user would recognise as a business rule. They are pure tax on a
schema decision.

And the split never even settled. Both tables carry a live `status` column
alongside their real status field, each commented *"Legacy field — kept for
compatibility during transition."* That transition never finished. **Two
status fields per table, four state machines, and a manual polymorphic
pointer, to express "someone wants an asset on Tuesday."**

The note's instinct — that request and dispatch have merged — isn't a
simplification for its own sake. It's recognising that the thing that forced
them apart (alternative outcomes) is rare, and the thing being paid for it
(pointer integrity machinery) is constant.

## 2. Proposed shape: one table, progressive enrichment

### 2.1 `Reservation` — the whole simple product

One row. Intent and fulfillment columns side by side. For the common case, the
user fills both halves in one action and never sees a workflow.

```
Reservation
  # Intent
  requested_by, requested_for
  desired_start, desired_end
  location, notes
  asset_class            (nullable — "any excavator" for the request-first path)
  # Fulfillment
  asset                  (nullable while unfulfilled; set directly in the simple path)
  scheduled_start, scheduled_end
  actual_start, actual_end     ← check-out / check-in, nothing more
  # One lifecycle
  status                 DRAFT → REQUESTED → RESERVED → IN_PROGRESS → COMPLETE / CANCELLED
  cancellation_reason
  # Origin / grouping
  domain, audit columns
```

Two paths through one table:

- **Simple (the 90% case):** pick an asset, pick a window, save. Row is created
  at `RESERVED` with `asset` set. No approval, no manifest, no review queue.
- **Request-first:** submit with `asset_class` and no `asset`. Sits at
  `REQUESTED` until a dispatcher assigns an asset, which moves it to `RESERVED`.

Same table, same list view, same calendar, same detail page. The difference is
which columns are populated, not which model was used.

`actual_start` / `actual_end` **are** the check-in/check-out system. It doesn't
need to be a separate concept — it was never more than two timestamps.

### 2.2 Dispatch = the same row with children attached

Everything the legacy app bolted on becomes an **optional child table pointing
inward at `Reservation`**, in the same direction-of-knowledge style as
`MaintenanceDemandLink → PartDemand` (D7):

| Legacy concept | Becomes |
| :-- | :-- |
| `dispatch_personnel` | `ReservationPersonnel` (child) |
| `dispatch_consumable` | resolved via `PartDemand` — see §4 |
| `dispatch_meter_reads` | `ReservationMeterRead` (child) |
| `requested_capability` / `requested_skill` | `ReservationRequirement` (child) |
| group dispatches | `ReservationGroup` (parent FK, nullable) |
| `dispatch_request_templates` + 6 template child tables | deferred entirely — see §5 |

`Reservation` holds no FK to any of them and does not know they exist. A
reservation with zero children **is** the simple reservation; there is no
"upgrade" operation, no migration between models, no type conversion. Adding a
person to a reservation is just inserting a child row.

### 2.3 One discriminator, for UI only

Add `reservation_kind` = `SIMPLE | DISPATCH`. It selects which editor and
which detail-card set to render — nothing else. **It must never branch a
business rule.** Rules key off the data (does this reservation have personnel?
does it have requirements?), never off the label. Same discipline as
`PartDemand.source_module` in [01](01_demand_issuance_grouping.md): a
display/routing convenience with a docstring that says so, and a review rule
that catches the first `if kind == DISPATCH:` in a policy class.

Without it the UI has to infer intent from emptiness, and a dispatch that
hasn't had its personnel added yet is indistinguishable from a simple
reservation. With it, the flag is honest about being a UI affordance.

### 2.4 Alternative outcomes: drop the machinery

- **Reject** → `status = CANCELLED` with a `cancellation_reason`. It was never
  a different kind of object.
- **Contract / reimbursement** → out of scope for the rebuild. If they come
  back, they come back as their own tables with their own FK to the
  reservation that prompted them — a reservation resolved by hiring a
  contractor is *still a cancelled reservation*, plus a separate commercial
  record. That relationship points inward and needs no polymorphic pointer.

This is what kills three policy classes and the entire
`alternative_outcomes/` + `virtual_dispatch_outcome` layer.

## 3. Policies worth carrying over

Of the eight legacy policies, three (`active_pointer`, `outcome_uniqueness`,
`intent_lock`) die with the schema. Of the rest:

- **`double_booking`** — **build this on day one.** It is not an enhancement;
  it is the entire value proposition of a reservation. An overlapping-window
  guard on `(asset, [scheduled_start, scheduled_end))` for rows in
  `RESERVED`/`IN_PROGRESS`. Worth a real database-level exclusion constraint if
  the backend supports it, and a `ReservationOverlapGuard` regardless.
- **`asset_dispatchability`** — keep. Rename to reservability. Should read
  asset status and any active maintenance blocker rather than owning its own
  flag; cross-check against `maintenance.maintenance_blocker_manager` so the
  two don't disagree about whether an asset is available.
- **`dispatch_status_validation`** → one `ReservationStateMachine` over the
  single status field. One machine, not four.
- **`parts_availability`**, **`manifest_uniqueness`** → dispatch-tier only,
  defer with the manifest.

**Hard rule from the legacy postmortem: one status column per table.** No
"legacy field kept for compatibility." That comment is how legacy ended up with
four state fields and no clear answer to "what state is this in."

## 4. Cross-app seams — all three already exist

- **Events.** Legacy `DispatchRequest` was an `EventDetailVirtual`. This repo
  already has `events.models.details.DispatchingDetail` — multi-table
  inheritance from `Event`, currently a two-field stub (`destination`,
  `resource_reference`). **Decide before writing any model:** is `Reservation`
  that detail table grown up, or is it a standalone model in a new
  `app/dispatching/` that *emits* dispatching events? Legacy chose the former.
  The events app here is heavier (activity threads, attachments, comments) and
  the inheritance is real MTI with a real join, so this is a genuine fork in
  the road, not a formality. Getting it wrong is expensive to undo.
- **Part demands.** `DemandSourceModule.DISPATCHING` already exists. A
  reservation needing consumables creates `PartDemand` rows with
  `source_module="dispatching"` — and, per
  [01](01_demand_issuance_grouping.md), `source_activity="reservation"` with
  `source_parent_identifier` = the reservation id. **This is the second
  consumer that makes those columns pay for themselves**, and it's the reason
  to settle doc 01 before this build rather than after. Legacy's
  `dispatch_consumable` table doesn't need to come across at all.
- **Assets.** Reservation needs asset availability and asset class. Read-only
  dependency, no new coupling.

## 5. Explicitly deferred

Say no to these out loud now, so they don't leak in during the build:

- **Request templates** — seven legacy tables
  (`dispatch_request_templates` + six `template_requested_*`). A whole
  parallel schema for pre-filling a form. Defer until someone asks twice.
- **Capabilities and skills registries** — the `details_types/` subtree, two
  registries plus join tables plus factories plus managers. Defer with the
  dispatch tier.
- **Group dispatches** — a nullable `group` FK is enough scaffolding; don't
  build group orchestration until a group exists.
- **Calendars** — legacy has three services (`my_calendar`, `asset_calendar`,
  `dispatcher_calendar`). Ship a plain reservation list with date filters
  first. The calendar is the second thing users ask for and the first thing
  that eats a week.

## 6. Build order for tomorrow

1. **Decide the events question in §4** — everything else hangs off it.
2. `Reservation` model, single status field, `ReservationStateMachine`,
   `ReservationOverlapGuard` (double-booking).
3. `python refresh_project.py`.
4. Control layer: `ReservationFactory`, `ReservationContext`,
   `ReservationStateManager`. Writes never from entrypoints — see the layer
   findings in [02](02_maintenance_code_review.md), and don't repeat them in a
   fresh app.
5. Entrypoints: list (with date + asset filters), detail, create, cancel,
   check-out (`actual_start`), check-in (`actual_end`).
6. Topnav: add a **Dispatching** portal group to
   `app/public_app/templates/shared/topnav.html` — the **D** in CJB-DIODE is
   currently the only letter with no application behind it.
7. Tests for the overlap guard and every state transition. The overlap guard
   especially — it is the one rule where a bug means two crews show up for the
   same excavator.
8. *Only then*, if wanted: child tables for personnel, meter reads,
   requirements.

## 7. The one thing to watch

The failure mode isn't building the reservation table wrong — it's
**rebuilding the dispatch tier by reflex** because the legacy code is sitting
right there and it's easier to port than to decide. Steps 1–7 are a complete,
shippable product on their own. Ship them, use them, and let the second tier be
pulled by an actual request rather than pushed by the existence of old code.
