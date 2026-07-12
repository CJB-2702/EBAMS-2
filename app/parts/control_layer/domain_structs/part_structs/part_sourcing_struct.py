"""PartSourcingStruct — how a Part is sourced, from one pass over SupplierItem.

Walks ``SupplierItem.objects.filter(internal_part=part)`` **once** and exposes
both ``.supplier_items()`` (full list) and ``.manufacturers()`` (deduped
``PartManufacturer``s with their items grouped) from that single query — rather
than two structs querying SupplierItem twice. Supplier-item rows are eager;
``eager_thread`` adds per-item documents/comments; the manufacturer rollup is a
lazy derivation with no consumer yet (struct plan §3).
"""

from __future__ import annotations

from app.parts.control_layer.domain_structs.reverse_structs.supplier_item_struct import (
    SupplierItemStruct,
)
from app.parts.models import SupplierItem


class PartSourcingStruct:
    def __init__(self, part_id: int, *, eager_thread: bool = False) -> None:
        self.part_id = part_id
        self.eager_thread = eager_thread
        self.items: list[SupplierItem] = list(
            SupplierItem.objects.filter(internal_part_id=part_id, is_active=True)
            .select_related("part_manufacturer", "internal_part", "thread")
            .order_by("part_manufacturer__name", "manufacturer_part_number")
        )

    @classmethod
    def from_id(cls, part_id: int, *, eager_thread: bool = False) -> "PartSourcingStruct":
        return cls(part_id, eager_thread=eager_thread)

    def supplier_items(self) -> list[dict]:
        return [self._item_dict(item) for item in self.items]

    def manufacturers(self) -> list[dict]:
        """Deduped manufacturers derived from the same single query pass, each
        with its supplier items grouped. Lazy — no template consumes this yet."""
        grouped: dict[int, dict] = {}
        for item in self.items:
            entry = grouped.setdefault(
                item.part_manufacturer_id,
                {
                    "id": item.part_manufacturer_id,
                    "name": item.part_manufacturer.name,
                    "items": [],
                },
            )
            entry["items"].append(
                {"id": item.id, "mpn": item.manufacturer_part_number}
            )
        return list(grouped.values())

    def to_dict(self) -> dict:
        return {
            "supplier_items": self.supplier_items(),
            "manufacturers": self.manufacturers(),
        }

    def _item_dict(self, item: SupplierItem) -> dict:
        data = SupplierItemStruct.from_instance(item).to_dict()
        if self.eager_thread:
            from app.parts.control_layer.managers.part_thread_manager import (
                PartThreadManager,
            )

            docs = PartThreadManager(item).documents()
            data["image_documents"] = [d for d in docs if d["is_image"]]
            data["other_documents"] = [d for d in docs if not d["is_image"]]
            data["comments"] = PartThreadManager(item).comments()
        return data
