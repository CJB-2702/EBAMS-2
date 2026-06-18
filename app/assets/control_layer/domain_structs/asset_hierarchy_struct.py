"""AssetHierarchyStruct — read model for one asset's place in its tree.

Gathers the asset's ancestors (root → parent, top-down), its direct children,
and its full descendant subtree, plus the resolved root and depth. Read-only;
``to_dict()`` for rendering breadcrumbs and tree panels.

The mutating counterpart is ``AssetHierarchyManager`` (reparenting). This struct
never writes — it only reads the flat ``parent_asset`` / ``root_asset`` /
``depth_from_root`` columns and walks them into a usable shape.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.assets.models import Asset

if TYPE_CHECKING:
    pass


class AssetHierarchyStruct:
    """Read model for an asset's ancestors, children, and descendant subtree."""

    def __init__(
        self,
        asset: Asset,
        ancestors: list[Asset],
        children: list[Asset],
        descendants: list[Asset],
    ) -> None:
        self.asset = asset
        # Top-down: root first, immediate parent last. Empty for a root asset.
        self.ancestors = ancestors
        # Direct children only (one level down).
        self.children = children
        # Every asset beneath this one, any depth (BFS order).
        self.descendants = descendants

    @classmethod
    def from_asset(cls, asset: Asset) -> "AssetHierarchyStruct":
        ancestors = cls._walk_ancestors(asset)
        children = list(
            Asset.objects.filter(parent_asset_id=asset.id).order_by("name")
        )
        descendants = cls._collect_descendants(asset)
        return cls(
            asset=asset,
            ancestors=ancestors,
            children=children,
            descendants=descendants,
        )

    @classmethod
    def from_id(cls, asset_id: int) -> "AssetHierarchyStruct | None":
        asset = (
            Asset.objects.select_related("parent_asset", "root_asset")
            .filter(id=asset_id)
            .first()
        )
        if asset is None:
            return None
        return cls.from_asset(asset)

    # ── Tree walks (read-only) ───────────────────────────────────────────────

    @staticmethod
    def _walk_ancestors(asset: Asset) -> list[Asset]:
        """Walk parent pointers up to the root, returned root-first."""
        chain: list[Asset] = []
        seen: set[int] = {asset.id}
        node = asset.parent_asset
        while node is not None and node.id not in seen:
            chain.append(node)
            seen.add(node.id)
            node = node.parent_asset
        chain.reverse()  # root-first for breadcrumbs
        return chain

    @staticmethod
    def _collect_descendants(asset: Asset) -> list[Asset]:
        """Breadth-first gather of every asset beneath this one.

        Scoped to the asset's own tree (same ``root_asset``) so the walk stays a
        single indexed query, then expanded level by level in memory.
        """
        root_id = asset.root_asset_id or asset.id
        tree = list(
            Asset.objects.filter(root_asset_id=root_id)
            .exclude(id=asset.id)
            .order_by("depth_from_root", "name")
        )
        children_by_parent: dict[int, list[Asset]] = {}
        for node in tree:
            children_by_parent.setdefault(node.parent_asset_id, []).append(node)

        ordered: list[Asset] = []
        queue: list[int] = [asset.id]
        seen: set[int] = {asset.id}
        while queue:
            parent_id = queue.pop(0)
            for child in children_by_parent.get(parent_id, []):
                if child.id in seen:
                    continue
                seen.add(child.id)
                ordered.append(child)
                queue.append(child.id)
        return ordered

    # ── Convenience ──────────────────────────────────────────────────────────

    @property
    def root(self) -> Asset:
        """The tree root — the topmost ancestor, or the asset itself."""
        return self.ancestors[0] if self.ancestors else self.asset

    @property
    def is_root(self) -> bool:
        return not self.ancestors

    @property
    def is_leaf(self) -> bool:
        return not self.children

    @property
    def depth(self) -> int:
        return self.asset.depth_from_root or 0

    # ── Serialization ────────────────────────────────────────────────────────

    @staticmethod
    def _node(asset: Asset) -> dict:
        return {
            "id": asset.id,
            "name": asset.name,
            "serial_number": asset.serial_number,
            "depth_from_root": asset.depth_from_root,
            "parent_asset_id": asset.parent_asset_id,
        }

    def to_dict(self) -> dict:
        return {
            "asset_id": self.asset.id,
            "depth": self.depth,
            "is_root": self.is_root,
            "is_leaf": self.is_leaf,
            "root": self._node(self.root),
            "ancestors": [self._node(a) for a in self.ancestors],
            "children": [self._node(c) for c in self.children],
            "descendants": [self._node(d) for d in self.descendants],
            "child_count": len(self.children),
            "descendant_count": len(self.descendants),
        }
