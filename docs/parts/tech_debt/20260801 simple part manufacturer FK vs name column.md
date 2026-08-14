---
type: "Technical Decision"
title: "Tech Debt: Part.primary_manufacturer — FK-to-id vs. denormalized name column"
description: "Open question on whether the simple-part manufacturer shortcut should store the manufacturer name directly instead of joining through the FK."
tags: [technical-decisions, technical-decision, tech-debt]
context_tier: 2
---

# Tech Debt: `Part.primary_manufacturer` — FK-to-id vs. denormalized name column

**Logged:** 2026-08-01
**Source:** review of `Part.is_simple_part` / `primary_manufacturer` / `primary_supplier_item`
denormalization (see [`desired workflow simple parts.md`](../../technical_decisions/tech_debt/desired%20workflow%20simple%20parts.md)).

`Part.primary_manufacturer` is a standard Django `ForeignKey` to `PartManufacturer.id` (the PK),
not to `PartManufacturer.name`, even though `name` carries a `unique=True` constraint. Kept as
`id` for now because:

- FK-to-`name` would make a manufacturer rename either a multi-row rewrite or an on-update
  cascade, versus a single-row edit today.
- It doesn't remove the join it's meant to avoid — `Part → PartManufacturer` is still one hop
  either way; only the join column changes.

**Open question (user to evaluate):** most manufacturer lookups on parts are by **name**, not
`id`. It may be faster in practice to denormalize the manufacturer **name** directly onto `Part`
as a plain `CharField` snapshot (in addition to or instead of the `primary_manufacturer` FK),
so common searches never join to `PartManufacturer` at all. Tradeoff to weigh before doing this:
a copied name column goes stale on manufacturer rename unless `SupplierItemManager` (or a
rename hook on `PartManufacturer`) is taught to re-sync it — same class of sync burden already
carried by `_sync_simple_part_pointers`, just extended to one more field.

Not yet decided. Revisit if manufacturer-name search on `Part` shows up as a real hot path.
