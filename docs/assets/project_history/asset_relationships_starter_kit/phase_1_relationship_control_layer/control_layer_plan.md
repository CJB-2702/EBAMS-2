# Phase 1 — Control Layer Plan

Builds the relationship write path and the tree read model. Suffix vocabulary per
[`OOP_CONTROL_PATTERNS`](../../harness/Architecture/OOP_CONTROL_PATTERNS.md). Reuses the existing
`AssetEvent` emit pattern and `AssetEventNarrator`.

Home: `app/assets/control_layer/`.

---

## `AssetTreeStruct` — nested tree read model

`domain_structs/asset_tree_struct.py`. Read-only. Builds a genuinely nested tree rooted at a
given asset, bounded by `max_depth`, in one batched query over the asset's `root_asset`
subtree (no per-node N+1). Distinct from `AssetHierarchyStruct`, which stays for
ancestors/breadcrumbs.

```
AssetTreeStruct(root_asset, nodes_by_parent, max_depth)
  .from_id(asset_id: int, *, max_depth: int = 2) -> "AssetTreeStruct | None"
  .from_asset(asset: Asset, *, max_depth: int = 2) -> "AssetTreeStruct"
  .to_dict() -> dict          # nested: {asset, depth, child_count, children:[...]}
  .level(depth: int) -> list  # the assets exactly `depth` below the root (HTMX next-ring)
  .has_more(node) -> bool     # node has children beyond the materialized max_depth
```

- A node dict carries `id`, `name`, `serial_number`, `asset_class`, `depth_from_root`,
  `child_count` (direct), and `children` (present up to `max_depth`; empty + `has_more=True`
  beyond it so the UI knows to offer "expand").
- `level(depth)` powers the HTMX depth-on-click request: the page asks for the next ring
  under a specific node without rebuilding the whole tree.
- Built from a single `Asset.objects.filter(root_asset_id=...)` fetch, grouped into a
  `parent_id → [children]` map, then walked to `max_depth`.

---

## `RelationshipPolicy` — "may C be a child of N?"

`guards/relationship_guard.py`. DB-light decision, no writes. Single source of truth for what
a legal attach is, so the manager and any future bulk importer agree.

```
RelationshipPolicy.check_attach(child: Asset, new_parent: Asset | None) -> None  # raises on violation
```

Rules:
- `new_parent is None` → always legal (detach to root).
- `child == new_parent` → reject (self-parent).
- `child` is an ancestor of `new_parent` → reject (cycle). Walk `new_parent.parent_asset`
  up; if `child` appears, reject.
- **No domain or class restriction** (OQ2 → resolved: allow cross-domain *and* cross-class).
  An asset from any domain/class may be attached under any other. The policy is purely
  structural: self-parent and cycles are the only rejections.
- **Already-parented child is allowed** (OQ3 → resolved): if `child.parent_asset` is already
  set, attaching it under `new_parent` is a **move**. The `AssetParentHistory` row and Event
  capture the prior parent; the child's whole subtree travels with it ([D5](../decisions.md)).

The cycle walk replaces the inline `_would_cycle` currently living in `AssetHierarchyManager`.

---

## `AssetRelationshipManager` — the write path

`managers/asset_relationship_manager.py`. Constructed for the asset whose children are being
edited (`parent_asset`), the way the Phase 2 edit page thinks. Absorbs the move logic from
`AssetHierarchyManager` ([D1](../decisions.md), [D8](../decisions.md)).

```
AssetRelationshipManager(parent: Asset, actor)
  .attach_child(child_id: int) -> None
  .detach_child(child_id: int) -> None
```

> **No batch verb** (DR4). Relationships are managed one at a time. Each call is already
> atomic (guard → move → cascade → history → event in one transaction).

### `attach_child(child_id)` delegation flow

1. Load `child = Asset.objects.get(id=child_id)`.
2. `RelationshipPolicy.check_attach(child, self.parent)` — raises on cycle/self/domain.
3. Compute `new_root_id = self.parent.root_asset_id or self.parent.id`,
   `new_depth = (self.parent.depth_from_root or 0) + 1`.
4. **In one `transaction.atomic()`:**
   a. Write `AssetParentHistory` (previous/new parent, root, depth) for `child`.
   b. Update `child`: `parent_asset = self.parent`, `root_asset_id = new_root_id`,
      `depth_from_root = new_depth`, `updated_by = actor`.
   c. **Cascade** (`_recompute_subtree(child)`): walk `child`'s descendants (BFS over
      `parent_asset` within the old subtree), set each descendant's
      `root_asset_id = new_root_id` and `depth_from_root = parent_depth + 1`. Bulk-update.
   d. Emit the Event (below).

### `detach_child(child_id)` flow

Same shape with `new_parent = None` → `new_root_id = child.id`, `new_depth = 0`; cascade
re-roots the subtree onto `child`. Emits `child_detached`.

### Eventing (`_emit_relationship_event`)

Mirrors `CapabilityManager._emit_event`, but links **two** assets:

```
title, description = AssetEventNarrator.child_attached(parent, child)   # or child_detached
event = Event.objects.create(
    domain_id=child.domain_id, title=..., description=...,
    event_type=EventType.ASSET_MANAGEMENT, status=EventStatus.COMPLETE,
    created_by=actor, updated_by=actor,
)
AssetEvent.objects.create(asset=parent, event=event, role="parent", ...)
AssetEvent.objects.create(asset=child,  event=event, role="child",  ...)
```

### New `AssetEventNarrator` methods

```
child_attached(parent, child) -> (title, description)
   title = f"Asset Attached: {child.name} → {parent.name}"
child_detached(parent, child) -> (title, description)
   title = f"Asset Detached: {child.name} from {parent.name}"
```

---

## `AssetContext` wiring

`asset_context.py`:

- Add `@property relationships` → `AssetRelationshipManager(self.asset, self.actor)`.
- Add `tree(max_depth=2)` → `AssetTreeStruct.from_asset(self.asset, max_depth=max_depth)`.
- Keep `reparent(new_parent_id)` as a thin passthrough — but route it through the new manager
  (`attach_child`/`detach_child`) so there is **one** write path ([D8](../decisions.md)). The
  old `AssetHierarchyManager.reparent` body is removed/forwarded; its cycle logic moves to
  `RelationshipPolicy`.

---

## Delegation summary

```
Phase 2 edit page ─▶ AssetContext(parent).relationships.attach_child(child_id)
                       └▶ RelationshipPolicy.check_attach()        (guard)
                       └▶ transaction:
                            AssetParentHistory.create()            (audit row)
                            child.save(parent/root/depth)          (the move)
                            _recompute_subtree(child)              (cascade — D5)
                            Event.create() + 2× AssetEvent.create()(dual-linked timeline — D3)

Phase 2 view page ─▶ AssetContext(n).tree(max_depth=2).to_dict()   (render)
HTMX expand       ─▶ AssetTreeStruct.from_id(node_id, max_depth=1).level(1)
```
