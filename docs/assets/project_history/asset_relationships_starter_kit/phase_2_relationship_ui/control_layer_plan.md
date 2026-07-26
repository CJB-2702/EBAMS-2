# Phase 2 — Control Layer Plan (Presentation)

This phase writes **no** new control-layer write logic. It adds presentation-layer
entrypoints and one search read, all delegating to Phase 1. Suffix vocabulary per
[`OOP_CONTROL_PATTERNS`](../../harness/Architecture/OOP_CONTROL_PATTERNS.md);
endpoint shape per [`ENDPOINT_PATTERNS`](../../harness/Architecture/ENDPOINT_PATTERNS.md) and
[`HTMX_PATTERNS`](../../harness/Architecture/HTMX_PATTERNS.md).

---

## Entrypoints — `presentation_layer/entrypoints/asset_relationships.py`

| Entrypoint | Method | Route | `format=` | Delegates to |
| :--- | :--- | :--- | :--- | :--- |
| `children_view` | GET | `assets/<asset_id>/children/view` | density (`condensed`/`medium`/`large`) | `AssetContext(id).tree(max_depth=2)` + `AssetHierarchyStruct` (breadcrumb) |
| `children_edit` | GET | `assets/<asset_id>/children/edit` | density | same as view, edit chrome |
| `children_expand` | GET | `assets/<asset_id>/children/expand?node=<child_id>` | `htmx-depth` | `AssetTreeStruct.from_id(node_id, max_depth=1).level(1)` |
| `children_search` | GET | `assets/<asset_id>/children/search?q=...` | `htmx-search-results` | `relationship_search(asset_id, q)` |
| `attach` | POST | `assets/<asset_id>/children/attach` | — | `AssetContext(id).relationships.attach_child(child_id)` |
| `detach` | POST | `assets/<asset_id>/children/detach` | — | `AssetContext(id).relationships.detach_child(child_id)` |

Notes:

- **F5 rule**: `children_view` / `children_edit` render the full current tree server-side from
  `AssetTreeStruct.to_dict()`. HTMX endpoints (`expand`, `search`) return fragments only.
- **`format=` discipline** ([D6](../decisions.md)): a request carries *either* a density value
  *or* an `htmx-*` value, never both. `expand` and `search` are HTMX-only routes.
- **Writes** (`attach`/`detach`) are POST, CSRF-protected, and on success return the updated
  subtree fragment (or `HX-Redirect`/re-render) so the tree refreshes in place. On a
  `RelationshipPolicy` / manager error, return the message inline (HTMX swap into an error
  slot), 422-style, changing nothing.
- Each entrypoint resolves `AssetContext(asset_id, request.user)` — ownership/permission
  scoping rides the existing context/middleware; no bespoke auth here.

---

## Search read — `presentation_layer/search/relationship_search.py`

Read-only, returns attachable assets for the attach bar. Reuses/extends the existing
`asset_search` query shape.

```
relationship_search(asset_id: int, q: str, *, limit: int = 20) -> list[Asset]
```

Excludes (per [Phase 2 data plan](data_relational_plan.md)): the asset itself, its existing
direct children, and its ancestors. Returns assets matching `q` on `name` / `serial_number`,
annotated with `asset_class` and direct `child_count` for the result card. Pure read — no
mutation, no policy decision (the authoritative cycle/domain check is in `attach`).

---

## Delegation summary

```
GET  children_view/edit ─▶ AssetContext(n).tree(2).to_dict()     ─▶ render tree (search row cards)
GET  children_expand     ─▶ AssetTreeStruct.from_id(c,1).level(1) ─▶ render child ring fragment
GET  children_search     ─▶ relationship_search(n, q)             ─▶ render attachable result cards
POST attach              ─▶ AssetContext(n).relationships.attach_child(c) ─▶ render updated subtree | error
POST detach              ─▶ AssetContext(n).relationships.detach_child(c) ─▶ render updated subtree | error
```

No new Structs/Managers/Handlers are introduced in this phase — it is entrypoints + one search
read over the Phase 1 surface.
