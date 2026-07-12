# Decisions

Architectural decision log for the Part Definitions kit. Each decision is binding across all
phases unless superseded. Last revised **2026-06-24** (D4 and D5 reworked; D9/D11 updated).

---

## D1 — New sub-app `app/parts/`

**Options.** (a) Extend `app/assets/`. (b) A new top-level sub-app `app/parts/`.

**Chosen: (b).** Parts are a distinct root domain with their own personas and their own future
satellites (BOM, configuration allowability). They follow the standard layered structure
(`presentation_layer/{entrypoints,search}/`, `control_layer/{adapters,domain_structs,...}/`,
`models/`, `templates/`). Keeping them out of `assets/` preserves the clean rule that the rest
of the app references parts only by **base Part id** (D3).

---

## D2 — Part Manufacturers are a separate table from asset Manufacturers

**Options.** (a) Reuse the existing `app/assets/.../manufacturer.py` (`Manufacturer`) for both
asset models and supplier items. (b) A new, independent `PartManufacturer` table in
`app/parts/`.

**Chosen: (b).** The existing `Manufacturer` is the **asset** manufacturer registry — few rows,
hit on every asset lookup, and must stay fast. Part manufacturers will grow to *many* rows. So
`parts.PartManufacturer` is created independently, mirroring `Manufacturer`'s shape so a future
merge stays mechanical. Future direction (merge vs. pointer) is logged as tech debt:
`docs/technical_decisions/tech_debt/20260624 Part definitions kit deferrals.md` (OQ4).

---

## D3 — The base Part id is the only thing the wider app references

The canonical contract: **assets, BOM tooling, configuration-allowability tooling, and any other
consumer reference a Part solely by its base `Part.id`** (and/or canonical internal
`part_number`). They never reach into Supplier Items, revisions, or documents. Supplier mapping
and revisions are *satellites*. Phase 1 builds and stabilizes the Part hub before any satellite
exists.

---

## D4 — Part revisions: numeric major/minor as source of truth, names as a feature *(revised 2026-06-24; supplier symmetry dropped 2026-06-28 — see [D13](#d13))*

**Supersedes the original flat `sequence`+`status` model and the interim base/previous self-FK
sketch.** Still **one flat table** (no nesting, no sub-revision tables — normalization
into separate major/minor tables is logged as tech debt, item 2), but the **numbers are the
source of truth** and names are an optional display feature.

> **Scope note (2026-06-28).** This major/minor model applies to **`PartRevision` only**. Supplier
> items do **not** get a symmetric revision table — that earlier assumption is withdrawn. Vendor
> revision history is captured as structured comments and a denormalized compatibility range on the
> `SupplierItem` instead ([D13](#d13)).

`PartRevision` columns:

| Column | Rule |
| :--- | :--- |
| `sequence` | Per-owner monotonic counter, **aligned with `date_of_release` order**. The machine "when". NOT NULL. |
| `date_of_release` | Date the revision was released. `sequence` tracks this ordering. |
| `major_revision_number` | Integer. The structural major revision. **Source of truth**, not the name. NOT NULL. |
| `minor_revision_number` | Integer. `0` = the base/major release; `1+` = redline under that major. **NOT NULL, default 0.** |
| `major_revision_name` | Optional human label — `A`, `B`, or generic junk like `Cobra`, `Mango`. **Nullable.** |
| `minor_revision_name` | Optional label for the redline — e.g. `"2"`, `"redline2"`. **Nullable, default null.** |
| `status` | Lifecycle enum `DRAFT`/`RELEASED`/`REDLINE`/`OBSOLETE`. (A redline is *also* structurally `minor_revision_number > 0`.) |
| `summary`, `notes` | Free text. |
| `thread_id` | FK → `events.ActivityThread` — comments + documents ([D5](#d5)). |

**Why force the numbers.** Users follow no reliable naming convention (`A,B,C`, animals, fruit,
`cobra-redline2`…). The numbers give a deterministic order and grouping the names cannot.

**Worked example** (user's own): `sequence 5`, `date_of_release 2 Apr 2025`,
`major_revision_number 3`, `minor_revision_number 2`, `major_revision_name "Cobra"`,
`minor_revision_name "2"`.

**"Current" revision rule.** The current revision is the **highest `minor_revision_number`
within the highest `major_revision_number`** — i.e. `ORDER BY major_revision_number DESC,
minor_revision_number DESC` → first row. **NOT** `max(sequence)`. This means a redline issued
against an *older* major (e.g. a fix for fielded units still at major 1) gets its own row with a
later `sequence`/`date_of_release` but does **not** become "current", because a higher major
already exists.

**Lineage is derived, not stored.** The earlier `base_revision_id` / `previous_base_id` self-FKs
are **dropped** — they are derivable: a redline's base = same `major_revision_number`,
`minor_revision_number = 0`; the previous baseline = the next-lower `major_revision_number` at
`minor 0`.

**Uniqueness.** `(owner_id, major_revision_number, minor_revision_number)` unique;
`(owner_id, sequence)` unique.

---

## D5 — Comments **and** documents at every level, via an events ActivityThread *(revised 2026-06-24; resolves OQ1)*

**Supersedes** the original "documents attach only to revisions, files-only `FileSet`" rule.

Each attachable entity — the **Part**, every **Part revision/redline**, and the **Supplier Item**
— owns an `events` **`ActivityThread`**, referenced by a `thread_id` FK. (Supplier items have no
revision rows of their own; their vendor history lives as structured comments on this same thread —
[D13](#d13).) An `ActivityThread` natively carries **both** `Comment`s and `Attachment`s
(which point at `events.File`), so one uniform mechanism gives every level the ability to hold
**comments** *and* **documents** (technical drawings, change history, datasheets, quotes).

This is OQ1 option **(a)** generalized: a direct FK from each parts entity to an
`events.ActivityThread`, lazily created on first comment/attachment. Because a revision row is
point-in-time, its thread (and thus its drawings/history) is naturally frozen once a higher
revision exists — preserving the original "documents locked to a state" intent for revisions,
while *also* allowing free-standing commentary/docs on the Part and Supplier Item themselves.

> Manufacturers do **not** get a thread — only Parts, Supplier Items, and their revisions.

---

## D6 — Supplier Items map forward to exactly one Part; a Part has many Supplier Items

`SupplierItem.internal_part → Part` is a many-to-one FK. One internal Part may be fulfilled by
**many** supplier items; each supplier item maps to exactly **one** internal Part. Realizes
"Supplier Independence": internal engineering stays single-source while procurement keeps options.

---

## D7 — Supplier Items point at Part Manufacturers (manufacturer is on the item)

`SupplierItem.part_manufacturer → PartManufacturer` is many-to-one. A manufacturer produces many
supplier items; the reference lives on the item. No item without a manufacturer.

---

## D8 — Aliases are auto-populated on create

When a `SupplierItem` is created with a manufacturer part number, an `Alias`
(`alias = MPN`, `association_type = PART_TO_VENDOR_ITEM`, `part → item.internal_part`,
`supplier_item → <item>`) is created **automatically** in the same transaction. A Part's
`part_number` is likewise mirrored into an `Alias` (`part → itself`,
`association_type = PART_TO_STRING`) on Part create. Manual aliases (NSN, legacy, regional…) go
through the alias write path. One write path owns alias creation so the index never drifts.
(Field names updated by [D9](#d9).)

---

## D9 — Alias = a forced primary Part anchor + a typed secondary link *(rewritten 2026-06-29; supersedes the original "exactly one of two nullable FKs" model)*

**Supersedes** the original two-nullable-FK (`internal_part` *or* `supplier_item`, exactly-one)
design. An `Alias` now always belongs to **one primary Part** and optionally carries **one typed
secondary link**. Still **revision-agnostic** (D4 — identifiers are not tied to major/minor rows).

**Columns.**

| Column | Rule |
| :--- | :--- |
| `part` | **FK → Part, NOT NULL.** The **primary association** — the real relationship and the lookup anchor. "This Part's aliases" = `Alias.objects.filter(part=…)`. |
| `alias` | The actual alias **value** string (a vendor/manufacturer part number most of the time). |
| `alias_type` | **Open business-source label** — what *kind* of number this is *to the business*: `MPN`, `NSN`, `INTERNAL`, `LEGACY`, regional, a medical-supply number, or anything obscure. A potentially **infinite** set → stored as a free **string** (not a closed enum). |
| `supplier_item` | FK → SupplierItem, **nullable.** Set only for `PART_TO_VENDOR_ITEM`. |
| `alternate_part` | FK → Part, **nullable.** Set only for `PART_TO_PART` — an **alternate internal part number** cross-referencing another Part row. |
| `association_type` | **Closed enum of exactly three structural behaviors** (below). Governs which secondary FK is set. |

**`association_type` — the three (and only three) behaviors:**

| Value | Meaning | FK state |
| :--- | :--- | :--- |
| `PART_TO_VENDOR_ITEM` | The alias string is a vendor MPN linked to a specific Supplier Item. | `supplier_item` set, `alternate_part` null. |
| `PART_TO_PART` | The alias is an **alternate internal part number** for another Part row. | `alternate_part` set, `supplier_item` null. |
| `PART_TO_STRING` | A free/unlinked string (NSN, legacy, regional…). | both null. |

A `CheckConstraint` ties `association_type` to the matching secondary-FK state; `part` is always set.

> **Two axes, deliberately separate.** `alias_type` describes the *source/meaning to the business*
> (open, extensible); `association_type` describes the *FK relationship/behavior in the schema*
> (closed, max three). They overlap but are not the same thing and are **both** kept.

**Resolution simplifies (confirmed).** Because the primary `part` is stored directly, the resolver
returns `alias.part` outright — it no longer follows `supplier_item.internal_part` forward (the old
D6 hop). `supplier_item` is now **provenance** ("which vendor item this MPN came from"), not the
resolution path. Possible future revision-aware aliasing remains tech debt (item 3 / OQ2).

---

## D10 — Single canonical resource per entity, `format=` density, F5 rule

Every UI resource is one canonical URL with a `format=` query for density
(`condensed`/`medium`/`large`) and HTMX fragments (`htmx-*`), never combined in one request.
Every parts page works under a plain reload (F5 rule); HTMX only layers interactivity. Page
inventory in [`phase_4_parts_ui/ui_features_plan.md`](phase_4_parts_ui/ui_features_plan.md).

---

## D11 — Authenticated-only now; personas shaped by views, gated by a reviewed role matrix *(updated 2026-06-24)*

No RBAC group templates or ownership scoping are built by this kit — routes are
authenticated-only (no `public_app` routes). The four personas (technician, engineer, supply,
sourcing) are served by **distinct views**, not permission gates, in this first cut.

**New requirement:** every kit (this one included) carries a
[`functionality_and_roles.md`](functionality_and_roles.md) document — an explicit
functionality-set × role matrix for the user to review. **Release/redline permission semantics
(former OQ6) are decided in that document**, not here. RBAC can later be layered onto the matrix
without reshaping the data.

---

## D12 — Standard project conventions apply

Audit columns (`created_at`, `updated_at`, `created_by_id`, `updated_by_id`) on every new table
via `AuditFieldsMixin`. `BigAutoField` PKs except where UUID7 is required for cross-table
polymorphic uniqueness (e.g. the reused `events.File`). No business logic on models. Suffix
vocabulary per `OOP_CONTROL_PATTERNS`. Schema changes use the full DB-reset workflow
(`/db-rebuild`), never incremental migrations.

---

## D13 — Supplier revisions: comments + a denormalized compatibility range, no revision table *(new 2026-06-28; resolves [open_questions.md](open_questions.md) residual confirm #1)*

**Supersedes the Phase 2 assumption that `SupplierItemRevision` mirrored `PartRevision`.** Both the
`SupplierItemRevision` table **and** any vendor-revision→part-revision mapping table are **removed**.
Reason: a production team cannot trust, and should not take on the maintenance burden of, mirroring
a vendor's sovereign revision system. Two cheaper mechanisms replace it:

**(a) Vendor revision history → structured comments on the Supplier Item's thread.** A form posts a
machine-formatted JSON body to the `SupplierItem`'s `events.ActivityThread` ([D5](#d5)) as a normal
`Comment` (`is_human_made = True` — a person filled the form, and it stays visible in the thread).
One comment per vendor revision, append-only; the thread *is* the flat history. Shape:

```json
{ "vendor_revision_history": {
    "vendor_revision_id": "<vendor's id or the internal name we chose>",
    "note": "<free text from the user about this vendor revision>"
} }
```

Firm, first-class vendor revision tracking is **explicitly deferred to tech debt** (deferrals item 6).

**(b) Interoperability → a denormalized compatibility range on `SupplierItem`.** Instead of linking a
vendor revision to a `PartRevision`, the `SupplierItem` carries four **nullable integer** bounds
expressing the band of *our* Part's revisions it satisfies:

| | major | minor |
| :--- | :--- | :--- |
| **min** | `min_major_revision_number` | `min_minor_revision_number` |
| **max** | `max_major_revision_number` | `max_minor_revision_number` |

- `null` = **unbounded** on that edge. All four null (the ~98% default) = "valid for all revisions."
- A set major with a null minor means "the whole major band" (e.g. min `(3,null)` / max `(3,null)` =
  valid for all minors of major 3 only).
- These are **plain numbers, not FKs** — compared against `PartRevision.major/minor` at query time,
  deliberately revision-agnostic (consistent with the alias rule, [D9](#d9)). Revisions can come and
  go without dangling references.
- **No constraint in v1** (`min ≤ max`, "null minor needs a major") — left loose; the control layer
  validates if/when this rare feature is exercised.

Called the **compatibility range** throughout the kit.

---

## D14 — Part visibility is scoped by data **Domains**: a `PartDomainAccessMapping` join + an `is_domain_limited` flag on `Part` *(new 2026-06-28; resolves the domain-block requirement at the bottom of [functionality_and_roles.md](functionality_and_roles.md))*

Parts reuse the existing **`administration.Domain`** model (`app/administration/models/data_ownership/domains.py`)
— "the atomic row-level access scope; every scoped data row carries… a domain." A Part's visibility
is governed by **two** pieces working together:

**(a) `Part.is_domain_limited` — a boolean gate on the Part.**

| State | Meaning |
| :--- | :--- |
| `False` (the default; the "unset / null = not limited" case the user described) | The Part is **not** limited to any data domain — visible to every authenticated user. The `PartDomainAccessMapping` rows (if any) are ignored. |
| `True` | Visibility is **restricted** to the domains listed in `PartDomainAccessMapping`. A user sees the Part only if they share at least one of its mapped domains (via their active `UserDomain` links / `DomainsMixin.has_domain`). |

Modeled as `BooleanField(default=False)` — every Part carries the flag (per the
functionality-and-roles requirement). The default-falsy state is the ~majority "open" case, so most
Parts need no mapping rows at all.

**(b) `PartDomainAccessMapping` — the join table (which domains may see this Part *and its children*).**
A many-to-many between `Part` and `administration.Domain`, mirroring the shape of the existing
`UserDomain` link table (soft-remove via `is_active`, `(part, domain)` unique). One row = "this domain
may see this Part." Because the wider app references a Part only by its base id ([D3](#d3)), this single
mapping governs the Part **and everything that hangs off it** (revisions, supplier items, aliases) —
they inherit the base Part's domain scope rather than carrying their own.

**(c) Issuing a domain set from a `DomainTemplate` (copy, don't bind).** A Part's domains can be
populated by **applying an existing `administration.DomainTemplate`** — the admin app's "named bundle
of domains representing a scope profile" (`DomainTemplate` + `DomainTemplateItem`). A control-layer
**Handler** expands the template's active `DomainTemplateItem` domains into `PartDomainAccessMapping`
rows for the Part, exactly mirroring the existing flatten-from-template pattern that materializes
`DomainTemplate → UserDomain` (the `TemplateDomainRebaseHandler` the `DomainsMixin` references).

- The template is a **source to copy from at apply time, not a stored FK** on the Part — once issued,
  the Part owns plain `PartDomainAccessMapping` rows; later edits to the template do **not** retroactively
  change already-issued Parts.
- **Re-issuing re-bases:** applying a template again reconciles the Part's active mapping rows to the
  template's current domains (add missing, soft-deactivate removed), the same rebase semantics as the
  user-domain path.
- Mappings can also be added/removed individually — the template is a convenience to seed/copy a whole
  set at once, not the only write path.

> **Enforcement is not built by this kit.** Consistent with [D11](#d11), Phase 1 only *models* the
> table and flag and leaves comment-labelled stubs at the read seams; a later RBAC/scoping agent wires
> the actual queryset filtering (the user's note in [functionality_and_roles.md](functionality_and_roles.md):
> "Ill have a second agent do the actual implementation"). See also the future **association framework**
> placeholders under `app/assets/` (Part↔Model, Part↔Class) where Part definitions will eventually live.
