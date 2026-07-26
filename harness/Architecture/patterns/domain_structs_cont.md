---
type: Architecture Guide
title: Domain Structs — Extended Patterns and Examples
description: Concrete construction, composition, and naming conventions for control_layer/domain_structs, with real examples from the codebase.
tags: [architecture, control-layer, domain-structs, examples]
---

# Domain structs — extended patterns and examples

This continues [../overview.md](../overview.md#domain-structs-pattern) and the **Struct** entry in [oop_control_patterns.md](oop_control_patterns.md). Read those first for the one-line rules; this document shows what they look like in real code.

## 1. Two tiers of struct

Not every struct is a full aggregate. In practice there are two tiers, and both are legitimate:

| Tier | Purpose | Example |
| :--- | :--- | :--- |
| **Base / identity struct** | Guarantees one row exists, loads its immediate FK neighbors via `select_related`. The seed other structs compose. | `AssetStruct`, `PartStruct`, `SupplierItemStruct` |
| **Aggregate / composite struct** | Clusters rows across relationships or **composes multiple structs** into one read model for a screen. | `AssetConfigurationStruct`, `AssetHierarchyStruct`, `AssetThreeSixtyStruct`, `EventDetailStruct` |

The "never touch only a single table" rule in the overview targets **aggregate** structs — a struct whose whole job is `Model.objects.filter(...)` with nothing composed or clustered around it isn't earning its place; that belongs in `presentation_layer/search/` as a plain queryset function instead.

A **base struct** loading one row plus its direct foreign keys is fine and expected — it exists to guarantee existence and give aggregate structs (and Contexts) a stable thing to compose from, not to stand alone as "the point" of a feature. If a base struct never gets composed into anything and never gains slices, it was probably just a search function wearing a struct's clothes — reconsider it.

```python
# app/assets/control_layer/domain_structs/asset_struct.py
class AssetStruct:
    def __init__(self, asset_id: int, *, eager: bool = False) -> None:
        self.asset_id = asset_id
        qs = Asset.objects.all()
        if eager:
            qs = qs.select_related("model", "asset_class", "domain", "parent_asset", "root_asset")
        try:
            self.asset: Asset = qs.get(id=asset_id)
        except Asset.DoesNotExist as exc:
            raise AssetNotFoundError(f"Asset {asset_id} not found.") from exc

    @classmethod
    def from_instance(cls, asset: Asset) -> "AssetStruct":
        struct = cls.__new__(cls)
        struct.asset_id = asset.id
        struct.asset = asset
        return struct

    def to_dict(self) -> dict: ...
```

## 2. Construction conventions

Every struct should support being built two ways: **by id** (issues queries) and **from an already-loaded instance** (issues none). This is what lets an aggregate struct compose slices without N+1-ing itself.

| Constructor | When to use | Query cost |
| :--- | :--- | :--- |
| `__init__(id, *, eager=False)` or `.from_id(id)` | Caller only has an id (typical entrypoint case). | 1+ queries |
| `.from_instance(model_obj)` / `.from_asset(asset)` | Caller (often another struct) already loaded the row. | 0 queries |
| `.from_components(*rows)` | Aggregate struct assembling from rows fetched elsewhere (bulk views, prefetch pipelines). | 0 queries |

`from_id` should return `None` (or the struct's own `*NotFoundError`) rather than raising `Model.DoesNotExist` — callers should never need to know the ORM exception name for a struct's backing model.

```python
# app/assets/control_layer/domain_structs/asset_hierarchy_struct.py
@classmethod
def from_asset(cls, asset: Asset) -> "AssetHierarchyStruct": ...

@classmethod
def from_id(cls, asset_id: int) -> "AssetHierarchyStruct | None":
    asset = Asset.objects.select_related("parent_asset", "root_asset").filter(id=asset_id).first()
    if asset is None:
        return None
    return cls.from_asset(asset)
```

`eager` is a keyword-only flag on base structs, not a separate method — it toggles whether `select_related` runs, not what gets returned.

## 3. Composition — building an aggregate from smaller structs

An aggregate struct's `__init__` takes already-built slice structs; a `from_*` classmethod does the actual fetching and wires them together. This keeps the aggregate cheap to reconstruct in tests (pass in fakes) while still offering a one-call convenience path for real callers.

```python
# app/assets/control_layer/domain_structs/asset_three_sixty_struct.py
class AssetThreeSixtyStruct:
    def __init__(self, base, capabilities, configuration, hierarchy, timeline) -> None:
        self.base = base
        self.capabilities = capabilities
        self.configuration = configuration
        self.hierarchy = hierarchy
        self.timeline = timeline

    @classmethod
    def from_asset(cls, asset: "Asset", *, timeline_limit=TIMELINE_LIMIT) -> "AssetThreeSixtyStruct":
        return cls(
            base=AssetStruct.from_instance(asset),
            capabilities=AssetCapabilityStruct.from_asset(asset),
            configuration=AssetConfigurationStruct.from_asset(asset),
            hierarchy=AssetHierarchyStruct.from_asset(asset),
            timeline=AssetTimelineStruct.from_asset(asset, timeline_limit=timeline_limit),
        )

    @classmethod
    def from_id(cls, asset_id: int, *, eager=True, timeline_limit=TIMELINE_LIMIT) -> "AssetThreeSixtyStruct":
        base = AssetStruct(asset_id, eager=eager)  # guarantees existence
        return cls.from_asset(base.asset, timeline_limit=timeline_limit)
```

Each slice (`AssetCapabilityStruct`, `AssetConfigurationStruct`, ...) stays independently usable — a partial page or an HTMX fragment can build just the one slice it needs instead of paying for the whole 360 view.

**One-way dependencies stay one-way even inside a struct.** `AssetThreeSixtyStruct` deliberately does **not** import anything from `detail_extensions` — the assets app must not know that app exists. The 360 template pulls extension cards separately over an HTMX panel URL. If composing a foreign slice would violate the dependency direction in [../overview.md](../overview.md#layer-responsibilities), leave that slice out of the struct and let the template fetch it independently.

## 4. Metrics and derived-data methods

Aggregate structs are allowed **query-free, pure computation** methods over data they already loaded — expected-vs-actual counts, progress percentages, diffs. These are not "business logic on models" (which is banned); they're read-side shaping, same as `to_dict()`, just broken into named methods instead of one blob.

```python
# app/assets/control_layer/domain_structs/asset_configuration_struct.py
def get_modification_progress(self) -> dict:
    """Expected vs documented modification counts."""
    expected_ids = {m.defined_modification_id for m in self.template_struct.modifications} if self.template_struct else set()
    documented_ids = {am.defined_modification_id for am in self.actual_modifications}
    matched = len(documented_ids & expected_ids)
    return {"documented": len(self.actual_modifications), "expected": len(expected_ids), "matched": matched}
```

Rule of thumb: if a method needs a new query, it doesn't belong here — put the query in the `from_*` constructor (or a sibling struct) and hand the method already-loaded data.

## 5. Tree / graph walks stay in the struct, not the template or view

`AssetHierarchyStruct` walks ancestor chains and BFS-collects descendants entirely in Python from one indexed queryset (scoped by `root_asset_id`), rather than issuing a query per level. When a screen needs a recursive or graph-shaped read (breadcrumbs, subtrees, threaded comments), do the walk once inside the struct's constructor and expose the result as plain lists/properties (`.ancestors`, `.children`, `.is_leaf`, `.depth`) — never make the template or entrypoint re-derive tree structure from a flat queryset.

## 6. `to_dict()` conventions

- Always JSON-serializable (call `.isoformat()` on datetimes, stringify UUIDs, resolve FK names instead of leaking bare ids where the template needs a label).
- Nest child structs' own `to_dict()` rather than re-flattening their fields — `AssetThreeSixtyStruct.to_dict()` just calls `self.capabilities.to_dict()`, `self.configuration.to_dict()`, etc.
- Omit slices that belong to another app instead of returning `None` for them silently — leave a comment stating *why* it's absent (see the extensions example above), so the omission reads as deliberate, not forgotten.

## 7. Where structs are consumed

- **`presentation_layer/search/`** and **control-layer write modules** are the preferred places to *construct* structs (per the overview's dependency rule — `domain_structs/` itself should stay import-light and not depend on `search/`).
- **`Context`** classes (see [oop_control_patterns.md](oop_control_patterns.md#context)) hold a struct as their source of truth and delegate mutations elsewhere:

```python
# app/parts/control_layer/part_context.py
class PartContext:
    def __init__(self, part_id: int, actor=None, *, eager: bool = False) -> None:
        self.actor = actor
        self.part_struct = PartStruct(part_id, eager=eager)
        self.part = self.part_struct.part

    def supplier_items(self) -> list:
        """Read-only forward lookup — the Part never depends on supplier items."""
        items = SupplierItem.objects.filter(internal_part=self.part, is_active=True)
        return [SupplierItemStruct.from_instance(item) for item in items]
```

Note `PartContext` does not subclass or wrap the struct — it *holds* one (`self.part_struct`) and exposes convenience accessors. Contexts orchestrate; structs carry data.

## 8. Checklist for a new struct

1. Does this cluster **more than one table's worth of related data**, or compose **existing structs**? If it's a bare filtered list from one table, it's a search function, not a struct.
2. Constructor takes an id and guarantees the row exists (raise a dedicated `*NotFoundError`, not a bare `DoesNotExist`).
3. Add `from_instance` (or `from_<parent>`) so composing structs can build this one for free when they already hold the row.
4. Keep `eager` as a keyword-only flag on the id-based constructor, not a second method.
5. `to_dict()` returns something template-safe and JSON-serializable.
6. Query-free derived-data methods (`get_*`, `is_*` properties) are fine; anything needing a new query belongs in a constructor.
7. Respect app boundaries — never import a struct from an app this app shouldn't know about (see §3); let the template fetch that slice independently instead.
