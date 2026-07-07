# Tech Debt: Part Definitions Kit — deferred items

**Logged:** 2026-06-24
**Source:** `part_definitions_kit/` planning review (see `open_questions.md` in that kit).

Items consciously deferred while planning the parts application. None block Phase 1
implementation; each is parked here for later.

## 1. Two manufacturer tables (asset vs. part) — future merge (OQ4)

`parts.PartManufacturer` is created separate from the existing asset `Manufacturer`
([decisions D2]). Accepted as fine for now (cf. the existing note *"dual 'manufacturers' for
parts and assets likely ok for now"*). Future direction, not yet chosen: either (i) merge the
two tables, or (ii) add a nullable `asset Manufacturer → part_manufacturer` pointer so the small
asset-manufacturer set resolves into the larger part registry without slowing asset reads.
`PartManufacturer` mirrors `Manufacturer`'s shape to keep both options mechanical.

## 2. Revision model normalization (denormalized for now)

The chosen revision design is **denormalized**: major/minor revision numbers + names live as
columns on a single flat `PartRevision` table. This could later be normalized into separate
major-revision / minor-revision tables. Deliberately **not** done now — the flat
numeric-source-of-truth model is simpler to build and query. Revisit if the major/minor duplication
becomes a maintenance problem. *(Note 2026-06-28: this applies to `PartRevision` only — supplier
items no longer have a revision table; see item 6 and [D13].)*

## 3. Revision-aware aliases (OQ2) — leave for later

Aliases currently point only at a Part or a Supplier Item and are **revision-agnostic** (an
identifier stays stable across revisions). If some identifier ever changes meaning per revision
(e.g. a re-numbered drawing), we'd need a revision pointer or validity window on the alias.
Deferred — no action now.

## 4. Search manager & API (OQ7) — important, deferred

Technician quick-lookup in the kit uses only case-insensitive exact/prefix matching on alias
`value` + Part `part_number`/`name` (SQLite-friendly). The user intends to build a dedicated
**search manager and API** supporting various search levels and component insertion (and a
Postgres trigram/full-text path). That is its own effort — keep parts search minimal until then.

## 5. Parking lot — downstream tools that will consume the base Part id

- **BOM management tool** — separate future kit; references `Part.id` only.
- **Configuration allowability tool** — separate future kit; references `Part.id` only.
- **Sourcing persona** — named as "potential"; no workflow defined yet.
- **Postgres migration** — system targets SQLite now, Postgres later; mainly affects search (#4).

## 6. Firm vendor revision tracking (deferred 2026-06-28 — D13)

Supplier items currently have **no revision table**. Vendor revision history is captured loosely as
structured JSON comments on the Supplier Item's events thread
(`{"vendor_revision_history": {"vendor_revision_id", "note"}}`), and interoperability is a
denormalized **compatibility range** (four nullable major/minor bounds) on the `SupplierItem`. This
is a deliberate compromise to get the application moving — it does **not** model the vendor's own
revision lineage as first-class data, and the compatibility range has no `min ≤ max` constraint.

If/when a production team needs to firmly respect a vendor's revision system, revisit: a real
`SupplierItemRevision` table and/or an explicit vendor-revision → `PartRevision` qualification
mapping (the earlier `locked`-flag + mapping-table sketch). Both were considered and consciously
shelved. No action now.
