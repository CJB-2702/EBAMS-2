"""Guard types for Phase 6 movements. `MovementValidator` checks the shape of
a move at the boundary; `MovementPolicy` gates the two-tier authorization
surface (mirrors `StockPolicy`) plus the destination-room domain check
part_movements.md §5 calls out by name — the source room's domain is already
enforced by `StockLedgerManager.withdraw` inside `transfer`, so this guard's
job is the extra destination-side check plus the `can_move_stock` permission.
"""

from __future__ import annotations

from app.inventory.control_layer.errors import (
    DomainAccessDenied,
    InventoryValidationError,
)
from app.inventory.control_layer.guards.room_guard import RoomDomainPolicy
from app.inventory.control_layer.guards.stock_guard import StockPolicy


class MovementValidator:
    @classmethod
    def check_not_same_location(
        cls, *, from_room_id: int, from_storage_location_id: int | None,
        to_room_id: int, to_storage_location_id: int | None,
    ) -> None:
        if (
            from_room_id == to_room_id
            and from_storage_location_id == to_storage_location_id
        ):
            raise InventoryValidationError(
                ["Source and destination are the same location."]
            )


class MovementPolicy:
    @classmethod
    def check_can_move(cls, *, actor) -> None:
        StockPolicy.check_permission(
            actor=actor, permission_codename="inventory.can_move_stock"
        )

    @classmethod
    def check_destination_domain_access(cls, *, actor, to_room) -> None:
        if actor is None:
            return
        if not RoomDomainPolicy.user_covers_room(actor, to_room):
            raise DomainAccessDenied(room_id=to_room.pk)
