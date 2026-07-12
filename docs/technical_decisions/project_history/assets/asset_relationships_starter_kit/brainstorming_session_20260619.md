# Brainstorming Session — 2026-06-19

## Goal

Turn "add asset parent/child relationships" into an executable plan: a dedicated manager, a
tree-building struct, auditable eventing, and a view/edit UI under Configurations.

## How the session ran

The request read as net-new schema work ("add a column `parent_asset`"). A codebase audit
flipped that assumption. The asset table already carries `parent_asset`, `root_asset`, and
`depth_from_root`; a single-hop `AssetHierarchyManager.reparent()` and an
`AssetHierarchyStruct` already exist; and — critically — the `AssetEvent` join already has a
`role` field, so one Event can reference two assets without any new table.

That reframed the whole kit from "build the hierarchy" to "wrap the existing seam in an
intention-revealing manager, make it emit events and cascade correctly, and put a UI on it."
The full audit is in [`existing_seams_audit.md`](existing_seams_audit.md).

## Key facts established

- **No schema changes needed.** Every column, history table, and link table already exists.
  Neither phase runs a migration.
- **The eventing seam is richer than expected.** `AssetEvent.role` + the
  `CapabilityManager._emit_event` pattern means a relationship change is "one Event, two
  links" — directly satisfying "an event with both the parent and child."
- **Two real bugs/gaps in the existing code**: `reparent` emits no Event, and it does not
  cascade root/depth to descendants. Both are fixed in Phase 1.
- **The UI vocabulary is "edit children,"** but the underlying operation is reparenting other
  assets onto the current one — the manager's API is written from the parent's point of view
  (`attach_child` / `detach_child`) to match how users think on that page.

## Decisions reached

See [`decisions.md`](decisions.md) for the full log. Headlines:

- **D1** Dedicated `AssetRelationshipManager` absorbing the move logic.
- **D2** New `AssetTreeStruct` building a nested, depth-bounded tree for the UI.
- **D3** One Event per change, dual-linked via `AssetEvent.role`; `AssetParentHistory` kept.
- **D5** Reparent cascades root/depth across the whole subtree (bug fix).
- **D6/D7** Canonical `children/view` + `children/edit` routes; edit uses search row cards
  with HTMX depth-on-click and search-to-attach.

## Phase shape

- **Phase 1 — relationship control layer.** Manager, tree struct, narrator methods,
  eventing, cascade. Headless-testable. Zero UI, zero migrations.
- **Phase 2 — relationship UI.** Configurations entry, the two pages, HTMX depth expansion,
  search-to-attach. Thin shell over Phase 1.

## Open questions — RESOLVED 2026-06-19

All five were answered by the user; recorded as binding decisions [DR1–DR5](decisions.md#resolved-open-questions-dr1dr5).

- **OQ1 — Depth/breadth thresholds.** ✅ Default render depth = **2**; paginate a single
  expand only when a node's direct-child count is very large.
- **OQ2 — Cross-domain / cross-class children.** ✅ **Allowed.** `RelationshipPolicy` is
  structural only (self-parent + cycle); domain and class never gate an attach.
- **OQ3 — Move vs. attach of an already-parented asset.** ✅ **Allowed** — attaching an
  already-parented asset is a move; its subtree travels intact, and the Event/history record
  the prior parent.
- **OQ4 — Bulk attach atomicity.** ✅ **All-or-nothing** in one transaction; any violation
  rolls the whole batch back.
- **OQ5 — Repurpose `hierarchy_edit.html`?** ✅ **Replace, don't salvage** — delete it and
  build the relationship templates fresh.
