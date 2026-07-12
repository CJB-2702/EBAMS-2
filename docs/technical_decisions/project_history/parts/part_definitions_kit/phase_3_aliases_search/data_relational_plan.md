# Phase 3 — Data & Relational Plan: Aliases & Unified Search

One new table plus the resolver logic. Audit columns via `AuditFieldsMixin` (not repeated).
`BigAutoField` PK.

---

## Table: `Alias` — the unified identifier index ([D9](../decisions.md))

A forced **primary Part anchor** plus an **optional typed secondary link**. Two independent axes:
`alias_type` (open business-source label) and `association_type` (closed 3-value structural enum).

| Field | Notes |
| :--- | :--- |
| `id` | PK. |
| `part_id` | **FK → Part, NOT NULL.** The **primary association** and lookup anchor ([D9](../decisions.md)). Indexed. |
| `alias` | The searchable identifier **value** string (a vendor MPN most of the time). **Indexed** (the hot search column). |
| `normalized_value` | Optional: case/whitespace-folded copy of `alias` for fast lookup (see search note). Indexed. |
| `alias_type` | **Open string** — what kind of number this is *to the business*: `MPN`, `NSN`, `INTERNAL`, `LEGACY`, regional, medical-supply, etc. **Not a closed enum** (potentially infinite set). |
| `supplier_item_id` | **FK → SupplierItem**, nullable. Set only when `association_type = PART_TO_VENDOR_ITEM` (provenance — which vendor item the MPN came from). |
| `alternate_part_id` | **FK → Part**, nullable. Set only when `association_type = PART_TO_PART` — an **alternate internal part number** cross-referencing another Part. |
| `association_type` | **Closed enum**: `PART_TO_VENDOR_ITEM` / `PART_TO_PART` / `PART_TO_STRING`. Governs which secondary FK is set. |
| `source` | Optional: `auto` (mirrored from a number) vs `manual` (entered by a user). |

- **Typed-link constraint ([D9](../decisions.md)):** a `CheckConstraint` ties `association_type`
  to the secondary FKs — `PART_TO_VENDOR_ITEM` ⇒ `supplier_item` set & `alternate_part` null;
  `PART_TO_PART` ⇒ `alternate_part` set & `supplier_item` null; `PART_TO_STRING` ⇒ both null.
  `part` is **always** set.
- **No revision FK** — an alias is revision-agnostic by design ([D9](../decisions.md), OQ2).
- **Uniqueness (suggested):** `(alias_type, normalized_value)` unique, or a softer
  unique-per-part — confirm at review (avoid blocking legitimately shared numbers; OQ7).

```
Alias ──(NOT NULL)── part ──────────> Part            (Phase 1)   ← primary anchor + lookup
      ──(nullable )── supplier_item ─> SupplierItem    (Phase 2)   ] secondary link, typed by
      ──(nullable )── alternate_part > Part            (Phase 1)   ]   association_type
        (exactly one secondary set for VENDOR_ITEM/PART; none for STRING)
```

---

## Resolution model (spec §3)

Given a search `value`:

1. Find matching `Alias` rows by `normalized_value` (exact, then prefix — OQ7).
2. For each hit: return `alias.part` **directly** — the primary Part is stored, so there is **no
   forward hop** through `supplier_item` anymore ([D9](../decisions.md)). (`supplier_item` /
   `alternate_part` are provenance/cross-reference, not the resolution path.)
3. De-duplicate to distinct Parts; return resolved `PartStruct`s.

The resolver returns a Part for every alias regardless of `association_type`, so the caller (Phase 4
lookup) never branches on alias kind.

---

## Auto-population sources ([D8](../decisions.md))

| Trigger | Alias created |
| :--- | :--- |
| `Part` created (Phase 1) | `part=<part>`, `alias=part_number`, `alias_type=INTERNAL`, `association_type=PART_TO_STRING`, `source=auto`. |
| `SupplierItem` created (Phase 2 hook) | `part=item.internal_part`, `alias=manufacturer_part_number`, `alias_type=MPN`, `supplier_item=<item>`, `association_type=PART_TO_VENDOR_ITEM`, `source=auto`. |
| User adds alternate internal part number (manual) | `part=<owner part>`, `alias=<other part's number>`, `alternate_part=<other part>`, `association_type=PART_TO_PART`, `source=manual`. |
| User adds NSN/legacy/regional (manual) | `part=<part>`, `alias_type=NSN\|LEGACY\|…`, `association_type=PART_TO_STRING`, `source=manual`. |

**Lifecycle / cleanup rule (define at implementation):** auto aliases are owned by their source
row. If a supplier item is hard-deleted, its `MPN` alias is removed with it (FK CASCADE on
`supplier_item_id` is the simplest enforcement). Soft-deactivation of an item should likewise
deactivate/hide its auto alias so search doesn't resolve to an inactive item. Manual aliases are
user-managed. (Confirm CASCADE vs. soft rule at review — see Phase 3 README exit criteria.)

---

## Explicitly excluded

- Any revision-aware aliasing (OQ2).
- Trigram/full-text ranking infrastructure — SQLite now; provisional prefix+exact (OQ7).
