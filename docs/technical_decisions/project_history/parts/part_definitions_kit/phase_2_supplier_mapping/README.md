# Phase 2 — Supplier Mapping (the supply side)

## Goal

Add the external supply chain as **satellites** of the Part hub: a new **Part Manufacturer**
registry and **Supplier Items** that map forward to exactly one Part — all decoupled from the
internal engineering lifecycle so vendor churn never disturbs an engineering record. Supplier items
have **no revision table** ([D13](../decisions.md)): vendor revision history is captured as
structured comments on the item's thread, and interoperability is a denormalized **compatibility
range** on the item.

## In scope

- `PartManufacturer` table (new, separate from the asset `Manufacturer` — [D2](../decisions.md)).
- `SupplierItem` table — FK to `PartManufacturer`, FK forward to `Part` ([D6](../decisions.md), [D7](../decisions.md)),
  plus the four-column **compatibility range** ([D13](../decisions.md)) and a thread for comments + documents ([D5](../decisions.md)).
- **No `SupplierItemRevision` table** ([D13](../decisions.md)). Vendor revision history is structured
  comments on the item's thread; firm revision tracking is deferred (tech debt item 6).
- Control layer: `PartManufacturerContext`/`Factory`, `SupplierItemContext`,
  `SupplierItemStruct`, `SupplierItemFactory`, `SupplierVendorRevisionManager`, narrator.
- Read access from a Part to its supplier items (the Part still doesn't *depend* on them).
- Seed contribution: multiple part manufacturers + supplier items with **distinct MPNs** mapped
  to each of the four car-part drivers (alternator, engine, starter, AC compressor), so
  many-suppliers-per-part and forward resolution are exercised. (See Phase 1 README → Seed data.)

## Out of scope

- Aliases / auto-indexing of MPNs — Phase 3 (this phase exposes the create hook Phase 3 binds).
- UI — Phase 4.
- Merging part/asset manufacturers — deferred (OQ4).

## Dependencies

- **Phase 1** — `Part` must exist for `SupplierItem.internal_part` to point at.
- Events file system (documents), same as Phase 1.

## Deliverables

- [ ] `PartManufacturer`, `SupplierItem` models (no `SupplierItemRevision` — [D13](../decisions.md)).
- [ ] `SupplierItemStruct` read model (carries the compatibility range).
- [ ] `PartManufacturerContext` + `PartManufacturerFactory`.
- [ ] `SupplierItemContext` + `SupplierItemFactory` (+ `SupplierVendorRevisionManager`).
- [ ] A clean create hook on supplier-item creation for Phase 3's alias orchestrator to attach to.
- [ ] `PartContext.supplier_items()` read — forward from a Part to its mapped items.
- [ ] Seed data; full DB reset.

## Exit criteria

- [ ] A Part Manufacturer can be created and listed.
- [ ] A Supplier Item can be created against a manufacturer **and** mapped to an existing Part in
      one transaction; it carries its own MPN.
- [ ] One Part can have **many** Supplier Items; each Supplier Item maps to exactly **one** Part.
- [ ] A vendor revision can be logged as a structured JSON comment on the Supplier Item's thread
      ([D13](../decisions.md)); datasheets/quotes attach to that same thread — and **none** of it
      creates a Part revision (isolation preserved without a supplier revision table).
- [ ] A Supplier Item carries an optional **compatibility range** (four nullable bounds, all-null =
      valid for all revisions); `SupplierItemContext.satisfies(major, minor)` answers whether a
      given Part revision is in range ([D13](../decisions.md)).
- [ ] `PartContext.supplier_items()` returns the mapped items, but nothing in Phase 1's Part
      read path *requires* a supplier item to exist (the Part stands alone).
- [ ] The supplier-item create path exposes a documented seam (signal or orchestrator call site)
      where Phase 3 will auto-create the MPN alias — wired as a no-op placeholder here.
