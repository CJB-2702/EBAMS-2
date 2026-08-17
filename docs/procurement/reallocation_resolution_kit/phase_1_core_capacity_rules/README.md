# Phase 1 — Core capacity rules (Demand↔PO Domain)

Introduce the locking concept and enforce every rule from
`reallocation_resolution_portal.md` that does **not** require a dedicated resolution
screen. This phase makes the existing purchase-order-line edit path correct and safe
on its own — the Reallocation Portal (Phase 2) is what makes the harder cases
*resolvable*, not what makes them *safe*. A build that stops after Phase 1 must never
produce an invalid state; it is allowed to simply refuse the cases it can't yet help
the user through.

## Goal

Every demand-to-order-line claim can be represented as **locked** or **open**, locked
being earned only by real-world fulfillment (§7.2), never assumed. The three rules
that don't need a UI screen are enforced directly on the order-line edit path: the
locked floor, the two silent auto-update paths, and automatic demand-requeue.

## In scope

- A way to record, per demand-to-order-line claim, whether it is **locked** — set the
  moment real-world fulfillment happens against that specific claim (its portion has
  arrived/been accepted), and cleared only by the deliberate two-popup override that
  Phase 2 will build (§7.2, §7.3). This phase can build the state and the "system
  never sets it back to open" rule without yet building the popup UI — the override
  path can be a placeholder that Phase 2 replaces.
- **Locked-floor refusal (§5, §7.11):** an order-line quantity edit that would drop
  below the sum of that line's locked claims is refused outright, before anything
  else runs, with a plain message stating how much is locked.
- **Silent full-cover update (§5):** an edit that still covers every active claim
  against the line updates with no interruption.
- **Silent single-claim update (§5, §7.9):** an edit that leaves a shortfall but only
  one active claim exists, and that claim is unlocked, updates that one claim to the
  new value with no interruption.
- **Automatic demand-requeue (§7.12):** any reduction to a claim — by whatever path —
  puts that demand's unmet amount back in front of the Buyer's open queue without
  manual re-entry.
- **Everything else (2+ claims, shortfall, no single-claim shortcut available):**
  refused for now with a plain "not yet supported — resolution tool is coming" message.
  This is a **temporary** state specific to Phase 1 landing before Phase 2 — it must
  not corrupt data, but it does not need to be a good experience yet.

## Out of scope

- The Reallocation Portal UI itself — Phase 2.
- The two-popup unlock confirmation UI — Phase 2 (this phase only needs the locked
  state to exist and be respected).
- Cross-domain visibility (inline hints, external-claim display) — Phase 3.
- Cross-order over-allocation refusal — Phase 4.
- Anything on the Package↔PO Domain — Phase 5.

## Dependencies

None. This is the first phase.

## Deliverables

- Locked/open state on each demand-to-order-line claim, set only by real-world
  fulfillment, never by a caller choosing to.
- Order-line quantity edit validation implementing the locked-floor refusal.
- Silent-update logic for the full-cover and single-open-claim cases.
- Demand-requeue triggered by any claim reduction, regardless of source.
- A safe (not silent, not corrupting) refusal path for every shortfall shape this
  phase doesn't yet resolve.

## Exit criteria

- [ ] Reducing an order line's quantity when locked claims alone exceed the new value
      is refused, with the locked total stated in the message. No data changes.
- [ ] Reducing an order line's quantity that still covers all active claims updates
      immediately, with no additional confirmation step.
- [ ] Reducing an order line's quantity that leaves exactly one active, unlocked claim
      short updates that claim's value automatically, with no additional confirmation
      step.
- [ ] A demand whose claim was just reduced appears in the open buying queue for
      exactly its new shortfall — verified by reading the queue immediately after.
- [ ] Any other shortfall shape (2+ claims short, or the sole claim locked) is refused
      cleanly with an explanatory message, not silently mis-applied and not a crash.
- [ ] Acceptance scenarios 1, 2, and 6 from `reallocation_resolution_portal.md` §11
      pass end to end.
