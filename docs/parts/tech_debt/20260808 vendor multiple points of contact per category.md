---
type: "Technical Decision"
title: "Tech Debt: Vendor points of contact — one string isn't enough per category"
description: "A single vendor_contact string can't represent a vendor with multiple category-specific contacts (e.g. one manufacturer, several product lines)."
tags: [technical-decisions, technical-decision, tech-debt]
context_tier: 2
---

# Tech Debt: Vendor points of contact — one string isn't enough per category

**Logged:** 2026-08-08
**Source:** `procurement_starter_kit` review — `purchase_ordering_system.md` §1's
`Vendor` entity (`vendor_contact` as a plain string).

## The problem

A real vendor often isn't a single point of contact — a large manufacturer/distributor can have
different contacts per product category. The example that surfaced this: a company like GM has a
separate contact for turbine parts than for avionics parts. A single `vendor_contact` string on
`Vendor` can't represent that; whoever's filling in the field has to pick one contact and the
others have nowhere to live, or contact info gets crammed into free-text notes where it isn't
queryable or presentable per-category.

This is fundamentally a **parts/vendor data-model problem**, not specific to the demand+purchasing
kit that surfaced it — it belongs with `PartManufacturer`/`Vendor` design in the parts application,
not as a one-off fix inside part-demand-purchasing.

## What was decided for now

`Vendor.vendor_contact` stays a plain string for the part-demand-purchasing kit (see
`purchase_ordering_system.md` §1). No category-aware contact model is being built in this pass.

## What to check first if revisited

- Whether contacts should key off `PartManufacturer`'s category/classification data (if any
  exists by then) or off a new lightweight `VendorContact` join table (`vendor_id`,
  `category`/`product_line`, `name`, `email`, `phone`).
- Whether this is really a `Vendor`-side concern (part-demand-purchasing) or a
  `PartManufacturer`-side concern (parts) — the turbine/avionics example suggests contacts are
  really scoped to what's being bought, which may mean the contact belongs closer to the part
  category than to the vendor record itself.
- No concrete second caller has asked for this yet; revisit once a real multi-contact vendor
  causes a workflow problem, not preemptively.
