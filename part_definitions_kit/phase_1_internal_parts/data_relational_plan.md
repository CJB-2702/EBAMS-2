# Phase 1 — Data & Relational Plan: Internal Parts

Core tables for the engineering hub. Audit columns (`created_at`, `updated_at`, `created_by_id`,
`updated_by_id`) via `AuditFieldsMixin` on every table — not repeated. `BigAutoField` PKs unless
noted. No supplier concepts appear here. Revision model per [D4](../decisions.md); comments +
documents per [D5](../decisions.md).

---

## Table: `Part` — the base internal part (the hub)

| Field | Notes |
| :--- | :--- |
| `id` | PK — **the base part id** the whole app references ([D3](../decisions.md)). |
| `part_number` | Canonical internal part number. **Unique.** Indexed. |
| `name` | Short human name. |
| `description` | Optional longer text. |
| `part_type` / `category` | Optional enum/char classification (component, assembly…). |
| `is_active` | Soft availability flag. |
| `is_domain_limited` | **Boolean, default `False`** — domain-visibility gate ([D14](../decisions.md)). `False` (the "unset / not limited" case) = visible to all authenticated users. `True` = visible only to users sharing one of the Part's `PartDomainAccessMapping` domains. |
| `thread_id` | **FK → `events.ActivityThread`**, nullable — Part-level comments + documents ([D5](../decisions.md)). Lazily created. |

- A `Part` has **many** `PartRevision` rows (one-to-many).
- A `Part` has **many** `PartDomainAccessMapping` rows (one-to-many) — its domain scope ([D14](../decisions.md)).
- Supplier Items (Phase 2) and Aliases (Phase 3) point **inward** at `Part`; `Part` knows
  nothing about them.

---

## Table: `PartRevision` — flat numeric major/minor history ([D4](../decisions.md))

One flat table; the **numbers are the source of truth**, names are an optional display feature.

| Field | Notes |
| :--- | :--- |
| `id` | PK. |
| `part_id` | **FK → Part** (many-to-one, CASCADE). Indexed. |
| `sequence` | Per-part monotonic counter, **aligned with `date_of_release`** order. NOT NULL. |
| `date_of_release` | Date released; `sequence` tracks this ordering. |
| `major_revision_number` | Integer, structural major rev. **Source of truth.** NOT NULL. |
| `minor_revision_number` | Integer. `0` = base/major release; `1+` = redline. **NOT NULL, default 0.** |
| `major_revision_name` | Optional label (`A`, `B`, `Cobra`…). **Nullable.** |
| `minor_revision_name` | Optional redline label (`"2"`, `"redline2"`). **Nullable, default null.** |
| `status` | Enum `DRAFT`/`RELEASED`/`REDLINE`/`OBSOLETE` (a redline is also structurally `minor > 0`). |
| `summary` | Short description of the change. |
| `notes` | Optional longer engineering / redline notes. |
| `thread_id` | **FK → `events.ActivityThread`**, nullable — this revision's drawings, change history, comments ([D5](../decisions.md)). |

- **Uniqueness:** `(part_id, major_revision_number, minor_revision_number)` unique;
  `(part_id, sequence)` unique.
- **Current revision (D4):** `ORDER BY major_revision_number DESC, minor_revision_number DESC` →
  first row. **NOT** `max(sequence)`. A redline against an older major does not become current.
- **Lineage is derived, not stored:** a redline's base = same major, `minor = 0`; previous
  baseline = next-lower major at `minor = 0`. (No `base_revision`/`previous_base` columns.)
- **Flat, not recursive** — no parent/child revision FK. (Normalizing major/minor into separate
  tables is deferred — tech debt item 2.)

---

## Table: `PartDomainAccessMapping` — which data domains may see a Part ([D14](../decisions.md))

The Part's domain scope. Mirrors the shape of the existing `administration.UserDomain` link table
(soft-remove via `is_active`, `(part, domain)` unique). Reuses the existing
`administration.Domain` model — **no new domain table.** Governs the Part **and everything that
hangs off it** (revisions, supplier items, aliases), since the rest of the app references a Part
only by its base id ([D3](../decisions.md)).

| Field | Notes |
| :--- | :--- |
| `id` | PK. |
| `part_id` | **FK → Part** (many-to-one, CASCADE). Indexed. |
| `domain_id` | **FK → `administration.Domain`** (many-to-one, PROTECT — domains are shared scope rows). Indexed. |
| `is_active` | Soft-remove flag, mirroring `UserDomain`. Default `True`. |

- **Uniqueness:** `(part_id, domain_id)` unique (active).
- **Only consulted when `Part.is_domain_limited = True`** ([D14](../decisions.md)). When the flag is
  `False`, these rows are ignored and the Part is visible to all authenticated users.
- **Issued/copied from a `DomainTemplate`** ([D14](../decisions.md) + control-layer plan): a control
  Handler expands a chosen `administration.DomainTemplate`'s active `DomainTemplateItem` domains into
  `PartDomainAccessMapping` rows for the Part — the same materialize-from-template pattern the admin
  app already uses to flatten `DomainTemplate → UserDomain`. The template is a **source to copy from**,
  not a stored FK on the Part; re-issuing re-bases the active rows.

---

## Documents **and comments** (reused from `events`, not new here) — [D5](../decisions.md)

Not a new parts table. Each of `Part`, `PartRevision` (and Phase 2's supplier rows) carries a
`thread_id → events.ActivityThread`. An `ActivityThread` natively holds **comments**
(`events.Comment`) **and documents** (`events.Attachment → events.File`):

```
Part        ── thread_id ─▶ events.ActivityThread ──< Comment
PartRevision ── thread_id ─▶ events.ActivityThread ──< Attachment ─▶ File   (drawings, change history)
```

- Attaching a document / leaving a comment = ensure the entity's thread exists, then use the
  events comment/attachment path against it.
- "Documents for the current revision" = active attachments on `current_revision.thread`.
- Because a revision is point-in-time, a superseded revision's thread (drawings + history) is
  naturally frozen.

---

## Relational summary

```
Part (1) ──< (N) PartRevision
  │                  │
  ├ thread ─▶ events.ActivityThread ◀─ thread ┘     (comments + documents at BOTH levels — D5)
  │
  └──< (N) PartDomainAccessMapping (N) >── domain ──> administration.Domain   (D14)
              ▲ only consulted when Part.is_domain_limited = True
              └ issued/copied from administration.DomainTemplate (control Handler)

Current state of a Part = its PartRevision with the highest (major, then minor) numbers (D4).
External consumers (assets, BOM, config-allowability) reference Part.id ONLY (D3).
```

## Explicitly excluded from this phase

- Part Manufacturers, Supplier Items, Supplier Item Revisions — Phase 2.
- Aliases — Phase 3.
- **Enforcement** of domain limiting (queryset filtering by user domains) — only the table + flag are
  *modeled* here; actual scoping is a later RBAC pass ([D11](../decisions.md), [D14](../decisions.md)).
- Auth/RBAC/ownership relations — not modeled in this kit ([D11](../decisions.md); see
  [`../functionality_and_roles.md`](../functionality_and_roles.md)).
