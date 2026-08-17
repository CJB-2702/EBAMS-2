"""Structs: parent/child reconciliation read models (FD-9's parent+child
grain — resolution_type only ever lives on the child)."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.inventory.models.intake.part_reconciliation_line import PartReconciliationLine
from app.inventory.models.intake.part_reconciliation_session import (
    PartReconciliationSession,
)


@dataclass(frozen=True)
class PartReconciliationLineStruct:
    line_id: int
    part_reconciliation_session_id: int
    shipment_line_id: int
    expected_quantity: Decimal
    allocated_quantity: Decimal
    rejected_quantity: Decimal
    resolution_type: str
    notes: str

    @classmethod
    def from_model(cls, line: PartReconciliationLine) -> "PartReconciliationLineStruct":
        return cls(
            line_id=line.pk,
            part_reconciliation_session_id=line.part_reconciliation_session_id,
            shipment_line_id=line.shipment_line_id,
            expected_quantity=line.expected_quantity,
            allocated_quantity=line.allocated_quantity,
            rejected_quantity=line.rejected_quantity,
            resolution_type=line.resolution_type,
            notes=line.notes,
        )

    def to_dict(self) -> dict:
        return {
            "line_id": self.line_id,
            "part_reconciliation_session_id": self.part_reconciliation_session_id,
            "shipment_line_id": self.shipment_line_id,
            "expected_quantity": self.expected_quantity,
            "allocated_quantity": self.allocated_quantity,
            "rejected_quantity": self.rejected_quantity,
            "resolution_type": self.resolution_type,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class PartReconciliationSessionStruct:
    reconciliation_id: int
    intake_session_id: int
    part_id: int
    part_number: str
    status: str
    total_expected_quantity: Decimal
    total_allocated_quantity: Decimal
    total_rejected_quantity: Decimal
    resolved_by_id: int | None
    resolved_at: object
    notes: str
    lines: tuple[PartReconciliationLineStruct, ...] = field(default_factory=tuple)

    @classmethod
    def load(cls, *, reconciliation_id: int) -> "PartReconciliationSessionStruct":
        reconciliation = PartReconciliationSession.objects.select_related("part").get(
            pk=reconciliation_id
        )
        return cls.from_model(reconciliation)

    @classmethod
    def from_model(
        cls, reconciliation: PartReconciliationSession
    ) -> "PartReconciliationSessionStruct":
        lines = list(
            reconciliation.lines.filter(deleted_at__isnull=True).order_by("id")
        )
        return cls(
            reconciliation_id=reconciliation.pk,
            intake_session_id=reconciliation.intake_session_id,
            part_id=reconciliation.part_id,
            part_number=reconciliation.part.part_number,
            status=reconciliation.status,
            total_expected_quantity=reconciliation.total_expected_quantity,
            total_allocated_quantity=reconciliation.total_allocated_quantity,
            total_rejected_quantity=reconciliation.total_rejected_quantity,
            resolved_by_id=reconciliation.resolved_by_id,
            resolved_at=reconciliation.resolved_at,
            notes=reconciliation.notes,
            lines=tuple(PartReconciliationLineStruct.from_model(line) for line in lines),
        )

    def to_dict(self) -> dict:
        return {
            "reconciliation_id": self.reconciliation_id,
            "intake_session_id": self.intake_session_id,
            "part_id": self.part_id,
            "part_number": self.part_number,
            "status": self.status,
            "total_expected_quantity": self.total_expected_quantity,
            "total_allocated_quantity": self.total_allocated_quantity,
            "total_rejected_quantity": self.total_rejected_quantity,
            "resolved_by_id": self.resolved_by_id,
            "resolved_at": self.resolved_at,
            "notes": self.notes,
            "lines": [line.to_dict() for line in self.lines],
        }
