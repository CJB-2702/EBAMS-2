"""Struct: aggregated read model for one ItemAllocation."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.inventory.models.intake.item_allocation import ItemAllocation


@dataclass(frozen=True)
class ItemAllocationStruct:
    allocation_id: int
    intake_session_id: int
    shipment_line_id: int | None
    part_id: int
    part_number: str
    quantity: Decimal
    serial_number: str
    composite_sn: str
    condition: str
    intake_method: str
    link_source: str
    linked_at: object
    raw_payload: str
    notes: str

    @classmethod
    def load(cls, *, allocation_id: int) -> "ItemAllocationStruct":
        allocation = ItemAllocation.objects.select_related("part").get(pk=allocation_id)
        return cls.from_model(allocation)

    @classmethod
    def from_model(cls, allocation: ItemAllocation) -> "ItemAllocationStruct":
        return cls(
            allocation_id=allocation.pk,
            intake_session_id=allocation.intake_session_id,
            shipment_line_id=allocation.shipment_line_id,
            part_id=allocation.part_id,
            part_number=allocation.part.part_number,
            quantity=allocation.quantity,
            serial_number=allocation.serial_number,
            composite_sn=allocation.composite_sn,
            condition=allocation.condition,
            intake_method=allocation.intake_method,
            link_source=allocation.link_source,
            linked_at=allocation.linked_at,
            raw_payload=allocation.raw_payload,
            notes=allocation.notes,
        )

    def to_dict(self) -> dict:
        return {
            "allocation_id": self.allocation_id,
            "intake_session_id": self.intake_session_id,
            "shipment_line_id": self.shipment_line_id,
            "part_id": self.part_id,
            "part_number": self.part_number,
            "quantity": self.quantity,
            "serial_number": self.serial_number,
            "composite_sn": self.composite_sn,
            "condition": self.condition,
            "intake_method": self.intake_method,
            "link_source": self.link_source,
            "linked_at": self.linked_at,
            "raw_payload": self.raw_payload,
            "notes": self.notes,
        }
