"""AssetHierarchyManager — parent/root/depth sub-area of AssetContext.

Reparents an asset: recomputes root + depth, guards against cycles, and records
an AssetParentHistory row. One transaction.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.assets.models import Asset, AssetParentHistory

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class HierarchyError(Exception):
    pass


class AssetHierarchyManager:
    def __init__(self, asset: "Asset", actor: "AbstractUser") -> None:
        self.asset = asset
        self.actor = actor

    def reparent(self, new_parent_id: int | None) -> None:
        asset = self.asset

        if new_parent_id == asset.id:
            raise HierarchyError("An asset cannot be its own parent.")

        new_parent = None
        if new_parent_id is not None:
            new_parent = Asset.objects.get(id=new_parent_id)
            if self._would_cycle(new_parent):
                raise HierarchyError(
                    "Reparenting would create a cycle in the asset hierarchy."
                )

        if new_parent is None:
            new_root_id = asset.id
            new_depth = 0
        else:
            new_root_id = new_parent.root_asset_id or new_parent.id
            new_depth = (new_parent.depth_from_root or 0) + 1

        with transaction.atomic():
            AssetParentHistory.objects.create(
                asset=asset,
                previous_parent_asset_id=asset.parent_asset_id,
                new_parent_asset_id=new_parent_id,
                previous_root_asset_id=asset.root_asset_id,
                new_root_asset_id=new_root_id,
                previous_depth=asset.depth_from_root,
                new_depth=new_depth,
                created_by=self.actor,
                updated_by=self.actor,
            )
            asset.parent_asset_id = new_parent_id
            asset.root_asset_id = new_root_id
            asset.depth_from_root = new_depth
            asset.updated_by = self.actor
            asset.save(
                update_fields=[
                    "parent_asset", "root_asset", "depth_from_root",
                    "updated_by", "updated_at",
                ]
            )

    def _would_cycle(self, candidate_parent: Asset) -> bool:
        """True if ``self.asset`` is an ancestor of ``candidate_parent``."""
        node = candidate_parent
        seen: set[int] = set()
        while node is not None:
            if node.id == self.asset.id:
                return True
            if node.id in seen:
                break
            seen.add(node.id)
            node = node.parent_asset
        return False
