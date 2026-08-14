---
okf_version: "0.1"
type: "Process Guide"
title: "Decisions — Procurement"
description: "Numbered, confirmed decisions from the questionnaire and the 2026-08-08 unresolved-questions review session. Each decision states the options considered and why one won."
tags: [starter-kit-process, process-guide, decisions, okf]
context_tier: 2
personas: [backend, business]
---

# Decisions — Procurement

Confirmed answers, numbered so they can be referenced and re-evaluated later. Session dates noted
per decision. Earlier decisions from `questionnaire.md`'s 2026-08-02 review session are referenced
there directly (G4, M1–M5, P4-partial); this file starts numbering from the questions resolved in
the 2026-08-08 open-questions review session.

---

## Personas & permissions

**D1 — Requester is a real persona of this app, now, not a future-app stopgap.**
This app ships its own demand-creation UI; a user can create a `PartDemand` directly through it.
Rejected: treating direct-create as dev/admin-only scaffolding until Maintenance/Dispatching exist.

**D2 — Approve and Buy are independent, separately-grantable permissions, usually co-held.**
Not mutually exclusive roles. PO CRUD (create/edit) requires the Buy permission. Approvers
(holding the Approve permission) may additionally transition a PO's state to Approved, even
without the Buy permission. In practice most Buyers also hold Approve, but the system does not
assume it.

**D3 — Allocating a demand to a PO line (`DemandSetLine`) is Buyer-only.**
No other persona writes this join row.

**D4 — Cancelling a demand: Approver and Requester can cancel; Buyer de-links instead.**
A Buyer disconnects a demand from a PO (removes the `DemandSetLine` allocation) rather than
cancelling the demand itself — cancellation is an Approver/Requester action. See D10 for the gate
on cancelling once a PO is Ordered.

**D5 — Every `PartDemand` requires exactly one domain assignment. Mandatory, not optional.**
Supersedes the questionnaire's P4 "what percentage" framing — there is no percentage, every demand
is domain-scoped. Confirms the existing single-domain contract, removes ambiguity about
unrestricted demands existing at all.

---

## Deletion / lifecycle

**D6 — `PartDemand` supports hard delete only while untouched; otherwise soft-delete/deactivate.**
"Untouched" = zero related rows beyond creation (no PO links, no issuance, no journal activity).
Once anything has happened to a demand, deletion becomes deactivation, never a hard delete.

**D7 — Delete-guard mechanism: this app checks only its own tables; consumer apps self-protect via FK.**
Consumer apps (Maintenance, Dispatching, a future Inventory app) own their own join tables that FK
to `PartDemand.id` — never the reverse. This app's delete guard checks only its own related tables
(`DemandSetLine`, `PartIssuance`, the update journal). Cross-app protection comes for free from
`on_delete=PROTECT` on the consumer side's own FK to `PartDemand`, with zero import of consumer
internals required — satisfies R6's ignorance rule without a registry/callback mechanism.

**D8 — Cross-app UI composition: consumer apps expose small HTMX fragment endpoints.**
A generalizable pattern for showing another app's data on this app's pages (or vice versa) without
backend coupling — e.g. `/inventory/part-demand-status-card/<id>` rendered on-load via HTMX. Not
specific to deletion; recorded here because it surfaced while resolving D7.

---

## Cross-dimension gates (R4)

**D9 — `purchasing_state` cannot leave `null` until `demand_state` reaches Approved. (Revised
2026-08-08 — axis rename only, same rule.)**
Pre-existing decision (2026-08-02), restated for the four-axis model (see D32): `order_state` and
`workflow_state` are renamed `purchasing_state` and `demand_state`; the rule itself — an unapproved
demand cannot be purchased against — is unchanged.

**D10 — Cancelling a demand once its PO is active requires cancelling the PO first. (Revised
2026-08-08 — axis rename only, same rule.)**
A demand's `demand_state` cannot transition to Cancelled while its linked PO's `purchasing_state`
is `Approved` or `Purchased` and the PO itself is not cancelled. The PO must first be cancelled;
only then can the demand's `demand_state` move to Cancelled. Matches real purchasing practice — an
order in flight is cancelled at the order level before the underlying request is closed out.

**D11 — `issuance_state` may advance independently of `purchasing_state`/`shipment_state`. (Revised
2026-08-08 — axis rename only, same rule.)**
Issuing from existing stock on hand (no PO ever cut for this specific demand) is allowed —
`issuance_state` is not gated on the purchasing or shipment axes reaching any particular stage.

**D9a — `demand_state → Completed` is a derived rollup, not a human transition (new, 2026-08-08).**
Added when the fourth axis (`shipment_state`) split out from purchasing: `Completed` requires
`purchasing_state`, `shipment_state` (where a PO exists), and `issuance_state` to each independently
sit in one of their own terminal states. For a demand fulfilled entirely from stock with no PO ever
linked, `shipment_state` is treated as vacuously satisfied for this rollup — it never blocks
`Completed` on an axis the demand never used.

**D9–D11 and D9a are the complete gate set for this kit phase** (see D21 below — the general
`StageTemplate`/rules-engine mechanism that would have generalized this is deferred to tech debt;
these gates are implemented as plain hardcoded checks instead).

---

## Enforcement & seams

**D12 — Inventory advances Order/Issue state via a direct control-layer manager call.**
E.g. `PartDemandManager.record_issuance(demand_id, ...)`. Consistent with R6's established
one-directional dependency (Inventory depends on this app). The manager call itself is the truth —
physical issuance auto-transitions `issue_state` on that call; no separate Supply-side confirmation
step. Resolves R6's open seam and the boundaries-doc question ("who has authority to close out a
demand on physical issuance").

**D13 — Undecidable transition checks fail open, flagged for review.**
If a guard cannot determine whether a transition is legal, it allows the transition through and
logs/flags it for human review, rather than blocking work.

---

## Demand ↔ PO shape

**D14 — A `PurchaseOrder` can exist with zero linked demands.**
Proactive/bulk restocking is in scope. `PartDemand` and `PurchaseOrder` remain peers joined via
`DemandSetLine`; `PurchaseOrder` is never modeled as nested under `PartDemand`.

**D15 — `PartDemandUpdate.notes` stays optional free text, even for Rejected/Cancelled outcomes.**
No mandatory reason-for-rejection requirement.

---

## Purchase order events & the integration API

**D16 — The external HTTP integration surface is out of scope for this kit. Deferred to tech debt.**
No concrete external (non-Django) caller exists today. Building an HTTP endpoint + payload contract
+ service-account auth ahead of a confirmed need is not justified. See
`docs/procurement/tech_debt/20260808 external purchase order integration api.md`.

**D17 — `PurchaseOrder` gets one `Event` row (the `Event` surface class, not `ActivityThread`),
created alongside the PO.**
Not one `Event` row per status change — a single Event row per PO for its whole lifetime. Chosen
over `ActivityThread` specifically because `Event` carries the status/comments/attachments trio
this use case needs, while `ActivityThread` strips the event-specific columns. This supersedes the
questionnaire's M6 answer ("`PurchaseOrder` gets its own `events.ActivityThread`-backed event
trail") — same infrastructure family, corrected surface class.

**D18 — Status updates post as machine comments on the PO's Event, not a separate journal table.**
No `PurchaseOrderUpdate` table. A caller reporting a status change (today: only the internal
manager-call seam per D16; later, potentially an external caller) posts a comment to the PO's
existing `Event` comment stream. Rejects the "separate structured journal + free-form thread"
split that `PartDemandUpdate` vs. `PartDemand.notes` uses on the demand side — deliberately
different from that pattern, not an oversight.

**D19 — PO document library uses the Event's existing attachment support.**
No new document-library infrastructure — `Event`'s built-in direct-attachment capability covers it.

**D20 — A Django signal fires on each PO status-update comment, as an unbuilt extension point.**
No listener is implemented yet. This is a stable seam for a future webhook/email plugin (or the
deferred external API from D16) to hook into later without changing the write path.

---

## Process/workflow engine — simplified (2026-08-08, supersedes the StageTemplate design)

**D21 — The full `StageTemplate`/generic-interpreter process-template engine is deferred to tech
debt in its entirety for this kit phase.**
The design (per-org/per-process templated stage graphs, a runtime rules-engine guard, mermaid
diagram generation, a future visual template builder) is too complex for this kit's actual need
right now. Rejected in favor of D22–D23 below. Relocated to
`docs/procurement/tech_debt/20260808 process template workflow engine.md`, which records
the underlying problem for if/when this is revisited.

**D22 — Each dimension is one fixed, hardcoded Django `TextChoices` enum — identical for every
demand regardless of organization or process. (Revised 2026-08-08 — now four dimensions, see D32.)**
No per-org/per-template variation, no `StageTemplate` table, no runtime interpretation. This
directly reverses the mid-session direction (making `order_state`, and possibly `issue_state`,
templated/variable) reached earlier in the 2026-08-08 session — that direction is superseded. The
dimensions themselves were later split from three to four (D32) — the "fixed hardcoded enum, no
per-org variation" rule applies identically to all four.

**D23 — Transitions are unrestricted by default, except D9–D11's hardcoded gates, which live as a
single, glanceable Python dict per dimension in code (not database-driven).**
"Allow all transitions" means no general legality engine — but the three specific gates already
decided (D9, D10, D11) are still enforced, as plain hardcoded checks in a guard/manager method. The
dict exists purely so the legal-transition shape is visible in one place in the codebase, not as
the seed of a generalized engine.

**D24 — Enum values, pinned down 2026-08-02/2026-08-08, superseded 2026-08-08 by the four-axis
split — see D32–D36 for the current values.**
Kept here for history only. The three-axis values this decision originally pinned
(`workflow_state`: `Pending → Approved | Rejected`, `Cancelled` gated by D10;
`order_state`: `Not Ordered → Ordered → Partially Received → Received`, `Cancelled` gated by D10;
`issue_state`: `Not Issued → issued_to_requestor`, deliberately binary) no longer reflect the
current design. Do not implement from this entry — use D32–D36.

**Note on deferred work:** the general `StageTemplate`/per-organization workflow-template engine
that would have generalized D21–D24, and the external (non-Django) PO-status integration API, are
both deferred to tech debt — see
`docs/procurement/tech_debt/20260808 process template workflow engine.md` and
`docs/procurement/tech_debt/20260808 external purchase order integration api.md`. Those
documents record the actual business problems each was solving, not just the shape considered, so a
future revisit doesn't re-derive them from scratch.

---

## Partial fulfillment & quantity summary columns (2026-08-08)

**D25 — `PartDemand` gets two denormalized summary columns: `purchased_qty` and `issued_qty`, both
integers defaulting to 0.**
Same rationale as the existing per-dimension snapshot columns (fast list/filter without joining to
history): `purchased_qty` is the live sum of `DemandSetLine.quantity_allocated` across every
non-cancelled allocation linking this demand to a PO line — "how much has been put on order for
this demand." `issued_qty` is the live sum of `PartIssuance.quantity` rows recorded against this
demand — "how much has actually been handed to the requester." Both are refreshed alongside the
writes that change them, never written to directly by a caller, same discipline as the four state
dimensions (D32). **Revised 2026-08-08 (D39):** `issued_qty` is redefined as the net/active
quantity, not a running total — see D39.

**D26 — `DemandSetLine` gets a second quantity column: `quantity_received`, integer, default 0.**
`quantity_allocated` already answers "how much of this PO line's stock is claimed by this demand."
`quantity_received` answers "how much of that claim has actually arrived from the vendor" —
recorded against the allocation row, not the PO line, specifically because one PO line can be
shared by several demands (D-shape from R1/D14) and receiving must be attributable per-demand, not
just per-line. `quantity_received` can never exceed `quantity_allocated` on the same row.

**D27 — `PurchaseOrder` gets its own header-level `status` enum, separate from any demand's state
axes.**
`Draft → Placed → Partially Received → Received`, plus `Cancelled` (reachable from `Draft` or
`Placed`). This is the PO's own lifecycle as a commercial document — distinct from, but the thing
that *drives*, each linked demand's `purchasing_state` and `shipment_state` (see D29, revised for
the four-axis split at D32/D40). A `PurchaseOrder` in `Draft` has not been sent to the vendor yet;
`purchasing_state` cannot leave `null` for any demand allocated to it until the PO reaches `Placed`
(this is the PO-level counterpart to D9, which gates on `demand_state` instead).

**D28 — Allocating a demand to a PO line is capped at the demand's outstanding requested quantity —
but the Buyer can choose to raise the request instead of being blocked, and a PO line may carry
unallocated excess quantity. (Revised 2026-08-08, see below.)**
`PartDemand.quantity_requested` (the requested amount) minus its current `purchased_qty` is the outstanding
need, and the allocation write path enforces this as a real cap on `DemandSetLine.quantity_allocated`
— a Buyer cannot silently allocate more to *this demand* than it actually asked for. But when a
Buyer needs to buy more than the outstanding amount against one demand (bulk pricing, a vendor's
minimum order quantity, etc.), the UI intercepts with an explicit choice instead of a flat
rejection: increase `PartDemand.quantity_requested` to cover it — with a strong warning that this is only
appropriate if the task that originated the demand genuinely needs that much — or leave the excess
unallocated. A `PurchaseOrderLine` is always free to carry more ordered quantity than is allocated
to any demand; the unallocated remainder simply sits on the line, available to link to another
demand later, or stands as genuinely proactive/bulk stock (extends D14, which already allows a PO
with zero linked demands at all — this generalizes it to *partially*-linked PO lines too).

**D29 — `purchasing_state`/`shipment_state`'s early stages are computed from receiving data; the
explicit close-out is a human action, not a strict quantity match. (Revised 2026-08-08, then again
2026-08-08 for the four-axis split — see D40 for the current mapping.)**
Originally written against the old single `order_state`. `Not Ordered`/`Ordered`/`Partially
Received` derivation and the "`Received` is an explicit Buyer action, never an automatic quantity
match" principle both still hold — they're now split across `purchasing_state` (the money side:
`Purchased` once a PO is `Placed`) and `shipment_state` (the physical side, driven by
`DemandSetLine.quantity_received`, closed out explicitly by the Buyer). See D40 for the exact
current mapping from `PurchaseOrder.status` to the two axes. `Cancelled` — per D10, only once every
linked PO reaches its own `Cancelled` status (D27).

**D30 — `issued_qty` is a fully independent counter with no cap in either direction; the explicit
issuance close-out is a human action, never computed from quantity. (Revised 2026-08-08, then again
2026-08-08 for the four-axis split — see D36/D39.)**
Unlike `purchased_qty` (D28, capped against the request with an explicit override path),
`issued_qty` can be recorded as more or less than `purchased_qty` — or the original
`PartDemand.quantity_requested` — with **no validation blocking either direction**. Real-world consumption
doesn't always match the number on the request (a work order might call for 5 gallons of oil but
only need 4.5 in practice), and this app's job is to record what actually happened, not dictate what
should have. `issuance_state` never auto-flips to `Issued` based on comparing `issued_qty` to any
other quantity while reconciliation is pending; whoever handles the issuance/return explicitly
closes it out. `issuance_state` gained a `Partially Issued` and an `Issued Pending Reconciliation`
value in the four-axis split (D36) — the binary framing this decision originally described is
superseded there; the "human closes it out, not a quantity threshold" principle is unchanged.

**Why D29's and D30's explicit close-outs are both human actions, not computed thresholds:**
business processes are messy, and this app's job is to give users the tools to record what actually
happened as accurately as possible — not to over-dictate what must be true before a demand can be
marked done. `purchased_qty`, `issued_qty`, and every `quantity_received` value stay fully
informational inputs to that human judgment call, never a gate blocking it.

**D31 — The demand's requested-amount field is named `PartDemand.quantity_requested`, not
`quantity` (2026-08-08).**
Renamed explicitly to avoid future mix-ups with `purchased_qty`, `issued_qty`, and
`DemandSetLine.quantity_allocated`/`quantity_received` — with four quantity-flavored fields now in
play across two models, a bare `quantity` on `PartDemand` was too easy to confuse with the others at
a glance or in code review. No behavior change, naming only.

---

## Four-axis redesign (2026-08-08, supersedes the three-axis model)

Reviewing the legacy `asset_management` app's `part_demands`/`inventory` modules (predecessor to
this rebuild) surfaced that its single `order_status` conflated two genuinely separate real-world
processes: whether money has been authorized to move, and where the material physically is in
transit. They don't move in lockstep — a PO can be fully approved and paid for while the vendor is
still mid-production. The three-axis model is replaced by a four-axis model to split them apart.
Full detail lives in `part_demand_system.md`; this section is the decision record.

**D32 — `PartDemand` moves from three state dimensions to four:
`demand_state`, `purchasing_state`, `shipment_state`, `issuance_state`.**
Renames: `workflow_state → demand_state`, `issue_state → issuance_state`. Split: `order_state`
becomes two independent axes, `purchasing_state` (money authorization) and `shipment_state`
(physical logistics). See D24 (superseded) for the old values; D33–D36 for the current ones.

**D33 — `demand_state` enum: `Projected → Required → Approved → Completed`, plus `Rejected` and
`Cancelled` carried forward from the old `workflow_state`.**
`Projected` — a forecasted future need (e.g. a maintenance template projecting a future PM's
parts), not yet real. `Required` — the need became real, typically when a worker starts the task
it's attached to. `Approved` — authorizes `purchasing_state` to leave `null` (D9). `Rejected` loops
back to `Required` on resubmission (no separate reopen action, per M5 — updated from looping to
`Pending`, since `Pending` no longer exists). `Cancelled` — terminal, gated by D10. `Completed` — a
**derived rollup**, not a human decision: true once `purchasing_state`, `shipment_state` (if a PO
is linked), and `issuance_state` each independently reach one of their own terminal states (D9a).
**Confirmed 2026-08-08:** `Rejected` and `Cancelled` carry forward unchanged from the old
`workflow_state` — the open item this decision originally flagged is resolved.

**D34 — `purchasing_state` enum: `null → Approved | Denied → Purchased → Cancelled`. No
`Manufactured Onsite` value.**
A tracker for whether/when money moves for this demand, decoupled from shipment logistics. `null`
is the default before a purchasing decision is made. An in-house/self-fulfillment path was
considered as a distinct terminal value (`Manufactured Onsite`) and **rejected same-session**: if a
demand is fulfilled by making the part in-house, that's modeled as an ordinary PO placed against an
internal/self vendor, going through the regular `Approved → Purchased` states — not a special
enum value. Keeps `purchasing_state` to one concern (was money authorized to move) rather than also
encoding *how* fulfillment happens.

**D35 — `shipment_state` enum: the granular vendor logistics chain — `Request Not Sent → Request
Received by Vendor → Production in Progress → Vendor Prepared to Ship → Shipped → Delivered to
Depot → Delivered to Local Receiving Location → In Stock`, plus `Backordered`/`Lost` off `Shipped`.**
Decoupled from `purchasing_state` specifically because a PO can be fully paid for while nothing has
shipped yet. **Scope split:** this kit only builds the enum surface and drives it up through
`Shipped`/`Backordered`/`Lost` (via `PurchaseOrder.status`, D40) and an explicit Buyer close-out at
`Delivered to Local Receiving Location` (the kit-owned terminal stage — same "explicit human
action" principle as the old D29). The stages beyond that (`In Stock`, and the general
receiving/put-away mechanics) belong to the separate, later Inventory build kit (package intake,
physical inventory, issuance) — left open here, not designed.

**D36 — `issuance_state` enum: `Not Issued → Partially Issued → Issued`, plus `Issued Pending
Reconciliation` as the active borrow/return state.**
Renamed from `issue_state`, no longer binary. `Partially Issued` — some but not the full expected
amount has been handed over (mirrors the old `order_state.Partially Received` idea, for hand-off
instead of receiving). `Issued Pending Reconciliation` — the active state for material expected to
be partially returned (tools, borrow-and-return stock): `issued_qty` reflects the full amount
currently out while in this state; returning resolves it back to `Issued` with `issued_qty` netted
down (D39). Same "explicit human close-out, not a quantity threshold" principle as D30 — the
Reconciliation → Issued transition is a human action, not automatic.

**D37 — Cross-dimension gates restated for the new axis names; see D9, D10, D11, D9a above.**
No new gate logic beyond the D9a rollup — D9–D11 govern the same relationships they always did,
just against the renamed/split axes.

**D38 — Two new informational columns on `PartDemand`: `source_module` and
`serial_number_tracking_required`.**
`source_module` — renamed from the legacy app's `part_demand_type` (`Maintenance`/`Dispatching`/
`General`); a denormalized convenience for cheap filtering/display, not a source of truth for
origin detail (that still resolves through each consumer app's own link table, per D7/G3).
`serial_number_tracking_required` — boolean, default `False`. Flags that this demand's fulfillment
needs serial-number-level tracking. The actual serial-tracking logic is implemented by the future
Inventory/issuance application; this column exists now purely so upstream demand templates (a
Maintenance task template, etc.) have somewhere to declare it, since they often already know
whether serials matter for a given part.

**D39 — Borrow/return is modeled as two linked `PartIssuance`-style rows (one positive, one
negative), not a dedicated return table or boolean. `issued_qty` is redefined as the net/active
quantity and may legitimately be `0`.**
Supersedes the borrow/return framing implied by the legacy app's unused `was_borrow_and_return`/
`quantity_returned` columns (never actually populated there) and updates D25/D30's description of
`issued_qty` as a running total. An issuance out is a positive row against the demand; a return is
a second, negative row against the same demand — both visible in the append-only journal (§4 of
`part_demand_system.md`) without needing a separate returns table. `issued_qty` is always the net
of those rows: a demand that issued 10 and had all 10 returned nets to `issued_qty = 0`. A boolean
specifically flagging "this issuance had a return" may be added later; deliberately not built now.

**D40 — `PurchaseOrder.status` (D27) now drives both `purchasing_state` and `shipment_state` on
linked demands, replacing its old single-`order_state`-driving role.**
Mapping: `Draft` → `purchasing_state` stays wherever it is short of `Purchased`; `shipment_state =
Request Not Sent`. `Placed` → `purchasing_state = Purchased` (the money-moved boundary — this is
what used to set `order_state = Ordered`); `shipment_state` advances to `Request Received by
Vendor` as an optimistic default, then may be advanced manually (`Production in Progress` →
`Vendor Prepared to Ship` → `Shipped`) as vendor updates come in — no auto-computation for that
middle stretch in this kit. `Partially Received`/`Received` (PO-level, driven by
`sum(quantity_received)` per D26/D29) → the Buyer's explicit close-out sets the linked demands'
`shipment_state` to `Delivered to Local Receiving Location` (this kit's owned terminal stage, D35)
— never automatic. `Cancelled` → `purchasing_state = Cancelled`.

**D41 — Vendor multi-point-of-contact problem relocated to `docs/parts/tech_debt/`, not this kit.**
A vendor can have different contacts per product category (e.g. one manufacturer, separate turbine
vs. avionics contacts) — `Vendor.vendor_contact` staying a plain string can't represent that. This
is a parts/vendor data-model problem, not specific to part-demand-purchasing, so it's logged at
`docs/parts/tech_debt/20260808 vendor multiple points of contact per category.md` rather than in
this kit's tech debt. `vendor_contact` stays a plain string for this kit; no category-aware contact
model is being built here.

---

## Real-world workflow behavior & persona volume (2026-08-08, resolves questionnaire P2)

**D42 — Linking a demand to a PO line auto-promotes `demand_state → Approved` by default; the
Buyer can opt out per-submission.**
Real usage has Purchasing routinely acting before an Approver has explicitly signed off — the
formal "approve, then purchase" order is frequently bypassed via outside-channel direction. Rather
than hard-blocking a Buyer's `DemandSetLine` creation on an unapproved demand (which Gate 1, D9,
would otherwise do), the default behavior is to auto-promote `demand_state` to `Approved` as a side
effect of the link. A Buyer who specifically wants to preserve the strict approve-first process for
a given item checks a box before submitting the link to leave the demand unapproved instead — in
that case Gate 1 still blocks `purchasing_state` from leaving `null` until an Approver actually acts.
Gate 1 itself (D9) is unchanged; this decision only changes *how* `Approved` is usually reached.

**D43 — `demand_state → Completed` auto-triggers from `purchasing_state` + `issuance_state` only;
`shipment_state` is excluded from the rollup. Supersedes D9a's "all three axes must be terminal"
framing.**
Triggers once `purchasing_state` has progressed past `null`/`Denied` (i.e. at least `Approved`) and
`issuance_state` reaches `Issued` — checked on every write to either axis, whichever condition is
satisfied second. Matches the real Requester workflow: they mark material received and expect the
demand to read as done, full stop, regardless of where shipment/stocking tracking happens to sit.
`shipment_state` is treated as a decoupled background process — ideally kept current by an external
system feed (ties directly into the deferred integration API at D16, which is now understood to
have this as its concrete motivating use case, though it remains unbuilt this kit).

**D44 — Persona volume, resolving questionnaire P2.**
- **Requester** — high frequency, daily. Real job is closing demands out (marking material received
  / triggering `Completed` via D43); they don't interact with the four axes directly.
- **Approver** — comparatively low frequency. The formal approve-before-purchase step is often
  skipped in practice (see D42); Purchasing frequently acts first via outside-channel direction.
- **Buyer** — high frequency, daily. Continuously links demands to POs and updates PO status.
- **Shipping/stocking updates** — very high frequency, ideally machine-driven (external system feed
  per D16). `Partially Issued` and `Backordered` are common, everyday occurrences — not edge cases.
- **Cancellations** (any type: `demand_state`, `purchasing_state`, `PurchaseOrder.status`) — rare.

This resolves `open_questions.md` #1 (P2) — see there for the original question. Front-end kit
UI/UX priority should weight toward Requester's "mark received" flow and Buyer's linking/PO-update
flow as the two highest-traffic surfaces, with Approver's explicit action and all cancellation
flows treated as lower-frequency, correctness-first paths.

---

## Build-scoping session (2026-08-08) — models, boundaries, naming

Decisions taken while writing `models/` and `control/`, after reviewing the legacy
`asset_management` `part_demands`/`inventory` modules directly.

**D45 — No `Vendor` table. A PO's vendor is an FK to `parts.PartManufacturer`; the point of
contact is a plain string column on the `PurchaseOrder`.** — **SUPERSEDED, see below.**
Reverses questionnaire G4.2, which specified a new lightweight `Vendor` entity owned by this app.
`PartManufacturer` already carries exactly the field list `Vendor` was going to have
(`name`/`code`/`website`/`is_active`), and one registry to maintain beats two nearly identical
ones. Accepted cost: G4's manufacturer-vs-vendor distinction collapses — a distributor or reseller
must be registered in `PartManufacturer` as if it made the part. Two knock-ons: **D41 dissolves
rather than resolves** (per-PO contact strings record category-specific contacts naturally, with
nothing modeling them — the parts-app tech-debt note stays valid for a future real contact
registry), and **G4.1's "scrub vendor language out of the parts app" cleanup is now wrong** and
should be retired, since `PartManufacturer` genuinely serves both roles.

**D45 reversed (2026-08-09) — a real `procurement.Vendor` table now exists.**
A vendor is not a manufacturer — a reseller like Walmart has no relationship to the parts it
sells, and collapsing the two concepts was a mistake. `PurchaseOrder.vendor` now FKs to
`procurement.Vendor` (`name`/`code`/`website`/`is_active`, procurement-owned), decoupled entirely
from `parts.PartManufacturer`. `vendor_contact` stays a plain string on `PurchaseOrder` (D41's
per-category-contact problem remains open, unaffected by this change). This restores the original
G4.2 questionnaire intent that D45 had reversed away from.

**D46 — `PartIssue` lives in `app/inventory/`, not in this app.**
Supersedes questionnaire G2's minimal `PartIssuance` CRUD carve-out inside this app. Strictly
better: it removes a table explicitly declared as retire-later scaffolding, and it makes D7's
delete guard cleaner rather than messier — `PartIssue`'s `PROTECT` FK to `PartDemand` blocks
deletion from the consumer side exactly as D7 describes, so this app's guard checks only
`PurchaseOrderDemandLink` and `PartDemandUpdate`. Consequence: `issued_qty` is no longer derivable
by this app; `PartDemandContext.record_issuance(...)` takes the net quantity as an argument and the
orchestrator in `inventory` is the only supported write path (D12). Material is signed — positive
out, negative returned (D39). No source-of-quantity, location, bin, lot, serial, or cost columns.

**D47 — `Package` and `PackageLine` are built this cycle in `app/procurement/` (revised D59, 2026-08-08).**
Packages are pre-possession shipment tracking — what the vendor shipped. `Package` (+ `PackageLine`)
FKs to `PurchaseOrder`; one PO has many packages. `Package.status` drives `PartDemand.shipment_state`.
The legacy app merged the two concepts into `ArrivalHeader`/`ArrivalLine`, which was simultaneously
"a package that arrived" and "the receiving transaction" — that conflation is why receipts there
could only ever attribute to PO lines, never to demands. **Intake is entirely out of scope for this
build**: no intake table, no receiving workflow, no put-away. Packages belong in procurement because
they describe the order fulfillment; intake (what to do with goods once they arrive) belongs in
inventory.

**D48 — The PO event emitter ships as a defined interface with no listeners, replacing D20's
Django signal.**
A `po_events/` tools package with a typed `PurchaseOrderEventType` enum, a frozen
`PurchaseOrderEventPayload` (IDs and scalars only), an emitter, an abstract
`PurchaseOrderEventListener`, and an in-process registry. Zero listeners registered. Chosen over
D20's Django signal because signals are stringly-typed and hide their subscribers, while a registry
makes "what listens to POs" answerable by reading one file. Emission is fire-and-forget, after
commit, and never fails the write that emitted it. **Outbound only** — not the deferred inbound
integration API (D16), which still has no payload contract or auth model.

**D49 — The Django app label is `procurement` (revised 2026-08-08).**
`app/procurement/`. The docs folder is `docs/procurement/`.

**D50 — `DemandSetLine` is renamed `PurchaseOrderDemandLink` (singular).**
Third and final name for this join (legacy `PartDemandPurchaseOrderLink` → M1's `DemandSetLine` →
here). Forward-looking: this will not be the only table linking demands to something — Maintenance
actions, dispatches, and later inventory concepts each need their own — so the family reads
`<thing>DemandLink`. `DemandSetLine` gave no such handle and implied a "set" grouping concept that
does not exist. Singular per this codebase's model naming; table `purchase_order_demand_link`.
Renamed throughout `part_demand_system.md`, `purchase_ordering_system.md`, `models/`, and
`control/`; earlier mentions in `questionnaire.md` and the boundaries doc are left as history.

**D51 — `PurchaseOrderLine` carries no line-level `status`.**
The legacy line had one (`Pending/Ordered/Shipped/Complete/Cancelled`) cascaded from the header,
so header, line, and demand each held a partial copy of the same fact and could disagree. A line's
state is its header's `status`; fulfillment progress lives on
`PurchaseOrderDemandLink.quantity_received`, where it is actually attributable per demand.

**D52 — A PO is created as `Draft`, never directly as `Placed`.**
The legacy `from_dict` factory created POs already `Ordered`, so there was no state in which a PO
could be reviewed before the vendor was told. Placing is a separate deliberate act.

**D53 — Derived quantities live on structs, never as model properties.**
The legacy `PurchaseOrderLine` exposed `quantity_received_total`, `quantity_linked`,
`total_quantity_linked_from_arrivals`, and `line_total` as `@property` methods that each issued
their own query, so rendering a 40-line PO cost well over a hundred queries. All such values are
annotated once on `PurchaseOrderStruct`/`PurchaseOrderLineStruct`. Reinforces the standing
no-business-logic-on-models rule with a concrete failure case.

**D54 — The legacy "cannot link an already-issued demand" validation is dropped.**
The legacy factory refused to link a demand whose `issue_status` was `Issued`/`Installed`. A demand
can legitimately be issued from stock on hand and *then* have a PO cut to replace what was taken.
`issuance_state` gates nothing (D11). *Note: the rule the legacy check was reaching for was about
**lines**, not issuance — "you cannot move a line on an already-purchased PO." That concern is
addressed by D57's audit requirement instead of a block.*

---

## Packages, arrival attribution, and line auditing (2026-08-08)

**D55 — `PurchaseOrderDemandLink.quantity_received` is removed. Per-demand arrival is derived, not
stored. Reverses D26.**
The column assumed per-demand arrival is a fact waiting to be recorded. For a PO line serving two
or more demands it is not: the arriving units are fungible, nobody decided whose they were, and any
attribution a receiver typed would be an invention stored as an observation. Arrival is now
recorded once, physically, as `PackageLine.quantity_accepted` against a PO line. Per-demand arrival
is derived under an explicit rule — **exactly one** active demand link on a line makes it
attributable (that demand's arrival is the line's accepted total); **two or more** makes it a
**shared demand session**, where the only truthful report is the session total and its membership,
never a per-demand figure. Full treatment in `shared_demand_sessions.md`, which exists as its own
document because the tension is permanent and will otherwise be re-litigated. Consequence:
`record_receipt_against_allocation` no longer exists as a workflow, and D26's
`quantity_received <= quantity_allocated` constraint is gone with it.

**D56 — Cancelling a PO line removes its demand links and resets those demands'
`purchasing_state` to `null`.**
Not configurable, not prompted. The demands return to "no purchasing decision has been made,"
which is accurate once the thing that was going to buy them is gone. `demand_state` is deliberately
untouched — the need may still be real and buyable elsewhere; a Requester or Approver cancels it
manually later if it is not (D4). Requires `purchasing_state: Purchased → null` as a legal
transition — the only backward move in that axis, existing solely for this path.

**D57 — Lines stay editable after placement; every mutation on a `Placed`-or-later PO posts a
machine comment carrying a JSON snapshot of the row before the change. Cancellation is a soft
delete plus that comment, not a status column.**
Supersedes the earlier "lines are immutable once purchased, cancel and replace instead" framing.
Vendors substitute, short-ship, and re-price after an order goes out; the record should say what
happened. The permissiveness is paid for in audit rather than restriction — pre-state snapshots on
edit *and* delete mean nothing is silently rewritten and nothing is lost, without a second journal
table. The UI raises a soft warning; the control layer does not refuse. This also resolves the
line-status question left open by D51: there is no `status` column and no `is_cancelled` flag — a
cancelled line is a soft-deleted line whose Event comment explains it. One hard stop survives: a
line's `quantity_ordered` cannot drop below what has already been accepted against it.

**D58 — One active line per part per PO, enforced in the control layer as a soft UI error.**
Scoped to **non-deleted** lines, so cancel-and-replace legitimately leaves a deleted same-part line
behind. Not a database constraint, for two reasons: the rule is about pricing simplicity (one part,
one price, one line) rather than data integrity, so relaxing it later for split delivery dates or
tiered pricing should be a guard change and not a migration; and package-line assignment resolves
*part → PO line*, which is only unambiguous while the rule holds — the soft version keeps that
failure visible rather than impossible. A duplicate that gets through degrades gracefully:
arriving package lines land unassigned rather than mis-assigned.

**D59 — Packages are built this cycle in `app/procurement/` with a header→PO FK, line→PO-line FK,
a drift flag, and a splitting wizard. No `PurchaseOrderPackageLink` table.**
`Package` is a child of a `PurchaseOrder`; `PackageLine` is a child of both a `Package` and a
`PurchaseOrderLine`. Lines **copy** the header's PO link at creation so the common case needs no
per-line assignment, and are reassignable afterward — one physical box routinely holds items from
several orders to the same vendor. `Package.mixed_po_assignments` flags that drift; it blocks
nothing and exists so the condition is queryable rather than puzzled over. A line spanning several
PO lines is **split into sibling rows** (`split_from` preserves lineage) rather than linked through
a join table with quantities: with a link table, an arriving line's quantity and the sum of its
links can disagree, which is exactly the reconciliation problem the legacy
`ArrivalLine.quantity_available_for_linking` column existed to describe. Splitting makes the rows
sum to the shipment by construction. The splitting wizard's real work is the **PO lookup** across a
vendor's open orders, not the arithmetic. `Package.status` drives `PartDemand.shipment_state`, the
role D35/D40 always intended for it; a demand behind several packages takes the **least advanced**
status among them. Acceptance is `PackageLine.quantity_accepted` — a nullable quantity, not a
boolean, because partial acceptance is the normal outcome of a damaged shipment and `null`
(uninspected) is meaningfully different from `0` (inspected, all rejected). **Intake remains out of
scope**: accepting a package line records that goods arrived intact, not that they were put
anywhere.

**D60 — `PurchaseOrderFulfillmentStruct` lives in `procurement` and reads `Package`/`PackageLine`
directly, no longer marked `# DELIBERATE ANTI-PATTERN`.**
Because packages now live in `procurement`, this is a straightforward within-app read — no anti-pattern
needed. The struct exposes four non-overlapping quantities per line — `qty_ordered`, `qty_allocated`,
`qty_from_accepted_packages`, `qty_issued` — plus each line's attribution mode, with the per-demand
arrival field **absent, not null**, on the shared-session branch so a caller cannot default it to
zero and report a lie (D55/D56 / `shared_demand_sessions.md`).

---

## Build session (2026-08-09) — models and control layer implemented

The backend was built in this session. These decisions were taken during it; several resolve
contradictions the kit had accumulated across earlier sessions.

**D61 — `PurchaseOrder` gets its own mandatory `domain` FK. The PO's `Event` takes the same domain.**
Discovered while building: `events.Event` has a **non-nullable** `domain` FK, and D17 requires every
PO to carry an Event — but no version of this kit ever gave `PurchaseOrder` a domain, so a PO could
not have been created at all as specified. Options considered: derive the Event's domain from the
first linked demand (fails for the zero-demand PO that D14 explicitly permits, and gives POs no
scoping of their own), or ask the Buyer per-PO (more clicks on the highest-traffic surface, D44).
Chosen: a `domain` FK meaning **who is buying**, distinct from each demand's domain meaning **who
is receiving**. A PO whose lines serve demands across several domains still has exactly one owning
domain, which is the honest shape — the buying office is one place.

**D62 — Permissions are deferred entirely to the presentation layer. No custom `Meta.permissions`,
no group fixtures, no permission checks in the control layer this build.**
Reverses the mid-session direction of this same session, deliberately, to reduce complexity while
the backend is being established. Consequences, stated plainly because this is the least safe
decision here: **any caller reaching a `Context` verb can perform any action on any row**, including
across domains. The D2 Approve/Buy split, the D3 Buyer-only allocation rule, and the D4
"a Buyer never cancels a demand" rule are currently **documented conventions with nothing enforcing
them**. `PartDemandApprovalPolicy` (specced in `control/index.md`) was consequently not built.
The `domain` columns on `PartDemand` and `PurchaseOrder` **are** in place, and `OpenDemandSearch`
takes a `domain_ids` parameter, so the data fence has its seam ready — nothing calls it yet.
Enforcement lands with the entrypoints in the UI build, and is the first thing that should.
`PartDemandDeletionPolicy` was still built: despite the `Policy` suffix it is a business rule (D6's
hard-vs-soft decision), not authorization.

**D63 — Package placement contradiction resolved in favor of D59/D60: everything in `procurement`.**
The kit disagreed with itself — `models/index.md` and D59/D60 put packages in `procurement`, while
`control/index.md` listed every Package class under `app/inventory/control_layer/`, `package.md`
gave `PackageLine` an `app/inventory/` path, and `shared_demand_sessions.md` §5 still described
`PurchaseOrderFulfillmentStruct` as a cross-app `# DELIBERATE ANTI-PATTERN` that D60 had already
removed. Models **and** control classes for `Package`/`PackageLine` are in `app/procurement/`.
`app/inventory/` contains exactly two things: `PartIssue` and `PartIssuanceOrchestrator`. There is
now **no `# DELIBERATE ANTI-PATTERN` anywhere in either app** — the boundary needs no exception.

**D64 — All quantity columns are `DecimalField(max_digits=12, decimal_places=3)`.**
Resolves a contradiction between D25 ("integers defaulting to 0") and every model doc
(`DecimalField`). Decimal wins: `part_demand_system.md` §5 justifies the whole issuance design with
"a work order might call for 5 gallons of oil but only need 4.5", which integers cannot represent.
D25's integer wording is stale and is superseded here. Money columns stay at 2 decimal places.

**D65 — `purchasing_state`'s unset value is stored as `""` (blank), not SQL `NULL`.**
The kit consistently describes the default as `null`. Implemented as a blank `CharField` so that the
column, `PartDemandUpdate.stage`/`previous_stage`, and the transition dicts all speak one type —
three-valued logic across a join for a value that is a real, meaningful state ("no purchasing
decision has been made") buys nothing. `PURCHASING_STATE_UNSET` is the named constant; no code
compares against a bare `""`.

**D66 — `commit=False` means "do not open your own transaction", never "do not write".**
Recorded because getting it wrong was a real bug caught by the seed: `PartDemandQuantityManager`
originally skipped its `save()` when `commit=False`, so every demand created through the PO wizard
had `purchased_qty` computed and then discarded, resting at `0`. The rule is now uniform across
every manager, and the quantity manager always writes.

**D67 — Derived package/allocation quantities are computed with correlated subqueries, never
joined `Sum()`s alongside another multi-row join.**
Also caught by the seed. `PurchaseOrderFulfillmentStruct` annotated `Sum(package_lines__…)` next to
a join on `allocations`, so a line with 55 accepted units and 2 demands reported **110** — and then
raised the over-receipt exception flag on a number that never happened. This is the same class of
error as D53's per-property queries: a reporting surface confidently stating something false. Every
such aggregate is now a `Subquery`.

**Not built this session, and worth knowing:** no tests (deliberate, this pass), and no
`presentation_layer/entrypoints/`, `urls.py`, or templates — the build stops exactly at the starter
kit's own line, "the backend could theoretically perform these tasks."

---

## Front-end kit build session (2026-08-09) — Package gets its own Event

**D68 — `Package` gets its own `Event` row (not `ActivityThread`), created alongside the package.
Its domain is copied from `Package.purchase_order.domain` at creation, and `Package` itself does
not gain a `domain` column.**

Raised while planning the package UI: packages need the same status-comments/document-library/
human-comments trio a PO already gets (D17–D19) — a shipping PDF or a customs form to attach, a
comment trail as the package moves, in-transit photos, and machine comments narrating status
advances and (new, see below) line reassignments. `events.Event` and `events.ActivityThread` both
support comments and direct attachments (see the feature matrix in the real `events/kitchen-sink`
page) — the actual differentiator is that only `Event` carries a `domain` FK and the
type/status/priority metadata that make a row independently listable/filterable (`Event.objects
.visible_to(user)` scopes by domain). A package is exactly the kind of thing someone browses
("what shipped against my domain recently") the same way PO events already are, which
`ActivityThread`'s "subordinate to the owning item, no independent visibility" shape does not
support. This is the same reasoning D17 used for `PurchaseOrder`, applied to `Package` for the same
reason.

**No new `domain` column on `Package` itself** — unlike D61's `PurchaseOrder.domain` (which had to
exist as a real column because nothing upstream could supply one), a package's domain is never
ambiguous: it is always its `purchase_order`'s domain, and `Package.purchase_order` is
**non-nullable** (D59, "never free-floating"). `PackageFactory.create` reads
`purchase_order.domain` once, at creation, and writes it onto the new `Event` row — the same
one-time copy `Event.domain` needs, without adding a redundant column that could drift from the PO's
own domain.

**The "package arrives before the PO exists" edge case does not apply.** It was raised as a future
concern during planning, but `create_package` already requires `purchase_order_id` (D59) — a
`Package` cannot be created without a PO to copy the domain from, so there is no ambiguous-domain
state to design for under the current model. Revisit only if a future kit relaxes that constraint.

**Machine comments move from the PO's Event to the package's own.** `package_lifecycle.md`
currently posts every package-lifecycle machine comment (create, status advance, line acceptance,
splitting) onto **the PO's** Event (D18's original scope). With `Package` carrying its own Event,
each package-specific event narrates on **its own** Event instead:

- `create_package`, `advance_package_status`, `inspect_and_accept_package_line` → machine comment on
  the package's own Event.
- The line-splitting wizard, when a split lands on a **different** PO's line, still additionally
  posts to **that other PO's** Event (not the header PO's) — the receiving PO is genuinely affected
  and D18's PO-side narration should still say so — in addition to the machine comment on the
  package's own Event describing the split. A same-PO split/reassignment narrates only on the
  package's Event.

**Extends D57's audit-snapshot pattern to package line moves against a delivered package.** D57
requires a JSON pre-state snapshot machine comment for every line mutation on a `Placed`-or-later
PO. The same shape now applies one level down: adding, removing, or reassigning a line on a
`Package` that has already reached its delivered stages (`Delivered to Local Receiving Location` or
`Accepted`) requires **both** a JSON snapshot of the line's prior state (machine comment) **and** a
mandatory human comment explaining the change, on the package's own Event — undelivered packages
(`Awaiting Shipment` through `Delivered to Depot`) mutate freely, same as a `Draft` PO's lines do
today. **Revised by D69 below**: rather than capturing this note inline during bulk drag-and-drop
editing, a delivered (or split, see D69) package is locked out of the bulk tool entirely and its
edits are forced onto the single-line edit page, which captures the note per mutation, immediately —
see [front-end-kit/procurement/packages/package_edit_and_linkage.md](../front-end-kit/procurement/packages/package_edit_and_linkage.md).

**Consequence for `package_workflows.md`/`models/package.md`:** both need a follow-up pass to add
`Package.event` (OneToOne → `events.Event`, `PROTECT`, nullable — same shape as
`PurchaseOrder.event`) and retarget the "machine comment on the PO's Event" language above. Not
done in this pass — this decision is recorded so the change is deliberate and traceable when that
pass happens, not rediscovered as a contradiction the way D63 was.

**D69 — The bulk drag-and-drop package manager locks (excludes from editing) any package that is
either delivered or has ever been split, rather than allowing in-tool edits with an inline audit
popup.**

Raised while designing [front-end-kit/procurement/packages/basic_package_manager.md](../front-end-kit/procurement/packages/basic_package_manager.md):
capturing D57/D68's mandatory audit note *during* a bulk drag-and-drop sorting session added real
complexity (session-pending-note tracking, same-line-move supersession, dual-Event posting for
cross-package moves) for a case that's rare in that tool's own common path (per D44-style framing,
most packages being sorted there are fresh, undelivered, unsplit). Simpler split: the bulk tool
handles only straightforward, not-yet-delivered, not-yet-split packages; anything past either
threshold is edited exclusively on
[package_edit_and_linkage.md](../front-end-kit/procurement/packages/package_edit_and_linkage.md),
which already captures the audit note per mutation, immediately, with no session/deferral logic
needed since it commits one line at a time.

**Second lock trigger: `Package.has_splits`, a new `BooleanField(default=False)`.** Mirrors
`mixed_po_assignments`'s existing shape (D59) — maintained by `PackageLineSplitHandler`, set `True`
the moment a split creates a sibling row for one of this package's lines (`split_from` populated on
the new row). A plain reassignment (the "degenerate case," full quantity moved with no new row) does
**not** set it — only an actual split does, because only a split introduces `split_from` lineage
that the bulk tool's simple line-chip model isn't built to represent or preserve safely. Not yet
added to `models/package.md` — same "recorded, not yet implemented" status as D68's `Package.event`.

**Consequence:** a package is locked in the bulk tool if `status` has reached
`Delivered to Local Receiving Location`/`Accepted`, **or** `has_splits` is `True` — either condition
independently, and a package can be locked by one without the other (a fresh, unsplit but delivered
package; or an undelivered package someone already ran through the splitting tool). Locked packages
still render in the bulk tool, read-only, for context — their lines count toward "already packaged"
totals on the PO-lines column — but are not drop targets and carry no unassign control; a link
points to `package_edit_and_linkage.md` instead.

**D70 — `PurchaseOrderDemandLink` is confirmed many-to-many in both directions, with no new schema
required; the read side gets a corrected shallow formula plus one new bounded graph-traversal class
for the admin-only case.**

Raised while planning: earlier docs (`shared_demand_sessions.md` above all) were written and read as
if sharing only ran "one PO line, several demands." The other direction — one demand allocated
across several PO lines, which can themselves be shared with other demands, which can touch other
POs — was always equally legal in the schema (`models/purchase_order_demand_link.md` never capped
either side) and is common in practice (backorders re-sourced elsewhere, split-vendor buys). Nothing
in the schema changes. Full reasoning, the corrected purchasing-coverage formula, and the graph
model: [po_demand_association_graph.md](po_demand_association_graph.md).

Two consequences, kept deliberately separate:

- **Every routine per-entity read stays shallow and fast** — `shared_demand_sessions.md`'s existing
  per-line evaluation already handled this correctly for *arrival*; the same per-line-then-combine
  shape now applies to the *purchasing coverage* display
  ([part_demand_workflows.md](../front-end-kit/procurement/part_demand_workflows.md) needs a
  follow-up pass to its Rules section and purchasing axis card — not done in this pass).
  This never walks past a demand's direct lines and those lines' direct co-demands — one hop, not a
  graph traversal, regardless of how large the wider network is.
- **A new, separate, admin-only surface does the real graph walk**: `PoDemandAssociationGraphResolver`
  (proposed), a breadth-first traversal over `PartDemand`/`PurchaseOrderLine`/`Package` nodes with an
  explicit safety cap — not assumed-shallow, bounded on purpose. Backs the new graph-association
  visualizer page. Nothing else in the app should ever call this class; routine pages use the
  shallow read above.

Packages extend the graph a third way that demand-side rules (D28's allocation cap, D58's one-line-
per-part) don't reach: `mixed_po_assignments` means a single package can bridge lines across
different POs with no demand in common, so the graph's real growth bound is the resolver's own
safety cap, not the demand-side rules. See `po_demand_association_graph.md` §4.

---

**D71 — Front-end kit Phase 0 ships nine schema changes, a five-permission vocabulary, and a
separate PO approval axis; D2's clause allowing an Approver alone to place an order is retired.**

Raised while building [front-end-kit/procurement/build_plan/phase_0_schema_and_shell.md](../front-end-kit/procurement/build_plan/phase_0_schema_and_shell.md),
the hard gate before any sector UI. Full detail lives in D72-D78 below; this entry is the umbrella.

D2 previously allowed a holder of `approve` alone to place a purchase order. With a real purchasing-
manager gate (D76) that reasoning no longer holds: placing is the Buyer's act (`buy`), approval is the
manager's act (`purchase_approve`). `PurchaseOrderContext.place()` now refuses to run unless
`approval_state == Approved`, full stop, regardless of who is placing.

**D72 — `Package.event`, a `OneToOneField(events.Event, PROTECT, null=True)`.**

Same shape as `PurchaseOrder.event` (D17-D19): one Event row per package for its whole lifetime,
created in the same transaction as the package, nullable only because the FK is set after the Event
row exists. Package-lifecycle machine comments (`PackageNarrator`, new) move here from the PO's Event
— a package finally has its own history rather than borrowing the PO's.

**D73 — `Package.has_splits`, a new `BooleanField(default=False)`.**

Mirrors `mixed_po_assignments`'s existing shape. Maintained by `PackageLineSplitHandler`, set `True`
the moment a split creates a sibling row for one of this package's lines (`split_from` populated). A
plain reassignment (full quantity moved, no new row — the degenerate case) does NOT set it. Locks the
package out of the bulk drag-and-drop sorting tool alongside a Delivered/Accepted status — see the
prior lock-trigger entry above this one in the file.

**D74 — `Package.purchase_order` becomes nullable; `Package.domain` becomes a required
`ForeignKey(administration.Domain)`. This REVERSES D59's "a package is never free-floating" rule.**

A package can now be received before its purchase order exists — the reactive receiving entry point
(`packages/receive/`). `Package.domain` is the consequence: D68's "no column needed, walk
`purchase_order.domain`" reasoning falls with its premise once `purchase_order` can be null. Copied
from the PO's domain when one is supplied at create; chosen explicitly by the receiver otherwise.
`PackageContext.attach_purchase_order(purchase_order, actor)` (new) links a PO onto a package later —
auto-linking every unlinked line to the PO line whose part matches, same D58-caveat rule
`create_package` already applies: no match, or more than one matching active line, leaves that line
unlinked. Safe failure, never a guess. `mixed_po_assignments` stays `False` on a PO-less package —
there is no header PO to be mixed against.

**D75 — `Package.tracking_number` renamed to `shipment_id`; stays a `CharField(max_length=200,
blank=True)`, indexed, NOT unique.**

The existing column already had the right shape for the vendor's own tracking string — a generator was
never needed here (that requirement was for `po_number`/`package_number`, already generated by their
respective Factories, see D78). Kept as a string deliberately: an integer column would eat leading
zeros. Not unique on purpose — vendors reuse and mistype their own numbers.

**D76 — `PurchaseOrder.approval_state`, a new blank-default `CharField` axis beside `status`.**

A separate axis for the same reason `PartDemand` carries four: "has a manager blessed this" and "where
is this order in the world" are different questions. Blank (`""`) is the meaningful default —
"Unsubmitted" — following D65's precedent on `PurchasingState`, not a member of the enum itself.

    Unsubmitted -> Pending Approval -> Approved
         |               |
       Denied / Cancelled (reachable from either non-terminal state, any time)

`Approved` is NOT revocable through this axis — an approved order is cancelled through `status`
instead. New verbs on `PurchaseOrderContext`: `submit_for_approval` (`buy`), `approve_order`
(`purchase_approve`), `deny_order` (`purchase_approve`). **Self-approval is legal**: one person may
hold both `buy` and `purchase_approve` and approve their own order — small organizations run this way.
Never blocked, always recorded — `PurchaseOrderNarrator.approved()` posts an explicit self-approval
note when the approving actor is the PO's own creator. No cost thresholds in this build; submitting is
always available, never automatic — threshold-driven approval is per-organization policy, deferred
whole to the process-template engine (see the tech-debt note referenced from
`part_demand_state_guard.py`'s module docstring).

**D77 — `PurchaseOrder.vendor_po_id`, `CharField(max_length=200, blank=True)`, indexed, NOT unique;
and the `IssuanceState` collision is resolved by ADDING a distinct value, `ISSUED_RECONCILIATION_REQUIRED`,
rather than repurposing `ISSUED_PENDING_RECONCILIATION`.**

`vendor_po_id` is the buyer-entered, externally sourced number a vendor's own paperwork carries —
distinct from the system-generated `po_number` (D78). Non-unique on purpose, same reasoning as D75's
`shipment_id`: vendors reuse and mistype their own numbers. Not yet wired into the PO wizard's draft —
that is Phase 2's job; this phase only lands the column.

The collision: `ISSUED_PENDING_RECONCILIATION` already meant "the active borrow/return state" (material
out on loan, expected back, D39's netting-return mechanics). The newly requested state — "Part Issued,
Inventory Reconciliation Required" — answers a different question: a physical movement already
happened and the inventory system's books have not caught up to it yet. One is "this is out and
expected back." The other is "the books are behind reality." Kept as two distinct enum members because
a later Inventory kit needs to tell them apart, and overloading the existing value would have been
exactly the kind of contradiction D63 already had to clean up once. The formerly-illegal backwards
`Issued -> Reconciliation Required` transition is now legal (`part_demand_state_guard.py`), covering
the case where a hand-off is discovered after the row was already marked `Issued`.

**D78 — Five permissions declared via `Meta.permissions` on the models they gate; `po_number` and
`package_number` stay the existing unique `CharField` columns, generated by their Factories, never on
the model.**

| Permission | Declared on | Holder | Grants |
| :--- | :--- | :--- | :--- |
| `request` | `PartDemand` | Requester | Create/edit demands. Viewing does not require it. |
| `demand_manage` | `PartDemand` | Floor manager | Transition `demand_state`/`issuance_state` on any in-domain demand |
| `buy` | `PurchaseOrder` | Buyer | PO create/edit/line-edit, allocate/de-link (D3), submit for approval, place |
| `purchase_approve` | `PurchaseOrder` | Purchasing manager | Approve or deny a PO pre-purchase |
| `receive` | `Package` | Receiving staff | Create packages, advance status, inspect/accept lines |

Every codename lives under the `procurement` app label regardless of which model declares it
(`request.has_perm("procurement.buy")` etc.), so the vocabulary reads as one flat namespace rather than
five model-scoped ones. No allowlist was needed on the administration side — any `Permission` row
already surfaces automatically in the permission-group grant UI (`permission_group_edit`), which lists
`Permission.objects.all()` unfiltered.

The `po_number`/`package_number` requirement ("system-generated identifier plus a separate buyer-
entered string") was already satisfied by the existing columns plus their Factories'
`generate_po_number`/`generate_package_number` classmethods — no third column was needed, only the
buyer-entered strings above (`vendor_po_id`, `shipment_id`) which did not exist yet.

---

## Graph materialization, Shipment rename, and inventory mirror (2026-08-13)

Raised reviewing three architecture-review documents (external, PDF) proposing a materialized
graph-summary model for the Demand ↔ PO Line ↔ Package Line network, plus a dramatic scope
change: renaming the package/receiving concept to "Shipments" end-to-end and duplicating its UI
into `app/inventory/`.

**D79 — `PoDemandAssociationGraphResolver`'s on-demand BFS design (D70) is reversed. The
Demand/PO-Line/Shipment-Line network is now materialized as a `GraphSummary` row per connected
component, with `graph_id` stored directly on each of the three entity tables (entity-level
pointer, not an edge/allocation-level pointer).**

D70 chose an on-demand resolver deliberately, to keep routine reads shallow and avoid a maintained
cluster column. That reasoning is superseded: the same sparsity argument D70 used to justify "should
resolve fast" (D58 one-line-per-part, D28's allocation cap, real purchasing data staying mostly
one-hop) is now read as evidence that materialization is cheap to maintain rather than as evidence
resolving on read is fine. An entity-level `graph_id` gives every routine page (list views, PO
detail, demand detail) a plain `WHERE graph_id = X` for cluster-wide numbers, with no join fan-out
and no risk of a resolver silently walking a larger-than-expected graph on a hot request path.
`PoDemandAssociationGraphResolver` (D70 §3.5) is **not** built — the graph visualizer reads the
materialized `GraphSummary` plus its member rows instead of doing a traversal at render time.

Placement choice — entity-level over edge/allocation-level — follows the same reasoning the
reviewed documents give: this domain's connected clusters stay small (the same real-world sparsity
D70 §3.4 already established), so the O(N) cost of a merge/split touching every member row is
negligible, and it buys every routine read an O(1) lookup instead of a join through
`PurchaseOrderDemandLink`/`ShipmentLine`.

**D80 — `GraphSummary` lives in `app/procurement/`, alongside the models it summarizes.** Same
placement reasoning as D63 (packages/shipments in procurement, not inventory) — the graph is a
procurement-side execution-tracking concept; inventory reads it, never owns or writes it.

**D81 — `GraphSummary` carries eight metric columns, mapped onto existing fields, not the PDFs'
generic totals or their entropy score:**

| `GraphSummary` column | Derivation |
| :--- | :--- |
| `demand_qty` | `Σ PartDemand.quantity_requested` across member demands |
| `po_qty_waiting_for_purchase` | `Σ PurchaseOrderLine.quantity_ordered` on member lines whose `PurchaseOrder.status` is still `Draft`/pre-`Placed` |
| `po_qty_purchased` | `Σ PurchaseOrderLine.quantity_ordered` on member lines whose `PurchaseOrder.status` has reached `Placed` or later (not `Cancelled`) |
| `qty_shipments_in_route` | `Σ ShipmentLine.quantity` on member lines whose `Shipment.status` is after `Awaiting Shipment` and before `Delivered to Local Receiving Location`/`Accepted` (i.e. `Shipped`/`Delivered to Depot`/`Backordered`) |
| `qty_shipments_delivered` | `Σ ShipmentLine.quantity` on member lines whose `Shipment.status` is `Delivered to Local Receiving Location` or `Accepted` |
| `qty_accepted` | `Σ ShipmentLine.quantity_accepted` (excluding `null`) on member lines |
| `qty_rejected` | `Σ (ShipmentLine.quantity - ShipmentLine.quantity_accepted)` on member lines where `quantity_accepted` is not null (the inspected-and-short/damaged remainder — there is no separate "rejected" column, D-package-line design already treats the shipped/accepted delta as the rejection) |
| `intake_qty_recorded` | `0` for every row in this build. No intake table exists yet (D47, unchanged) — the column exists now so the metric has a home, and is wired up when the Inventory intake build lands. Documented as always-zero in the model docstring, not silently omitted, so a future reader does not mistake it for a bug. |

The PDFs' `entropy_score`/`Egraph` weighting formula is **not** adopted — no operational-drift
scoring for this pass. `GraphSummary.status` is kept as a simple derived label (`BALANCED` /
`AWAITING_PURCHASE` / `AWAITING_SHIPMENT` / `AWAITING_ACCEPTANCE`), recomputed the same pass as the
quantity columns, not a weighted composite.

**D82 — Graph maintenance mechanics: node-init on isolated creation, coalescing merge on link
creation, BFS split on unlink, and a single recalculation entrypoint — mirroring the reviewed
documents' merge/split shape, adapted to this schema's actual write paths.**

- **Node init**: creating a `PartDemand`, `PurchaseOrderLine`, or `ShipmentLine` with no link yet
  gets its own new single-member `GraphSummary` in the same transaction as its own creation.
- **Merge**: creating an active `PurchaseOrderDemandLink`, or assigning/reassigning a
  `ShipmentLine.purchase_order_line` to a line in a different graph, coalesces the two graphs —
  every member row of the smaller graph is re-pointed to the surviving `graph_id`, the absorbed
  `GraphSummary` row is deleted, and the surviving row is recalculated.
- **Split**: soft-deleting/deactivating a `PurchaseOrderDemandLink`, or a `ShipmentLine`
  reassignment away from a line, may sever the only bridge between two parts of a graph. The write
  path runs a bounded BFS over the graph's remaining active edges (`PurchaseOrderDemandLink`,
  `ShipmentLine.purchase_order_line`) from an arbitrary surviving member; if the reachable set is
  smaller than the graph's full membership, the unreached rows are re-pointed to a newly created
  `GraphSummary`, and both resulting summaries are recalculated. Reuses the same "small clusters, an
  O(N) BFS on unlink is negligible" reasoning as D79/D70 §3.4 — no separate safety cap needed here
  the way D70 §3.5's resolver needed one, because membership is already bounded by the graph itself,
  not an unbounded traversal target.
- **Recalculate**: one function/manager method, `GraphSummaryManager.recalculate(graph_id)`,
  computing D81's eight columns plus `status` from current member rows. Called at the end of every
  node-init/merge/split above — never left for a caller to remember separately.

These hooks are wired into `PurchaseOrderDemandLinkManager` (create/deactivate) and
`ShipmentLineManager`/`ShipmentLineSplitHandler` (create/reassign/split), the existing control-layer
seams that already own those writes — no new write path is introduced solely for graph maintenance.

**D83 — `Package`/`PackageLine` are fully renamed to `Shipment`/`ShipmentLine` throughout the
codebase — models, `db_table`s, migrations (full reset per this project's migration strategy),
control-layer class names, guards/managers/narrators/factories, `urls_packages.py` →
`urls_shipments.py`, entrypoints, templates, and tests. `PackageStatus` → `ShipmentStatus`,
`package_number` → `shipment_number`, `PurchaseOrder.packages` related_name → `PurchaseOrder.shipments`.**

Not a relabel-only change — the earlier "UI label only" option was considered and rejected in
favor of the full rename, so the codebase's naming matches the UI end to end rather than carrying a
permanent Package/Shipment naming mismatch between the database and the screen. The `receive`
permission codename (D78) and its docstring ("Can create packages...") are updated to say
"shipments"; the codename itself (`procurement.receive`) is unchanged, since renaming a permission
codename after any group fixture references it is a migration hazard this pass avoids — only the
human-readable name changes.

**Scope reaffirmed, not changed:** a `Shipment` still tracks pre-possession only — from the moment
a PO exists (or a shipment is received reactively ahead of one, D74) through
`Delivered to Local Receiving Location`/`Accepted`. Intake (put-away, bin, stock levels) is still
out of scope (D47), unchanged by the rename.

**D84 — The Inventory side of "Shipments" is a thin duplicate view/edit surface, not a
second owned table.** `app/inventory/` gains a mirrored URL surface at `inventory/shipments/...`
(paralleling `procurement/shipments/...`) that reads and manually edits the **same**
`Shipment`/`ShipmentLine` rows procurement owns — there is no `inventory.Shipment` model. Consistent
with this app's existing one-directional-dependency rule (D7, D46) — Inventory is the one app
allowed to depend on Procurement's data, not the reverse — and avoids a second source of truth that
would need reconciling with procurement's own shipment records. "Manual editing of columns" for this
pass means direct field edits through the mirrored UI (no new business rules, no new guard beyond
what `ShipmentContext`/`ShipmentLineManager` already enforce) — the promised heavier
Inventory-side logic (intake, stocking, movement) is future work, not this pass's job.

**D85 — The graph visualizer page (`procurement/graph/<graph_id>/` or similar) renders a
mermaid.js swimlane diagram of the graph's Demand/PO-Line/Shipment-Line membership and edges, above
a three-column summary (Demand headers+rows, PO headers+rows, Shipment headers+rows) — same visual
shape D70 §5 already specified for the (now unbuilt) resolver-backed visualizer, re-pointed at the
materialized `GraphSummary`'s member rows instead of a live traversal.** `mermaid.js` is vendored
into `app/static/` (no CDN dependency at runtime, consistent with this project having no external
JS package pipeline) and rendered client-side from a small edge-list the view serializes into the
page. This is the only page in the app that visualizes `GraphSummary` membership directly; every
other page keeps using the entity's own `graph_id`-scoped rollup numbers (D81), never a rendered
graph.
