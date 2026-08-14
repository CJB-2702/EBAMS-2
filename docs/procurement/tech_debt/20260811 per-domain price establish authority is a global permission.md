---
type: "Technical Decision"
title: "Tech Debt: price_establish is a global Django permission, not scoped per-domain"
description: "D89 defines establish authority as per-domain, but Phase 1 of the price observation kit ships price_establish as an ordinary global Django permission — anyone holding it can verify a price for every domain, not just the ones they own."
tags: [technical-decisions, technical-decision, tech-debt, procurement, pricing, authorization]
context_tier: 2
---

# Tech Debt: `price_establish` is a global Django permission, not scoped per-domain

**Logged:** 2026-08-11
**Source:** `price_observation_mini_kit/README.md` D89; `price_observation_mini_kit/build_plan.md`
§3.5, §4.1, §7.3.
**Status:** deliberately deferred for the pricing kit's first cut (Phases 1–4 + 7). Not a defect in
that build — a known, accepted gap flagged in the kit itself.

## The problem

D89 splits pricing authority into three levels — **use**, **record**, **establish** — and is
explicit that establish authority is **per-domain**: East Coast's price authority is not West
Coast's. Django's permission system has no notion of "this permission, but only for domain X";
`request.user.has_perm("procurement.price_establish")` is a single global yes/no.

Phase 1 ships `price_establish` as an ordinary custom permission on
`PartPriceObservation.Meta.permissions` (`app/procurement/models/pricing/part_price_observation.py`)
and exposes it through `can_establish_price(request)` in
`app/procurement/presentation_layer/tools/procurement_access.py`. Anyone holding it can write
`is_verified=True` for **any** domain their `visible_domain_ids` covers, not only the domain(s)
they hold establish authority for. The "only one person in the whole organization" case D89
describes as a free special case of the per-domain model is, right now, the *only* case the system
actually enforces.

## Where the gap is enforced but not closed

`PartPriceObservationValidator.validate` in
`app/procurement/control_layer/guards/part_price_observation_guard.py` carries the guard's single
call site for this check, marked in place:

```python
if is_verified and not actor_can_establish:
    # TODO(D89): narrow this to the row's own domain once per-domain
    # establish authority exists — today it is a global permission.
    errors.append(...)
```

`actor_can_establish` is computed once per request (today, from the global permission) and passed
down uniformly to every row in a bulk write, including the batch-level "Record as verified"
checkbox on the bulk grid (`bulk_observation_screen.md`) and any future single-row verify action.

## What it costs while deferred

- A Buyer holding `price_establish` for their own domain can verify a price for a domain they have
  no real authority over, as long as it's in their visible-domain set. The mistake is visible (an
  append-only row, attributable to `created_by`) but not prevented.
- The dev fixture grants `price_establish` at the group level
  (`app/administration/fixtures/dev_auth_groups.json`), which is correct for exercising the
  established/unverified code paths in dev but cannot model per-domain authority at all.

## Shape if revisited

This is an admin-engineering task (build_plan.md explicitly hands it off): the mapping from
"actor X may establish prices for domain Y" needs a per-domain grant, most naturally shaped like
the existing `UserDomain`/ownership-group scoping already used elsewhere in `administration`
(`harness/Authorization/data_ownership.md`) rather than a new bespoke table. Once that grant exists,
`can_establish_price` becomes `can_establish_price_for_domain(request, domain_id)`, and the guard's
`actor_can_establish: bool` parameter becomes a `establishable_domain_ids: set[int]` set, checked
per-row instead of once per request.

## Related

- [`20260811 soft lock on line price override is deferred.md`](20260811%20soft%20lock%20on%20line%20price%20override%20is%20deferred.md)
  — D90, the other authority-level gap left open by the same phase.
- `price_observation_mini_kit/README.md` D89.
- `price_observation_mini_kit/build_plan.md` §1.7, §3.5, §7.3.
