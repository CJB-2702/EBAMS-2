# Build Phase 1 — Models

Every table in the dispatching module, built in one schema pass.

---

## 0. The stance: rebuild, do not port

> **Write the data layer from the design documents. Do not translate legacy models.**

The legacy data layer is **not a source**. It is a **coverage checklist** — useful for asking
"did we forget something", useless as a thing to translate. Four reasons, any one of which
would be sufficient:

| | |
| :--- | :--- |
| **The concepts diverged** | Outcomes became line items. Reservations left the hierarchy and became standalone. Rejection moved onto the header. Parts became demands. Templates gained real revisioning. That is not refactoring — those are different objects |
| **The framework differs** | SQLAlchemy declarative with `db.Column` and `db.relationship` versus Django models, `TextChoices`, and `Meta.constraints`. Nothing copies |
| **The layering differs** | Legacy puts business logic on models (`DispatchAsset.workflow_step`, `DispatchAsset.checkout_manager`) and imports from `app.business` inside `app.data`. Both are forbidden here |
| **Half the tables are dead** | Two were already deprecated in legacy itself; four more describe concepts that no longer exist |

**Opening a legacy model file to decide what a new one should contain is the failure mode this
document exists to prevent.** The design documents are the specification. Legacy gets consulted
for one thing only: *what did we store that we might have forgotten?*

### 0.1 Where legacy IS still authoritative

| Still trust legacy for | Why |
| :--- | :--- |
| Screens, layout, workflow sequence | Explicit decision — the old UI is the UI specification. Phase 3 |
| The dual-track handover semantics | Legacy got this right. Design doc 3 §7.2 keeps it deliberately |
| Operational vocabulary | Condition values, personnel roles, rejection categories |
| Coverage | "Did we forget a field anyone actually used?" |

---

## 1. Reference material

### 1.1 Specification — the authority

| Document | Covers |
| :--- | :--- |
| [2_dispatch.md](2_dispatch.md) | Dispatch, requirements, intent, lifecycle |
| [3_asset_reservations.md](3_asset_reservations.md) | Reservation, update log, meter references |
| [4_dispatch_line_items.md](4_dispatch_line_items.md) | Expense, statuses |
| [1_dispatch_templates.md](1_dispatch_templates.md) | Template, revisions, template manifest |
| [5_roles_and_permissions.md](5_roles_and_permissions.md) | Custom permissions to declare on models |
| [design_drift.md](design_drift.md) | **Read §2.11 before adding any field.** Four cut features |
| [application_map.md](application_map.md) | Legacy route inventory with per-route verdicts — a coverage checklist |

### 1.2 Legacy — checklist only, never a source

Full paths under `/home/cb/REPOS/asset_management/app/data/dispatching/`:

| Legacy file | Verdict |
| :--- | :--- |
| `request.py` — `DispatchRequest` | **DISCARD.** Rebuild as `DispatchingDetail`. Drop `all_details_id`, `status`, `resolution_type`, `active_outcome_type`, `active_outcome_row_id`, `major_location_id`, `requested_asset_id` |
| `virtual_dispatch_outcome.py` — `VirtualDispatchOutcome` | **DISCARD ENTIRELY.** The outcome hierarchy no longer exists |
| `dispatch_manifest/standard_dispatch.py` — `StandardDispatch` | **DISCARD.** Rebuild as `AssetReservation`, standalone, per-asset |
| `dispatch_manifest/dispatch_asset.py` — `DispatchAsset` | **DISCARD.** Merges into `AssetReservation`. Its handover columns are the one part worth reading |
| `dispatch_manifest/dispatch_personnel.py` — `DispatchPersonnel` | **DISCARD.** Rebuild against the dispatch, not the reservation |
| `dispatch_manifest/dispatch_consumable.py` — `DispatchConsumable` | **DISCARD.** Replaced by demand links |
| `dispatch_manifest/dispatch_meter_reads.py` — `DispatchMeterRead` | **DISCARD ENTIRELY.** Two references into asset meter history replace the table |
| `alternative_outcomes/contract.py` — `Contract` | **DISCARD.** Merges into `DispatchExpense` |
| `alternative_outcomes/reimbursement.py` — `Reimbursement` | **DISCARD.** Merges into `DispatchExpense` |
| `alternative_outcomes/reject.py` — `Reject` | **DISCARD ENTIRELY.** Fields move onto the dispatch |
| `request_manifest/requested_dispatch_capability.py` | **DISCARD.** Rebuild |
| `request_manifest/requested_dispatch_skill.py` | **DISCARD.** Rebuild |
| `request_manifest/requested_make_model.py` | **DISCARD.** Rebuild as requested *model* |
| `request_manifest/requested_modification.py` | **DISCARD.** Rebuild |
| `request_manifest/requested_configuration_template.py` | **DISCARD ENTIRELY.** Not rebuilt as its own table — a configuration template is an optional attribute of a requested-model row (nullable FK on the same row), not a requirement kind of its own. See [1_dispatch_templates.md](1_dispatch_templates.md) §6.4 |
| `request_manifest/requested_part.py` — `RequestedPart` | **DISCARD ENTIRELY.** Replaced by demand links |
| `template_request/dispatch_request_template.py` | **DISCARD.** Revisioning is redesigned |
| `template_request/template_requested_*.py` — 6 files | **DISCARD.** Rebuild as 4 mirrors plus a material requirement (configuration template merges into the model mirror, not its own table) |
| `details_types/skills/dispatch_skill.py` | **DISCARD, rebuild faithfully.** The closest thing to a straight port. Keep expiry |
| `details_types/skills/user_dispatch_skill.py` | **DISCARD, rebuild faithfully.** Keep levels, dates, certificate number |
| `details_types/capabilities/dispatch_capability.py` | **IGNORE.** Deprecated in legacy already |
| `details_types/capabilities/asset_dispatch_capability.py` | **IGNORE.** Deprecated in legacy already |

Also relevant, outside the dispatching folder:

- `/home/cb/REPOS/asset_management/app/data/core/user_created_base.py` — the audit base. Replaced by `AuditFieldsMixin`
- `/home/cb/REPOS/asset_management/app/data/core/event_info/event.py` — `EventDetailVirtual`. Replaced by Django MTI
- `/home/cb/REPOS/asset_management/app/data/core/major_location.py` — **IGNORE.** Superseded by Data Domain

### 1.3 EBAMS-2 patterns to copy

Read these before writing anything — they are the house style:

| Pattern | Path |
| :--- | :--- |
| MTI event detail | `app/events/models/details/maintenance.py` |
| The stub to replace | `app/events/models/details/dispatching.py` |
| Abstract mixins for near-identical tables | `app/maintenance/models/abstract_mixins.py` |
| Revision lineage self-FK | `app/maintenance/models/templates/template_action_set.py` |
| Demand link to the hub | `app/maintenance/models/demand_link.py` |
| Typed update log | `app/procurement/models/demand/part_demand_update.py` |
| Registry table | `app/parts/models/supply/part_manufacturer.py` |
| Junction with certification | `app/assets/models/capabilities/asset_capability.py` |
| Activity thread OneToOne | `app/maintenance/models/planning/maintenance_plan.py` |
| Audit / soft delete mixins | `app/administration/models/auditable_mixin.py`, `soft_delete_mixin.py` |
| Meter history target | `app/assets/models/core/meter_history.py` |

---

## 2. Decisions to settle before the first migration

All three are now settled. Recorded here because each looks like an open choice when you reach
the file.

### D1 — A reservation is an `Event` subclass — **SETTLED: MTI**

`AssetReservation` subclasses `events.Event` via multi-table inheritance, exactly as
`DispatchingDetail` does. This requires **adding `RESERVATION` to `EventType`** — a small change
to the `events` app, and the only one dispatching forces on another app.

What it buys: parity with the dispatch as doc 3 §2.1 describes, presence on the asset timeline
through `assets.AssetEvent`, and `domain` / title / description inherited rather than declared.

**`AssetReservation.status` stays a separate field from `Event.status`.** The reservation
lifecycle — Tentative → Confirmed → CheckedOut → Returned, plus Cancelled and NoShow — is not
the event vocabulary and must not be forced into it.

### D2 — `DispatchSkill` lives under `dispatching` — **SETTLED**

Models, control layer, and screens all under `dispatching`. It looks like an `administration`
table and someone will ask; the reasoning is in doc 2 §6.2.

*"User capabilities system" throughout this kit means the **skills** registry — the catalogue
plus per-person certifications. There is no user-capability concept: capabilities are
asset-side, skills are user-side.*

### D3 — Templates are a lineage header plus revision rows — **SETTLED**

**Two tables, not one self-referencing chain.**

| Table | Holds |
| :--- | :--- |
| `dispatch_template` — the lineage | Domain, head-revision pointer, retirement, copied-from |
| `dispatch_template_revision` | Title, pre-fill values, change note, committed-by/at, prior revision — **and the entire requirement manifest** |

The manifest hangs off the **revision**, which is what makes a revision genuinely immutable. A
dispatch points at a **revision**, never at the lineage.

### D4 — Draft editing is session-held — **SETTLED, and it removes tables**

**There are no draft revision rows.** Editing loads the head into a working draft in the
session; nothing reaches the database until commit, at which point one revision and its whole
manifest are written in a single transaction.

Consequences for the schema:

| | |
| :--- | :--- |
| **No draft state** on a revision. Revisions are only current or superseded — and even that is derivable from the head pointer |
| **No "one draft per lineage" constraint.** Nothing to constrain |
| **No discard-draft path.** Abandoning clears a session key |

Concurrency is handled in the control layer, not the schema: a commit is refused if the head
moved while the draft was open. Doc 1 §3.3.

---

## 3. Tables to build

Twenty-one tables: twenty new, one altered.

### 3.1 Core

| # | Table | Notes |
| ---: | :--- | :--- |
| 1 | `event_detail_dispatching` | **ALTER.** Replace the two stub fields wholesale. MTI on `Event` |
| 2 | `asset_reservation` | D1. Own domain, status, type, one accountable person, two meter references, dual handover tracks |
| 3 | `reservation_update` | Typed change log. Copy `PartDemandUpdate`'s shape |
| 4 | `dispatch_expense` | Contract and reimbursement in one. Activity thread OneToOne. **No currency field** |
| 5 | `dispatch_personnel` | Crew roster. FK to the **dispatch**, not the reservation |

### 3.2 Dispatch requirements

| # | Table | Points at |
| ---: | :--- | :--- |
| 6 | `dispatch_requested_capability` | `assets.CapabilityDefinition` |
| 7 | `dispatch_requested_skill` | `dispatching.DispatchSkill` |
| 8 | `dispatch_requested_model` | `assets.AssetModel` |
| 9 | `dispatch_requested_modification` | `assets.DefinedModification` |
| ~~10~~ | ~~`dispatch_requested_configuration_template`~~ | **Removed.** Not its own table — `dispatch_requested_model` (8) carries a nullable `configuration_template` FK instead, since a configuration means nothing without a model as its subject. See [1_dispatch_templates.md](1_dispatch_templates.md) §6.4 |
| 11 | `dispatch_demand_link` | `procurement.PartDemand` — copy `MaintenanceDemandLink` |

### 3.3 Templates

| # | Table | Notes |
| ---: | :--- | :--- |
| 12 | `dispatch_template` | **The lineage.** Domain, head-revision FK, retirement fields, copied-from FK. No content |
| 13 | `dispatch_template_revision` | **The version.** Title, pre-fill values, revision number, change note, committed by/at, prior revision. `UNIQUE(template, revision_number)` |
| 14–17 | `dispatch_template_requested_{capability,skill,model,modification}` | Mirror 6–9. FK named **`revision`**, not `template`. The model mirror carries the same nullable `configuration_template` FK as its dispatch-side counterpart |
| 19 | `dispatch_template_material_requirement` | FK to **`revision`**. **Not** a demand link — a template holds part + quantity; instantiation raises the real demand |

**The manifest FK points at the revision.** Pointing it at the lineage would make revisions
mutable, which defeats the whole design.

### 3.4 Skills

| # | Table | Notes |
| ---: | :--- | :--- |
| 20 | `dispatch_skill` | Registry. **Keeps `requires_expiry`** |
| 21 | `user_dispatch_skill` | Level 1–5, certification and expiry dates, certificate number. `UNIQUE(user, skill)` |

### 3.5 Not built

Do not create these, and delete them if they appear:

`dispatch_requested_part` · `dispatch_consumable` · `dispatch_meter_read` · any outcome base or
subclass · `dispatch_reject` · `major_location` · any currency field · any capability expiry
field · any approval or sign-off table · **any template draft table or draft state** (D4).

→ [design_drift.md](design_drift.md) §2.11

---

## 4. Proposed layout

```
app/dispatching/
  models/
    __init__.py
    abstract_mixins.py          # AbstractRequirement, AbstractTemplateRequirement
    enums.py                    # scope, workflow status, reservation status/type,
                                #   expense type/status, revision state, condition
    reservations/
      asset_reservation.py
      reservation_update.py
    line_items/
      dispatch_expense.py
      dispatch_personnel.py
    requirements/
      requested_capability.py
      requested_skill.py
      requested_model.py              # carries the optional configuration_template FK
      requested_modification.py
      demand_link.py
    templates/
      dispatch_template.py           # the lineage
      dispatch_template_revision.py  # the version — manifest hangs off this
      template_requested_*.py        # four, FK to revision
      template_material_requirement.py
    skills/
      dispatch_skill.py
      user_dispatch_skill.py
```

`DispatchingDetail` stays at `app/events/models/details/dispatching.py`, matching how
`MaintenanceDetail` lives in `events` while the rest of maintenance lives in its own app.

**Ten near-identical requirement tables is the cost of the copy-on-instantiate design.**
Contain it with abstract mixins, as `app/maintenance/models/abstract_mixins.py` does — so
adding a requirement type is one mixin and two thin subclasses.

---

## 5. Rules that must land as constraints

Not documentation — `Meta.constraints`.

| Rule | Constraint |
| :--- | :--- |
| A requirement stated once per dispatch | `UNIQUE(dispatch, target)` on tables 6–10 |
| Same for template revisions | `UNIQUE(revision, target)` on 14–18 |
| Revision numbers unique per lineage | `UNIQUE(template, revision_number)` |
| One skill record per person | `UNIQUE(user, skill)` |
| Certification level in range | `CHECK level IS NULL OR 1 <= level <= 5` |
| Reservation window ordered | `CHECK scheduled_start <= scheduled_end` |
| Handover ordered, each track independently | Two `CHECK`s — doc 3 §4.4 |
| Quantities positive | `CHECK quantity > 0` |
| Expense amount non-negative | `CHECK amount >= 0` |
| *(no draft constraint — drafts are not rows)* | D4 |

Custom permissions from doc 5 §2 are declared in `Meta.permissions` on the owning model.

---

## 6. Traps

| Trap | Guard |
| :--- | :--- |
| Adding a currency field | design_drift §2.11 |
| Adding capability expiry columns to `assets` | design_drift §2.11 — user *skill* expiry is different and stays |
| Keeping a second `status` on the dispatch | design_drift §2.6 |
| Making `requested_assets` a real reference | doc 2 §4 — free-form, informational. **The warning comment on that field is required output** |
| Creating a per-asset line beside the reservation | doc 3 §4 — they are one table |
| A draft-state column on a revision | D4 — drafts live in the session |
| Hanging the template manifest off the lineage | D3 — it belongs to the revision |
| Putting crew or material on the reservation | doc 3 §11 |
| Business logic on a model | House rule. Legacy does it; do not copy it |
| Incremental migrations | Full project rebuild after any schema change |

---

## 7. Done when

- [ ] `RESERVATION` added to `EventType` (D1)
- [ ] All 20 new tables exist; `event_detail_dispatching` replaced
- [ ] None of §3.5 exists
- [ ] Every §5 rule is a `Meta.constraints` entry
- [ ] Every enum-shaped field is a `TextChoices`
- [ ] `requested_assets` carries its warning comment verbatim
- [ ] Ten requirement tables share abstract mixins
- [ ] Custom permissions declared
- [ ] No model carries business logic
- [ ] `python refresh_project.py` completes and re-seeds
- [ ] `./venv/bin/python manage.py check` passes
- [ ] Template manifest FKs point at the **revision**, not the lineage
- [ ] No draft table, no draft state anywhere
- [ ] A seed command produces: a template lineage with three committed revisions; skills with certified users; a standalone reservation; a dispatch with reservations, an expense, and demands
