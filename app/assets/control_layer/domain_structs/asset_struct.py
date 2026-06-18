"""AssetStruct — aggregated read model for a single asset.

Guarantees the base row exists; ``eager=True`` loads the related slices a detail
screen needs (model, class, domain, threads, current meters, parent/root).
Read-only — no mutations.
"""

from __future__ import annotations

from app.assets.models import Asset


class AssetNotFoundError(Exception):
    pass


class AssetStruct:
    def __init__(self, asset_id: int, *, eager: bool = False) -> None:
        self.asset_id = asset_id
        qs = Asset.objects.all()
        if eager:
            qs = qs.select_related(
                "model", "asset_class", "domain",
                "photo_gallery", "documentation",
                "parent_asset", "root_asset",
            )
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

    def to_dict(self) -> dict:
        a = self.asset
        return {
            "id": a.id,
            "name": a.name,
            "serial_number": a.serial_number,
            "status": a.status,
            "is_active": a.is_active,
            "domain_id": a.domain_id,
            "model_id": a.model_id,
            "asset_class_id": a.asset_class_id,
            "parent_asset_id": a.parent_asset_id,
            "root_asset_id": a.root_asset_id,
            "depth_from_root": a.depth_from_root,
            "meters": [a.meter1, a.meter2, a.meter3, a.meter4],
        }
