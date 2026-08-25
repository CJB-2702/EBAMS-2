# Dispatching — Models Review (Legacy → EBAMS-2)

> ### ⚠️ Legacy reference only
>
> This describes the **old system**, column by column, and is still accurate for that purpose —
> use it to answer *"what did the old system store?"*
>
> Its **verdicts and recommendations are stale.** They predate the redesign: outcomes became
> line items, reservations became standalone, templates gained a lineage-plus-revisions shape.
> Do not follow them.
>
> **The design lives in [HANDOFF.md](HANDOFF.md)** and the documents it lists. Where the two
> disagree, the design documents win.


**Scope of this document:** every table the legacy dispatching module owns, its columns,
and — beneath each table — an FK-by-FK review locating the analogous table in the current
EBAMS-2 schema.

**Sources scanned (models only, per instruction):**

- Legacy: `/home/cb/REPOS/asset_management/app/data/dispatching/` (plus `data/core/` for base classes)
- Current: `app/*/models/` across `administration`, `assets`, `detail_extensions`, `events`,
  `inventory`, `maintenance`, `parts`, `procurement`

No control-layer, route, or template code was read for this pass. Verdicts about *behavior*
are inferred from column names and docstrings only and are marked as such.

**Companion document:** [model_diagram.md](model_diagram.md) draws the same FK relationships as
Mermaid diagrams — cluster maps, per-cluster ER diagrams for both systems, delta diagrams for
each transformation, and the reverse-FK tables the front-end kit consumes. Read this document
for *columns and verdicts*; read that one for *shape*.

---

## 0. Reading this document

### 0.1 Legacy base classes (columns you will not see repeated below)

Every legacy dispatching model inherits one of three bases. Their columns are implicit on
every table and are **not** re-listed per table.

| Legacy base | Columns it contributes | EBAMS-2 equivalent |
| :--- | :--- | :--- |
| `UserCreatedBase` | `id`, `created_at`, `created_by_id`, `updated_at`, `updated_by_id` | `AuditFieldsMixin` (`app/administration/models/auditable_mixin.py`) — exact match |
| `EventDetailVirtual` (extends `UserCreatedBase`) | `event_id` → `events.id`, `all_details_id` (global sequence), `asset_id` → `assets.id` | Django **MTI**: subclass `events.Event`. `all_details_id` is **dropped** — MTI's shared PK does the same job. |
| `VirtualDispatchOutcome` (abstract, extends `UserCreatedBase`) | `created_by_id` (NOT NULL override), `request_id` → `dispatch_requests.id`, `request_event_id` → `events.id`, `outcome_type`, `cancelled`, `cancelled_at`, `cancelled_by_id`, `cancelled_reason` | Django abstract model `AbstractDispatchOutcome(AuditFieldsMixin, SoftDeleteMixin)` — same pattern as `maintenance.AbstractActionItem` |

### 0.2 Status legend used in every FK review

| Symbol | Meaning |
| :--- | :--- |
| ✅ | Direct analogue exists in EBAMS-2; FK ports 1:1 |
| ⚠️ | Analogue exists but the **shape differs** — cardinality, naming, or semantics changed |
| ❌ | **No analogue.** Must be built, or the FK must be redesigned |
| 🆕 | Target is a new dispatching table introduced by this port |

### 0.3 Cross-cutting FK resolution table

Every distinct legacy FK target, resolved once. Per-table reviews below reference this.

| Legacy target table | Legacy model | EBAMS-2 model | EBAMS-2 table | Status |
| :--- | :--- | :--- | :--- | :--- |
| `users` | `User` | `administration.User` | `administration_user` | ✅ |
| `assets` | `Asset` | `assets.Asset` | `asset` | ✅ |
| `asset_classes` | `AssetClass` | `assets.AssetClass` | `asset_class` | ✅ |
| `make_models` | `MakeModel` | `assets.AssetModel` | `asset_model` | ⚠️ renamed |
| `events` | `Event` | `events.Event` | `event` | ⚠️ MTI, not FK |
| `major_locations` | `MajorLocation` | `administration.Domain` | `core_domain` | ✅ **superseded** — see §0.4 |
| `parts` | `PartDefinition` | `parts.Part` | `part` | ✅ |
| `part_issues` | `PartIssue` | `inventory.PartIssue` | `part_issue` | ⚠️ semantics widened |
| `part_demands` | `PartDemand` | `procurement.PartDemand` | `part_demand` | ✅ |
| `meter_history` | `MeterHistory` | `assets.MeterHistory` | `meter_history` | ⚠️ 1 row/4 meters → 1 row/meter |
| `capability_definitions` | `CapabilityDefinition` | `assets.CapabilityDefinition` | `capability_definition` | ✅ |
| `configuration_templates` | `ConfigurationTemplate` | `assets.ConfigurationTemplate` | `configuration_template` | ✅ |
| `defined_modifications` | `DefinedModification` | `assets.DefinedModification` | `defined_modification` | ✅ |
| `dispatch_capabilities` | `DispatchCapability` *(deprecated)* | `assets.CapabilityDefinition` | `capability_definition` | ⚠️ superseded upstream |
| `dispatch_skills` | `DispatchSkill` | *(this port — new table under `dispatching`)* | `dispatch_skill` | 🆕 — see §0.4 |
| `dispatch_requests` | `DispatchRequest` | *(this port)* | — | 🆕 |
| `dispatches` | `StandardDispatch` → **`AssetReservation`** | *(this port)* | `asset_reservation` | 🆕 renamed |
| `dispatch_request_templates` | `DispatchRequestTemplate` | *(this port)* | — | 🆕 |
| `requested_parts` | `RequestedPart` | *(this port)* | — | 🆕 |

### 0.4 Structural decisions — settled

**✅ `major_locations` → `administration.Domain`. Superseded, do not build.**
Legacy `MajorLocation` (`name`, `description`, `address`, `is_active`) was a site/facility
grouping. In EBAMS-2 that job belongs to the **Data Domain** primitive
(`administration.Domain`, table `core_domain`), which is already the row-level ownership and
scoping axis for `Asset`, `Event`, `PartDemand`, `PurchaseOrder`, `MaintenancePlan`, and every
other scoped entity. **No `MajorLocation` table is created.**

Consequences:

- `DispatchRequest.major_location_id` (NOT NULL) → the `domain` FK `DispatchingDetail`
  already inherits from `Event`. The column disappears; nothing replaces it.
- `DispatchRequestTemplate.major_location_id` (nullable pre-fill) → the template's own
  `domain` FK (§6.1).
- The two **free-text** location fields survive untouched, because they were never
  `MajorLocation` FKs: `DispatchRequest.activity_location` (String 255) and
  `AssetReservation.location_from` / `location_to` (String 100). Legacy's `_id` suffix on the
  latter pair is a naming lie — they are strings. See §2.1.

This collapses the legacy request's "where" into one axis (domain) plus free text, which is
what EBAMS-2 does everywhere else.

**🆕 `dispatch_skills` / `user_dispatch_skills` — new tables, owned by `dispatching`.**
EBAMS-2 has no skill model at all; the only trace is
`maintenance.ProtoActionItem.required_skills`, a free-text `TextField` — not a catalog and
not a per-user certification record. Both legacy tables port as new tables.

**Ownership:** a per-user skill/certification registry arguably belongs under
`administration`, next to roles and user assignments — `UserDispatchSkill` is a
user-attribute table, not a dispatching-transaction table. **Decision: build it under
`dispatching` anyway**, together with its control layer, entrypoints, and templates. The
dispatching port is the only consumer today, and moving a table between apps later is a
mechanical change; guessing at a shared cross-app skills model before a second consumer
exists is not. Recorded here so the eventual promotion to `administration` is a deliberate
move rather than a discovery. See §3.1, §3.2.

**⚠️ `domain` scoping is absent from every legacy table.**
EBAMS-2's row-level authorization requires a `domain` FK on scoped operational entities
(`Event`, `Asset`, `PartDemand`, `PurchaseOrder`, `MaintenancePlan`, … all carry one).
No legacy dispatching table has a domain column. Every new root-level dispatching table
(`DispatchRequest`, `AssetReservation`, `DispatchRequestTemplate`) needs one added, or must
inherit it — `DispatchRequest` gets it free from `Event` via MTI. Child/manifest rows can
scope through their parent.

---

## 1. Request core

### 1.1 `dispatch_requests` → `DispatchRequest`

**Legacy:** `app/data/dispatching/request.py` · `class DispatchRequest(EventDetailVirtual)`
**Proposed EBAMS-2:** `app/events/models/details/dispatching.py` · `class DispatchingDetail(Event)`
· table `event_detail_dispatching`

> **A stub already exists.** `app/events/models/details/dispatching.py` currently defines
> `DispatchingDetail(Event)` with just `destination` and `resource_reference` — two
> placeholder CharFields. This port **replaces** those two fields wholesale; nothing
> references them yet. This mirrors exactly how `MaintenanceDetail` was fleshed out from
> its own stub.

| Legacy column | Type | Null | Notes / EBAMS-2 disposition |
| :--- | :--- | :--- | :--- |
| `event_id` | FK `events.id` | NO | **Dropped** — MTI parent link (`event_ptr_id`) replaces it |
| `all_details_id` | Integer | NO | **Dropped** — global sequence made redundant by MTI shared PK |
| `asset_id` | FK `assets.id` | YES | Keep. Legacy semantics unclear (request has both this *and* `requested_asset_id`); see note below |
| `requested_by` | FK `users.id` | YES | Keep → `administration.User` |
| `requested_for` | FK `users.id` | NO | Keep → `administration.User` |
| `desired_start` | DateTime | NO | Keep. Overlaps `Event.event_start` — see note |
| `desired_end` | DateTime | NO | Keep. Overlaps `Event.event_end` — see note |
| `num_people` | Integer | YES | Keep |
| `names_freeform` | Text | YES | Keep |
| `asset_class_id` | FK `asset_classes.id` | NO | Keep → `assets.AssetClass` |
| `asset_subclass_text` | String(255) | NO | Keep — free text, no FK |
| `dispatch_scope` | String(50) | NO | Keep → `TextChoices` enum (values not discoverable from models alone) |
| `estimated_meter_usage` | Float | YES | Keep |
| `major_location_id` | FK `major_locations.id` | NO | **Dropped** — superseded by the `domain` FK inherited from `Event`. §0.4 |
| `activity_location` | String(255) | YES | Keep — free text |
| `notes` | Text | YES | Keep. Overlaps `Event.description` — see note |
| `requested_asset_id` | FK `assets.id` | YES | Keep → `assets.Asset` |
| `submitted_at` | DateTime | YES | Keep |
| `workflow_status` | String(50) | NO, def `Requested` | Keep → `TextChoices`: Requested, Submitted, UnderReview, FixesRequested, Planned, Resolved, Cancelled |
| `status` | String(50) | NO, def `Requested` | **Drop** — legacy self-documents this as "kept for compatibility during transition". Superseded by `workflow_status` and by `Event.status` |
| `active_outcome_type` | String(50) | YES | Keep — `'dispatch'\|'contract'\|'reimbursement'\|'reject'\|null` |
| `active_outcome_row_id` | Integer | YES | **Untyped pointer, no FK.** Half of a hand-rolled generic relation. Port as-is *or* replace with four nullable FKs; recommend keeping the legacy shape for phase 1 and revisiting |
| `resolution_type` | String(50) | YES | **Drop** — legacy comment: "Legacy field, may become redundant" |
| `previous_request_id` | FK `dispatch_requests.id` (self) | YES | Keep → self-FK |
| `created_from_template_id` | FK `dispatch_request_templates.id` | YES | Keep → 🆕 `DispatchRequestTemplate` |

**Field-overlap note (needs a decision, flagged not resolved):** `desired_start`/`desired_end`
duplicate `Event.event_start`/`Event.event_end`, and `notes` duplicates `Event.description`.
`MaintenanceDetail` resolved the same collision by *inheriting* the Event fields rather than
redeclaring. Whether dispatching does the same depends on whether "desired" and "actual
scheduled" are semantically distinct here — legacy keeps `desired_*` on the request and
`scheduled_*` on `AssetReservation`, which suggests they **are** distinct and both should stay.
Recommend: keep `desired_start`/`desired_end` as request intent, map `notes` → `Event.description`.

**`asset_id` vs `requested_asset_id`:** the request inherits `asset_id` from
`EventDetailVirtual` *and* declares `requested_asset_id`. From models alone their roles are
indistinguishable. Suspect `asset_id` is vestigial inheritance and `requested_asset_id` is the
real intent field. Flagged for control-layer pass.

#### FK review

| Legacy FK column | → legacy table | EBAMS-2 analogue | Status |
| :--- | :--- | :--- | :--- |
| `event_id` | `events` | `events.Event` via MTI parent link | ⚠️ becomes inheritance, not FK |
| `asset_id` | `assets` | `assets.Asset` | ✅ |
| `requested_by` | `users` | `administration.User` | ✅ |
| `requested_for` | `users` | `administration.User` | ✅ |
| `asset_class_id` | `asset_classes` | `assets.AssetClass` | ✅ |
| `major_location_id` | `major_locations` | `administration.Domain` (inherited from `Event`) | ✅ superseded |
| `requested_asset_id` | `assets` | `assets.Asset` | ✅ |
| `previous_request_id` | `dispatch_requests` | self | 🆕 |
| `created_from_template_id` | `dispatch_request_templates` | `DispatchRequestTemplate` | 🆕 |
| *(implied)* domain | — | `administration.Domain` | ✅ inherited from `Event` |

---

## 2. Outcomes

All four outcome tables share the abstract `VirtualDispatchOutcome` base (§0.1). Its FKs are
reviewed once here and not repeated per table.

#### Shared base FK review — `VirtualDispatchOutcome`

| Legacy FK column | → legacy table | EBAMS-2 analogue | Status |
| :--- | :--- | :--- | :--- |
| `request_id` | `dispatch_requests` | `DispatchingDetail` | 🆕 |
| `request_event_id` | `events` | `events.Event` | ✅ — but **redundant** once `request_id` points at an MTI subclass of Event, since `request.event_ptr_id == request.id`. Recommend dropping |
| `created_by_id` | `users` | `administration.User` | ✅ (via `AuditFieldsMixin`, tightened to `null=False`) |
| `cancelled_by_id` | `users` | `administration.User` | ✅ |

**Cancellation vs soft delete:** `cancelled` / `cancelled_at` / `cancelled_by_id` /
`cancelled_reason` is structurally identical to EBAMS-2's `SoftDeleteMixin`
(`is_deleted`/`deleted_at`/`deleted_by`) but semantically different — a cancelled outcome is
a real historical record, not a deleted one. Keep them as distinct explicit fields; do **not**
collapse into `SoftDeleteMixin`.

---

### 2.1 `dispatches` → `AssetReservation`

**Legacy:** `app/data/dispatching/dispatch_manifest/standard_dispatch.py`
**Proposed EBAMS-2:** `app/dispatching/models/outcomes/asset_reservation.py` · table `asset_reservation`

**Renamed: `StandardDispatch` → `AssetReservation`.**

The rename carries a concept change, not just a label change. In legacy, "the dispatch" *was*
this row — one outcome record with an asset bolted to it. In EBAMS-2:

> **A Dispatch is the whole picture** — the request plus everything it needs: required
> capabilities, skills, models, modifications, configuration templates, parts, personnel, and
> **asset reservations**. An **Asset Reservation** is one of those constituent parts: a block
> of time claimed against asset capacity, with its own lifecycle and its own status.

So `DispatchingDetail` (§1.1) is the dispatch, and `AssetReservation` is a thing the dispatch
contains — alongside the §4 request manifest and the §5 dispatch manifest.

The primary outcome: an asset and/or person is actually reserved and assigned.

| Legacy column | Type | Null | Notes |
| :--- | :--- | :--- | :--- |
| *(base)* | | | see §0.1 / §2 |
| `outcome_type` | String(50) | NO, def `dispatch` | Discriminator |
| `assigned_by_id` | FK `users.id` | YES | |
| `assigned_person_id` | FK `users.id` | YES | Redundant with the `dispatch_personnel` manifest — see note |
| `asset_dispatched_id` | FK `assets.id` | YES | Redundant with the `dispatch_assets` manifest — see note |
| `scheduled_start` | DateTime | NO | |
| `scheduled_end` | DateTime | NO | |
| `actual_start` | DateTime | YES | |
| `actual_end` | DateTime | YES | |
| `location_from_id` | String(100) | YES | **Named `_id` but is a String** — freeform text, not an FK. Legacy comment: "freeform or codes" |
| `location_to_id` | String(100) | YES | Same |
| `resolution_status` | String(50) | NO, def `Planned` | → `TextChoices`: Planned, In Progress, Complete, Cancelled |
| `status` | String(50) | NO, def `Planned` | **KEEP** — see note. This is the individual reservation's own status |
| `conflicts_resolved` | Boolean | def False | |

**`status` is kept — reversing my §7.5 recommendation.** Everywhere else in this document I
recommend dropping legacy's duplicate `status` columns, because legacy's own comments call
them transitional. **`AssetReservation` is the exception.** Now that a dispatch contains
*several* reservations, each reservation needs a status of its own — "this vehicle's block is
confirmed, that trailer's is still tentative" is a real distinction the dispatch-level status
cannot express. Two status fields with distinct jobs:

| Field | Scope | Answers |
| :--- | :--- | :--- |
| `resolution_status` | the outcome as a resolution of the request | Planned / In Progress / Complete / Cancelled |
| `status` | **this individual reservation** | the reservation's own lifecycle |

Both become `TextChoices`. The concrete `status` values are not discoverable from the models
alone (legacy defaults it to `Planned` and never constrains it) — settle them during the
control-layer port by reading `policies/dispatch_status_validation.py` and `state_machine.py`.

**Singular vs manifest duplication:** `assigned_person_id` and `asset_dispatched_id` are
single-value fields that the `dispatch_personnel` and `dispatch_assets` manifest tables
supersede. The `DispatchAsset` docstring explicitly argues *why* one asset is not enough
("truck + trailer, vehicle + generator"). These two columns look like pre-manifest leftovers
kept for convenience. Port them, but flag as candidates for removal after the control-layer
pass confirms nothing depends on them.

> **Deferred to the refactor phase:** the rename sharpens a tension that was already latent.
> If a Dispatch contains *many* asset reservations, then `AssetReservation` and `DispatchAsset`
> (§5.2) are describing the same thing at different grains — one reservation per asset is the
> natural end state, which would merge the two tables. **Do not do this during the port.**
> Legacy's shape (one outcome row, N manifest rows) ports as-is; the merge is a feature-level
> refactor to run once the control layer and UI are across and working.

**`location_from_id` / `location_to_id`:** the `_id` suffix on a `String(100)` is a naming
trap — these were never FKs, and with `MajorLocation` superseded by `domain` (§0.4) they never
will be. Rename to `location_from` / `location_to` as plain `CharField` to stop the suffix
lying.

#### FK review

| Legacy FK column | → legacy table | EBAMS-2 analogue | Status |
| :--- | :--- | :--- | :--- |
| `assigned_by_id` | `users` | `administration.User` | ✅ |
| `assigned_person_id` | `users` | `administration.User` | ✅ |
| `asset_dispatched_id` | `assets` | `assets.Asset` | ✅ |
| `location_from_id` | *(not an FK)* | — | ⚠️ misnamed String |
| `location_to_id` | *(not an FK)* | — | ⚠️ misnamed String |

---

### 2.2 `dispatch_contract_details` → `Contract`

**Legacy:** `app/data/dispatching/alternative_outcomes/contract.py`
**Proposed EBAMS-2:** `app/dispatching/models/outcomes/contract.py` · table `dispatch_contract`

Outcome: the need is met by contracting an outside company instead of dispatching own assets.

| Legacy column | Type | Null | Notes |
| :--- | :--- | :--- | :--- |
| *(base)* | | | see §0.1 / §2 |
| `outcome_type` | String(50) | NO, def `contract` | |
| `resolution_status` | String(50) | NO, def `Planned` | Planned, Complete, Cancelled |
| `company_name` | String(255) | NO | Free text — see note |
| `cost_currency` | String(10) | NO | |
| `cost_amount` | Float | NO | Use `DecimalField` in EBAMS-2 — money |
| `contract_reference` | String(255) | YES | |
| `notes` | Text | YES | |

**`company_name` is free text in legacy, but EBAMS-2 has `procurement.Vendor`.** A real
vendor registry now exists that legacy did not have. Adding `vendor` FK (nullable, alongside
the free-text field) is a cheap, non-breaking upgrade. Flagged as an **intentional
improvement candidate**, not part of a faithful port.

#### FK review

| Legacy FK column | → legacy table | EBAMS-2 analogue | Status |
| :--- | :--- | :--- | :--- |
| *(base FKs only)* | | | see §2 |
| *(none own)* | — | — | — |
| *(candidate)* `company_name` | *(free text)* | `procurement.Vendor` | ⚠️ upgrade available |

---

### 2.3 `dispatch_reimbursement_details` → `Reimbursement`

**Legacy:** `app/data/dispatching/alternative_outcomes/reimbursement.py`
**Proposed EBAMS-2:** `app/dispatching/models/outcomes/reimbursement.py` · table `dispatch_reimbursement`

Outcome: the requester uses their own means and is paid back.

| Legacy column | Type | Null | Notes |
| :--- | :--- | :--- | :--- |
| *(base)* | | | see §0.1 / §2 |
| `outcome_type` | String(50) | NO, def `reimbursement` | |
| `resolution_status` | String(50) | NO, def `Planned` | Planned, Complete, Cancelled |
| `from_account` | String(100) | NO | Free text account code |
| `to_account` | String(100) | NO | Free text account code |
| `amount` | Float | NO | Use `DecimalField` |
| `reason` | Text | NO | |
| `policy_reference` | String(255) | YES | |

No currency column — inconsistent with `Contract`, which has one. Flagged.

#### FK review

| Legacy FK column | → legacy table | EBAMS-2 analogue | Status |
| :--- | :--- | :--- | :--- |
| *(base FKs only)* | | | see §2 |
| `from_account` / `to_account` | *(free text)* | *(no account/GL model in EBAMS-2)* | ❌ no analogue — keep as text |

---

### 2.4 `dispatch_reject_details` → `Reject`

**Legacy:** `app/data/dispatching/alternative_outcomes/reject.py`
**Proposed EBAMS-2:** `app/dispatching/models/outcomes/reject.py` · table `dispatch_reject`

Outcome: request denied.

| Legacy column | Type | Null | Notes |
| :--- | :--- | :--- | :--- |
| *(base)* | | | see §0.1 / §2 |
| `outcome_type` | String(50) | NO, def `reject` | |
| `resolution_status` | String(50) | NO, def `Complete` | Reject is complete on creation. Complete, Cancelled |
| `reason` | Text | NO | |
| `rejection_category` | String(100) | YES | → `TextChoices`: Resource Unavailable, Policy Violation, Timing Conflict, Other |
| `notes` | Text | YES | |
| `alternative_suggestion` | Text | YES | |
| `can_resubmit` | Boolean | def False | |
| `resubmit_after` | DateTime | YES | |

#### FK review

| Legacy FK column | → legacy table | EBAMS-2 analogue | Status |
| :--- | :--- | :--- | :--- |
| *(base FKs only)* | | | see §2 |

Note: `can_resubmit` / `resubmit_after` pair with `DispatchRequest.previous_request_id` — the
resubmission lineage lives on the request, not here.

---

### 2.5 `reservation_update` → `ReservationUpdate` 🆕 **NO LEGACY EQUIVALENT**

**Legacy:** *(none — new in EBAMS-2)*
**Proposed EBAMS-2:** `app/dispatching/models/outcomes/reservation_update.py` · table `reservation_update`

The formal, structured record of changes to an `AssetReservation`. This is a **new table with
no legacy counterpart** — legacy narrated reservation changes through comments only.

**Deliberately NOT the comment system.** EBAMS-2's default narration path is
`events.Comment` on an `ActivityThread`, and `procurement.PartDemandUpdate`
(`app/procurement/models/demand/part_demand_update.py`) is the existing precedent for
choosing otherwise: a typed, queryable update row rather than prose a human has to read.
Reservation updates get the same treatment. Comments remain available for human discussion;
`ReservationUpdate` is for the machine-legible change record.

**Columns: deliberately left empty for now.** The shape depends on what the control-layer port
reveals about which reservation changes actually matter — reschedules, asset swaps, status
transitions, cancellations. Filling it in speculatively would guarantee a rewrite.

What is settled:

| | |
| :--- | :--- |
| Table name | `reservation_update` |
| Owning app | `dispatching` |
| Base | `AuditFieldsMixin` (gives `created_at` / `created_by` — the "who changed it, when") |
| Required FK | `reservation` → `AssetReservation`, `on_delete=CASCADE`, `related_name="updates"` |
| Not used | `events.Comment`, `events.ActivityThread` |

**Model to copy:** `procurement.PartDemandUpdate` — same job, same shape, already in this
codebase. It carries `part_demand` FK + `actor` FK + typed change fields. Read it before
designing this one.

#### FK review

| Column | → target | EBAMS-2 analogue | Status |
| :--- | :--- | :--- | :--- |
| `reservation` | — | 🆕 `AssetReservation` | 🆕 |
| *(remaining columns TBD)* | | | |

---

## 3. Skills catalog (dispatching-owned)

### 3.1 `dispatch_skills` → `DispatchSkill`

**Legacy:** `app/data/dispatching/details_types/skills/dispatch_skill.py`
**Proposed EBAMS-2:** `app/dispatching/models/skills/dispatch_skill.py` · table `dispatch_skill`

🆕 **New registry table, built under `dispatching`** — along with its full infrastructure:
control layer, guards, entrypoints, templates, URLs. Decision recorded in §0.4 (it arguably
belongs under `administration`; it goes here anyway, because dispatching is the only consumer
and relocating a table later is cheaper than guessing at a shared model now).

No analogue exists to reuse. Legacy's docstring draws the distinction explicitly:
`DispatchSkill` = "can you *operate* this?" (CDL, radio, site access) vs. maintenance skills =
"can you *fix* this?". EBAMS-2's only skill trace is
`maintenance.ProtoActionItem.required_skills`, a free-text `TextField` — no catalog, no
per-user record, no expiry.

| Legacy column | Type | Null | Notes |
| :--- | :--- | :--- | :--- |
| *(base)* | | | `UserCreatedBase` → `AuditFieldsMixin` |
| `skill_name` | String(255) | NO, **unique** | |
| `description` | Text | YES | |
| `skill_category` | String(50) | YES | → `TextChoices`: License, Certification, Training, Access, Other |
| `requires_expiry` | Boolean | NO, def False | |
| `uses_certification_levels` | Boolean | NO, def False | Gates the 1–5 level scale |
| `active` | Boolean | NO, def True | Map to EBAMS-2's `is_active` naming convention |

**Shape:** this is textbook "simple registry" — the `scaffold-registry` skill covers it
(uniqueness guard, create manager, form adaptor, list/create entrypoint, HTMX search).
Compare `parts.PartManufacturer` and `procurement.Vendor`.

**Needs a domain FK?** Every other EBAMS-2 catalog is either domain-scoped
(`maintenance.ProtoActionItem` has `domain`) or global (`assets.CapabilityDefinition`,
`parts.PartManufacturer` have none). `CapabilityDefinition` — the closest sibling, since
`RequestedDispatchCapability` and `RequestedDispatchSkill` are parallel structures — is
**global**. Recommend global, for symmetry.

#### FK review

| Legacy FK column | → legacy table | EBAMS-2 analogue | Status |
| :--- | :--- | :--- | :--- |
| *(none)* | — | — | — |
| *(reverse)* `user_skills` | `user_dispatch_skills` | 🆕 `UserDispatchSkill` | 🆕 |
| *(reverse)* `requested_in` | `requested_dispatch_skills` | 🆕 `RequestedDispatchSkill` | 🆕 |

---

### 3.2 `user_dispatch_skills` → `UserDispatchSkill`

**Legacy:** `app/data/dispatching/details_types/skills/user_dispatch_skill.py`
**Proposed EBAMS-2:** `app/dispatching/models/skills/user_dispatch_skill.py` · table `user_dispatch_skill`

Junction: user ↔ skill, with certification tracking. The personnel-matching filter reads this.

| Legacy column | Type | Null | Notes |
| :--- | :--- | :--- | :--- |
| *(base)* | | | |
| `user_id` | FK `users.id` | NO | |
| `skill_id` | FK `dispatch_skills.id` | NO | |
| `certification_level` | Integer | YES | CHECK 1–5 |
| `certification_date` | Date | YES | |
| `expiry_date` | Date | YES | |
| `certification_number` | String(255) | YES | |
| `notes` | Text | YES | |
| `active` | Boolean | NO, def True | → `is_active` |

**Constraints:** `UNIQUE(user_id, skill_id)`; `CHECK certification_level IS NULL OR BETWEEN 1 AND 5`.
Both port directly to `Meta.constraints` (`UniqueConstraint`, `CheckConstraint`).

#### FK review

| Legacy FK column | → legacy table | EBAMS-2 analogue | Status |
| :--- | :--- | :--- | :--- |
| `user_id` | `users` | `administration.User` | ✅ |
| `skill_id` | `dispatch_skills` | 🆕 `DispatchSkill` | 🆕 |

**Structural analogue in EBAMS-2:** `assets.AssetCapability` (asset ↔ `CapabilityDefinition`)
is the exact same junction-with-certification shape. Mirror its conventions.

---

### 3.3 `dispatch_capabilities` → **DO NOT PORT** *(deprecated in legacy)*

**Legacy:** `app/data/dispatching/details_types/capabilities/dispatch_capability.py`

Legacy's own `details_types/capabilities/__init__.py` marks this DEPRECATED and no longer
imported: "Capability data models have moved to the assets module." Legacy already repointed
`RequestedDispatchCapability.capability_id` at `capability_definitions.id`.

EBAMS-2's `assets.CapabilityDefinition`
(`app/assets/models/capabilities/capability_definition.py`, table `capability_definition`)
carries: `name` (unique), `code` (unique), `description`, `is_active`.

| Legacy column | EBAMS-2 field | Status |
| :--- | :--- | :--- |
| `capability_name` | `name` (unique) | ✅ |
| `description` | `description` | ✅ |
| `capability_category` | *(none)* | ❌ **missing** |
| `requires_expiry` | *(none)* | ❌ **missing** |
| `active` | `is_active` | ✅ renamed |
| *(none)* | `code` (unique) | 🆕 EBAMS-2 addition |

**Verdict:** ⚠️ superseded upstream — **but not at full parity.** Zero new dispatching tables,
however `capability_category` and `requires_expiry` genuinely do not exist on
`CapabilityDefinition`. Two options:

- Add both fields to `assets.CapabilityDefinition`. This is an **assets change**, not a
  dispatching one, and touches an app dispatching does not own.
- Drop them. `requires_expiry` is the load-bearing one — it gates whether a capability needs
  an expiry date on `AssetCapability`, which §3.4 shows is also missing. If both are dropped,
  dispatch capability matching loses expiry awareness entirely.

Recommend adding both to `assets`, and coordinating with whoever owns that app.

---

### 3.4 `asset_dispatch_capabilities` → **DO NOT PORT** *(deprecated in legacy)*

**Legacy:** `app/data/dispatching/details_types/capabilities/asset_dispatch_capability.py`

Same deprecation notice. Replaced by `assets.AssetCapability`
(`app/assets/models/capabilities/asset_capability.py`, table `asset_capability`), which
already links `assets.Asset` ↔ `assets.CapabilityDefinition`.

EBAMS-2's `assets.AssetCapability` (`app/assets/models/capabilities/asset_capability.py`,
table `asset_capability`) carries: `asset`, `capability_definition`, `is_active`, `qty`,
`notes`, and `UNIQUE(asset, capability_definition)`.

| Legacy column | EBAMS-2 field | Status |
| :--- | :--- | :--- |
| `asset_id` | `asset` | ✅ |
| `capability_id` | `capability_definition` | ✅ |
| `certification_date` | *(none)* | ❌ **missing** |
| `expiry_date` | *(none)* | ❌ **missing** |
| `notes` | `notes` | ✅ |
| `active` | `is_active` | ✅ renamed |
| `UNIQUE(asset_id, capability_id)` | `uq_asset_capability` | ✅ |
| *(none)* | `qty` | 🆕 EBAMS-2 addition |

**Verdict:** ⚠️ superseded upstream — **but the expiry-tracking columns are gone.** Same
decision as §3.3: `certification_date` and `expiry_date` must be added to
`assets.AssetCapability` (an **assets** change), or dispatching gives up expiry-aware
capability matching. The two gaps are paired — `CapabilityDefinition.requires_expiry` is
meaningless without `AssetCapability.expiry_date`, and vice versa. Decide them together.

Otherwise EBAMS-2 goes **further** than legacy here: it also has `AssetClassCapability` and
`ModelCapability` for class- and model-level capability declaration, which legacy lacked
entirely.

---

## 4. Request manifest — "what the requester asked for"

Six tables, all children of `dispatch_requests`, all `UserCreatedBase`. Each expresses one
kind of requirement. The `request_id → dispatch_requests.id` FK is identical on all six and
resolves to 🆕 `DispatchingDetail` in every case; it is not repeated in each FK table below.

### 4.1 `requested_dispatch_skills` → `RequestedDispatchSkill`

**Legacy:** `app/data/dispatching/request_manifest/requested_dispatch_skill.py`
**Proposed:** `app/dispatching/models/request_manifest/requested_skill.py` · table `dispatch_requested_skill`

| Legacy column | Type | Null | Notes |
| :--- | :--- | :--- | :--- |
| `request_id` | FK `dispatch_requests.id` | NO | |
| `skill_id` | FK `dispatch_skills.id` | NO | |
| `minimum_certification_level` | Integer | YES | CHECK 1–5 |
| `count_required` | Integer | NO, def 1 | CHECK > 0 |
| `is_required` | Boolean | NO, def True | True=required, False=preferred |
| `notes` | Text | YES | |

No unique constraint in legacy — the same skill *can* appear twice on one request. Probably an
oversight given `count_required` exists; flagged, not changed.

#### FK review

| Legacy FK column | → legacy table | EBAMS-2 analogue | Status |
| :--- | :--- | :--- | :--- |
| `request_id` | `dispatch_requests` | 🆕 `DispatchingDetail` | 🆕 |
| `skill_id` | `dispatch_skills` | 🆕 `DispatchSkill` | 🆕 |

---

### 4.2 `requested_dispatch_capabilities` → `RequestedDispatchCapability`

**Legacy:** `app/data/dispatching/request_manifest/requested_dispatch_capability.py`
**Proposed:** `app/dispatching/models/request_manifest/requested_capability.py` · table `dispatch_requested_capability`

| Legacy column | Type | Null | Notes |
| :--- | :--- | :--- | :--- |
| `request_id` | FK `dispatch_requests.id` | NO | |
| `capability_id` | FK `capability_definitions.id` | NO | Already repointed to assets module in legacy |
| `is_required` | Boolean | NO, def True | |
| `notes` | Text | YES | |

No unique constraint — inconsistent with `RequestedConfigurationTemplate` and
`RequestedModification`, which both have one. Recommend adding `UNIQUE(request, capability)`.

#### FK review

| Legacy FK column | → legacy table | EBAMS-2 analogue | Status |
| :--- | :--- | :--- | :--- |
| `capability_id` | `capability_definitions` | `assets.CapabilityDefinition` | ✅ |

**This is the cleanest FK in the whole port** — legacy already did the decoupling work, and
EBAMS-2's `capability_definition` table is a direct match.

---

### 4.3 `requested_parts` → `RequestedPart`

**Legacy:** `app/data/dispatching/request_manifest/requested_part.py`
**Proposed:** `app/dispatching/models/request_manifest/requested_part.py` · table `dispatch_requested_part`

| Legacy column | Type | Null | Notes |
| :--- | :--- | :--- | :--- |
| `request_id` | FK `dispatch_requests.id` | NO | |
| `part_id` | FK `parts.id` | NO | Legacy `PartDefinition` |
| `quantity_requested` | Float | NO | CHECK > 0 |
| `expect_return` | Boolean | NO, def False | Returnable vs consumable |
| `usage_notes` | Text | YES | |

#### FK review

| Legacy FK column | → legacy table | EBAMS-2 analogue | Status |
| :--- | :--- | :--- | :--- |
| `part_id` | `parts` (`PartDefinition`) | `parts.Part` | ✅ |

**Procurement interaction to resolve (control-layer scope, flagged here):** EBAMS-2 routes all
material need through the `procurement.PartDemand` hub — `maintenance` does not FK parts
directly for its live demands, it goes through `maintenance.MaintenanceDemandLink → PartDemand`.
Legacy dispatching *also* has a `part_demand_id` on `DispatchConsumable` (§5.3), so the hub
pattern is half-present in legacy. Whether `RequestedPart` should stay a direct `Part` FK
(request-time intent, no demand raised yet) or spawn a `PartDemand` is the single biggest
architectural question in this port. Preliminary read: **intent stays direct, issuance goes
through the hub** — which is exactly what legacy does.

---

### 4.4 `requested_make_models` → `RequestedMakeModel`

**Legacy:** `app/data/dispatching/request_manifest/requested_make_model.py`
**Proposed:** `app/dispatching/models/request_manifest/requested_model.py` · table `dispatch_requested_model`

| Legacy column | Type | Null | Notes |
| :--- | :--- | :--- | :--- |
| `request_id` | FK `dispatch_requests.id` | NO | |
| `make_model_id` | FK `make_models.id` | NO | |
| `quantity_requested` | Float | NO, def 1.0 | CHECK > 0. `Float` for a unit count is odd; recommend `PositiveIntegerField` |
| `usage_notes` | Text | YES | |

Constraint: `UNIQUE(request_id, make_model_id)`.

#### FK review

| Legacy FK column | → legacy table | EBAMS-2 analogue | Status |
| :--- | :--- | :--- | :--- |
| `make_model_id` | `make_models` (`MakeModel`) | `assets.AssetModel` | ⚠️ **renamed** |

**Naming:** legacy `MakeModel` became `assets.AssetModel` (table `asset_model`) in EBAMS-2,
with manufacturer split out into `assets.Manufacturer` via the `ModelManufacturer` M2M. So
"make" and "model" are now separate concepts. Recommend renaming the ported class/field to
`RequestedModel` / `model` to stop carrying the legacy compound name forward.

---

### 4.5 `requested_configuration_templates` → `RequestedConfigurationTemplate`

**Legacy:** `app/data/dispatching/request_manifest/requested_configuration_template.py`
**Proposed:** `app/dispatching/models/request_manifest/requested_configuration_template.py` · table `dispatch_requested_configuration_template`

Legacy docstring: intent-only, no enforcement on asset selection.

| Legacy column | Type | Null | Notes |
| :--- | :--- | :--- | :--- |
| `request_id` | FK `dispatch_requests.id` | NO | |
| `configuration_template_id` | FK `configuration_templates.id` | NO | |
| `is_required` | Boolean | NO, def True | |
| `notes` | Text | YES | |

Constraint: `UNIQUE(request_id, configuration_template_id)`.

#### FK review

| Legacy FK column | → legacy table | EBAMS-2 analogue | Status |
| :--- | :--- | :--- | :--- |
| `configuration_template_id` | `configuration_templates` | `assets.ConfigurationTemplate` | ✅ |

`assets.ConfigurationTemplate` exists at `app/assets/models/configurations/templates/configuration_template.py`
(table `configuration_template`) and even carries a `model` FK, `TemplateChild`, and
`TemplateModification` — richer than legacy. Direct match.

---

### 4.6 `requested_modifications` → `RequestedModification`

**Legacy:** `app/data/dispatching/request_manifest/requested_modification.py`
**Proposed:** `app/dispatching/models/request_manifest/requested_modification.py` · table `dispatch_requested_modification`

| Legacy column | Type | Null | Notes |
| :--- | :--- | :--- | :--- |
| `request_id` | FK `dispatch_requests.id` | NO | |
| `defined_modification_id` | FK `defined_modifications.id` | NO | |
| `is_required` | Boolean | NO, def True | |
| `notes` | Text | YES | |

Constraint: `UNIQUE(request_id, defined_modification_id)`.

#### FK review

| Legacy FK column | → legacy table | EBAMS-2 analogue | Status |
| :--- | :--- | :--- | :--- |
| `defined_modification_id` | `defined_modifications` | `assets.DefinedModification` | ✅ |

`assets.DefinedModification` exists at
`app/assets/models/configurations/modifications/defined_modification.py` (table
`defined_modification`), with `ModificationAssetClass` / `ModificationModel` applicability
junctions and `ActualModification` for installed instances. Richer than legacy. Direct match.

---

## 5. Dispatch manifest — "what actually went out"

Four tables, all children of `dispatches` (`AssetReservation`), all `UserCreatedBase`.

### 5.1 `dispatch_personnel` → `DispatchPersonnel`

**Legacy:** `app/data/dispatching/dispatch_manifest/dispatch_personnel.py`
**Proposed:** `app/dispatching/models/dispatch_manifest/dispatch_personnel.py` · table `dispatch_personnel`

| Legacy column | Type | Null | Notes |
| :--- | :--- | :--- | :--- |
| `dispatch_id` | FK `dispatches.id` | NO | |
| `user_id` | FK `users.id` | NO | |
| `role` | String(50) | NO, def `Passenger` | → `TextChoices`: Driver, Passenger, Operator, Crew Chief, Observer, Other |
| `checked_out_at` | DateTime | YES | |
| `checked_in_at` | DateTime | YES | |
| `confirmed_present` | Boolean | NO, def False | |
| `notes` | Text | YES | |

Constraint: `CHECK checked_out_at IS NULL OR checked_in_at IS NULL OR checked_out_at <= checked_in_at`.

#### FK review

| Legacy FK column | → legacy table | EBAMS-2 analogue | Status |
| :--- | :--- | :--- | :--- |
| `dispatch_id` | `dispatches` | 🆕 `AssetReservation` | 🆕 |
| `user_id` | `users` | `administration.User` | ✅ |

---

### 5.2 `dispatch_assets` → `DispatchAsset`

**Legacy:** `app/data/dispatching/dispatch_manifest/dispatch_asset.py`
**Proposed:** `app/dispatching/models/dispatch_manifest/dispatch_asset.py` · table `dispatch_asset`

**The widest table in the port** — 24 own columns, 7 FKs, a dual dispatcher/user checkout
audit trail, and its own per-asset Event.

| Legacy column | Type | Null | Notes |
| :--- | :--- | :--- | :--- |
| `dispatch_id` | FK `dispatches.id` | NO | |
| `asset_id` | FK `assets.id` | NO | |
| `event_id` | FK `events.id` | YES | Per-asset audit trail — one Event per dispatch-asset row |
| `planned_for` | FK `users.id` | YES | Explicitly **non-historical**; auto-synced to `user_checked_out_by_id` |
| **Dispatcher-recorded (authoritative)** | | | |
| `condition_out` | String(50) | YES | Good, Fair, Poor, Damaged |
| `condition_in` | String(50) | YES | Same |
| `checked_out_at` | DateTime | YES | **Real-world** time asset left, as stated by dispatcher |
| `checked_in_at` | DateTime | YES | **Real-world** time asset returned |
| `notes_out` | Text | YES | |
| `notes_in` | Text | YES | |
| **Dispatcher verification machine timestamps** | | | |
| `dispatcher_checkout_verified_at` | DateTime | YES | When the *paperwork* was done |
| `dispatcher_checkout_verified_by_id` | FK `users.id` | YES | |
| `dispatcher_return_verified_at` | DateTime | YES | |
| `dispatcher_return_verified_by_id` | FK `users.id` | YES | |
| **User-reported (audit trail)** | | | |
| `user_checked_out_at` | DateTime | YES | Machine timestamp of self-service form |
| `user_checked_out_by_id` | FK `users.id` | YES | |
| `user_condition_out` | String(50) | YES | |
| `user_notes_out` | Text | YES | |
| `user_checked_in_at` | DateTime | YES | |
| `user_checked_in_by_id` | FK `users.id` | YES | |
| `user_condition_in` | String(50) | YES | |
| `user_notes_in` | Text | YES | |
| **Line state** | | | |
| `line_status` | String(50) | YES, def `Planned` | Planned, Checked Out, In Use, Returned, Complete |

Constraints: two CHECKs enforcing `out <= in` independently for the dispatcher pair and the
user pair.

**Meter readings are NOT on this table** — they live in `dispatch_meter_reads` (§5.4), keyed
by `(asset_id, standard_dispatch_id)`.

**Model-layer properties to relocate:** legacy puts `is_checked_out`, `is_checked_in`,
`is_user_checked_out`, `is_user_checked_in`, `can_delete`, `workflow_step`, and a
`checkout_manager` factory property **on the model**. EBAMS-2 forbids business logic on models
(CLAUDE.md: "No business logic on models — schema and constraints only"). The read-only
derivations belong in a `DispatchAssetStruct`/`Context`; `checkout_manager` becomes a
`CheckoutManager` in the control layer, instantiated by the caller, not by the model.

#### FK review

| Legacy FK column | → legacy table | EBAMS-2 analogue | Status |
| :--- | :--- | :--- | :--- |
| `dispatch_id` | `dispatches` | 🆕 `AssetReservation` | 🆕 |
| `asset_id` | `assets` | `assets.Asset` | ✅ |
| `event_id` | `events` | `events.Event` | ✅ |
| `planned_for` | `users` | `administration.User` | ✅ |
| `dispatcher_checkout_verified_by_id` | `users` | `administration.User` | ✅ |
| `dispatcher_return_verified_by_id` | `users` | `administration.User` | ✅ |
| `user_checked_out_by_id` | `users` | `administration.User` | ✅ |
| `user_checked_in_by_id` | `users` | `administration.User` | ✅ |

**On `event_id`:** EBAMS-2 has a richer precedent than legacy. `assets.AssetEvent`
(table `asset_event`) is a dedicated asset↔event junction, and `Event` doubles as
`ActivityThread`/`FileSet` for comments and attachments. A per-dispatch-asset Event here gets
comments and file attachments for free via `events.Comment` and `events.Attachment`. Confirm
whether the per-asset Event should be a plain `Event` FK (as legacy) or route through
`AssetEvent` — a control-layer question, flagged.

---

### 5.3 `dispatch_consumables` → `DispatchConsumable`

**Legacy:** `app/data/dispatching/dispatch_manifest/dispatch_consumable.py`
**Proposed:** `app/dispatching/models/dispatch_manifest/dispatch_consumable.py` · table `dispatch_consumable`

| Legacy column | Type | Null | Notes |
| :--- | :--- | :--- | :--- |
| `dispatch_id` | FK `dispatches.id` | NO | |
| `part_id` | FK `parts.id` | NO | |
| `requested_part_id` | FK `requested_parts.id` | YES | Back-link to the original request line |
| `part_demand_id` | FK `part_demands.id` | YES | Link to the demand hub |
| `quantity_issued` | Float | NO | CHECK > 0 |
| `quantity_returned` | Float | YES, def 0 | CHECK >= 0 and <= issued |
| `expect_return` | Boolean | NO, def False | |
| `issue_part_issue_id` | FK `part_issues.id` | YES | Inventory-out transaction |
| `return_part_issue_id` | FK `part_issues.id` | YES | Inventory-in transaction |
| `notes` | Text | YES | |

#### FK review

| Legacy FK column | → legacy table | EBAMS-2 analogue | Status |
| :--- | :--- | :--- | :--- |
| `dispatch_id` | `dispatches` | 🆕 `AssetReservation` | 🆕 |
| `part_id` | `parts` | `parts.Part` | ✅ |
| `requested_part_id` | `requested_parts` | 🆕 `RequestedPart` | 🆕 |
| `part_demand_id` | `part_demands` | `procurement.PartDemand` | ✅ |
| `issue_part_issue_id` | `part_issues` | `inventory.PartIssue` | ⚠️ |
| `return_part_issue_id` | `part_issues` | `inventory.PartIssue` | ⚠️ |

**⚠️ `PartIssue` semantics widened in EBAMS-2.** `inventory.PartIssue`
(`app/inventory/models/issuance/part_issue.py`) now carries an `issue_type` discriminator —
`FOR_PART_DEMAND`, `DIRECT_TO_ASSET`, `DIRECT_TO_USER` — plus `session`, `from_room`,
`from_storage_location`, and stock provenance snapshots. Critically, its docstring states:

> "THE WRITE PATH IS THE SEAM, NOT THE TABLE. Creating a row here is not, by itself, an
> issuance: for `FOR_PART_DEMAND` rows, the demand's issued_qty and issuance_state only move
> when `PartIssuanceOrchestrator` calls `PartDemandContext.record_issuance()` in the same
> transaction (D12)."

So the two FK columns port cleanly, but **dispatching may not create `PartIssue` rows
directly** — it must go through `PartIssuanceOrchestrator`. This is the single most
consequential control-layer constraint the port inherits, and it did not exist in legacy.
It also means the `expect_return` / `quantity_returned` return leg needs an explicit
return-path verb; whether `PartIssuanceOrchestrator` already exposes one is a control-layer
question outside this pass.

**`part_demand_id` on a manifest row is already the EBAMS-2 pattern** — compare
`maintenance.MaintenanceDemandLink` (`action` + `part_demand`) and
`procurement.PurchaseOrderDemandLink`. Legacy is aligned here.

---

### 5.4 `dispatch_meter_reads` → `DispatchMeterRead`

**Legacy:** `app/data/dispatching/dispatch_manifest/dispatch_meter_reads.py`
**Proposed:** `app/dispatching/models/dispatch_manifest/dispatch_meter_read.py` · table `dispatch_meter_read`

One row per meter-reading event: per phase (checkout/return) × role (dispatcher/requestor).

| Legacy column | Type | Null | Notes |
| :--- | :--- | :--- | :--- |
| `standard_dispatch_id` | FK `dispatches.id` | NO | |
| `asset_id` | FK `assets.id` | NO | |
| `role` | String(20) | NO | CHECK IN ('dispatcher','requestor') |
| `phase` | String(20) | NO | CHECK IN ('checkout','return') |
| `meter1` | Float | YES | |
| `meter2` | Float | YES | |
| `meter3` | Float | YES | |
| `meter4` | Float | YES | |
| `meter_history_id` | FK `meter_history.id` | YES | Set when a dispatcher read updates core asset meters |
| `recorded_at` | DateTime | NO, def now | |
| `recorded_by_id` | FK `users.id` | YES | |

Legacy note: keyed by `(asset_id, standard_dispatch_id)` rather than `dispatch_asset.id`,
"because the reads are logically per dispatch-asset but looked up by the dispatch + asset pair."
That is a query-convenience justification for a weaker key. In EBAMS-2, `DispatchAsset` is the
natural parent and the pair is reachable through it. **Recommend re-keying to a single
`dispatch_asset` FK** — it eliminates the possibility of a meter read pointing at an
(asset, dispatch) pair that has no manifest row. Flagged as an intentional deviation, not a
faithful port.

#### FK review

| Legacy FK column | → legacy table | EBAMS-2 analogue | Status |
| :--- | :--- | :--- | :--- |
| `standard_dispatch_id` | `dispatches` | 🆕 `AssetReservation` | 🆕 |
| `asset_id` | `assets` | `assets.Asset` | ✅ |
| `meter_history_id` | `meter_history` | `assets.MeterHistory` | ⚠️ **cardinality change** |
| `recorded_by_id` | `users` | `administration.User` | ✅ |

**⚠️ The meter model changed shape.** Legacy `MeterHistory` stores **four meters in one row**
(`meter1`–`meter4` + `recorded_at` + `asset_id`). EBAMS-2 `assets.MeterHistory`
(`app/assets/models/core/meter_history.py`) stores **one meter per row**:

```
asset FK · meter_index (PositiveSmallIntegerField) · value (Float) · recorded_at · source
```

Consequences for this table:

- `meter_history_id` was a **1:1** link in legacy. In EBAMS-2 one dispatch meter read can
  produce **up to four** `MeterHistory` rows. A single nullable FK cannot express that.
- Two workable shapes: (a) keep `meter1`–`meter4` on `DispatchMeterRead` and replace the FK
  with a reverse relation — add a nullable `dispatch_meter_read` FK on... no, that is an
  `assets` change; instead (b) **normalize `DispatchMeterRead` to one row per meter**, adding
  `meter_index` + `value`, which makes `meter_history` a clean nullable 1:1 again and matches
  the EBAMS-2 meter model exactly.
- Option (b) is the better fit and is the recommendation, but it changes the table's grain
  from "one read event" to "one meter value", so `role`/`phase`/`recorded_at`/`recorded_by`
  become repeated. If that repetition is unacceptable, split into a header
  (`DispatchMeterRead`: dispatch_asset, role, phase, recorded_at, recorded_by) and a line
  (`DispatchMeterReadValue`: read, meter_index, value, meter_history FK).

**This is a real decision, not a mechanical mapping. It needs an answer before migration.**

`assets.AssetModel` carries `meter1_unit`–`meter4_unit`, so the four-slot concept survives at
the model level in EBAMS-2 — only the *history* table was normalized.

---

## 6. Template request — reusable request presets

Seven tables. `DispatchRequestTemplate` is the header; the other six mirror the §4 request
manifest one-for-one, swapping `request_id` for `template_id`. When a request is created from
a template, rows are copied across.

### 6.1 `dispatch_request_templates` → `DispatchRequestTemplate`

**Legacy:** `app/data/dispatching/template_request/dispatch_request_template.py`
**Proposed:** `app/dispatching/models/templates/dispatch_request_template.py` · table `dispatch_request_template`

| Legacy column | Type | Null | Notes |
| :--- | :--- | :--- | :--- |
| `title` | String(255) | NO | |
| `asset_class_id` | FK `asset_classes.id` | YES | Pre-fill |
| `major_location_id` | FK `major_locations.id` | YES | **Dropped** — superseded by this table's own `domain` FK. §0.4 |
| `asset_subclass_text` | String(255) | YES | |
| `dispatch_scope` | String(50) | YES | |
| `notes` | Text | YES | |
| `activity_location` | String(255) | YES | |
| `estimated_meter_usage` | Float | YES | |
| `num_people` | Integer | YES | |
| `deprecated` | Boolean | NO, def False | |
| `revision_of_template_id` | FK self | YES | Revision lineage |
| `revision_number` | Integer | NO, def 1 | |

Legacy explicitly does **not** store `requested_by`, `requested_for`, `desired_start`,
`desired_end` — always supplied at request time.

**Locking rule (business rule, recorded here because it's schema-adjacent):** a template
becomes read-only once any `DispatchRequest.created_from_template_id` points at it. New
revisions may only be cut from the current highest revision (the one no other template points
at). This is enforced in the control layer, not by a constraint.

**EBAMS-2 has a direct precedent for all of this.** `maintenance.TemplateActionSet` and
`maintenance.ProtoActionItem` both carry `prior_revision` self-FKs, and
`administration.TraceableHistoryMixin` provides an `origin_id` self-FK for exactly this
lineage pattern. Reuse rather than reinvent: the legacy pair
(`revision_of_template_id`, `revision_number`) maps onto `prior_revision` + a revision
counter, matching `TemplateActionSet`'s conventions.

Also note `TemplateActionSet` carries `domain` and an `activity_thread` OneToOne. A dispatch
request template should almost certainly carry both too — domain for scoping (§0.4), thread
for comments on the template itself.

#### FK review

| Legacy FK column | → legacy table | EBAMS-2 analogue | Status |
| :--- | :--- | :--- | :--- |
| `asset_class_id` | `asset_classes` | `assets.AssetClass` | ✅ |
| `major_location_id` | `major_locations` | `administration.Domain` | ✅ superseded |
| `revision_of_template_id` | self | self — model on `maintenance.TemplateActionSet.prior_revision` | 🆕 |
| *(needed)* `domain` | — | `administration.Domain` | ✅ add |
| *(candidate)* `activity_thread` | — | `events.ActivityThread` | ✅ add |

---

### 6.2 `template_requested_skills` → `TemplateRequestedSkill`

Mirrors §4.1. **Proposed table:** `dispatch_template_requested_skill`

| Legacy column | Type | Null | Notes |
| :--- | :--- | :--- | :--- |
| `template_id` | FK `dispatch_request_templates.id` | NO | |
| `skill_id` | FK `dispatch_skills.id` | NO | |
| `minimum_certification_level` | Integer | YES | CHECK 1–5 |
| `count_required` | Integer | NO, def 1 | CHECK > 0 |
| `is_required` | Boolean | NO, def True | |
| `notes` | Text | YES | |

#### FK review

| Legacy FK column | → legacy table | EBAMS-2 analogue | Status |
| :--- | :--- | :--- | :--- |
| `template_id` | `dispatch_request_templates` | 🆕 `DispatchRequestTemplate` | 🆕 |
| `skill_id` | `dispatch_skills` | 🆕 `DispatchSkill` | 🆕 |

---

### 6.3 `template_requested_capabilities` → `TemplateRequestedCapability`

Mirrors §4.2. **Proposed table:** `dispatch_template_requested_capability`

| Legacy column | Type | Null | Notes |
| :--- | :--- | :--- | :--- |
| `template_id` | FK `dispatch_request_templates.id` | NO | |
| `capability_id` | FK `capability_definitions.id` | NO | |
| `is_required` | Boolean | NO, def True | |
| `notes` | Text | YES | |

#### FK review

| Legacy FK column | → legacy table | EBAMS-2 analogue | Status |
| :--- | :--- | :--- | :--- |
| `template_id` | `dispatch_request_templates` | 🆕 `DispatchRequestTemplate` | 🆕 |
| `capability_id` | `capability_definitions` | `assets.CapabilityDefinition` | ✅ |

---

### 6.4 `template_requested_parts` → `TemplateRequestedPart`

Mirrors §4.3. **Proposed table:** `dispatch_template_requested_part`

| Legacy column | Type | Null | Notes |
| :--- | :--- | :--- | :--- |
| `template_id` | FK `dispatch_request_templates.id` | NO | |
| `part_id` | FK `parts.id` | NO | |
| `quantity_requested` | Float | NO | CHECK > 0 |
| `expect_return` | Boolean | NO, def False | |
| `usage_notes` | Text | YES | |

#### FK review

| Legacy FK column | → legacy table | EBAMS-2 analogue | Status |
| :--- | :--- | :--- | :--- |
| `template_id` | `dispatch_request_templates` | 🆕 `DispatchRequestTemplate` | 🆕 |
| `part_id` | `parts` | `parts.Part` | ✅ |

Note: unlike `RequestedPart`, this table has **no** `UNIQUE(template, part)`. Same gap as §4.1.

---

### 6.5 `template_requested_make_models` → `TemplateRequestedMakeModel`

Mirrors §4.4. **Proposed table:** `dispatch_template_requested_model`

| Legacy column | Type | Null | Notes |
| :--- | :--- | :--- | :--- |
| `template_id` | FK `dispatch_request_templates.id` | NO | |
| `make_model_id` | FK `make_models.id` | NO | |
| `quantity_requested` | Float | NO, def 1.0 | CHECK > 0 |
| `usage_notes` | Text | YES | |

Constraint: `UNIQUE(template_id, make_model_id)`.

#### FK review

| Legacy FK column | → legacy table | EBAMS-2 analogue | Status |
| :--- | :--- | :--- | :--- |
| `template_id` | `dispatch_request_templates` | 🆕 `DispatchRequestTemplate` | 🆕 |
| `make_model_id` | `make_models` | `assets.AssetModel` | ⚠️ renamed |

---

### 6.6 `template_requested_configuration_templates` → `TemplateRequestedConfigurationTemplate`

Mirrors §4.5. **Proposed table:** `dispatch_template_requested_configuration_template`

| Legacy column | Type | Null | Notes |
| :--- | :--- | :--- | :--- |
| `template_id` | FK `dispatch_request_templates.id` | NO | |
| `configuration_template_id` | FK `configuration_templates.id` | NO | |
| `is_required` | Boolean | NO, def True | |
| `notes` | Text | YES | |

Constraint: `UNIQUE(template_id, configuration_template_id)`.

#### FK review

| Legacy FK column | → legacy table | EBAMS-2 analogue | Status |
| :--- | :--- | :--- | :--- |
| `template_id` | `dispatch_request_templates` | 🆕 `DispatchRequestTemplate` | 🆕 |
| `configuration_template_id` | `configuration_templates` | `assets.ConfigurationTemplate` | ✅ |

**Name collision warning:** "template" means two different things in this one table —
a dispatch request template and an asset configuration template. Recommend naming the ported
fields `request_template` and `configuration_template` so the collision is impossible to
misread.

---

### 6.7 `template_requested_modifications` → `TemplateRequestedModification`

Mirrors §4.6. **Proposed table:** `dispatch_template_requested_modification`

| Legacy column | Type | Null | Notes |
| :--- | :--- | :--- | :--- |
| `template_id` | FK `dispatch_request_templates.id` | NO | |
| `defined_modification_id` | FK `defined_modifications.id` | NO | |
| `is_required` | Boolean | NO, def True | |
| `notes` | Text | YES | |

Constraint: `UNIQUE(template_id, defined_modification_id)`.

#### FK review

| Legacy FK column | → legacy table | EBAMS-2 analogue | Status |
| :--- | :--- | :--- | :--- |
| `template_id` | `dispatch_request_templates` | 🆕 `DispatchRequestTemplate` | 🆕 |
| `defined_modification_id` | `defined_modifications` | `assets.DefinedModification` | ✅ |

---

## 7. Roll-up

### 7.1 Table count

| Category | Count | Notes |
| :--- | ---: | :--- |
| Legacy dispatching tables total | **26** | |
| New tables to create | **24** | 4 outcomes + **1 `ReservationUpdate`** + 2 skills + 6 request manifest + 4 dispatch manifest + 7 template |
| ↳ of which have no legacy counterpart | **1** | `ReservationUpdate` — §2.5 |
| Existing tables altered | **1** | `event_detail_dispatching` — §1.1 fleshes out the stub rather than adding a table |
| Legacy tables NOT ported (deprecated upstream) | **2** | `dispatch_capabilities`, `asset_dispatch_capabilities` — §3.3, §3.4 |
| Legacy tables superseded by an existing primitive | **1** | `major_locations` → `administration.Domain` — §0.4 |
| Existing EBAMS-2 tables reused as FK targets | **13** | `administration_user`, `asset`, `asset_class`, `asset_model`, `event`, `part`, `part_issue`, `part_demand`, `meter_history`, `capability_definition`, `configuration_template`, `defined_modification`, **`core_domain`** |
| Missing prerequisite tables | **0** | `MajorLocation` no longer needed — §0.4 |
| Existing tables needing new columns | **2** | `capability_definition`, `asset_capability` — §3.3, §3.4 (an **assets** change) |

### 7.2 FK health scorecard

| Status | Distinct legacy FK targets | Which |
| :--- | ---: | :--- |
| ✅ Direct analogue | 9 | users, assets, asset_classes, parts, part_demands, capability_definitions, configuration_templates, defined_modifications, **major_locations → `Domain`** |
| ⚠️ Exists, shape differs | 4 | make_models→AssetModel (rename), events (MTI), part_issues (orchestrator seam), meter_history (grain change) |
| ⚠️ Table matches, **columns missing** | 2 | `capability_definition` (no `requires_expiry`, no category), `asset_capability` (no `certification_date`, no `expiry_date`) |
| ❌ No analogue | **0** | — |
| 🆕 New in this port | 5 | dispatch_requests, dispatches→`asset_reservation`, dispatch_request_templates, requested_parts, dispatch_skills |

**Overall:** the port is in good shape, and better than the first pass suggested — the
`major_locations` gap closed once Data Domain was recognized as its successor, leaving **zero
❌ FK targets**. Legacy already did the hard decoupling work on capabilities, and EBAMS-2's
`assets` app independently grew richer versions of exactly the three catalogs dispatching
depends on (capabilities, configuration templates, defined modifications).

### 7.3 Settled decisions

| Decision | Resolution | § |
| :--- | :--- | :--- |
| `MajorLocation` | **Superseded by `administration.Domain`.** No table built; the column disappears from request and template | §0.4 |
| `DispatchSkill` ownership | **Built under `dispatching`**, with its full infrastructure. Promotion to `administration` is a later, deliberate move | §0.4, §3.1 |
| `StandardDispatch` naming | **Renamed `AssetReservation`.** A Dispatch is the whole picture; a reservation is one constituent | §2.1 |
| `AssetReservation.status` | **Kept**, alongside `resolution_status` — an individual reservation needs its own lifecycle | §2.1 |
| Reservation change tracking | **New `ReservationUpdate` table**, columns TBD. Explicitly *not* the comment system | §2.5 |

### 7.4 Blocking decisions still open, in priority order

1. **Meter read grain** — legacy's 4-meters-per-row vs EBAMS-2's 1-meter-per-row makes
   `DispatchMeterRead.meter_history_id` unrepresentable as a single FK. §5.4
2. **`PartIssue` write path** — dispatching cannot create issue rows directly; it must call
   `PartIssuanceOrchestrator`. Confirm a return-leg verb exists. §5.3
3. ~~**Capability expiry tracking**~~ — **RESOLVED: cut as a feature.** No columns are added to
   `assets`. Asset capabilities become a plain has-or-has-not catalogue with no certification or
   expiry dimension. *User **skill** expiry is a separate thing and is retained — a lapsed CDL
   is a real operational fact.* See [design_drift.md](design_drift.md).
4. **`RequestedPart` vs the `PartDemand` hub** — does request-time intent raise a demand, or
   only issuance? §4.3
5. **Domain scoping** — `DispatchingDetail` inherits `domain` from `Event`. Do
   `AssetReservation` and `DispatchRequestTemplate` carry one directly, or scope through
   their parent? §0.4

### 7.5 Deferred to the refactor phase — NOT part of the port

The port reproduces legacy's structure with the tweaks above. These are feature-level changes
to run **after** the control layer and UI are across and working.

- **Merge `AssetReservation` and `DispatchAsset`.** If a Dispatch contains many reservations,
  one-reservation-per-asset is the natural end state and these two tables collapse into one.
  Legacy's shape (one outcome row, N manifest rows) ports as-is for now. §2.1, §5.2
- **Fill in `ReservationUpdate`'s columns** once the control-layer port shows which reservation
  changes actually need recording. §2.5
- **Drop `AssetReservation.assigned_person_id` / `asset_dispatched_id`** if the control-layer
  port confirms the manifests fully supersede them. §2.1
- **Re-key `DispatchMeterRead`** to a single `dispatch_asset` FK. §5.4
- **Promote `DispatchSkill` / `UserDispatchSkill` to `administration`** if a second consumer
  appears. §0.4

### 7.6 Free wins EBAMS-2 offers that legacy lacked

Not part of a faithful port; listed so they are not accidentally reinvented.

- **Comments and attachments for free.** Any table with an `Event` / `ActivityThread` link
  gets `events.Comment` + `events.Attachment` + `FileSet` galleries with no new tables.
  `DispatchAsset.event_id` already opens this door.
- **`procurement.Vendor`** exists — `Contract.company_name` can become a real FK. §2.2
- **Class- and model-level capabilities** (`AssetClassCapability`, `ModelCapability`) exist in
  `assets`; legacy only had per-asset. Capability matching can be smarter than legacy's.
- **Revision lineage is a solved pattern** — `TraceableHistoryMixin.origin_id` and
  `TemplateActionSet.prior_revision`. §6.1
- **`SoftDeleteMixin`** exists; legacy had no soft delete anywhere in dispatching.

### 7.7 Legacy anti-patterns not to carry across

- `DispatchRequest.status` alongside `workflow_status` — legacy's own comment calls it "kept
  for compatibility during transition", and `Event.status` already exists. Drop. §1.1
  **Exception: `AssetReservation.status` is KEPT** — an individual reservation needs its own
  lifecycle separate from `resolution_status`. §2.1
- `DispatchRequest.resolution_type` — legacy: "Legacy field, may become redundant." Drop. §1.1
- `location_from_id` / `location_to_id` are `String(100)`, not FKs, despite the `_id` suffix.
  Rename. §2.1
- Business logic on models (`DispatchAsset.workflow_step`, `.checkout_manager`, five `is_*`
  properties). Move to the control layer. §5.2
- `all_details_id` global sequence — MTI's shared PK replaces it. §0.1
- `active_outcome_row_id` as an untyped integer pointer. Port cautiously; revisit. §1.1

---

## 8. Proposed app layout

New sub-app `app/dispatching/`, following the standard layered structure. Model files only —
control/presentation layout is out of scope for this pass.

```
app/dispatching/
  models/
    __init__.py
    abstract_mixins.py                  # AbstractDispatchOutcome  (§0.1)
    outcomes/
      asset_reservation.py              # §2.1  (was StandardDispatch)
      contract.py                       # §2.2
      reimbursement.py                  # §2.3
      reject.py                         # §2.4
      reservation_update.py             # §2.5  NEW — no legacy counterpart
      enums.py                          # outcome_type, resolution_status,
                                        #   reservation status, rejection_category
    skills/
      dispatch_skill.py                 # §3.1
      user_dispatch_skill.py            # §3.2
      enums.py                          # skill_category
    request_manifest/
      requested_skill.py                # §4.1
      requested_capability.py           # §4.2
      requested_part.py                 # §4.3
      requested_model.py                # §4.4
      requested_configuration_template.py  # §4.5
      requested_modification.py         # §4.6
    dispatch_manifest/
      dispatch_personnel.py             # §5.1
      dispatch_asset.py                 # §5.2
      dispatch_consumable.py            # §5.3
      dispatch_meter_read.py            # §5.4
      enums.py                          # personnel role, condition, line_status, meter role/phase
    templates/
      dispatch_request_template.py      # §6.1
      template_requested_skill.py       # §6.2
      template_requested_capability.py  # §6.3
      template_requested_part.py        # §6.4
      template_requested_model.py       # §6.5
      template_requested_configuration_template.py  # §6.6
      template_requested_modification.py            # §6.7
```

`DispatchingDetail` (§1.1) stays in `app/events/models/details/dispatching.py`, matching how
`MaintenanceDetail` lives in `events` while the rest of maintenance lives in `app/maintenance/`.

**Migration note:** every table here is new, and §1.1 alters an existing one. Per CLAUDE.md
always-apply rule #1, this is a full `python refresh_project.py`, not an incremental migration.
