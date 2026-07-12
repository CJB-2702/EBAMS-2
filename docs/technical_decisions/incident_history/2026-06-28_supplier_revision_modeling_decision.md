---
type: "Technical Decision"
title: "Supplier Item Revision Modeling — Decision Walkthrough"
description: "the item's events thread; interoperability is a denormalized **compatibility range** on the."
tags: [technical-decisions, technical-decision, incident-history]
context_tier: 2
---

# Supplier Item Revision Modeling — Decision Walkthrough

> **Placement note (author's own):** I don't have a better home for this yet, so it's parked under
> `incident_history/`. It isn't really an incident — it's the record of a design back-and-forth I
> kept reopening — but it's the closest existing folder. Move it if a better location appears (e.g.
> a future `design_explorations/`). The binding decision itself lives in
> [`part_definitions_kit/decisions.md` → D13](../../../part_definitions_kit/decisions.md); this doc
> is the *why* and the roads not taken.

- **Date:** 2026-06-28
- **Area:** `app/parts/` (planned) — Phase 2 supplier mapping of the Part Definitions kit.
- **Outcome:** Supplier items get **no revision table**. Vendor history is structured comments on
  the item's events thread; interoperability is a denormalized **compatibility range** on the
  `SupplierItem`. Firm vendor-revision tracking is deferred to tech debt (deferrals item 6).

---

## The question I kept reopening

Should **supplier items have revisions**, and if so, how should my production team's revision
reality relate to the vendor's own revision reality? I went back and forth on this multiple times.
The kit had been sitting on an unresolved "residual confirm" assuming `SupplierItemRevision` would
mirror `PartRevision`'s numeric major/minor model — chosen for *symmetry*, not because the supplier
domain demanded it.

The honest tension: the symmetric design was mechanically clean (one revision shape, one set of
control code, one "current" rule) but the business description of supplier history was a
**straight-line** thing — datasheets, quotes, vendor rev bumps — which doesn't need the major/minor
machinery that exists to express the *non-linear* case (a redline against an older major).

## The business problems (what's actually hard)

Boiled down from a longer list; these are the ones I decided actually matter:

1. **Trigger mismatch** — vendors revise for *their* reasons; only *some* of those changes affect
   my part's interoperability. Which vendor changes are "so what" vs "stop the line"? *(keep)*
2. **Interoperability is revision-to-revision** — "this vendor item satisfies our part" really means
   "vendor item at rev X satisfies our part at rev Y," and both sides move independently. *(keep —
   the key problem)*
3. **Sign-off authority** — a vendor change that might affect fit/form/function needs a human to
   bless it, with an owner + date. *(solved-enough by a notes field for now)*
4. **Vendor's "latest" ≠ my "approved"** — I may deliberately buy an older vendor revision because
   the new one isn't qualified. *(the real problem I've actually hit)*
5. **How much vendor history to even carry** — none / a flat log / their full structured history.
   *(chose: flat log)*
6. Fan-out, full audit/traceability, forced-migration-on-obsolescence — *(dropped or → tech debt)*

## Options considered

### Option A — Symmetric `SupplierItemRevision` (the kit's old assumption)
A full mirror of `PartRevision`: `sequence`, major/minor numbers + names, status, per-revision
thread, "current = highest (major, minor)." **Rejected:** takes on the maintenance burden of
mirroring a sovereign system I don't control or trust, to express a non-linearity vendors rarely
have. Dead weight for the 98% case.

### Option B — Flat log + `locked` flag + optional mapping table
Simplify supplier revisions to a flat counter (newest wins for "latest"), add a `locked` boolean
marking the one revision I've qualified (solving problem 4: latest vs approved as two pointers over
one list), and add a normally-empty `SupplierItemRevisionMapping` (vendor revision → `PartRevision`,
+ notes) for the rare revision-to-revision qualification (problems 1 & 2). **Considered and
shelved** — still two extra tables and a revision concept I'd have to maintain. Recorded for revival
in tech-debt item 6.

### Option C — Denormalized compatibility range, no revision table *(chosen — D13)*
Collapse it entirely. A `SupplierItem` stops being "a vendor product with its own history" and
becomes "a procurement option that satisfies a band of *our* part's revisions." Two cheap mechanisms:

- **Vendor history → comments.** A form posts one append-only `Comment` per vendor revision to the
  item's `events.ActivityThread` (`is_human_made = True`), machine-formatted JSON body:

  ```json
  { "vendor_revision_history": {
      "vendor_revision_id": "<vendor id or internal name>",
      "note": "<free text about this vendor revision>"
  } }
  ```

  The thread *is* the flat history. Datasheets/quotes attach to the same thread as documents.

- **Interoperability → a compatibility range** on the item: four **nullable integer** bounds
  (`min/max` × `major/minor` revision number), compared against `PartRevision.major/minor` at query
  time. **No FK** (revision-agnostic, like aliases). `null` = unbounded; all-null (the ~98% default)
  = valid for all revisions; a set major with null minor = "the whole major band." No `min ≤ max`
  constraint in v1 — the control layer validates if/when the rare feature is used.

## Why C won

- Solves problem 2 directly and inline — no join, no normally-empty table.
- Solves problem 4 implicitly: I order against a *range* I've set, independent of the vendor's
  newest.
- Zero new revision concept to maintain for data I don't own.
- Keeps the engineering record clean — vendor churn is comments, never a Part revision (the original
  isolation goal survives without a supplier revision table).
- "Get the application moving, come back later if needed." The infrastructure for the harder cases
  is consciously parked, not foreclosed.

## Known costs (accepted)

- **Vendor history is not SQL-queryable** — it's JSON text in `comment.content`, fine for display
  but not for "find all items whose vendor revision matches X." That needs the firm tracking in
  tech-debt item 6.
- The compatibility range is unconstrained in v1; a nonsensical `min > max` is possible until the
  control layer guards it.
- No first-class model of the vendor's own revision lineage.

## If/when this gets reopened (the revival path)

Tech-debt item 6 in
[`20260624 Part definitions kit deferrals.md`](../tech_debt/20260624%20Part%20definitions%20kit%20deferrals.md):
a real `SupplierItemRevision` table and/or the explicit vendor-revision → `PartRevision`
qualification mapping (Option B's `locked`-flag + mapping-table sketch). Both were considered and
consciously shelved.

## Files touched by the decision

`part_definitions_kit/`: `decisions.md` (D4 narrowed, D5 reworded, **D13** added), `open_questions.md`
(residual confirm #1 resolved), `STATUS.md`, `functionality_and_roles.md`,
`phase_2_supplier_mapping/{README,data_relational_plan,control_layer_plan}.md`,
`phase_4_parts_ui/{README,ui_features_plan,control_layer_plan,data_relational_plan}.md`. Plus
tech-debt item 6.
