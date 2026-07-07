"""ManufacturerStruct — aggregated read model for a single Manufacturer.

Eager mode prefetches the models this manufacturer produces (and their classes)
so a detail screen renders from one coherent object graph.
"""

from __future__ import annotations

from app.assets.models import Manufacturer


class ManufacturerNotFoundError(Exception):
    pass


class ManufacturerStruct:
    def __init__(self, manufacturer_id: int, *, eager: bool = False) -> None:
        self.manufacturer_id = manufacturer_id
        qs = Manufacturer.objects.all()
        if eager:
            qs = qs.prefetch_related("models__asset_class")
        try:
            self.manufacturer: Manufacturer = qs.get(id=manufacturer_id)
        except Manufacturer.DoesNotExist as exc:
            raise ManufacturerNotFoundError(
                f"Manufacturer {manufacturer_id} not found."
            ) from exc

    @classmethod
    def from_instance(cls, manufacturer: Manufacturer) -> "ManufacturerStruct":
        struct = cls.__new__(cls)
        struct.manufacturer_id = manufacturer.id
        struct.manufacturer = manufacturer
        return struct

    def to_dict(self) -> dict:
        m = self.manufacturer
        return {
            "id": m.id,
            "name": m.name,
            "code": m.code,
            "website": m.website,
            "is_active": m.is_active,
        }
