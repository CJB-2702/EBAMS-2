---
type: "Technical Decision"
title: "Build Plan"
description: "Order of construction for the Reallocation Resolution Portal, derived from reallocation_resolution_portal.md."
tags: [technical-decisions, technical-decision, reallocation-resolution-kit]
context_tier: 2
---

# Build Plan

Five phases, in dependency order. Phases 1–4 build the Demand↔PO Domain end to end;
Phase 5 mirrors the shrinking-source mechanics onto the Package↔PO Domain, which is
deliberately simpler (§3 of the source document — a package line has no "outside"
relationship to worry about).

```
Phase 1 (data + core rules) ──▶ Phase 2 (Reallocation Portal UI)
                                       │
                                       ├──▶ Phase 3 (cross-domain visibility)
                                       │
                                       └──▶ Phase 4 (cross-order refusal)

Phase 1's pattern (independently) ───▶ Phase 5 (Package↔PO mirror)
```

Phase 5 can start any time after Phase 1 lands — it does not depend on Phases 2–4,
since the Package↔PO Domain never needs cross-domain visibility or cross-order
refusal. Building it in parallel with Phase 2 is fine if two people/sessions are
available; sequential is fine too.

## Phase 1 — Core capacity rules (Demand↔PO Domain)

The quantity columns and the non-negotiable validation rules: the locked floor, the
two silent auto-update paths, and the automatic demand-requeue on any reduction.
**No new UI in this phase** — these rules must hold even before the Portal exists,
enforced directly on the existing PO-line-edit path.

→ [phase_1_core_capacity_rules/README.md](phase_1_core_capacity_rules/README.md)

## Phase 2 — The Reallocation Portal (Demand↔PO Domain)

The interrupt screen itself: LOCKED/OPEN split, the priority+needed-by waterfall,
manual entry, and the two-popup unlock sequence. This is the centerpiece — the
deliberate modal exception (§7.8, `# DELIBERATE ANTI-PATTERN`).

→ [phase_2_reallocation_portal/README.md](phase_2_reallocation_portal/README.md)

## Phase 3 — Cross-domain visibility (Demand↔PO Domain only)

Makes the conflicts Phase 4 refuses visible *before* a user hits them: the inline
"claimed elsewhere" hint on the linkage screen, and the Portal's external-locked
claims display (§4).

→ [phase_3_cross_domain_visibility/README.md](phase_3_cross_domain_visibility/README.md)

## Phase 4 — Cross-order over-allocation refusal (Demand↔PO Domain only)

The hard-stop guard, independent of the Portal's own shrinking-source math: refuse a
new/grown claim that would push a demand's total across every order it touches beyond
its requested quantity, with a message naming the conflicting order and a direct link
to it (§10).

→ [phase_4_cross_order_refusal/README.md](phase_4_cross_order_refusal/README.md)

## Phase 5 — Package↔PO Domain mirror

Same shrinking-source mechanics and Portal shape as Phases 1–2, scoped to package
(shipment) lines and their order-line allocations. No cross-domain visibility, no
cross-order refusal — a package line has no equivalent conflict to surface (§3, §10
closing note).

→ [phase_5_package_po_mirror/README.md](phase_5_package_po_mirror/README.md)

## Checkpoints

- **After Phase 1:** a shrinking order line's claims resolve correctly with zero UI —
  auto-update, single-claim auto-update, and locked-floor refusal are all provable
  from the existing edit form, before the Portal exists to catch the harder cases.
- **After Phase 2:** every acceptance scenario in `reallocation_resolution_portal.md`
  §11 that involves only one order (scenarios 1–6, 9) passes end to end.
- **After Phase 3:** scenario 8 (proactive visibility) passes — a user can see a
  demand's other-order claim before attempting a conflicting one.
- **After Phase 4:** scenario 7 (cross-order refusal) passes.
- **After Phase 5:** scenario 10 (package side, fully independent) passes.

## Confirmed UI placement (2026-08-16)

Resolved during the front-end kitting session, before UI build began. These are
binding on every phase's UI deliverables — do not re-litigate placement per phase.

- **PO line quantity-edit control:** inline in **Edit & Linkage**'s (`purchase_orders/edit.html`)
  Lines list, not PO Detail.
- **Reallocation Portal (Demand↔PO Domain):** full-screen/modal overlay on **Edit &
  Linkage** — the deliberate no-modal-for-assignment exception (§7.8).
- **`record_receipt`:** inline per claim row in Edit & Linkage's current-links table.
  Adds a "manually adjusted — not a safe computed value" flag/badge on the resulting
  locked claim (reuses the existing `is_locked` field — no new schema column). Submitting
  shows a confirmation popup warning that adding shipment lines later will require
  manual reconciliation.
- **Shipment line quantity-edit control:** inline in `shipment_edit`'s (`shipments/edit.html`)
  Items list. No backend blocker — `shipment_edit`'s handler already supports this.
- **Reallocation Portal (Package↔PO Domain):** mirrors the Demand↔PO Portal, overlaid on
  `shipment_edit`. No backend blocker.
- **Routing prerequisite:** see [routing_decision_pending.md](routing_decision_pending.md) —
  Option A confirmed. `edit_line`, `record_receipt`, and the six `reallocation_*` actions
  must be added to `purchase_order_edit`'s own POST handler before the Demand↔PO-side UI
  above can be wired up; the Package↔PO side has no such blocker.

## Guardrails (apply to every phase)

- Every rule in `reallocation_resolution_portal.md` §7, §10's rule list, and the
  acceptance scenarios in §11 is the acceptance bar — not this build plan's prose.
  If this plan and that document ever disagree, the document is correct.
- The Reallocation Portal is a **deliberate** exception to the platform's normal
  no-modal-for-assignment convention (§7.8). Do not "fix" it into an in-page pattern.
- Demand↔PO Domain and Package↔PO Domain code must not share state or reach into each
  other (§7.7). Phase 5 is a parallel implementation, not a generalization of
  Phases 1–4.
- No phase introduces a cached/staleness window — every screen re-checks live totals
  on view and on submit (§10, point 3).
