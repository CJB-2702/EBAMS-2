# Dispatching Starter Kit

What the dispatching module should be, in terms of the goals it serves and the processes that
serve them.

> **Handing this to someone — or something — that has not seen it before?**
> Give them **[HANDOFF.md](HANDOFF.md)**. It carries the reading order, the settled decisions,
> the cut features, the build sequence, and the list of files that must not be read.

---

## Design documents

| # | Document | Subject |
| :--- | :--- | :--- |
| 1 | [1_dispatch_templates.md](1_dispatch_templates.md) | Reusable standards. **Proper revisioning** — draft, publish, supersede, retire, and copy |
| 2 | [2_dispatch.md](2_dispatch.md) | **The Dispatch** — the request *is* the dispatch. Intent, requirements, material demands, lifecycle, the portal |
| 3 | [3_asset_reservations.md](3_asset_reservations.md) | Standalone bookings. One asset, one window, one accountable person, one reservation type |
| 4 | [4_dispatch_line_items.md](4_dispatch_line_items.md) | Reservations and expenses as line items on a dispatch header. Narration |
| 5 | [5_roles_and_permissions.md](5_roles_and_permissions.md) | Seven personas, permission groups, roles, and endpoint-level scoping |

**Reading order: 2 → 3 → 4 → 1 → 5.**

| Also | |
| :--- | :--- |
| [design_drift.md](design_drift.md) | **Read before porting any legacy screen.** Every place the legacy UI's concepts disagree with this design, and the ten traps most likely to slip through |

## Build plans

| Phase | Document | Scope |
| :--- | :--- | :--- |
| 1 | [build_phase_1_models.md](build_phase_1_models.md) | All 20 tables, one schema pass |
| 2 | [build_phase_2_control_layer.md](build_phase_2_control_layer.md) | Every verb, guard, and policy — whole module |
| 3 | [build_phase_3_ui.md](build_phase_3_ui.md) | Pass-1 screens: dispatch templates and skills |

Each carries full paths to its legacy reference files and a per-file verdict — discard, rebuild,
or port.

**The stance, in one line:** rebuild the data and control layers from these documents; port only
the *screens*, and only their shape.

---

## The decisions these turn on

**1. A request and a dispatch are the same record.** The difference was whether it had been
resolved — a status, not a different kind of thing. → [2](2_dispatch.md) §1

**2. A reservation stands on its own.** One asset, one window, its own scope, status,
accountable person, and activity record. The dispatch link is optional. Book a truck for Tuesday
without filing anything. → [3](3_asset_reservations.md) §2

**3. A dispatch is a header with line items — there are no "outcomes".** Reservations are the
expected line item; expenses are attached when our assets are not the answer. Both coexist on
one job. Nothing is "selected". → [4](4_dispatch_line_items.md) §2

**4. Contracts and reimbursements are one record.** Same shape, different payee. Two parallel
records drift — and demonstrably did. → [4](4_dispatch_line_items.md) §3

**5. Rejection lives on the dispatch.** It never coexists with anything, never accrues cost, and
is terminal. A child record implied otherwise. → [2](2_dispatch.md) §9

**6. Material needs raise real demands.** No private wish list. A dispatch saying "this job
consumes 100 ft of wire" produces an issuable demand in the shared queue at the moment it is
filed. → [2](2_dispatch.md) §7

**7. Template revisions are immutable, and drafts live in the session.** A template is a lineage
plus revision rows; improving a standard commits a new revision beside the old one, so a
dispatch's reference never needs updating. Editing happens in a session-held working draft —
**four edits produce one revision, not four.** → [1](1_dispatch_templates.md) §2, §3

**8. Everything narrates onto the dispatch timeline.** Every meaningful line item change writes
a plain-language note to the job's activity record, automatically. A job history that assembles
itself. → [4](4_dispatch_line_items.md) §5

---

## Two paths, one boundary

> **Just need the asset?** → a reservation. Light path.
> **Need a crew, material, or money spent?** → a dispatch. Full path.

Promotion is one action. A standalone booking that turns out to need parts and a crew gets
attached to a new dispatch, keeping its identity, event, history, and handover record. Choosing
the light path wrongly costs one action to correct.

→ [3](3_asset_reservations.md) §11.1

---

## Scope — what is being built now

The module splits into two passes.

### Pass 1 — now

| | |
| :--- | :--- |
| **Data layer** | The whole module. Every record in documents 1–4 |
| **Control layer** | The whole module. Every verb, guard, and policy |
| **UI** | **Dispatch templates** and the **user skills and certifications** system only |

Both UI targets are self-contained registries with no dependency on the dispatch or reservation
screens. They are also the two things a dispatch needs to *exist* before it can be raised well —
standards to instantiate from, and certified people to assign.

### Pass 2 — deferred

The dispatch and reservation UI: the queue, review and planning, assignment, calendars,
checkout and return. Deferred deliberately — it is the largest surface, the one most tightly
coupled to the legacy screens, and the one that benefits most from a settled control layer
underneath it.

**The data and control layers are built in full in pass 1**, not just the parts pass 1's screens
touch. Building half a control layer means discovering its shape twice.

---

## Answered in this round

| Question | Answer |
| :--- | :--- |
| Template shape | **A lineage header plus revision rows.** The requirement manifest belongs to the revision, which is what makes it immutable → [1](1_dispatch_templates.md) §2 |
| Template revisioning | Edit a session-held working draft, then commit one revision with a change note. No draft rows, no locking. Copy-to-new-template is a separate, explicit operation → [1](1_dispatch_templates.md) §3 |
| Is a reservation an event? | **Yes — an `Event` subclass**, in parallel with the dispatch. Adds `RESERVATION` to the shared event types → [build_phase_1_models.md](build_phase_1_models.md) D1 |
| "User capabilities system" | The **skills** registry — catalogue plus per-person certifications. Capabilities are asset-side; skills are user-side |
| Dispatch scope values | On-site, local, regional, national, international → [2](2_dispatch.md) §5 |
| Requested assets | A free-form informational list, written once, **never** synced from reservations. Auto-reserves only assets free for the window → [2](2_dispatch.md) §4 |
| Required vs preferred | Informational only. Nothing auto-filters; dispatchers decide → [2](2_dispatch.md) §6.1 |
| Terminal state naming | `Closed` → **Completed**; `Resolved` → **Alternate Resolution** → [2](2_dispatch.md) §8 |
| Does a standalone reservation get an event? | Yes. The dispatch gets one, and every reservation gets its own → [3](3_asset_reservations.md) §2.1 |
| Meter readings | Owned by the asset. The reservation holds two references — initial and final → [3](3_asset_reservations.md) §7.3 |
| Accountable person | Exactly one, required → [3](3_asset_reservations.md) §5 |
| Sub-reservations | None. Assets moving as one unit of work is a dispatch → [3](3_asset_reservations.md) §4 |
| Maintenance holding an asset | A reservation with type *maintenance*, booked by the shop lead. **No enforcement** against maintenance records in either direction → [3](3_asset_reservations.md) §6.1 |
| Recurring bookings | Out of scope |
| Merging outcomes | Done, and reframed — see decisions 3, 4, 5 |
| Approval thresholds | **Out of scope.** Expenses record what happened; they are not requests for permission → [4](4_dispatch_line_items.md) §1.1 |
| Expense history and paperwork | Activity thread on every expense — file uploads and comments. History via comments, not a structured log → [4](4_dispatch_line_items.md) §3.4 |
| Multi-currency | **Cut.** One organisational currency → [4](4_dispatch_line_items.md) §3.3 |
| Cancelling a dispatch | Cancels unissued material demands; delegates to the demand side to decide what cancelling means → [2](2_dispatch.md) §13 |
| Overdue returns | **Nothing happens.** Explicitly a non-feature → [3](3_asset_reservations.md) §13 |
| Rental and customer counterparty | Not recorded. Reservation type is a rough consumer label → [3](3_asset_reservations.md) §6 |
| Asset capability expiry | **Cut as a feature.** User skill expiry is unaffected and retained → [design_drift.md](design_drift.md) §2.11 |
| Who may do what | Seven personas, fifteen permission groups, five roles → [5](5_roles_and_permissions.md) |

---

## Still open

| Question | Where | Blocks |
| :--- | :--- | :--- |
| Who may commit a revision — same permission as authoring, or separate? | [1](1_dispatch_templates.md) §9.1 | Pass 1 — currently split |
| Should requesters see newer template revisions exist? | [1](1_dispatch_templates.md) §9.2 | Pass 1 UI polish |
| How long should a working draft survive? | [1](1_dispatch_templates.md) §9.3 | Pass 1 UI polish |
| Cross-domain and personal templates | [1](1_dispatch_templates.md) §9.4, §9.5 | Nothing — additive later |
| Does Completed need automatic entry? | [2](2_dispatch.md) §14.1 | Pass 2 |
| Requester visibility of the auto-reserve outcome | [2](2_dispatch.md) §14.2 | Pass 2 |
| No-show handling — automatic or judgement? | [3](3_asset_reservations.md) §14.1 | Pass 2 |
| Can a line item be added after Completed? | [4](4_dispatch_line_items.md) §8.1 | Pass 2 |
| Reimbursement payee — always stated, or defaults? | [4](4_dispatch_line_items.md) §8.2 | Pass 2 |
| Should a shop lead see dispatches? | [5](5_roles_and_permissions.md) §6.1 | Pass 2 |

**None of these block pass 1.** All either concern the deferred screens or are additive.

---

## The portal

The dispatch experience is a **multi-page portal**, not one form.

**The presentation layer stays close to the old application.** The data layer changes
substantially — demands instead of wish lists, standalone reservations, expenses instead of
outcome types — but the screens, their sequence, and the dispatcher's habits carry over largely
intact. The old interface is the specification.

→ [2](2_dispatch.md) §11

---

## Legacy reference

| Document | Status |
| :--- | :--- |
| [application_map.md](application_map.md) | **Current.** All 93 legacy routes with source, template, and a verdict each |
| [models_review.md](models_review.md) | **Reference only.** Legacy columns are accurate; its verdicts predate the redesign |
| [model_diagram.md](model_diagram.md) | **Current.** Target diagrams in §1–§5, legacy in §6 |
| `questionnaire.md` · `old_application_map.md` · `initial_prompt.md` | ⛔ **Superseded.** Do not read — see [HANDOFF.md](HANDOFF.md) §2.4 |

---

## Build order

**Data layer, whole module.** Reservations, dispatch, line items, templates, skills. One schema
pass — any schema change means a full project rebuild, so doing it once is the cheap path.

**Control layer, whole module,** in dependency order:

1. **Skills and certifications** — a standalone registry, no dependencies
2. **Reservations** — the only operational part that works alone
3. **Dispatch** — header, requirements, material demands, lifecycle
4. **Line items** — expenses, cancellation, narration
5. **Templates** — revisioning, publication, instantiation into a dispatch

**UI, pass 1 only:** templates and skills. Both registries, both self-contained.

**UI, pass 2:** everything else.
