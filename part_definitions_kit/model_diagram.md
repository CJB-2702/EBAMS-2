# Model Diagram — Part Definitions Kit

The single, canonical data-model picture for this kit. Kept in sync with [`decisions.md`](decisions.md)
and the per-phase `data_relational_plan.md` files — if they disagree, those decision docs win and
this diagram should be corrected. Last revised **2026-06-29** (Alias reworked per D9; domain scoping
per D14).

Reuses existing app models rather than re-creating them: `events.ActivityThread`/`Comment`/
`Attachment`/`File` (D5) and `administration.Domain`/`DomainTemplate`/`DomainTemplateItem` (D14).

---

## Entity-Relationship Diagram

```
                          app/parts/  (new sub-app)
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                        │
│   ┌──────────────────────┐                                                             │
│   │  PartManufacturer    │  (separate from assets.Manufacturer — D2)                   │
│   │ id, name★, code○,    │                                                             │
│   │ website○, is_active  │                                                             │
│   └──────────┬───────────┘                                                             │
│              │ 1 ──< N (PROTECT)                                                        │
│   ┌──────────┴───────────────────────────┐                                            │
│   │  SupplierItem                         │         ┌────────────────────────┐         │
│   │ id (PK)                               │   N   1 │  Part  (THE HUB)        │         │
│   │ part_manufacturer_id →PartManuf.      │────────▶│ id (PK) ◀ only id the   │         │
│   │ internal_part_id →Part (PROTECT)      │ forward │   app refs (D3)         │         │
│   │ manufacturer_part_number  ⌕           │   (D6)  │ part_number ★unique     │         │
│   │ name, description, is_active          │         │ name, description○      │         │
│   │ compatibility range (D13):            │         │ part_type/category      │         │
│   │   min/max _major/_minor _rev_num ○int │         │ is_active               │         │
│   │ thread_id →events.ActivityThread ○    │         │ is_domain_limited (D14) │         │
│   └───┬──────────────────────────▲────────┘         │ thread_id ○ ──┐         │         │
│       │ 1                        │                  └──┬────┬────────┼─────────┘         │
│       │ N (provenance,           │ N (provenance,      │ 1  │ 1      │ 1               │
│       │  PART_TO_VENDOR_ITEM)    │  nullable)          │ N  │ N      │ N               │
│       │                          │                     │    │        │                 │
│   ┌───┴──────────────────────────┴──────────────┐      │    │        │                 │
│   │  Alias  (Phase 3) — D9                       │      │    │        │                 │
│   │──────────────────────────────────────────────│      │    │        │                 │
│   │ id (PK)                                      │      │    │        │                 │
│   │ part_id →Part   ‼NOT NULL  ⌕  ───────────────┼──────┘    │        │  PRIMARY anchor │
│   │   ▲ primary association + the lookup column  │           │        │  (+ resolution) │
│   │ alias              ⌕  (value, MPN usually)   │           │        │                 │
│   │ normalized_value   ⌕                         │           │        │                 │
│   │ alias_type   (OPEN string: MPN/NSN/INTERNAL/ │           │        │                 │
│   │     LEGACY/regional/medical/… — infinite)    │           │        │                 │
│   │ association_type  {ENUM, exactly 3}:         │           │        │                 │
│   │     PART_TO_VENDOR_ITEM | PART_TO_PART |      │           │        │                 │
│   │     PART_TO_STRING                           │           │        │                 │
│   │ supplier_item_id →SupplierItem ○ ────────────┼───────────┘        │ (VENDOR_ITEM)   │
│   │ alternate_part_id →Part        ○ ────────────┼────────────────────┘ (PART_TO_PART:  │
│   │ source {auto, manual}                        │            alternate internal part#) │
│   │ CheckConstraint: association_type ⇄ secondary FK; part always set                   │
│   └──────────────────────────────────────────────┘                                      │
│                                                                                        │
│   ┌────────────────────────┐   ┌───────────────────────────────┐                       │
│   │ PartRevision (D4)      │   │ PartDomainAccessMapping (D14)  │                       │
│   │ part_id →Part (CASCADE)│   │ part_id →Part / domain_id →    │                       │
│   │ sequence, date_of_rel  │   │   administration.Domain        │                       │
│   │ major/minor_rev_num ‼  │   │ is_active; ★uniq(part,domain)  │                       │
│   │ major/minor_rev_name ○ │   │ (only when is_domain_limited)  │                       │
│   │ status, summary, notes │   │ ← copied from DomainTemplate   │                       │
│   │ thread_id ○            │   │   via PartDomainTemplateHandler│                       │
│   └────────────────────────┘   └───────────────────────────────┘                       │
└────────────────────────────────────────────────────────────────────────────────────────┘

   events.ActivityThread ──< Comment / ──< Attachment ─▶ events.File   (Part, PartRevision, SupplierItem — D5)
   administration: Domain / DomainTemplate / DomainTemplateItem  (REUSED — D14)

  Legend:  ★ unique   ○ nullable   ‼ NOT NULL   ⌕ indexed   N/1 cardinality
```

---

## Table summary

**Six new `app/parts/` tables**, plus reuse of `events` (threads/comments/files) and
`administration` (`Domain`, `DomainTemplate`). No new domain table.

| Table | Role | Key relationships |
| :--- | :--- | :--- |
| **`Part`** | The engineering hub. `Part.id` is the **only** thing the wider app references ([D3](decisions.md)). Carries **`is_domain_limited`** ([D14](decisions.md)). | 1 ──< N `PartRevision`; 1 ──< N `PartDomainAccessMapping`; receives inward FKs from `SupplierItem` / `Alias`. |
| **`PartRevision`** | Flat numeric major/minor history ([D4](decisions.md)). Numbers are the source of truth; names are decoration. | N ──> 1 `Part` (CASCADE). |
| **`PartManufacturer`** | External manufacturer registry, separate from `assets.Manufacturer` ([D2](decisions.md)). No thread. | 1 ──< N `SupplierItem`. |
| **`SupplierItem`** | Purchasable vendor item mapped forward to one Part ([D6](decisions.md)); carries the compatibility range ([D13](decisions.md)). No `SupplierItemRevision` table. | N ──> 1 `Part` (PROTECT); N ──> 1 `PartManufacturer` (PROTECT). |
| **`Alias`** | Unified searchable identifier index ([D9](decisions.md)). Forced primary `part` anchor + typed secondary link. | `part` NOT NULL; nullable `supplier_item` **or** `alternate_part`, gated by `association_type`. |
| **`PartDomainAccessMapping`** | Which data domains may see a Part **and its children** ([D14](decisions.md)). | N ──> 1 `Part` (CASCADE); N ──> 1 `administration.Domain` (PROTECT). |

---

## Key model rules

- **`Alias` ([D9](decisions.md))** — every alias has a **forced primary `part` FK** (the real
  relationship and the lookup/search anchor; resolution returns it directly — no forward hop). Two
  independent axes: **`alias_type`** = the open business-source label (MPN/NSN/INTERNAL/LEGACY/
  regional/medical/… — an infinite, extensible set, stored as a free string) and
  **`association_type`** = a closed enum of exactly three structural behaviors —
  `PART_TO_VENDOR_ITEM` (secondary `supplier_item` set), `PART_TO_PART` (secondary `alternate_part`
  set — an *alternate internal part number*), `PART_TO_STRING` (neither set). A `CheckConstraint`
  keeps `association_type` and the secondary FKs consistent.
- **Revisions ([D4](decisions.md))** — one flat table; numeric `(major, minor)` is authoritative,
  names optional. "Current" = highest `(major, minor)`, not highest `sequence`. Lineage derived, not
  stored.
- **Supplier interoperability ([D13](decisions.md))** — no `SupplierItemRevision`; vendor history is
  structured JSON comments on the item's thread, and compatibility is a denormalized four-int range
  on `SupplierItem` (plain numbers, no FK to `PartRevision`).
- **Comments + documents ([D5](decisions.md))** — `Part`, `PartRevision`, and `SupplierItem` each
  own an `events.ActivityThread` (`thread_id`) carrying both comments and file attachments.
  Manufacturers and domains get no thread.
- **Domain scoping ([D14](decisions.md))** — `Part.is_domain_limited` (default `False` = visible to
  all). When `True`, visibility is restricted to the domains in `PartDomainAccessMapping`, which can
  be issued/copied from an `administration.DomainTemplate` via `PartDomainTemplateHandler` (copied at
  apply time, not bound by FK). Enforcement (queryset filtering) is **modeled only** — deferred to a
  later RBAC pass ([D11](decisions.md)).
