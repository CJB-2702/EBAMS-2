"""SupplierItemActivityStruct — reverse view from a SupplierItem up to its base Part.

Resolves *up* from a supplier item to its ``PartManufacturer`` and the base Part
it is mapped to, and gathers both the item's own thread and the base Part's
activity thread, so a write flow triggered on a supplier item can locate the
base Part and post to the single Part audit feed (§5).

Distinct from ``SupplierItemStruct`` (the *downward* single-item detail view).
"""

from __future__ import annotations

from app.parts.models import SupplierItem


class SupplierItemActivityNotFoundError(Exception):
    pass


class SupplierItemActivityStruct:
    def __init__(self, item_id: int) -> None:
        self.item_id = item_id
        try:
            self.item: SupplierItem = SupplierItem.objects.select_related(
                "part_manufacturer",
                "internal_part",
                "internal_part__documents_thread",
                "thread",
            ).get(id=item_id)
        except SupplierItem.DoesNotExist as exc:
            raise SupplierItemActivityNotFoundError(
                f"SupplierItem {item_id} not found."
            ) from exc

    @classmethod
    def from_instance(cls, item: SupplierItem) -> "SupplierItemActivityStruct":
        struct = cls.__new__(cls)
        struct.item_id = item.id
        struct.item = item
        return struct

    @property
    def part(self):
        """The base Part this item is mapped to — the machine-comment target."""
        return self.item.internal_part

    @property
    def part_manufacturer(self):
        return self.item.part_manufacturer

    def to_dict(self) -> dict:
        from app.events.control_layer.managers.activity_thread_manager import (
            ActivityThreadManager,
        )

        item = self.item
        part = self.item.internal_part
        return {
            "supplier_item": {
                "id": item.id,
                "mpn": item.manufacturer_part_number,
                "name": item.name,
            },
            "manufacturer": {
                "id": item.part_manufacturer_id,
                "name": item.part_manufacturer.name,
            },
            "part": {
                "id": part.id,
                "part_number": part.part_number,
                "name": part.name,
            },
            "supplier_item_thread": {
                "documents": ActivityThreadManager(item).documents(),
                "comments": ActivityThreadManager(item).comments(),
            },
            "part_thread": {
                "documents": ActivityThreadManager(
                    part, thread_attr="documents_thread"
                ).documents(),
                "comments": ActivityThreadManager(
                    part, thread_attr="documents_thread"
                ).comments(),
            },
        }
