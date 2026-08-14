---
type: "Technical Decision"
title: "Tech Debt: D90's soft lock on PO line price override is not enforced"
description: "D90 says a Use-level actor may fill a blank unit_cost but not override an existing one; the permission set has no Use level yet, so any editor can currently overwrite any line's price unconditionally."
tags: [technical-decisions, technical-decision, tech-debt, procurement, pricing, authorization]
context_tier: 2
---

# Tech Debt: D90's soft lock on PO line price override is not enforced

**Logged:** 2026-08-11
**Source:** `price_observation_mini_kit/README.md` D89/D90; `price_observation_mini_kit/build_plan.md`
§7.3.
**Status:** deliberately deferred for the pricing kit's first cut (Phases 1–4 + 7). Flagged as
deferred in the build plan itself, not a defect in that build.

## The problem

D89 defines three authority levels — **use**, **record**, **establish**. D90 adds a soft lock at
the *use* level: an actor who can only *use* a suggested price may type a value into a blank
`unit_cost` field, but may not change one that already has a value. The point is to avoid a hard
dead end (a part with no price on record blocking someone from filing) while still stopping the
lowest-authority actor from silently overwriting an established or recorded price.

Today there is no *use* level in the Django permission set at all — only `procurement.buy` (record)
and `procurement.price_establish` (establish). `_detail_edit_line` in
`app/procurement/presentation_layer/entrypoints/purchase_orders.py` and its sibling on the
create-wizard path let any actor who can reach the PO detail/edit screen change `unit_cost` on any
line, blank or not, with no override check. The marker sits at
`app/procurement/presentation_layer/entrypoints/purchase_orders.py` in `_detail_edit_line`,
directly above where `unit_cost` is read out of `changes`:

```python
# TODO(D90): soft lock — a Use-level actor may fill a blank unit_cost but
# not override one that already exists. Deferred: there is no "Use"
# authority level in the permission set yet (build_plan.md §7.3), so this
# currently lets any editor overwrite any line's price unconditionally.
```

## What it costs while deferred

- Anyone who can edit a PO line (today, effectively anyone with `procurement.buy`) can overwrite an
  established price on their own order with no distinct guard rail — the three-level authority
  model D89 describes collapses to two in practice (record and establish; use does not exist as a
  restriction).
- The chip's **Use this** button (D91/D92) and the divergence prompt's *Just this order* path
  (Phase 6, not yet built) both write `unit_cost` through this same entrypoint, so they inherit the
  same gap once built.

## Shape if revisited

Needs the same admin-engineering groundwork as
[`20260811 per-domain price establish authority is a global permission.md`](20260811%20per-domain%20price%20establish%20authority%20is%20a%20global%20permission.md):
a *use* level has to exist as a checkable capability before `_detail_edit_line` (and its
create-wizard sibling) can gate on it. Once it does, the check is local — compare `changes` against
the existing `line.unit_cost`, and reject the change (or downgrade it to a no-op with a message)
when the actor holds only *use* authority and the line's `unit_cost` is already non-null.

## Related

- [`20260811 per-domain price establish authority is a global permission.md`](20260811%20per-domain%20price%20establish%20authority%20is%20a%20global%20permission.md)
  — D89, the other authority-level gap left open by the same phase.
- `price_observation_mini_kit/README.md` D90.
- `price_observation_mini_kit/build_plan.md` §7.3.
