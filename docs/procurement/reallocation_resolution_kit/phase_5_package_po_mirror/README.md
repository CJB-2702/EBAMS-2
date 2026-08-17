# Phase 5 — Package↔PO Domain mirror

Build the same shrinking-source resolution mechanics and Portal shape as Phases 1–2,
scoped entirely to package (shipment) lines and their order-line allocations. This
domain is deliberately simpler: a package line has no "outside" relationship the way a
demand does, so nothing from Phases 3–4 has an equivalent here (§3, §10 closing note).

## Goal

An order-line allocation drawn from a package line behaves identically, rule-for-rule,
to Phases 1–2's demand-side mechanics — locked floor, silent auto-update paths,
demand-requeue's package-side equivalent, the Portal, the waterfall, manual entry, and
the two-popup unlock sequence — entirely self-contained to that one package line.

## In scope

- Locked/open state on each package-line-to-order-line claim, earned the same way:
  set only when real-world progress (received/accepted) has happened against that
  specific claim.
- Locked-floor refusal: a package line's quantity/accepted-quantity edit cannot drop
  below the sum of its own locked claims.
- The same two silent auto-update paths (full-cover, single-open-claim).
- The Reallocation Portal, built as its own independent instance for this domain — not
  a generalization of Phase 2's Portal (§7.7). Same waterfall ordering rule, same
  manual-entry rules, same two-popup unlock sequence.
- Whatever this domain's equivalent of "the claim's own upstream need reappears
  somewhere for someone to notice" turns out to be, if one exists here — confirm with
  the Business Architect persona before building; §7.12 was specified for the demand
  side and was not explicitly re-confirmed for packages in the source document.

## Out of scope

- Cross-domain visibility (Phase 3) — does not apply; a package line has no other
  package it could also be claimed against.
- Cross-order over-allocation refusal (Phase 4) — does not apply, same reason.
- Any code sharing with the Demand↔PO Domain's implementation that would create a
  dependency between the two domains. Shared *patterns* are fine and expected; shared
  *state or lookups* are not (§7.7).

## Dependencies

None beyond Phase 1 having established the pattern once. Can be built in parallel with
Phases 2–4 rather than strictly after them.

## Deliverables

- Locked/open state on package-to-order-line claims.
- Locked-floor refusal and the two silent auto-update paths, package-side.
- An independent Reallocation Portal instance for this domain.

## Exit criteria

- [ ] A package line's accepted-quantity reduction below its own locked total is
      refused, mirroring Phase 1's order-line behavior exactly.
- [ ] A shortfall across multiple package-to-order-line claims opens this domain's own
      Portal and resolves via the same waterfall/manual/unlock rules as Phase 2.
- [ ] No code path in this phase reads or writes anything belonging to the Demand↔PO
      Domain.
- [ ] Acceptance scenario 10 from `reallocation_resolution_portal.md` §11 passes end
      to end.
