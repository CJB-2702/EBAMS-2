# Phase 2 — The Reallocation Portal (Demand↔PO Domain)

Build the interrupt screen itself: the deliberate, full-attention resolution tool that
Phase 1 deferred to. This is the centerpiece of the whole kit and the one screen this
project's normal no-modal-for-assignment convention does not apply to (§7.8) — it
exists specifically to force resolution before a save can proceed, which an in-page
pattern cannot do.

## Goal

Every shortfall shape Phase 1 safely refused now has a real path through it: the
Portal opens instead of refusing, shows LOCKED and OPEN claims, offers auto-allocate
and manual paths, and lets a user deliberately unlock a claim through the two-popup
sequence when nothing else can free enough capacity.

## In scope

- **Portal trigger:** replaces Phase 1's "not yet supported" refusal for any shortfall
  involving 2+ claims, or a single locked claim, on an order line (§5's flowchart).
- **LOCKED/OPEN display:** every active claim on the line being resolved, split by
  lock state.
- **Auto-allocate waterfall (§7.1, §7.6):** reduces OPEN claims only, ordered by
  priority tier (Critical → High → Medium → Low), then needed-by date within a tier,
  then earliest-claimed as the final tie-break.
- **Manual entry:** per-claim value entry against OPEN claims only, allowing
  under-claiming but never a total that exceeds the new source quantity (§7.4, §7.5).
- **The two-popup unlock sequence (§6):** selecting a locked claim to free opens a
  *second*, separate confirmation carrying the explicit downstream-risk warning
  ("this forces an automated status update on the demand and may cause downstream
  errors or inconsistencies"); only explicit approval moves the claim from locked to
  open, and only within this already-open Portal session.
- **Commit gate:** the triggering order-line edit cannot save until
  `sum(OPEN + LOCKED) == new source quantity` is achieved by either path.
- Demand-requeue (Phase 1's rule) must keep firing correctly from every path through
  this Portal, including after an unlock-and-redistribute.

## Out of scope

- Anything about a demand's claims on *other* orders — Phase 3 builds the visibility,
  and this phase's own math never includes them (§4's note under the core-rule
  flowchart: external claims are never part of `sum(OPEN + LOCKED)`).
- The cross-order over-allocation refusal for *growing* a claim — Phase 4. This phase
  only handles a *shrinking* source.
- The Package↔PO Domain — Phase 5 builds its own, independent Portal instance; do not
  generalize this one to serve both domains (§7.7).

## Dependencies

Phase 1 (locked/open state, the silent paths this Portal is the fallback for, and the
demand-requeue rule this Portal must keep triggering correctly).

## Deliverables

- The Reallocation Portal screen/flow, triggered from the order-line edit path.
- Auto-allocate waterfall logic.
- Manual entry with the under-claim-allowed / over-claim-never validation.
- The two-popup unlock confirmation sequence, replacing Phase 1's placeholder.
- Commit gating tied to portal resolution state.

## Exit criteria

- [ ] A shortfall across 3 unlocked claims of differing priority resolves via
      auto-allocate exactly per the waterfall order, protecting the highest-priority /
      soonest-needed claim first.
- [ ] The same scenario with the lowest-priority claim already locked correctly
      refuses to auto-reduce it, and the Portal surfaces that the shortfall has
      nowhere to go without an unlock.
- [ ] Choosing to unlock that claim requires the second confirmation popup with the
      stated warning; declining leaves the claim locked and the Portal open;
      approving moves it to open and lets resolution continue.
- [ ] Manual entry rejects any combination of values summing above the new source
      quantity, and accepts a combination that leaves some of it unclaimed.
- [ ] The triggering order-line save is blocked at every point until the Portal
      reaches a valid state, and proceeds immediately once it does.
- [ ] Acceptance scenarios 3, 4, 5, and 9 from `reallocation_resolution_portal.md` §11
      pass end to end.
