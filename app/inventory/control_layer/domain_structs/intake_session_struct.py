"""Struct: aggregated read model for one IntakeSession — metadata, linked
shipments, and its allocations, in the shapes the Auto Intake portal and
session-detail page both need.

`recording_locked_at` / `stock_posted_at` are the authority on session
state, not `status` (intake_portal_workflow.md §11.4). The totals below are
SESSION-SCOPED counts of what this run recorded — they are NOT the truth
about any shipment line, which is always the sum across every live session
(§5.5). Do not build a line's progress bar from these.
"""

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
    started_at: object
    recording_locked_at: object
    stock_posted_at: object
    active_shipment_id: int | None
    continues_session_id: int | None
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
            started_at=session.started_at,
            recording_locked_at=session.recording_locked_at,
            stock_posted_at=session.stock_posted_at,
            active_shipment_id=session.active_shipment_id,
            continues_session_id=session.continues_session_id,
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
            "started_at": self.started_at,
            "recording_locked_at": self.recording_locked_at,
            "stock_posted_at": self.stock_posted_at,
            "active_shipment_id": self.active_shipment_id,
            "continues_session_id": self.continues_session_id,
            "hardware_device_id": self.hardware_device_id,
            "notes": self.notes,
            "shipments": [s.to_dict() for s in self.shipments],
            "allocation_count": self.allocation_count,
            "total_good_qty": self.total_good_qty,
            "total_rejected_qty": self.total_rejected_qty,
        }
