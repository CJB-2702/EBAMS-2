# New Part — creation wizard proposal

Goal: replace the current bare `part_create` form (`app/parts/presentation_layer/entrypoints/parts.py`) with a single-page, multi-card wizard at `/parts/new/` that lets a user create a Part and its sub-information — manual aliases, supplier items, extra revisions, images — in one sitting, following the multi-card wizard pattern in `harness/UX_UI/design_patterns/multi_step_flows.md` (one route, vertical scroll, session-backed draft, no separate step URLs).

This is a proposal for discussion — no code implied yet.

## Why this qualifies as a wizard, not a form

Part has more than one reverse FK a user would plausibly populate in the same sitting: `Alias` (manual), `SupplierItem`, `PartRevision` (beyond the auto-created base), and the photo gallery (`PartImageManager`). Per the trigger rule in `multi_step_flows.md`, that's a wizard.

## What's already automatic (not a card)

- **Base revision** — `PartFactory.create` auto-creates major=1, minor=0, DRAFT via `PartRevisionManager.release_major` inside the same transaction as the Part insert. The wizard doesn't need a "create first revision" step; it can *display* the auto-created revision as a confirmation, not collect input for it.
- **INTERNAL alias** — `PartFactory` auto-mirrors `part_number` into an alias (source=AUTO). Any alias card only needs to collect *additional* manual aliases (NSN, legacy part numbers, etc.) — never re-collect the part number itself.

## Proposed card order (dependency-first)

1. **Part identity** (required, always enabled)
   `part_number` (required, unique), `name`, `description`, `part_type`, `category`, `is_active`, `is_domain_limited`. This is the only card that determines whether every later card unlocks — nothing else can be created without a `part.id`.

2. **Revisions** (optional, unlocks once card 1 validates)
   Shows the auto-created base revision (major 1.0, DRAFT) as a read-only confirmation row. Optionally lets the user immediately redline (add a minor) or release a further major if they know up front they're entering a part with existing revision history (e.g. migrating legacy data). Default state: collapsed/skipped — most parts start at 1.0 and don't need this touched at creation.

3. **Manufacturers & supplier items** (optional, unlocks once card 1 validates)
   A `SupplierItem` requires an *existing* `PartManufacturer` (no create-inline hook in `SupplierItemManager` today) plus `manufacturer_part_number`. So this card needs a manufacturer picker with the existing "quick create" HTMX sub-flow (`parts/manufacturers/_manufacturer_picker.html`, the one legitimate round-trip inside the wizard, per the comment in `entrypoints/manufacturers.py` — a `PartManufacturer` needs a real DB id before the rest of the row can reference it). Repeatable row: manufacturer + MPN + optional name/description/compatibility range (min/max major/minor). Each row created here auto-generates its MPN alias and machine comment via `SupplierItemManager.create` — don't also expose an alias field for the MPN on this card, it'd be redundant with what the alias card would otherwise let you add manually.

4. **Additional aliases** (optional, unlocks once card 1 validates)
   Manual aliases only — `alias`, `alias_type` (free text today, e.g. NSN/legacy — consider constraining to a picklist once real usage data exists), and for `PART_TO_PART` type, a linked alternate Part picker. Skip `PART_TO_VENDOR_ITEM` here entirely — that association type is created automatically by card 3, don't let a user hand-create a duplicate path to the same row shape.

5. **Images** (optional, unlocks once card 1 validates)
   Drag/drop or file picker onto `PartImageManager` (gallery + auto-primary-on-first-image). No dependency on other cards — could be reordered earlier if the business wants the identity+photo pairing visually adjacent, but keep it last since it's the least structurally important of the four.

## Session draft shape

Following the pattern, hold state in `request.session['part_draft']` until final submit:

```
part_draft = {
    "identity": {part_number, name, description, part_type, category, is_active, is_domain_limited},
    "revisions": [{major, minor, summary, status}, ...]  # optional extra rows beyond auto base
    "supplier_items": [{part_manufacturer_id, manufacturer_part_number, name, description, min_major, min_minor, max_major, max_minor}, ...],
    "aliases": [{alias, alias_type, alternate_part_id}, ...],
    # images are binary — likely uploaded to a scratch FileSet on first drop rather than session-serialized, mirroring how the manufacturer quick-create round-trips for an id
}
```

## Open questions to confirm before building

- **Commit granularity**: does the whole wizard commit as one `transaction.atomic()` on final submit (matches `PartFactory`'s existing single-transaction shape), or does Part get created on card 1 submit (giving a real `part.id` immediately, needed anyway for the manufacturer quick-create and image upload round trips) with subsequent cards writing incrementally? The manufacturer-picker precedent (real DB id needed mid-wizard) suggests **Part commits on card 1**, and cards 2–5 write directly against that `part.id` rather than staying purely session-drafted — worth deciding explicitly since it changes the "no DB write until final submit" default from `multi_step_flows.md`.
- **Alias-type picklist**: formalize the currently free-text `alias_type` field, or leave it open text in the wizard UI too?
- **Revision card default visibility**: collapsed-by-default vs. always-expanded — depends on how often real users create parts with pre-existing revision history vs. always starting fresh at 1.0.
