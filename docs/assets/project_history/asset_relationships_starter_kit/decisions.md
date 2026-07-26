# Decisions

Architectural decision log for the Asset Relationships kit. Each decision is binding for
both phases unless superseded.

---

## D1 — Dedicated `AssetRelationshipManager`, not a bare `reparent`

**Options.** (a) Keep calling the existing `AssetHierarchyManager.reparent(new_parent_id)`
from the UI. (b) Add a new `AssetRelationshipManager` with intention-revealing operations.

**Chosen: (b).** The UI thinks in "attach this asset as a child of N" / "remove this child",
not "reparent asset X to N". A dedicated manager exposes `attach_child(child_id)`,
`detach_child(child_id)`, and `attach_children(child_ids)` from the perspective of the asset
whose children are being edited. It **absorbs** the low-level move logic (cycle guard, root +
depth recompute, history row) so there is one home for relationship writes.

**Disposition of the old manager.** `AssetHierarchyManager.reparent` is folded into the new
manager (or the new manager becomes the single owner and `reparent` delegates to it). No two
parallel write paths — see [D8](#d8--single-write-path).

---

## D2 — Dedicated `AssetTreeStruct` for the nested tree

**Options.** (a) Reuse `AssetHierarchyStruct` (ancestors + flat children + flat descendant
list). (b) Add an `AssetTreeStruct` that builds a genuinely **nested** node tree.

**Chosen: (b).** The UI renders a tree and lazy-loads one more depth per click. A flat
descendant list does not express parent→child nesting cleanly. `AssetTreeStruct` builds nodes
with a `children` list to a requested `max_depth`, exposes `to_dict()` (nested) and a
`level(depth)` slice so an HTMX request can fetch exactly the next ring. `AssetHierarchyStruct`
stays for breadcrumb/ancestor reads.

---

## D3 — One Event per change, linked to BOTH assets via existing `AssetEvent.role`

**Options.** (a) Add a new `event_asset` link table. (b) Two separate events, one per asset.
(c) **One** Event linked to two assets using the existing `AssetEvent` join's `role` field.

**Chosen: (c).** `AssetEvent` is already a many-to-one join with a `role` CharField, so a
single `Event` ("Child *C* attached under *P*") gets two `AssetEvent` rows — `role="child"`
on C and `role="parent"` on P. One timeline entry, visible from both assets, no new table.
Detach emits its own Event (`child_detached`). `AssetParentHistory` is **still** written as
the structured, machine-readable audit — the Event is the human-readable surface.

---

## D4 — "Edit children" = reparenting other assets onto N; detach → null parent

Editing asset *N*'s children operates on **other** assets. Attaching child *C* sets
`C.parent_asset = N`. Detaching *C* sets `C.parent_asset = null`, making *C* its own root
(`root_asset = C`, `depth = 0`) along with its whole subtree (per [D5](#d5--reparent-cascades-to-the-whole-subtree)).
There is no separate "relationship" row — the parent pointer *is* the relationship.

---

## D5 — Reparent cascades to the whole subtree

When a node moves, every descendant's `root_asset` and `depth_from_root` is recomputed in the
same transaction (descendant new depth = node's new depth + its offset below the node; new
root = node's new root). This fixes the current bug where only the moved node was updated.
The cycle guard already prevents a node from being attached under its own descendant, so the
subtree is always well-formed before the cascade runs.

---

## D6 — Canonical URLs with `format=`, single resource per page

Per project convention, the children surface is one canonical resource per asset:

- `assets/<asset_id>/children/view` — read-only tree view.
- `assets/<asset_id>/children/edit` — editable tree + search-to-attach.

Density and HTMX fragments ride the `format=` query (`htmx-depth`, `htmx-search-results`),
never combined with a density value in the same request. Both pages satisfy the **F5 rule** —
a plain reload renders the current tree server-side; HTMX only adds depth-on-click and
incremental search.

---

## D7 — Edit page uses the Search Row Cards pattern

The edit page renders each child as a full-width **search row card**
([`harness/UX_UI/Examples/search_row_cards_pattern.md`](../harness/UX_UI/Examples/search_row_cards_pattern.md)):
title + class tag + depth/childcount stats inline, flush right-hand action pane (Expand /
Detach). Clicking a card's expand control HTMX-loads its next depth of children inline. The
search-to-attach bar lives below the tree and returns the same card shape with an **Attach**
action.

---

## D8 — Single write path

All relationship mutations — UI, seed, future bulk import — go through
`AssetRelationshipManager` via `AssetContext`. No view writes `parent_asset` directly, and no
second manager duplicates the move logic. This keeps the cycle guard, cascade, history row,
and Event emission inseparable from every write.

---

## Resolved open questions (DR1–DR5)

Confirmed by the user 2026-06-19. Binding.

| ID | Question | Decision |
| :--- | :--- | :--- |
| **DR1** | Default tree render depth / expand breadth | Render depth **2**; paginate a single expand only when a node has a very large direct-child count. |
| **DR2** | Cross-domain / cross-class children | **Allowed.** `RelationshipPolicy` enforces only self-parent and cycles — domain and class never gate an attach. |
| **DR3** | Attaching an already-parented asset | **Allowed** — it is a *move*. The subtree travels intact ([D5](#d5--reparent-cascades-to-the-whole-subtree)); the Event and `AssetParentHistory` record the prior parent. No "detach first" rule. |
| **DR4** | Bulk attach | **No batch.** Relationships are managed one parent↔child at a time — `attach_child` / `detach_child` only. (Each is already atomic: guard → move → cascade → history → event in one transaction.) A multi-select `attach_children` was dropped to keep the tool focused on small, deliberate groupings. |
| **DR6** | Hub page | A dedicated **`/assets/asset-relationships/`** asset search page (search-row-cards) lists every asset with its direct-child count and View / Edit-children actions — the front door to the feature, in addition to the Configurations entry and sidebar link. |
| **DR7** | Scope framing | The UI explicitly states this is a tool for grouping assets in small sets (tank↔scuba gear, trailer↔truck) and **is not a bill-of-materials (BOM) manager** — shown as a disclaimer on the hub and edit pages. |
| **DR5** | Legacy `hierarchy_edit.html` | **Replace, don't salvage** — delete it and build the relationship templates fresh for a coherent system. |
