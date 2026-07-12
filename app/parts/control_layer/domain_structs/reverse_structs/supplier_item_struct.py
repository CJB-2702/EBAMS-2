from __future__ import annotations

from app.parts.models import SupplierItem


class SupplierItemNotFoundError(Exception):
    pass


class SupplierItemStruct:
    def __init__(self, item_id: int) -> None:
        self.item_id = item_id
        try:
            self.item: SupplierItem = SupplierItem.objects.select_related(
                "part_manufacturer", "internal_part"
            ).get(id=item_id)
        except SupplierItem.DoesNotExist as exc:
            raise SupplierItemNotFoundError(f"SupplierItem {item_id} not found.") from exc

    @classmethod
    def from_instance(cls, item: SupplierItem) -> "SupplierItemStruct":
        struct = cls.__new__(cls)
        struct.item_id = item.id
        struct.item = item
        return struct

    def to_dict(self) -> dict:
        i = self.item
        return {
            "id": i.id,
            "mpn": i.manufacturer_part_number,
            "name": i.name,
            "description": i.description,
            "is_active": i.is_active,
            "manufacturer": {
                "id": i.part_manufacturer_id,
                "name": i.part_manufacturer.name,
            },
            "internal_part": {
                "id": i.internal_part_id,
                "part_number": i.internal_part.part_number,
            },
            "compatibility_range": {
                "min_major": i.min_major_revision_number,
                "min_minor": i.min_minor_revision_number,
                "max_major": i.max_major_revision_number,
                "max_minor": i.max_minor_revision_number,
            },
        }
