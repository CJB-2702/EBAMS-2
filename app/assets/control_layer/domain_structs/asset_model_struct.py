"""AssetModelStruct — aggregated read model for a single AssetModel."""

from __future__ import annotations

from app.assets.models import AssetModel


class AssetModelNotFoundError(Exception):
    pass


class AssetModelStruct:
    def __init__(self, model_id: int, *, eager: bool = False) -> None:
        self.model_id = model_id
        qs = AssetModel.objects.all()
        if eager:
            qs = qs.select_related("asset_class", "base_model").prefetch_related(
                "manufacturer_links__manufacturer", "domains"
            )
        try:
            self.model: AssetModel = qs.get(id=model_id)
        except AssetModel.DoesNotExist as exc:
            raise AssetModelNotFoundError(f"AssetModel {model_id} not found.") from exc

    @classmethod
    def from_instance(cls, model: AssetModel) -> "AssetModelStruct":
        struct = cls.__new__(cls)
        struct.model_id = model.id
        struct.model = model
        return struct

    def to_dict(self) -> dict:
        m = self.model
        return {
            "id": m.id,
            "model_name": m.model_name,
            "subtype_name": m.subtype_name,
            "revision": m.revision,
            "is_base_model": m.is_base_model,
            "base_model_id": m.base_model_id,
            "asset_class_id": m.asset_class_id,
            "is_active": m.is_active,
        }
