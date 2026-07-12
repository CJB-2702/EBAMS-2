# Phase 1 — Data Relational Plan

**This phase adds no tables and no columns.** Every persistence seam already exists. This
document records what is *read from* and *written to*, and the direction of each relationship,
so the control layer plan can be verified against real storage.

## Tables touched (all pre-existing)

### `asset` (the hierarchy columns)

| Field | Role in this phase |
| :--- | :--- |
| `id` | Node identity. |
| `parent_asset` → `asset` | **The relationship.** `null` = a root. Written on attach/detach. |
| `root_asset` → `asset` | Topmost ancestor (self if root). Recomputed on every move, for the node **and all descendants**. |
| `depth_from_root` | Distance from root (0 at root). Recomputed for the node and all descendants. |
| `domain` → `domain` | Read for display only. **Not** a gating field — cross-domain attach is allowed (OQ2 resolved). |
| `asset_class` → `asset_class` | Read for display only. Cross-class attach is allowed. |

Self-referential FK: `parent_asset` and `root_asset` both point back into `asset`
(`on_delete=SET_NULL`). Children are reachable via the reverse relation `children`;
descendants of a tree via `descendants` (reverse of `root_asset`).

### `asset_parent_history` (structured audit — written, never mutated)

Already exists. One row per relationship change:

| Field | Source |
| :--- | :--- |
| `asset` → `asset` | The child being moved. |
| `previous_parent_asset` / `new_parent_asset` | Before/after parent. |
| `previous_root_asset` / `new_root_asset` | Before/after root. |
| `previous_depth` / `new_depth` | Before/after depth. |
| audit columns | `created_by` = actor. |

### `asset_event` (the dual link — written)

Already exists, **already has `role`**. Per relationship change, **two** rows linking one
`Event` to the two assets:

| Field | Value (attach) |
| :--- | :--- |
| `asset` → `asset` | parent *N*, then child *C* |
| `event` → `event` | the single emitted Event |
| `role` | `"parent"` on N's row, `"child"` on C's row |

Unique constraint `(asset, event)` already prevents a duplicate link.

### `event` (the timeline entry — written)

Already exists. One `Event` per change, `event_type = ASSET_MANAGEMENT`,
`status = COMPLETE`, `domain` = the child's domain, title/description from
`AssetEventNarrator`.

## What is explicitly NOT modeled here

- No new "relationship" or "membership" table — the `parent_asset` pointer **is** the
  relationship ([D4](../decisions.md)).
- No new event↔asset link table — `asset_event.role` already carries the parent/child
  distinction ([D3](../decisions.md)).
- Audit columns (`created_at`, etc.) are assumed present everywhere per project convention
  and are not re-listed.

## Integrity rules enforced in the control layer (not the DB)

- **Acyclic**: a node may never be attached under itself or any descendant.
- **Root/depth coherence**: for every node, `depth_from_root` = distance to `root_asset`
  along `parent_asset` pointers; maintained transactionally on every move incl. descendants.
- **Root of a root**: a node with `parent_asset = null` has `root_asset = self`, `depth = 0`.
