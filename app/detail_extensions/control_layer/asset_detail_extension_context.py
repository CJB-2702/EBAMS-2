"""AssetDetailExtensionContext — entry point for an asset's extensions.

Replaces the old ``AssetContext.plugins`` accessor (P2): extension read/CRUD now
lives in ``detail_extensions``, so the assets app stays ignorant of extensions. Hosts
``AssetExtensionsManager`` as its ``.extensions`` collaborator — callers use verbs
(``list`` / ``get`` / ``add`` / ``update`` / ``remove``), never raw ORM.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.detail_extensions.control_layer.managers.asset_extensions_manager import (
    AssetExtensionsManager,
)

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from app.assets.models import Asset


class AssetDetailExtensionContext:
    def __init__(self, asset_id: int, actor: "AbstractUser") -> None:
        from app.assets.models import Asset

        self.actor = actor
        self.asset: "Asset" = Asset.objects.get(id=asset_id)

    @classmethod
    def from_instance(
        cls, asset: "Asset", actor: "AbstractUser"
    ) -> "AssetDetailExtensionContext":
        ctx = cls.__new__(cls)
        ctx.actor = actor
        ctx.asset = asset
        return ctx

    @property
    def extensions(self) -> AssetExtensionsManager:
        return AssetExtensionsManager(self.asset, self.actor)
