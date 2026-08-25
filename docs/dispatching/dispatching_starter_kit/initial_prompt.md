# Dispatching Port — Schema, Control Layer, UI

> # ⛔ SUPERSEDED — DO NOT USE
>
> Superseded by the three build plans — [build_phase_1_models.md](build_phase_1_models.md), [build_phase_2_control_layer.md](build_phase_2_control_layer.md), [build_phase_3_ui.md](build_phase_3_ui.md). Its phasing and 'settled tweaks' predate the redesign and are wrong.
>
> **Start at [HANDOFF.md](HANDOFF.md).** Kept only for provenance; safe to delete.

Reoriented from `portprompt.md`, which targets **one UI page at a time**. This kit widens that
to the whole module and puts the phases in order.

    NEW (EBAMS-2):  /home/cb/REPOS/ebams2/app/dispatching/  (new sub-app)
    OLD (legacy):   /home/cb/REPOS/asset_management/app/{data,business,intermediate,presentation}/dispatching/

---

## Phasing — port first, refactor second

**Phase 1 (this kit): get it across and working.** Build the schema with the five settled
tweaks below, port the control layer, port the UI. Reproduce legacy's structure faithfully
except where the tweaks say otherwise.

**Phase 2 (later): feature migration and refactor.** Once dispatching runs in EBAMS-2, revisit
the structural questions the port deliberately left alone. models_review.md §7.5 is the list.

The point of the split is that a working port is a fixed reference. Refactoring during the
port means changing two things at once and having nothing to compare against when it breaks.
**Resist improving things mid-port.** models_review.md §7.6 lists the tempting ones.

### The five settled tweaks

Applied during Phase 1, not deferred. Full detail in models_review.md §7.3.

1. **`MajorLocation` is superseded by the Data Domain primitive.** No such table is built.
   `major_location_id` disappears from both the request and the template; `domain` does that
   job. Free-text location fields (`activity_location`, `location_from`/`location_to`) stay.
2. **`DispatchSkill` / `UserDispatchSkill` are built under `dispatching`** — models, control
   layer, guards, entrypoints, templates, URLs. They arguably belong under `administration`;
   they go here anyway because dispatching is the only consumer.
3. **`StandardDispatch` → `AssetReservation`.** A **Dispatch** is now the whole picture —
   required capabilities, skills, models, parts, personnel, **and asset reservations**. An
   **Asset Reservation** is one constituent of it.
4. **`AssetReservation.status` is kept**, alongside `resolution_status`. An individual
   reservation carries its own lifecycle. This is the one exception to dropping legacy's
   duplicate `status` columns.
5. **New `ReservationUpdate` table** — the formal record of changes to a reservation,
   deliberately *not* the comment system. Create it with its FK to `AssetReservation` and
   leave the remaining columns for later; the control-layer port decides what belongs there.

---

## Reference material — read in this order

1. **[models_review.md](models_review.md)** — every legacy table, every column, and an
   FK-by-FK review locating each analogue in the current schema. This is the source of truth
   for what gets built. Start at §7.3 (settled decisions), §7.4 (still open), and §7.1
   (counts) for orientation.
2. **[model_diagram.md](model_diagram.md)** — the same relationships as Mermaid diagrams:
   cluster maps for both systems, per-cluster ER diagrams, a delta diagram per transformation,
   and the reverse-FK tables that drive the form-vs-wizard decision (§5). Fastest way to get
   oriented before reading any code.
3. `app/data/dispatching/` in the legacy repo — the models themselves, if a column's intent
   is unclear from the review.
4. `app/business/dispatching/` — the control layer to port. Structure:

   ```
   context.py                     ← DispatchContext, the primary route-facing interface
   state_machine.py               ← request workflow transitions
   outcome_manager.py             ← picks/creates/swaps the active outcome
   narrator.py                    ← machine comment text
   errors.py
   full_request_struct.py         ← read struct assembling request + manifest + outcomes
   base_outcome_handler.py
   alternative_outcomes/          ← contract_handler, reimbursement_handler, reject_handler
   dispatch_manifest/             ← checkout_manager, dispatch_handler,
                                    dispatch_manifest_struct, dispatch_meter_read_service
   request_manifest/              ← request_builder, request_manager,
                                    request_manifest_editor, request_manifest_struct
   template_request/              ← template_manager, template_manifest_struct,
                                    template_revision
   details_types/skills/          ← dispatch_skill_factory, skill_manager,
                                    dispatch_user_skills_struct
   details_types/capabilities/    ← capability_manager, dispatch_capability_factory,
                                    dispatch_asset_capabilities_struct
   policies/                      ← active_pointer, asset_dispatchability,
                                    dispatch_status_validation, double_booking,
                                    intent_lock, manifest_uniqueness, outcome_uniqueness,
                                    parts_availability
   ```

5. `app/intermediate/dispatching/` — read-side services (calendars, filtered lists, search).
   These map to EBAMS-2's `presentation_layer/search/` and `control_layer/adapters/`, not to
   the write path.
6. `app/presentation/routes/dispatching/` and its templates — the UI to port, once the control
   layer underneath it exists.

**Order matters:** schema → control layer → UI. A UI ported against a half-built control layer
ends up with logic in the entrypoint, which `harness/Architecture/layer_rules.md` forbids and
which is tedious to unpick later.

**Screenshots:** `maintenance_starter_kit/legacy_ui/screenshots/` covers maintenance, not
dispatching. Capture dispatching's pages from the running legacy app when you reach the UI
phase — `maintenance_starter_kit/legacy_ui/capture_screenshots.py` has a working
login-then-shoot script to crib from.

---

## Navigating the legacy app

Legacy is a three-layer Flask app: `data/` (SQLAlchemy models) → `business/` (write logic,
one folder per bounded concern) → `intermediate/` (read services) → `presentation/` (routes,
templates). Dispatching has a folder in all four.

Naming is nearly the same vocabulary EBAMS-2 uses, which makes the port mostly mechanical:

| Legacy suffix | EBAMS-2 suffix | Notes |
| :--- | :--- | :--- |
| `*Context` | `*Context` | Same role — the façade a caller holds |
| `*Manager` | `*Manager` | Same |
| `*Handler` | `*Handler` | Same |
| `*Factory` | `*Factory` | Same |
| `*Struct` | `*Struct` (`control_layer/domain_structs/`) | Same |
| `*Service` | usually `*Manager` or a search tool | EBAMS-2 has no `Service` suffix |
| `policies/*` | `*Policy` / `*_guard.py` | Legacy policies split into Policy classes and guard modules |
| `state_machine.py` | `*StateMachine` | Same |
| `narrator.py` | `*Narrator` | Same |

The class-suffix vocabulary is authoritative in
[harness/Architecture/patterns/oop_control_patterns.md](../harness/Architecture/patterns/oop_control_patterns.md).

**Do not trust legacy layering.** Legacy puts business logic on models
(`DispatchAsset.workflow_step`, `DispatchAsset.checkout_manager`) and imports business code
from the data layer. EBAMS-2 forbids both. See models_review.md §7.7.

---

## Running the legacy app

Back up the DB first, and do **not** use `./run` — it calls `z_clear_data.py`:

```bash
cp ~/REPOS/asset_management/instance/asset_management.db /tmp/old_db_backup.db
cd ~/REPOS/asset_management && nohup ./venv/bin/python3 app.py > /tmp/oldapp.log 2>&1 &
```

Log in as `admin` / `admin987654321!`. For the schema and control-layer phases, reading the
source is almost always faster than clicking through the app. For the UI phase, run it — the
screenshots are the spec.

EBAMS-2: `./run.sh` (`./stop.sh` to stop), log in as `generic_admin` / `changeme`
(see `default_users_passwords.json`).

---

## What "faithful" means here

**Schema and control layer:** reproduce the legacy **data relationships and business rules** —
every entity, every FK, every constraint, every state field that carries meaning, every guard.

**UI:** reproduce the legacy page's **information architecture and capabilities** — every card,
every field, every action, every empty state, in the same order and grouping. Do **not**
reproduce its visual style; this is Bulma + HTMX with sharp corners, not Bootstrap.

Do **not** reproduce:

- Legacy naming that is now wrong (`MakeModel` → `AssetModel`, `location_from_id` on a String)
- Vestigial columns legacy itself flags as transitional (`status` alongside
  `workflow_status`/`resolution_status`, `resolution_type`)
- Business logic on models
- Tables legacy already deprecated (`dispatch_capabilities`, `asset_dispatch_capabilities` —
  both superseded by `assets.CapabilityDefinition` / `assets.AssetCapability`)
- Legacy pages that are vestigial or wrong

Where legacy is wrong or vestigial, skip it and say so. models_review.md §7.7 lists the
anti-patterns I already found; flag anything further.

---

## Constraints

- `.claude/CLAUDE.md` always-apply rules. Rule #1 especially: **this port is a full
  `python refresh_project.py`**, not an incremental migration. Say so before running it.
- `harness/Architecture/layer_rules.md` — writes go through the control layer, never from an
  entrypoint. Reads may use search/adapters.
- `harness/Architecture/patterns/model_patterns.md` — no business logic on models; audit
  columns on every table; `BigAutoField` PKs.
- `harness/Authorization/data_ownership.md` — every scoped root entity needs a `domain` FK.
  No legacy dispatching table has one, and Data Domain now also absorbs what `MajorLocation`
  used to do. See models_review.md §0.4.
- `harness/UX_UI/` — `format=` for density and HTMX fragments, one canonical URL per resource,
  no parallel fragment-only routes, **assignment never in a modal**. The last one matters here:
  attaching skills, capabilities, parts, personnel, and assets to a request is the bulk of this
  UI. See `harness/UX_UI/design_patterns/modals.md`.
- CLAUDE.md rule #5 — a card renders even when empty, with an explicit empty state.
- **`inventory.PartIssue` may not be written directly.** Dispatching must call
  `PartIssuanceOrchestrator`; the demand's `issued_qty` only moves inside that call (D12).
  models_review.md §5.3.

---

## Definition of done — Phase 1

**Schema**

- [ ] The five open decisions in models_review.md §7.4 are answered and recorded
- [ ] `app/dispatching/models/` exists with all 24 tables, matching §8's layout
- [ ] The five settled tweaks above are applied — no `MajorLocation`, skills under
      `dispatching`, `AssetReservation` naming, its `status` kept, `ReservationUpdate` created
- [ ] `event_detail_dispatching` is fleshed out from its two-field stub (§1.1)
- [ ] Every constraint in models_review.md is expressed as a `Meta.constraints` entry
- [ ] Every enum-shaped `String` column is a `TextChoices`
- [ ] `python refresh_project.py` completes and re-seeds
- [ ] `./venv/bin/python manage.py check` passes

**Control layer**

- [ ] `DispatchContext`, the outcome handlers, the state machine, the eight policies, and the
      manifest managers ported — with tests for each new verb and guard
- [ ] No business logic on models; legacy's model-level properties relocated (§5.2)
- [ ] `ReservationUpdate`'s columns settled and filled in, informed by what the port revealed
- [ ] A dev seed command creates at least one request in each workflow state, one of each
      outcome type, and a reservation with updates

**UI**

- [ ] Every legacy dispatching page either ported or explicitly listed as deferred, with a
      reason
- [ ] Reachable from the sidebar and/or the topnav popover
      (`app/public_app/templates/shared/topnav.html`)
- [ ] Cross-linked from wherever the legacy pages were reached
- [ ] F5 rule holds — every state survives a plain full-page reload
- [ ] `format=` used for density and HTMX fragments; no parallel fragment-only routes
- [ ] Side-by-side screenshot pairs, old vs new

**Not in this phase:** anything in models_review.md §7.5.

---

## Report back

A short list of: what mapped cleanly, what you changed on purpose and why, what you skipped,
and what you're still unsure about. Don't bury a judgement call in a diff.
