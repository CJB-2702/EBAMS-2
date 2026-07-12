from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.parts.models import Part, SupplierItem


class SupplierItemNarrator:
    @staticmethod
    def item_mapped(item: "SupplierItem", part: "Part") -> str:
        return f"Supplier item {item.manufacturer_part_number} mapped to {part.part_number}"
