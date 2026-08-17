# Phase 3 — Cross-domain visibility (Demand↔PO Domain only)

Make a demand's claims on *other* orders visible everywhere in this domain, so a user
can understand a conflict before triggering it rather than only being told about it
after (§4). This phase does not change any capacity math from Phases 1–2 — it adds
read-only context around it.

## Goal

Wherever a demand's claim is shown or being created in the Demand↔PO Domain, the
person looking at it can see, at a glance, whether that demand is also claimed on a
different order, and how much — without leaving the screen.

## In scope

- **Linkage screen inline hint (§4, point 1):** each demand-claim row on the
  order-line linkage screen shows, when applicable, which other order(s) that demand
  is also claimed against and for how much. Read-only at this location.
- **Reallocation Portal external-claims display (§4, point 2):** when the Portal
  (Phase 2) opens for a shortfall, it shows each affected demand's **full** claim
  picture — its local claim (from Phase 2, fully editable per those rules) plus any
  claims on other orders, displayed as a **third, distinct locked category** —
  visible, never editable here, and never counted in the Portal's own
  `sum(OPEN + LOCKED)` math (§4's note under the core-rule flowchart in §5).
- The distinction between this "external" lock and the Phase 1/2 "arrived/received"
  lock must be visually and textually unambiguous (§4's comparison table) — they have
  completely different remedies, and conflating them would tell a user an override
  exists where it does not.

## Out of scope

- Any ability to edit, unlock, or otherwise act on an external claim from this screen
  — that authority exists in exactly one place, the other order's own screen (§7.10).
  If this phase's implementation makes an external claim actionable from here in any
  way, that is a defect, not a feature.
- The refusal behavior itself for a cross-order over-allocation attempt — Phase 4.
  This phase only makes the situation visible; Phase 4 is what blocks it.
- The Package↔PO Domain — it has no equivalent relationship to surface (§3).

## Dependencies

Phase 1 (a claim's data must already distinguish a demand's various order-line
relationships). Benefits from Phase 2 existing (the Portal is one of the two places
this phase extends), but the linkage-screen hint can be built independently of it if
sequencing requires.

## Deliverables

- Inline "also claimed on Order X — Y units" indicator on demand-claim rows on the
  linkage screen.
- External-claims section/display inside the Reallocation Portal, clearly
  distinguished from the arrived/received lock category.

## Exit criteria

- [ ] A demand claimed on two orders shows the second order's claim inline on the
      first order's linkage screen, without navigating away.
- [ ] Opening the Reallocation Portal for a shortfall involving a demand that also
      has an external claim shows that external claim, visibly locked, with no control
      that could edit or unlock it.
- [ ] A user cannot distinguish an external-locked claim from an arrived-locked claim
      by behavior alone — the labeling makes the difference in remedy obvious without
      trial and error.
- [ ] Acceptance scenario 8 from `reallocation_resolution_portal.md` §11 passes end to
      end.
