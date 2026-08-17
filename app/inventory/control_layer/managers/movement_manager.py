"""Manager: `MovementManager.execute` is the one place a `PartMovement` row
is ever written — it classifies the movement type from the source/destination
shape, domain-gates the destination, runs `StockLedgerManager.transfer`, and
writes the ledger row, all in one transaction (part_movements.md §1, §4-5).
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction

from app.inventory.control_layer.guards.movement_guard import (
    MovementPolicy,
    MovementValidator,
)
from app.inventory.control_layer.managers.stock_ledger_manager import StockLedgerManager
from app.inventory.control_layer.narrators.movement_narrator import MovementNarrator
from app.inventory.models.movements.enums import MovementType
from app.inventory.models.movements.part_movement import PartMovement


class MovementManager:
    @classmethod
    def classify(cls, *, from_warehouse_id: int, from_room, to_warehouse_id: int, to_room) -> str:
        if from_warehouse_id != to_warehouse_id:
            return MovementType.INTER_WAREHOUSE
        if from_room.is_intake_room and from_room.pk != to_room.pk:
            return MovementType.PUTAWAY
        if from_room.pk == to_room.pk:
            return MovementType.BIN_ADJUSTMENT
        return MovementType.INTER_ROOM

    @classmethod
    def execute(
        cls,
        *,
        part,
        quantity: Decimal,
        serial: str = "",
        from_warehouse,
        from_room,
        from_storage_location,
        to_warehouse,
        to_room,
        to_storage_location,
        actor=None,
        notes: str = "",
        movement_date=None,
    ) -> PartMovement:
        # `can_move_stock` is checked by whichever presentation-layer portal
        # owns this workflow (StockPolicy's two-tier convention), not here —
        # this seam is also the seed scripts' direct write path and must not
        # require a permission grant just to construct dev fixtures.
        MovementValidator.check_not_same_location(
            from_room_id=from_room.pk,
            from_storage_location_id=(
                from_storage_location.pk if from_storage_location else None
            ),
            to_room_id=to_room.pk,
            to_storage_location_id=(
                to_storage_location.pk if to_storage_location else None
            ),
        )
        MovementPolicy.check_destination_domain_access(actor=actor, to_room=to_room)

        movement_type = cls.classify(
            from_warehouse_id=from_warehouse.pk,
            from_room=from_room,
            to_warehouse_id=to_warehouse.pk,
            to_room=to_room,
        )

        with transaction.atomic():
            StockLedgerManager.transfer(
                warehouse=to_warehouse,
                from_room=from_room,
                from_storage_location=from_storage_location,
                to_room=to_room,
                to_storage_location=to_storage_location,
                part=part,
                qty=quantity,
                serial=serial,
                actor=actor,
            )
            movement = PartMovement.objects.create(
                movement_number=MovementNarrator.generate_movement_number(),
                part=part,
                quantity=quantity,
                serial_number=serial,
                movement_type=movement_type,
                from_warehouse=from_warehouse,
                from_room=from_room,
                from_storage_location=from_storage_location,
                to_warehouse=to_warehouse,
                to_room=to_room,
                to_storage_location=to_storage_location,
                moved_by=actor,
                notes=notes,
                created_by=actor,
                updated_by=actor,
                **({"movement_date": movement_date} if movement_date is not None else {}),
            )
        return movement
