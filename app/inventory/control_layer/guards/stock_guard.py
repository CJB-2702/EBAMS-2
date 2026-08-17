"""Guard types: Validator and Policy. `StockValidator` checks quantity and
serial invariants at the boundary before `StockLedgerManager` writes.
`StockPolicy` gates the two-tier authorization surface: a Django permission
plus room-level data-domain coverage (`RoomDomainPolicy`).
"""

from __future__ import annotations

from decimal import Decimal

from app.inventory.control_layer.errors import (
    DomainAccessDenied,
    InventoryValidationError,
    SerialInUseError,
)
from app.inventory.control_layer.guards.room_guard import RoomDomainPolicy
from app.inventory.models.stock.active_inventory import ActiveInventory


class StockValidator:
    @classmethod
    def check_quantity_positive(cls, *, qty: Decimal) -> None:
        if qty <= 0:
            raise InventoryValidationError(["Quantity must be greater than zero."])

    @classmethod
    def check_serial_implies_unit_qty(cls, *, serial: str, qty: Decimal) -> None:
        if serial and qty != 1:
            raise InventoryValidationError(
                ["A serialized quantity must be exactly 1."]
            )

    @classmethod
    def check_serial_available(
        cls, *, part_id: int, serial: str, exclude_id: int | None = None
    ) -> None:
        if not serial:
            return
        qs = ActiveInventory.objects.filter(
            part_id=part_id, serial_number=serial, quantity_on_hand__gt=0
        )
        if exclude_id is not None:
            qs = qs.exclude(pk=exclude_id)
        if qs.exists():
            raise SerialInUseError(part_id=part_id, serial_number=serial)


class StockPolicy:
    """The two-tier authorization surface: a Django permission (checked by
    whichever higher-level Context owns the specific workflow — intake,
    movement, issuance, audit) plus room-level data-domain coverage, which
    `StockLedgerManager` enforces on every verb regardless of caller."""

    @classmethod
    def check_domain_access(cls, *, actor, room) -> None:
        if actor is None:
            return
        if not RoomDomainPolicy.user_covers_room(actor, room):
            raise DomainAccessDenied(room_id=room.pk)

    @classmethod
    def check_permission(cls, *, actor, permission_codename: str) -> None:
        if actor is None:
            return
        if not actor.has_perm(permission_codename):
            raise InventoryValidationError(
                [f"You do not have the '{permission_codename}' permission."]
            )
