# Phase 2 — Control Layer Plan: Supplier Mapping

Suffix vocabulary per
[`OOP_CONTROL_PATTERNS`](../../docs/ARCHITECTURE/OOP_CONTROL_PATTERNS.md). Home:
`app/parts/control_layer/`. Supplier items have **no revision table** ([D13](../decisions.md)):
vendor history is comments on the item's thread and interoperability is a denormalized
**compatibility range** on the item. Reuses the shared `PartThreadManager` for comments + documents
([D5](../decisions.md)).

---

## `PartManufacturerContext` + `PartManufacturerFactory`

```
PartManufacturerFactory.create(data, actor) -> PartManufacturer    # name/code uniqueness validated
PartManufacturerContext(manufacturer_id, actor)
  .struct() -> PartManufacturerStruct
  .supplier_items() -> list[SupplierItem]
```

Thin registry; `PartManufacturerValidator` enforces uniqueness. No thread (D5).

---

## `SupplierItemStruct`

```
SupplierItemStruct(item, manufacturer, internal_part, compatibility_range)
  .from_id(item_id) -> ... | None
  .to_dict() -> {id, mpn, name, manufacturer:{...}, internal_part:{id, part_number},
                 compatibility_range:{min_major, min_minor, max_major, max_minor},
                 is_active}
```

- Resolves forward to the internal Part (one batched `select_related`).
- No revision sub-struct — supplier items have no revision rows ([D13](../decisions.md)). The
  `compatibility_range` is the four nullable bounds read straight off the item.

---

## `SupplierItemContext` — entry point for one supplier item

```
SupplierItemContext(item_id, actor)
  .struct() -> SupplierItemStruct
  .compatibility_range() -> {min_major, min_minor, max_major, max_minor}
  .satisfies(major, minor) -> bool                 # is a given Part revision inside the range?
  .vendor_revisions() -> list                       # parsed vendor-revision JSON comments, oldest→newest
  .documents() -> list                              # datasheets/quotes on the item thread
  .comments() -> list                               # all human comments on the item thread
  @property thread -> PartThreadManager             # item-level comments/docs (shared helper)
```

No revision manager, no per-revision document scoping — everything hangs off the single item thread.
`satisfies()` applies the null-aware range rule ([D13](../decisions.md)); `vendor_revisions()` reads
the JSON-bodied comments back as the flat history.

---

## `SupplierItemFactory` — creation + the alias hook

`factories/supplier_item_factory.py`. Class methods only.

Flow (one `transaction.atomic()`):
1. `SupplierItemValidator.check(...)` — manufacturer + internal Part exist, MPN present,
   `(manufacturer, mpn)` not duplicated. Compatibility range optional; if supplied, all four bounds
   accepted as-is (no `min ≤ max` enforcement in v1 — [D13](../decisions.md)).
2. Create the `SupplierItem` (FK → manufacturer, FK → internal Part, compatibility range bounds —
   default all null = valid for all revisions).
3. **No base revision** — supplier items have no revision rows ([D13](../decisions.md)).
4. **Alias hook ([D8](../decisions.md)):** fire the post-create seam. **No-op placeholder** in
   Phase 2; Phase 3 attaches `SupplierAliasOrchestrator` here (explicit call, same transaction).

## `SupplierVendorRevisionManager`

`managers/supplier_vendor_revision_manager.py`. Records a vendor revision by posting **one
append-only `Comment`** to the item's thread ([D13](../decisions.md)) — not a revision row:

```
SupplierVendorRevisionManager(item_id, actor)
  .record(vendor_revision_id, note) -> Comment      # is_human_made=True; JSON body via PartThreadManager
  .list() -> list[dict]                              # parse JSON comments back, oldest→newest
```

The JSON body is `{"vendor_revision_history": {"vendor_revision_id": ..., "note": ...}}`. The only
writer of vendor history. Documents (datasheets/quotes) attach via the shared `PartThreadManager`.

## `SupplierItemNarrator`

`item_mapped(item, part)` → `"Supplier item {mpn} mapped to {part.part_number}"`;
`vendor_revision_recorded(item, vendor_revision_id)` → `"Vendor revision {id} logged on {mpn}"`.
No `major.minor` strings (supplier items have no structured revisions).

---

## Reading from a Part to its supplier items

Extend `PartContext` (Phase 1) with a **read-only** forward lookup — the Part still does not
depend on supplier items:

```
PartContext.supplier_items() -> list[SupplierItemStruct]
   # SupplierItem.objects.filter(internal_part_id=self.part.id, is_active=True)
```

---

## Delegation summary

```
register manufacturer ─▶ PartManufacturerFactory.create(...)

map a supplier item   ─▶ SupplierItemFactory.create(input, actor)
                           └▶ SupplierItemValidator.check()                (mfr + part exist, MPN)
                           └▶ transaction:
                                SupplierItem.objects.create(mfr, part, range)  (forward map + compat range — D6/D7/D13)
                                << alias hook >>                           (no-op now; Phase 3 fills)

log a vendor revision ─▶ SupplierVendorRevisionManager(id, actor).record(vendor_revision_id, note)
                           └▶ one Comment (JSON body) on the item thread — NO revision row, NO Part revision (D13)

attach datasheet/quote─▶ SupplierItemContext(id).thread.attach_document(file)   (item thread — D5)

"can I buy this for   ─▶ SupplierItemContext(id).satisfies(major, minor)    (null-aware compat range — D13)
 part rev X?"

part → its options    ─▶ PartContext(part_id).supplier_items()            (read-only forward)
```
