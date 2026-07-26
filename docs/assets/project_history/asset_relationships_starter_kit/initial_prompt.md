# Initial Prompt

## Verbatim user request

> I want to add asset parent child relationships,
> add a column to assets parent_asset optional
> Every time a relationship is added or removed an event should be added with both the
> parent and child describing the change
> make a struct that constructs a parent child tree
>
> add an item under configurations called asset relationships
> there should be pages
> http://127.0.0.1:8000/assets/assets/1/children/edit
> http://127.0.0.1:8000/assets/assets/1/children/view
> that allows the user to view and edit children
> the edit should be a `harness/UX_UI/Examples/search_row_cards_pattern.md` that shows the
> asset, its children and onclick htmx get an additional depth of children
> under this display I should be able to search for assets and add them to my current set
>
> I think i will need more views and tools for this lets brainstorm approaches and pages
> that should exist

Follow-up:

> ok lets have a manager explicitly for parent child relationships a struct that builds the
> tree and build a ui plan

## Clarifying decisions captured during interrogation

A codebase audit (see [`existing_seams_audit.md`](existing_seams_audit.md)) reframed the
request: most of the requested schema already exists. The binding decisions:

1. **The `parent_asset` column already exists** (`SET_NULL`, optional, indexed), alongside
   `root_asset` and `depth_from_root`. No column is added. The work is behavior + UI.
2. **A dedicated manager is wanted** — `AssetRelationshipManager` — exposing intention-
   revealing operations (`attach_child`, `detach_child`, bulk attach), absorbing the
   existing low-level `reparent` logic. (D1)
3. **A dedicated tree struct is wanted** — `AssetTreeStruct` — that builds the nested
   parent→child tree to arbitrary depth, with `to_dict()` and per-level slicing so the UI
   can lazy-load one more depth on click. (D2)
4. **Eventing**: every attach/detach emits **one `Event`** that references **both** the
   parent and the child. The existing `AssetEvent` join already carries a `role` field, so
   one Event links to two assets (roles `parent` / `child`). **No new link table.** The
   structured `AssetParentHistory` row is still written as the machine-readable audit. (D3)
5. **"Edit children" semantics**: editing asset *N*'s children means **reparenting other
   assets onto *N***. Attaching a child sets that asset's `parent_asset = N`; detaching a
   child sets its `parent_asset = null`, so it becomes its own root. (D4)
6. **Cascade correctness is in scope**: reparenting a node updates the `root_asset` and
   `depth_from_root` of **all its descendants**, fixing the current staleness bug. (D5)
7. **UI**: a new **Asset Relationships** entry under Configurations; canonical
   `assets/<id>/children/view` and `assets/<id>/children/edit` pages; the edit page uses the
   **search row cards** pattern with HTMX depth-on-click and a search-to-attach bar. (D6, D7)
8. **Phasing**: Phase 1 = control layer (manager, struct, eventing, cascade); Phase 2 = UI.
