---
type: "Technical Decision"
title: "Tech Debt: Vendor lives in procurement for build-order reasons, not design reasons"
description: "Vendor is fully described without ever mentioning a purchase order, so by the 'defined in terms of' test it belongs in a low parties/ app below parts and procurement — deferred because the pricing kit did not need a new app, receipt is PurchaseInfo.vendor/purchase_order_number degraded to free text."
tags: [technical-decisions, technical-decision, tech-debt, procurement, parts, detail-extensions, architecture]
context_tier: 2
---

# Tech Debt: `Vendor` lives in `procurement` for build-order reasons, not design reasons

**Logged:** 2026-08-11
**Source:** `price_observation_mini_kit/README.md` D79 (decided 2026-08-09 business-architecture
review).
**Status:** deliberately deferred — no code change implied, this is the receipt D79 asked to have
logged.

## The problem

`Vendor` lives at `app/procurement/models/purchasing/vendor.py`. By the project's "what is it
defined in terms of" test it does not belong there: `PurchaseOrder` cannot be described without
`Vendor`, but `Vendor` is fully described without ever mentioning a purchase order — its own
docstring says so. It lives in `procurement` because procurement needed it first (build order), not
because procurement is what it's *of*.

The clean move is a low `app/parties/` app holding external commercial organizations (`Vendor`,
`PartManufacturer`, later Customer/Contractor), sitting below both `parts` and `procurement`.

## Where the leak already shows up in the codebase

`app/detail_extensions/purchase_info/models.py`'s `PurchaseInfo` carries `vendor = CharField(200)`
and `purchase_order_number = CharField(100)` — two procurement concepts degraded to unjoinable free
text, because `assets` (which `detail_extensions` extends) cannot reach a real `Vendor` sitting
inside `procurement` without an inverted or sideways dependency. This is the receipt: a real
`parties.Vendor` FK is unreachable from `assets` today for exactly the reason D79 describes, and
this table is the place it would first matter.

## Why it was left out

Appetite for a new app was not there when D79 was decided, and the price-observation kit (D79–D92)
does not require it — everything in that kit stays inside `app/procurement/`.

## What it costs while deferred

- `PurchaseInfo.vendor` cannot be resolved against `PartPriceObservation.vendor` or
  `PurchaseOrder.vendor` — an asset's purchase-history free text and its procurement price history
  are two unconnected records of what may be the same fact.
- Any future application besides `procurement` that needs to name a vendor (e.g. a
  warranty/service-contract feature on `assets`) faces the same choice `detail_extensions` already
  made: a free-text field, or a dependency on `procurement` for a concept `procurement` doesn't own.

## Shape if revisited

A low `app/parties/` app holding `Vendor` and `PartManufacturer` (and later `Customer`/
`Contractor`), sitting below both `parts` and `procurement` so both can FK into it without either
depending on the other. This is the trigger condition D79 names: *"if a third application needs a
vendor, that is when the move stops being optional."* `detail_extensions.PurchaseInfo` reaching for
a real `Vendor` FK instead of free text is a plausible first user of the extraction.

## Related

- `price_observation_mini_kit/README.md` D79, D81 (the parts→procurement session breadcrumb this
  kit accepted as a contained anti-pattern specifically because the `parties/` extraction was out of
  appetite).
- `app/detail_extensions/purchase_info/models.py` — the receipt.
