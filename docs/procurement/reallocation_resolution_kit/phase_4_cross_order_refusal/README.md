# Phase 4 — Cross-order over-allocation refusal (Demand↔PO Domain only)

The hard-stop guard for the other shape of conflict: a claim trying to **grow** on one
order while the same demand already carries a claim on a different order (§10). This
is independent of the shrinking-source math in Phases 1–2 — it fires when *creating or
increasing* a claim, not when a source shrinks.

## Goal

A demand can never end up claimed, in total across every order it touches, for more
than it actually needs — and when an attempt would cross that line, the user is told
exactly which other order is the reason and sent straight there.

## In scope

- **The refusal itself (§10, rule 1):** creating or increasing a claim that would push
  a demand's total active claims — summed across *every* order it touches, not just
  the one on screen — beyond its requested quantity is refused outright. No
  auto-resolve, no waterfall, no unlock flow, and — deliberately — **no offer to raise
  the demand's requested quantity**, even though that escape hatch exists elsewhere in
  the system for other cap conflicts. This case is not offered it.
- **The message (§10, rule 2):** names the conflicting order and the exact shortfall
  in plain terms, and includes a direct link to that order's own linkage screen.
- **Always-live totals (§10, rule 3):** the total this guard checks against is
  computed fresh at the moment of submission, every time — there is no cached number
  that could let a stale page pass a check that should have failed.

## Out of scope

- Anything about a *shrinking* source — that is Phases 1–2's domain entirely; this
  phase never touches that logic.
- The proactive inline hint that helps a user avoid triggering this refusal in the
  first place — that's Phase 3, and this phase's guard is correct and necessary
  whether or not Phase 3 has shipped yet (Phase 3 reduces how often this fires; it
  does not replace the need for it — see §10's introduction).
- The Package↔PO Domain — a package line has no equivalent second ceiling to
  double-claim against, so this phase does not apply there at all (§10's closing
  note). Do not build a parallel version of this guard for Phase 5.

## Dependencies

Phase 1 (needs the same claim data model). Does not strictly depend on Phase 2 or 3 —
this guard is a write-time check on claim creation/growth, separable from the
Reallocation Portal's own shortfall-resolution flow. Building it right after Phase 1
is fine if that's a better sequencing fit; the build plan lists it after Phase 3 only
because seeing the conflict coming (Phase 3) is the better user experience to ship
alongside it, not because of a hard technical dependency.

## Deliverables

- Write-time validation on claim create/increase, checking the demand's total across
  every order, not just the local one.
- Refusal messaging that names the specific conflicting order and links to it.
- Confirmation that this check always reads live data, never a value cached from page
  load.

## Exit criteria

- [ ] Attempting to claim a quantity that would push a demand's cross-order total
      above its requested quantity is refused, with the specific other order named in
      the message and a working link to that order's linkage screen.
- [ ] No "raise the requested quantity" option appears anywhere in this refusal path.
- [ ] The check is proven to use a live total, not a page-load snapshot — e.g., a
      second claim added elsewhere between page load and this submission is correctly
      caught.
- [ ] Acceptance scenario 7 from `reallocation_resolution_portal.md` §11 passes end to
      end.
