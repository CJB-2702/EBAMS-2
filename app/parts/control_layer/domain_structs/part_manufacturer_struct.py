from __future__ import annotations

from app.parts.models import PartManufacturer


class PartManufacturerNotFoundError(Exception):
    pass


class PartManufacturerStruct:
    def __init__(self, manufacturer_id: int) -> None:
        self.manufacturer_id = manufacturer_id
        try:
            self.manufacturer: PartManufacturer = PartManufacturer.objects.get(
                id=manufacturer_id
            )
        except PartManufacturer.DoesNotExist as exc:
            raise PartManufacturerNotFoundError(
                f"PartManufacturer {manufacturer_id} not found."
            ) from exc

    @classmethod
    def from_instance(cls, manufacturer: PartManufacturer) -> "PartManufacturerStruct":
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
