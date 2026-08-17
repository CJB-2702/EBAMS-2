"""Guard types for Phase 7 audits. `AuditSessionStateMachine` — legal
`AuditSession.status` transitions. `AuditValidator` checks line-level
invariants at the boundary. `AuditPolicy` gates the two-tier authorization
surface (mirrors `StockPolicy`): the `can_audit_stock` permission plus
room-level data-domain coverage.
"""

from __future__ import annotations

from decimal import Decimal

from app.inventory.control_layer.errors import (
    DomainAccessDenied,
    InventoryValidationError,
)
from app.inventory.control_layer.guards.room_guard import RoomDomainPolicy
from app.inventory.models.audit.enums import AuditSessionStatus

AUDIT_SESSION_TRANSITIONS: dict[str, frozenset[str]] = {
    AuditSessionStatus.OPEN: frozenset(
        {AuditSessionStatus.COMPLETED, AuditSessionStatus.CANCELLED}
    ),
    AuditSessionStatus.COMPLETED: frozenset(),
    AuditSessionStatus.CANCELLED: frozenset(),
}


class AuditSessionStateMachine:
    @classmethod
    def check(cls, *, from_status: str, to_status: str) -> None:
        if from_status == to_status:
            raise InventoryValidationError(
                [f"The audit session is already '{from_status}'."]
            )
        legal = AUDIT_SESSION_TRANSITIONS.get(from_status, frozenset())
        if to_status not in legal:
            raise InventoryValidationError(
                [f"An audit session cannot move from '{from_status}' to '{to_status}'."]
            )


class AuditValidator:
    @classmethod
    def check_counted_non_negative(cls, *, counted_qty: Decimal) -> None:
        if counted_qty is None or counted_qty < 0:
            raise InventoryValidationError(
                ["Counted quantity cannot be negative."]
            )

    @classmethod
    def check_serial_count_shape(cls, *, serial_number: str, counted_qty: Decimal) -> None:
        if serial_number and counted_qty not in (0, 1):
            raise InventoryValidationError(
                ["A serialized line's counted quantity must be 0 or 1."]
            )


class AuditPolicy:
    @classmethod
    def check_can_audit(cls, *, actor) -> None:
        if actor is None:
            return
        if not actor.has_perm("inventory.can_audit_stock"):
            raise InventoryValidationError(
                ["You do not have the 'can_audit_stock' permission."]
            )

    @classmethod
    def check_domain_access(cls, *, actor, room) -> None:
        if actor is None or room is None:
            return
        if not RoomDomainPolicy.user_covers_room(actor, room):
            raise DomainAccessDenied(room_id=room.pk)
