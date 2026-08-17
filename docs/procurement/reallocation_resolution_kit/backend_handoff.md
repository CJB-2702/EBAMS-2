---
type: "Handoff"
title: "Backend Handoff — Reallocation Resolution Portal"
description: "What the backend build session delivered, and the exact surface the frontend build session should call. Backend-only; no templates exist yet."
tags: [reallocation-resolution-kit, handoff, backend, frontend]
context_tier: 1
---

# Backend Handoff — Reallocation Resolution Portal

**Status:** All 5 phases implemented on the backend (models, guards, managers,
contexts, entrypoint actions, domain structs). **No templates exist.** This
document is what a frontend build session needs to read before touching
`app/procurement/templates/`.

Source of truth for the business rules is still
[`reallocation_resolution_portal.md`](../reallocation_resolution_portal.md) —
read that first if you haven't. This document only maps those rules onto the
actual Python surface now in the codebase.

---

## 1. The one architectural decision you need to know about

The kit's §1 proposed storing allocated/received/accepted quantities directly
on the link tables. That reverses three previously-documented decisions in
this codebase (D53, D55, D90 — see `purchase_order_demand_link.py` and
`purchase_order_shipment_link.py` docstrings). **The user explicitly approved
the reversal** for this build. Two consequences that affect how you render
things:

- `PurchaseOrderDemandLink` (Demand↔PO side) now carries **real, stored**
  `quantity_received` and `is_locked` columns, written only by a deliberate
  human action (`record_receipt`). This is genuinely new data a receiver
  types in — build a UI action for it, it doesn't happen automatically.
- `PurchaseOrderShipmentLink` (Package↔PO side) only carries `is_locked` — a
  **cache**, not typed data. It flips true automatically the moment the
  shipment line is inspected (`quantity_accepted` set), applied to every
  claim on that line uniformly. There is no per-claim "mark received" action
  on this side — don't build one.

The docs update at the end of this document (§7) has the full decision
record.

---

## 2. Demand↔PO Domain (Buying) — Phases 1–4

### Where the trigger lives

`PurchaseOrderLineManager.edit_line()` (called via
`PurchaseOrderContext.edit_line()`) is the existing PO-line-edit path — same
route the current Edit & Linkage / PO detail "edit line" forms already post
to. Reducing `quantity_ordered` now runs through
`PurchaseOrderLineValidator.check_quantity_floor` (locked-floor hard stop) and
`PurchaseOrderLineManager._resolve_quantity_shortfall` (silent paths). Nothing
new to wire up here — **the existing edit-line form already exercises this**;
what changes is what can come back from it:

| Outcome | What happens today | What the frontend must show |
|---|---|---|
| Still covers all claims | Saves silently | Nothing — existing success flow |
| One open claim, shortfall | Claim auto-updated, saves silently | Nothing — existing success flow, maybe surface the narrator message |
| Below locked total | `ProcurementValidationError` | Existing error-message flow — no portal |
| 2+ claims, or sole claim locked | `ReallocationRequired` raised, **session draft seeded automatically** by the entrypoint, warning message flashed | **Redirect/prompt the user into the Reallocation Portal** |

The entrypoint (`app/procurement/presentation_layer/entrypoints/purchase_orders.py`,
`_detail_edit_line`) already catches `ReallocationRequired` and seeds
`reallocation_draft` in the session — you don't need to catch the exception
yourself from a template's perspective, just detect that a reallocation is
now in progress (see §4) and route the user there.

### The Portal's actions (all POST, `action=` dispatch on `purchase_order_detail`)

| `action` | Does | Needs |
|---|---|---|
| `reallocation_auto_allocate` | Runs the priority+needed-by waterfall, stages results in the session draft | Nothing — reads the draft's `line_id`/`new_quantity_ordered` |
| `reallocation_manual_entry` | Stages user-typed per-claim values | POST fields `claim_<link_id>` per open claim |
| `reallocation_unlock_claim` | Two-call contract: first call (no `confirmed`) returns the warning message and writes nothing; second call with `confirmed=1` actually unlocks | POST `link_id`, second call also `confirmed=1` |
| `reallocation_commit` | Validates `sum(OPEN + LOCKED) <= new_quantity_ordered`, writes everything in one transaction, clears the draft | Nothing extra |
| `reallocation_cancel` | Clears the draft, no writes | — |
| `record_receipt` | Marks part of a claim received → locks it. Separate from the Portal flow — this is what a receiver does on an ordinary day to CREATE a locked claim in the first place | POST `link_id`, `quantity_received` |

**Read models to render the Portal:**
- `ReallocationPortalStruct.load(line_id=...)` — the full picture: `open_claims`,
  `locked_claims` (each carrying its own `external_claims` tuple),
  `open_total`, `locked_total`. This is call site 2 from §4 of the business
  doc — re-derived live on every load, never cached.
- The session draft itself (`reallocation_draft.load(request.session)`) —
  `{line_id, new_quantity_ordered, proposed: {link_id: value}, unlocked_this_session: [...]}`.
  Join `proposed` against `ReallocationPortalStruct.open_claims` to show
  what the user has staged so far.

**§7.8 reminder:** this screen is a **deliberate exception** to the
no-modal-for-assignment rule (`# DELIBERATE ANTI-PATTERN`). Build it as a
full-screen/modal interrupt, not the usual in-page left-heavy pattern.

### Cross-domain visibility (Phase 3, read-only, no new actions)

- `PurchaseOrderStruct.load(purchase_order_id=...).allocations_by_line` —
  each `AllocationSlice` now carries `quantity_received`, `is_locked`, and
  `external_claims` (tuple of `ExternalClaim`). This is the existing PO
  detail/linkage-screen struct, just extended — no new call site needed on
  your end, just new fields to render inline per row.
- Render external claims **read-only**, visually distinct from `is_locked`
  (different remedy — see the comparison table in
  `reallocation_resolution_portal.md` §4). Link each external claim to its
  own order's detail page (`purchase_order_detail`, `purchase_order_id`).

### Cross-order refusal (Phase 4, no new UI surface — just an error to handle)

`_allocate_from_form` (the existing allocate action) now also raises
`CrossOrderAllocationExceeded` on a cross-order over-claim. It's handled
distinctly from `AllocationCapExceeded` already — the message names the
conflicting order and the entrypoint appends a direct URL to that order's
detail page. **No "raise the requested quantity" option should ever be
offered for this specific error** — that's deliberate (§10 rule 1); don't
reuse the cap-decision dialog's raise-request button for it.

---

## 3. Package↔PO Domain (Receiving) — Phase 5

Structurally identical shape, entirely separate code path (no shared state
with the Demand↔PO Domain — don't reuse components across the two).

| Concept | Demand↔PO | Package↔PO |
|---|---|---|
| Source | `PurchaseOrderLine.quantity_ordered` | `ShipmentLine.quantity` (the **shipped** amount — not `quantity_accepted`) |
| Claim | `PurchaseOrderDemandLink.quantity_allocated` | `PurchaseOrderShipmentLink.quantity_allocated` |
| Edit entrypoint | existing "edit line" action | **new** `action="edit_quantity"` on `shipment_edit` (`shipments.py`) — this action did not exist before this build |
| Trigger exception | `ReallocationRequired` | `PackageReallocationRequired` |
| Session draft | `reallocation_draft.py` | `package_reallocation_draft.py` |
| Portal actions | `reallocation_*` on `purchase_order_detail` | `reallocation_*` (same names) on `shipment_edit` |
| Guard | `ReallocationValidator` | `PackageReallocationValidator` |
| Waterfall | `ReallocationWaterfallHandler` | `PackageReallocationWaterfallHandler` |

There is **no** cross-domain-visibility or cross-order-refusal equivalent
here (§3/§10 of the source doc — a package line has no "outside"
relationship). Don't build those UI elements for this domain.

**Judgment call worth knowing:** a `PurchaseOrderShipmentLink` claim has no
priority/needed_by of its own (those live on `PartDemand`, and a PO line can
have zero, one, or several demand links). `PackageReallocationWaterfallHandler`
derives an effective priority from the most urgent active demand link on the
claimed PO line, falling back to lowest-priority-no-deadline for a claim on
an unlinked (proactive-stock) PO line. This is documented in the handler's
own docstring — surface it in the UI if useful (e.g. "derived from demand
#123" next to the priority badge) but it's not required.

**No demand-requeue equivalent was built for this domain.** The kit's own
Phase 5 README flagged this as unconfirmed with the Business Architect — it
was left out rather than guessed at. If the frontend session needs "what
happens to the shortfall after a package-side reduction" answered, that's a
business question to raise, not a missing frontend feature.

---

## 4. Detecting "a reallocation is in progress" for routing

There's no dedicated Portal URL/route yet — this build is backend-only.
Whatever frontend route you add for the Portal page should, on GET, check:

```python
from app.procurement.presentation_layer.tools import reallocation_draft
draft = reallocation_draft.load(request.session)  # None if nothing in progress
```

(and the `package_reallocation_draft` equivalent for the Receiving side). If
a draft exists for the PO/shipment being viewed, that's your signal to render
the Portal instead of (or as an overlay on) the normal detail page.

---

## 5. Seed data

`seed_procurement_dev` now includes a scenario built specifically for this
UI (`_seed_reallocation_demo`, run automatically as part of the normal seed):

- **PO-D** (vendor A, part index 15): one line, ordered 100, 90 claimed —
  deliberately under the shortfall threshold, so it never trips the Portal
  path on its own. Three demand claims:
  - one **LOCKED** claim (40 units, marked received via `record_receipt`) —
    use this to build/test the locked-claim rendering and the unlock flow.
  - one ordinary **OPEN** claim (30 units, single order).
  - one **OPEN** claim (20 units) that also carries an **external** claim
    (10 units) on a second order, **PO-E** — use this pair to build/test the
    cross-domain-visibility inline hint and the Portal's external-claims
    section.

Nothing in the seed currently produces a live, uncommitted shortfall (i.e.
nothing pre-populates a `reallocation_draft` session) — the Portal itself has
to be triggered live by reducing PO-D's line quantity below 90 while
developing.

Run `/refresh-project` (or `python refresh_project.py`) to get this data;
it's idempotent and marked with `[seeded by seed_procurement_dev]`.

---

## 6. Tests to read before you start

`app/procurement/tests/`:
- `test_reallocation_core_rules.py` — Phase 1, exercises the exact
  `PurchaseOrderContext.edit_line` call sequence the edit form will trigger.
- `test_reallocation_portal.py` — Phase 2, shows the waterfall/unlock/
  manual-entry/commit call shapes in isolation from HTTP.
- `test_reallocation_cross_domain_visibility.py` — Phase 3, shows exactly
  what `AllocationSlice.external_claims` and `ReallocationPortalStruct`
  contain for a real cross-order demand.

These are the fastest way to see the real shape of every struct/dict you'll
be rendering, without spinning up the dev server.

---

## 7. Outstanding backend items (not this session's job, flagging for awareness)

- Phase 4/5 backend tests were not written this session (Phases 1–3 were;
  Phase 4's guard is exercised indirectly by the Phase 3 cross-domain test).
  Not a frontend blocker, but worth closing out at some point.
- `procurement_current_state_kit/` docs (`domain_model.md`,
  `control_layer_map.md`) update recording the D55/D90 reversal is still
  pending — tracked separately, not required to start frontend work.
- No portal URL/template/route exists — that's this handoff's whole point.
