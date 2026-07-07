# Existing Seams Audit

A scan of the codebase before planning. This is the document that reframed the request:
the schema the user asked to "add" is already present, so the kit targets behavior, eventing
correctness, and UI rather than new tables.

## Already built — reuse as-is

| Seam | Location | Notes |
| :--- | :--- | :--- |
| `parent_asset` column | [`app/assets/models/core/asset.py`](../app/assets/models/core/asset.py) | Self-FK, `on_delete=SET_NULL`, `null=True, blank=True`, `related_name="children"`, indexed. **This is the column the prompt asked to add.** |
| `root_asset` column | same | Self-FK, `SET_NULL`, `related_name="descendants"`, indexed. |
| `depth_from_root` column | same | `PositiveSmallIntegerField`, nullable, indexed. |
| `AssetParentHistory` | [`app/assets/models/asset_parent_history.py`](../app/assets/models/asset_parent_history.py) | Structured move record: previous/new parent, root, depth + audit columns. |
| `AssetEvent` link (with `role`) | [`app/assets/models/core/asset_event.py`](../app/assets/models/core/asset_event.py) | Many-to-one join `asset → event` **with a `role` CharField**. One Event can link to many assets in different roles. Unique on `(asset, event)`. |
| `Event` + `EventType.ASSET_MANAGEMENT` | [`app/events/models/event.py`](../app/events/models/event.py) | Lifecycle events are generic + domain-scoped; the assets app owns the link. |
| Emit pattern | `CapabilityManager._emit_event()` in [`capability_manager.py`](../app/assets/control_layer/capabilities/capability_manager.py) | Canonical: build `Event`, then `AssetEvent` with a `role`. The relationship manager copies this, linking **two** assets per event. |
| `AssetEventNarrator` | [`app/assets/control_layer/narrators/asset_event_narrator.py`](../app/assets/control_layer/narrators/asset_event_narrator.py) | `(title, description)` tuple methods per lifecycle action. Add `child_attached` / `child_detached`. |
| `AssetHierarchyManager.reparent()` | [`app/assets/control_layer/managers/asset_hierarchy_manager.py`](../app/assets/control_layer/managers/asset_hierarchy_manager.py) | Single-hop move: recomputes root + depth, cycle guard, writes `AssetParentHistory`, one transaction. **Cascade and eventing are the gaps.** |
| `AssetHierarchyStruct` | [`app/assets/control_layer/domain_structs/asset_hierarchy_struct.py`](../app/assets/control_layer/domain_structs/asset_hierarchy_struct.py) | Reads flat columns into ancestors / children / descendant subtree, `to_dict()`. The basis for `AssetTreeStruct`. |
| `AssetContext.hierarchy` / `.reparent` | [`app/assets/control_layer/asset_context.py`](../app/assets/control_layer/asset_context.py) | Context already exposes a hierarchy manager property + `reparent` passthrough. |
| `hierarchy_edit.html` | `app/assets/templates/assets/assets/` | Legacy template — **to be deleted** in Phase 2 and replaced with fresh relationship templates (OQ5 resolved). |
| Configurations nav | [`app/assets/presentation_layer/entrypoints/configurations.py`](../app/assets/presentation_layer/entrypoints/configurations.py) | Existing index + sections (`asset_configuration_*`) the new entry slots beside. |
| Search row cards pattern | [`docs/UX_UI/Examples/search_row_cards_pattern.md`](../docs/UX_UI/Examples/search_row_cards_pattern.md) | The canonical markup the edit page adopts. |
| Asset search | [`app/assets/presentation_layer/search/asset_search.py`](../app/assets/presentation_layer/search/asset_search.py) | Already prefetches `children`; reuse/extend for the search-to-attach bar. |

## The actual gaps this kit closes

1. **No dedicated relationship manager.** Only a low-level `reparent(new_parent_id)` exists.
   There is no `attach_child` / `detach_child` / bulk-attach vocabulary, which is what the
   "edit children" UI needs to call. → Phase 1.
2. **No Event on relationship change.** `reparent` writes `AssetParentHistory` but emits no
   `Event`, so nothing appears on either asset's timeline. → Phase 1.
3. **Subtree cascade bug.** `reparent` updates only the moved node's `root_asset` /
   `depth_from_root`; descendants keep stale roots/depths. → Phase 1.
4. **No relationship UI.** The `children/view` and `children/edit` routes, the Configurations
   entry, HTMX depth expansion, and search-to-attach do not exist. → Phase 2.

## Confirmed: zero schema changes

Because `parent_asset`, `root_asset`, `depth_from_root`, `AssetParentHistory`, and
`AssetEvent.role` all already exist, **neither phase runs a migration**. This removes the
DB-rebuild step from both phases' exit criteria.
