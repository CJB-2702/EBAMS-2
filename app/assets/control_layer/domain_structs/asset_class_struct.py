"""AssetClassStruct — aggregated read model for a single AssetClass.

Eager mode prefetches the domain links and the declared capability links (with
their definitions) so a detail screen renders from one object graph.
"""

from __future__ import annotations

from app.assets.models import AssetClass


class AssetClassNotFoundError(Exception):
    pass


class AssetClassStruct:
    def __init__(self, class_id: int, *, eager: bool = False) -> None:
        self.class_id = class_id
        qs = AssetClass.objects.all()
        if eager:
            qs = qs.prefetch_related(
                "domains",
                "capability_links__capability_definition",
            )
        try:
            self.asset_class: AssetClass = qs.get(id=class_id)
        except AssetClass.DoesNotExist as exc:
            raise AssetClassNotFoundError(f"AssetClass {class_id} not found.") from exc

    @classmethod
    def from_instance(cls, asset_class: AssetClass) -> "AssetClassStruct":
        struct = cls.__new__(cls)
        struct.class_id = asset_class.id
        struct.asset_class = asset_class
        return struct

    def to_dict(self) -> dict:
        c = self.asset_class
        return {
            "id": c.id,
            "name": c.name,
            "category": c.category,
            "description": c.description,
            "is_active": c.is_active,
            "restrict_to_domain_set": c.restrict_to_domain_set,
        }
