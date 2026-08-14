"""Struct: one PO line's derived quantities.

Every value here was an @property on the legacy model, each issuing its own
query on access (D53). They live on the struct now, computed once from an
annotated queryset.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class PurchaseOrderLineStruct:
    line_id: int
    line_number: int
    part_id: int
    part_number: str
    part_name: str
    quantity_ordered: Decimal
    unit_cost: Decimal
    expected_delivery_date: object
    notes: str

    line_total: Decimal
    quantity_allocated_total: Decimal
    quantity_unallocated: Decimal
    active_allocation_count: int

    def to_dict(self) -> dict:
        return {
            "line_id": self.line_id,
            "line_number": self.line_number,
            "part_id": self.part_id,
            "part_number": self.part_number,
            "part_name": self.part_name,
            "quantity_ordered": self.quantity_ordered,
            "unit_cost": self.unit_cost,
            "expected_delivery_date": self.expected_delivery_date,
            "notes": self.notes,
            "line_total": self.line_total,
            "quantity_allocated_total": self.quantity_allocated_total,
            "quantity_unallocated": self.quantity_unallocated,
            "active_allocation_count": self.active_allocation_count,
        }
