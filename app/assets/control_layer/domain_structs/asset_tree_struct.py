"""AssetTreeStruct — nested parent→child tree read model.

Builds a genuinely nested tree rooted at one asset, bounded by ``max_depth``, for
the relationship view/edit screens. Distinct from ``AssetHierarchyStruct`` (which
reads ancestors/breadcrumbs and a flat descendant list); this struct expresses the
parent→child nesting and supports lazy depth expansion.

Read-only. The tree is built by walking ``parent_asset`` level by level (not by
trusting ``root_asset``/``depth_from_root``, which may be unset on never-parented
assets), so it is robust to stale or null denormalized columns. One query per
materialized level plus one count query for the deepest ring — bounded by
``max_depth``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.assets.models import Asset

if TYPE_CHECKING:
    pass


class AssetTreeNode:
    """One asset in the tree, with its materialized children and direct-child count."""

    def __init__(self, asset: Asset, depth: int, child_count: int = 0) -> None:
        self.asset = asset
        # Depth relative to the struct's root (0 = the root asset).
        self.depth = depth
        # Total number of DIRECT children, regardless of whether they were
        # materialized — drives the "expand" affordance.
        self.child_count = child_count
        # Materialized direct children (present up to max_depth).
        self.children: list[AssetTreeNode] = []

    @property
    def has_more(self) -> bool:
        """True when the node has children that were not materialized."""
        return self.child_count > 0 and not self.children

    @property
    def is_leaf(self) -> bool:
        return self.child_count == 0

    def to_dict(self) -> dict:
        return {
            "id": self.asset.id,
            "name": self.asset.name,
            "serial_number": self.asset.serial_number,
            "asset_class": self.asset.asset_class.name if self.asset.asset_class_id else None,
            "depth": self.depth,
            "child_count": self.child_count,
            "has_more": self.has_more,
            "children": [c.to_dict() for c in self.children],
        }


class AssetTreeStruct:
    """Nested subtree rooted at one asset, materialized to ``max_depth``."""

    def __init__(self, root: AssetTreeNode, max_depth: int) -> None:
        self.root = root
        self.max_depth = max_depth

    @classmethod
    def from_id(cls, asset_id: int, *, max_depth: int = 2) -> "AssetTreeStruct | None":
        asset = (
            Asset.objects.select_related("asset_class")
            .filter(id=asset_id)
            .first()
        )
        if asset is None:
            return None
        return cls.from_asset(asset, max_depth=max_depth)

    @classmethod
    def from_asset(cls, asset: Asset, *, max_depth: int = 2) -> "AssetTreeStruct":
        root = AssetTreeNode(asset, depth=0)
        frontier = [root]
        depth = 0
        while depth < max_depth and frontier:
            parent_ids = [n.asset.id for n in frontier]
            children = list(
                Asset.objects.select_related("asset_class")
                .filter(parent_asset_id__in=parent_ids)
                .order_by("name")
            )
            by_parent: dict[int, list[Asset]] = {}
            for c in children:
                by_parent.setdefault(c.parent_asset_id, []).append(c)

            next_frontier: list[AssetTreeNode] = []
            for node in frontier:
                kids = by_parent.get(node.asset.id, [])
                node.child_count = len(kids)
                for c in kids:
                    child_node = AssetTreeNode(c, depth=node.depth + 1)
                    node.children.append(child_node)
                    next_frontier.append(child_node)
            frontier = next_frontier
            depth += 1

        # The deepest materialized ring still needs accurate direct-child counts so
        # the UI knows whether to offer "expand". One grouped count query.
        if frontier:
            leaf_ids = [n.asset.id for n in frontier]
            counts: dict[int, int] = {}
            for parent_id in (
                Asset.objects.filter(parent_asset_id__in=leaf_ids)
                .values_list("parent_asset_id", flat=True)
            ):
                counts[parent_id] = counts.get(parent_id, 0) + 1
            for node in frontier:
                node.child_count = counts.get(node.asset.id, 0)

        return cls(root, max_depth)

    # ── Convenience ──────────────────────────────────────────────────────────
    def level(self, depth: int) -> list[AssetTreeNode]:
        """All nodes exactly ``depth`` levels below the root. Used by the HTMX
        expand endpoint: ``from_id(node_id, max_depth=1).level(1)`` yields a node's
        direct children, each already carrying its own ``child_count``/``has_more``."""
        out: list[AssetTreeNode] = []

        def walk(node: AssetTreeNode) -> None:
            if node.depth == depth:
                out.append(node)
                return
            for child in node.children:
                walk(child)

        walk(self.root)
        return out

    @property
    def children(self) -> list[AssetTreeNode]:
        return self.root.children

    def to_dict(self) -> dict:
        return self.root.to_dict()
