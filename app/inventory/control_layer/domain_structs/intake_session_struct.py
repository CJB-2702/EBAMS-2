"""Struct: aggregated read model for one IntakeSession — metadata, linked
shipments, and its allocations, in the shapes the Auto Intake portal and
session-detail page both need."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.inventory.models.intake.intake_session import IntakeSession


@dataclass(frozen=True)
class IntakeSessionShipmentLinkStruct:
    shipment_id: int
    shipment_number: str
    shipment_status: str

    def to_dict(self) -> dict:
        return {
            "shipment_id": self.shipment_id,
            "shipment_number": self.shipment_number,
            "shipment_status": self.shipment_status,
        }


@dataclass(frozen=True)
class IntakeSessionStruct:
    intake_session_id: int
    operator_id: int
    operator_display: str
    warehouse_id: int
    warehouse_code: str
    room_id: int | None
    room_name: str
    status: str
    intake_method: str
    has_unlinked_allocations: bool
    started_at: object
    closed_at: object
    hardware_device_id: str
    notes: str
    shipments: tuple[IntakeSessionShipmentLinkStruct, ...] = field(default_factory=tuple)
    allocation_count: int = 0
    total_good_qty: Decimal = Decimal("0")
    total_rejected_qty: Decimal = Decimal("0")

    @classmethod
    def load(cls, *, intake_session_id: int) -> "IntakeSessionStruct":
        session = IntakeSession.objects.select_related(
            "operator", "warehouse", "room"
        ).get(pk=intake_session_id)
        return cls.from_model(session)

    @classmethod
    def from_model(cls, session: IntakeSession) -> "IntakeSessionStruct":
        links = list(
            session.shipment_associations.filter(deleted_at__isnull=True)
            .select_related("shipment")
        )
        allocations = list(session.allocations.filter(deleted_at__isnull=True))
        good_total = sum(
            (a.quantity for a in allocations if a.condition == "good"), Decimal("0")
        )
        rejected_total = sum(
            (a.quantity for a in allocations if a.condition == "rejected"), Decimal("0")
        )
        return cls(
            intake_session_id=session.pk,
            operator_id=session.operator_id,
            operator_display=str(session.operator),
            warehouse_id=session.warehouse_id,
            warehouse_code=session.warehouse.code,
            room_id=session.room_id,
            room_name=session.room.room_name if session.room_id else "",
            status=session.status,
            intake_method=session.intake_method,
            has_unlinked_allocations=session.has_unlinked_allocations,
            started_at=session.started_at,
            closed_at=session.closed_at,
            hardware_device_id=session.hardware_device_id,
            notes=session.notes,
            shipments=tuple(
                IntakeSessionShipmentLinkStruct(
                    shipment_id=link.shipment_id,
                    shipment_number=link.shipment.shipment_number,
                    shipment_status=link.shipment.status,
                )
                for link in links
            ),
            allocation_count=len(allocations),
            total_good_qty=good_total,
            total_rejected_qty=rejected_total,
        )

    def to_dict(self) -> dict:
        return {
            "intake_session_id": self.intake_session_id,
            "operator_id": self.operator_id,
            "operator_display": self.operator_display,
            "warehouse_id": self.warehouse_id,
            "warehouse_code": self.warehouse_code,
            "room_id": self.room_id,
            "room_name": self.room_name,
            "status": self.status,
            "intake_method": self.intake_method,
            "has_unlinked_allocations": self.has_unlinked_allocations,
            "started_at": self.started_at,
            "closed_at": self.closed_at,
            "hardware_device_id": self.hardware_device_id,
            "notes": self.notes,
            "shipments": [s.to_dict() for s in self.shipments],
            "allocation_count": self.allocation_count,
            "total_good_qty": self.total_good_qty,
            "total_rejected_qty": self.total_rejected_qty,
        }
