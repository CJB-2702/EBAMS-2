# Phase 3 — Aliases & Unified Search

## Goal

Build the **single, high-performance identifier index** that lets any persona find an internal
part by *any* number it has ever been known by — internal number, national stock number, legacy
in-house code, or a vendor's manufacturer part number — and **resolve every hit to its owning Part**
directly through the alias's primary `part` anchor ([D9](../decisions.md)).

## In scope

- `Alias` table ([D9](../decisions.md)) — a **forced primary `part` FK** (the lookup anchor), an
  `alias` value string, an open **`alias_type`** business-source label, and an **`association_type`**
  enum (`PART_TO_VENDOR_ITEM` / `PART_TO_PART` / `PART_TO_STRING`) governing the optional secondary
  FK (`supplier_item` or `alternate_part` — an alternate internal part number).
- **Auto-population** ([D8](../decisions.md)): a `Part`'s canonical `part_number` is mirrored as
  a `PART_TO_STRING`/`INTERNAL` alias on create; a `SupplierItem`'s MPN is mirrored as a
  `PART_TO_VENDOR_ITEM`/`MPN` alias on create (wiring the Phase 2 hook).
- Manual alias creation (NSN, legacy, regional codes; alternate internal part numbers) via an alias
  write path.
- The **resolver**: alias → `alias.part` **directly** (primary anchor — no forward hop, [D9](../decisions.md)).
- A `PartSearch` presentation-layer search entry that the Phase 4 lookup UI consumes.

## Out of scope

- UI rendering — Phase 4 (this phase exposes the search/resolve API headless).
- Full-text / trigram ranking and a dedicated **search manager + API** — out of scope; parts
  search stays minimal (exact/prefix). Logged as tech debt (OQ7 →
  `docs/parts/tech_debt/20260624 Part definitions kit deferrals.md`, item 4).

## Dependencies

- **Phase 1** (Part + `part_number`) and **Phase 2** (Supplier Item + MPN, and its create hook).
  This phase can only index numbers that already exist.

## Deliverables

- [ ] `Alias` model: NOT NULL `part` + `alias` + open `alias_type` + `association_type` enum +
      nullable `supplier_item`/`alternate_part` + typed-link CheckConstraint + indexed `alias`.
- [ ] `AliasFactory` / alias write path (`for_string` / `for_vendor_item` / `for_alternate_part`).
- [ ] `PartAliasOrchestrator` + `SupplierAliasOrchestrator` wired into the Phase 1/2 create paths
      (the Phase 2 no-op hook becomes real here).
- [ ] `AliasResolver` — value → `alias.part` directly (no forward hop, [D9](../decisions.md)).
- [ ] `PartSearch` presentation entry returning resolved `PartStruct`s.
- [ ] Seed aliases appear automatically from seeded parts/items; a couple manual NSN/legacy ones.

## Exit criteria

- [ ] Creating a Part auto-creates exactly one `INTERNAL` alias for its `part_number`.
- [ ] Creating a Supplier Item auto-creates exactly one `MPN` alias for its manufacturer part
      number, in the **same transaction** as the item.
- [ ] Searching a manufacturer part number returns the **internal Part** directly via the alias's
      primary `part` anchor, per spec §3.
- [ ] Searching an internal/NSN/legacy/regional alias returns the Part directly.
- [ ] `association_type` always matches the secondary-FK state (DB CheckConstraint), and `part` is
      always set ([D9](../decisions.md)).
- [ ] Aliases carry **no** revision reference — they remain valid across revisions
      ([D9](../decisions.md)).
- [ ] Deactivating/removing a supplier item does not silently orphan a dangling alias (define the
      cleanup rule — see plan).
