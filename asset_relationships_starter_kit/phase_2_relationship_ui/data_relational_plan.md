# Phase 2 — Data Relational Plan

**No new tables, no new columns, no migration.** This is a presentation phase over the Phase 1
control layer and the existing schema.

## Data this phase reads (all via the control layer — no direct ORM in templates)

| Source | Used for |
| :--- | :--- |
| `AssetTreeStruct` (Phase 1) | Rendering the nested tree on `view` / `edit` and each HTMX depth ring. |
| `AssetHierarchyStruct` (existing) | Breadcrumb / ancestor strip showing where the current asset sits. |
| `Asset` catalog (via `relationship_search`) | The search-to-attach results. |
| `asset_event` / `event` (existing) | (Optional) showing the most recent relationship events on the page; read-only. |

## Data this phase writes (all via Phase 1, never directly)

| Action | Path |
| :--- | :--- |
| Attach a child | `AssetContext(parent).relationships.attach_child(child_id)` |
| Detach a child | `AssetContext(parent).relationships.detach_child(child_id)` |

No entrypoint sets `parent_asset`, writes `AssetEvent`, or touches `AssetParentHistory`
directly — that is the [D8](../decisions.md) single-write-path rule.

## Search read contract (`relationship_search`)

Returns attachable assets for the attach bar, **excluding**:

- the current asset itself,
- its existing direct children (already attached),
- its ancestors (attaching one would be an immediate cycle).

Other assets — including ones in a **different domain/class** and ones that already have a
parent (attaching is then a **move**, OQ3 resolved) — are returnable. The search read does
**not** mutate; the structural cycle/self enforcement still happens authoritatively in
`RelationshipPolicy` on attach.
