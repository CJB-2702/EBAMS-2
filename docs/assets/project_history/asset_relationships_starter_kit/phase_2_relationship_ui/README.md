# Phase 2 — Relationship UI

Put a face on the Phase 1 engine: a **view** and an **edit** screen for an asset's children,
reached from a new **Asset Relationships** entry under Configurations, with progressive
depth-on-click and a search-to-attach bar.

## Goal

From `assets/<id>/children/view` a user reads the asset's children as a tree, expanding one
more depth per click. From `assets/<id>/children/edit` they do the same and can **detach** any
child or **search** the asset catalog and **attach** results onto the current asset — every
action going through `AssetContext(...).relationships` from Phase 1.

## In scope

- NEW **Asset Relationships** entry on the Configurations index ([D6](../decisions.md)).
- NEW canonical routes (single resource + `format=`):
  - `assets/<asset_id>/children/view` — read-only tree.
  - `assets/<asset_id>/children/edit` — editable tree + search-to-attach.
- NEW entrypoints, templates, and a relationship-search read for the attach bar.
- HTMX **depth-on-click**: expanding a card loads its next ring of children inline
  (`format=htmx-depth`), F5-safe.
- HTMX **search-to-attach**: incremental asset search returning attachable row cards
  (`format=htmx-search-results`); Attach posts to the relationship manager.
- **Detach** action per child card; confirm dialog.
- Edit page built on the **Search Row Cards** pattern ([D7](../decisions.md),
  [`search_row_cards_pattern.md`](../../harness/UX_UI/Examples/search_row_cards_pattern.md)).

## Out of scope

- Any control-layer write logic — all reuse Phase 1's `AssetRelationshipManager`.
- Schema changes — none.
- Re-parenting via drag-and-drop (future; click-to-attach only this phase).

## Dependencies

- **Phase 1 complete**: `AssetRelationshipManager`, `AssetTreeStruct`, `AssetContext.tree` /
  `.relationships`.
- Existing Configurations index + entrypoint conventions; existing `asset_search` read;
  existing search row cards markup; the `format=` density/HTMX contract.

## Deliverables

- `app/assets/presentation_layer/entrypoints/asset_relationships.py` — `children_view`,
  `children_edit`, `children_expand` (htmx), `children_search` (htmx), `attach`, `detach`.
- URL entries for the routes above; **Asset Relationships** link on the Configurations index.
- `app/assets/presentation_layer/search/relationship_search.py` — attachable-asset search
  (excludes self, existing children, and ancestors to prevent obvious cycles).
- Templates under `app/assets/templates/assets/relationships/`: `view.html`, `edit.html`,
  `_tree_node_card.html`, `_search_results.html`. **Delete** the legacy
  `app/assets/templates/assets/assets/hierarchy_edit.html` and build these fresh (OQ5
  resolved — replace, don't salvage).

## Exit criteria

- [ ] The Configurations index shows an **Asset Relationships** entry that routes to a
      relationship surface.
- [ ] `assets/<id>/children/view` renders the asset and its children as a tree on a plain
      page load (F5 rule) and expands one more depth per click without a full reload.
- [ ] `assets/<id>/children/edit` renders the same tree using the **search row cards**
      pattern, with per-child **Detach** and a **search-to-attach** bar below the tree.
- [ ] Searching in the attach bar returns attachable assets only — **excluding** the current
      asset, its existing children, and its ancestors.
- [ ] Clicking **Attach** on a result calls `AssetRelationshipManager.attach_child`, the new
      child appears in the tree, and the timeline Event from Phase 1 is created.
- [ ] Clicking **Detach** calls `detach_child`, the child (and its subtree) leaves the tree,
      and the Event is created.
- [ ] An attempted illegal attach (self-parent / cycle) surfaces the manager's error message
      inline and changes nothing. (Cross-domain / cross-class attach is permitted.)
- [ ] No request combines a density value and an `htmx-*` value in the same `format=`
      (per project contract).
