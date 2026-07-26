# Phase 2 — Data & Relational Plan: Supplier Mapping

Supplier-side tables, all satellites of the Phase 1 `Part`. Audit columns via `AuditFieldsMixin`
(not repeated). `BigAutoField` PKs. Comments + documents via events threads ([D5](../decisions.md)).

> **Resolved 2026-06-28 ([D13](../decisions.md)).** Supplier items do **not** mirror the Part
> major/minor revision model. There is **no `SupplierItemRevision` table** and **no
> vendor→part-revision mapping table**. Vendor revision history is captured as structured comments
> on the Supplier Item's thread, and interoperability is a denormalized **compatibility range** on
> the `SupplierItem` itself (both below). Firm vendor revision tracking is deferred to tech debt.

---

## Table: `PartManufacturer` — external manufacturer registry (NEW)

Separate from `app/assets/.../manufacturer.py` ([D2](../decisions.md)); mirrors its shape for a
mechanical future merge. **No thread** (manufacturers don't carry comments/documents — [D5](../decisions.md)).

| Field | Notes |
| :--- | :--- |
| `id` | PK. |
| `name` | **Unique.** Indexed. |
| `code` | Optional short code; unique when present. |
| `website` | Optional URL. |
| `is_active` | Availability flag. |

- A `PartManufacturer` has **many** `SupplierItem` rows.

---

## Table: `SupplierItem` — a purchasable vendor item mapped to a Part

| Field | Notes |
| :--- | :--- |
| `id` | PK. |
| `part_manufacturer_id` | **FK → PartManufacturer** (many-to-one, PROTECT). Indexed. ([D7](../decisions.md)) |
| `internal_part_id` | **FK → Part** (many-to-one, PROTECT). Indexed. The forward map. ([D6](../decisions.md)) |
| `manufacturer_part_number` | Vendor MPN. Indexed — Phase 3 mirrors it into an Alias. |
| `name` | Vendor's item name. |
| `description` | Optional. |
| `is_active` | Availability flag. |
| `min_major_revision_number` | **Compatibility range** ([D13](../decisions.md)). Nullable int; null = unbounded below. |
| `min_minor_revision_number` | Nullable int. Set major + null minor = "whole major band." |
| `max_major_revision_number` | Nullable int; null = unbounded above. |
| `max_minor_revision_number` | Nullable int. |
| `thread_id` | **FK → `events.ActivityThread`**, nullable — Supplier-Item comments + documents **and** the vendor revision history ([D5](../decisions.md), [D13](../decisions.md)). |

- **Cardinality:** many `SupplierItem` → one `Part`; many `SupplierItem` → one `PartManufacturer`.
- **Uniqueness (suggested):** `(part_manufacturer_id, manufacturer_part_number)` unique.
- FK points **from** the item **to** the Part — the Part never references back ([D3](../decisions.md)).
- **Compatibility range** is plain numbers compared against `PartRevision.major/minor` at query
  time — **no FK** to `PartRevision`, revision-agnostic ([D13](../decisions.md)). All four null
  (the ~98% default) = valid for all revisions. No `min ≤ max` constraint in v1.

---

## Vendor revision history — comments, not a table ([D13](../decisions.md))

There is **no `SupplierItemRevision` table**. A vendor revision is recorded by posting one
append-only `Comment` to the Supplier Item's `events.ActivityThread` (`is_human_made = True`), with
a machine-formatted JSON body filled via a form:

```json
{ "vendor_revision_history": {
    "vendor_revision_id": "<vendor's id or the internal name we chose>",
    "note": "<free text from the user about this vendor revision>"
} }
```

The thread *is* the flat, newest-last history. Datasheets/quotes attach to the same thread as
documents ([D5](../decisions.md)). Firm, structured vendor revision tracking is deferred (tech debt
item 6).

---

## Relational summary

```
PartManufacturer (1) ──< (N) SupplierItem (N) >── internal_part ──> Part   (Phase 1 hub)
                                   │  ├ compatibility range (min/max major.minor — plain ints, NO FK)
                                   │  │     ↳ compared against PartRevision.major/minor at query time
                                   │  └ thread ─▶ events.ActivityThread
                                   │              (item comments + docs + vendor-revision JSON comments)
                                   (no SupplierItemRevision table — D13)

One Part ← many SupplierItems (forward FK only; Part stays independent — D3).
Vendor history is comments on the item's thread; it never creates a Part revision.
```

## Create hook for Phase 3 (no new table)

Supplier-item creation exposes one well-defined point (explicit orchestrator call site) where
Phase 3 attaches MPN-alias auto-population ([D8](../decisions.md)). In Phase 2 it's a documented
no-op placeholder.

## Explicitly excluded

- `Alias` table + resolver — Phase 3.
- Procurement/ordering workflow tables.
- Merge with the asset `Manufacturer` — deferred (tech debt OQ4).
