"""Context: the single public entrypoint for movement control logic. Callers
use domain verbs (`putaway`, `move`, `adjust_bin`) rather than reaching for
`MovementManager` directly — each verb resolves the source balance row and
figures out the destination shape (part_movements.md §1) before handing off.
"""

from __future__ import annotations

from decimal import Decimal

from app.inventory.control_layer.managers.movement_manager import MovementManager
from app.inventory.models.movements.part_movement import PartMovement
from app.inventory.models.stock.active_inventory import ActiveInventory
from app.inventory.models.topography.room import Room
from app.inventory.models.topography.storage_location import StorageLocation


class MovementContext:
    @staticmethod
    def _source(active_inventory_id: int) -> ActiveInventory:
        return ActiveInventory.objects.select_related(
            "warehouse", "room", "storage_location", "part"
        ).get(pk=active_inventory_id)

    @classmethod
    def putaway(
        cls,
        *,
        active_inventory_id: int,
        to_storage_location_id: int,
        quantity: Decimal | None = None,
        actor=None,
        notes: str = "",
    ) -> PartMovement:
        """Intake Room -> a real StorageLocation, same warehouse. Destination
        must be a StorageLocation — there is no skip-location putaway (UI
        review map §8)."""
        balance = cls._source(active_inventory_id)
        to_storage_location = StorageLocation.objects.select_related(
            "room_location__room__warehouse"
        ).get(pk=to_storage_location_id)
        to_room = to_storage_location.room_location.room

        return MovementManager.execute(
            part=balance.part,
            quantity=quantity if quantity is not None else balance.quantity_on_hand,
            serial=balance.serial_number,
            from_warehouse=balance.warehouse,
            from_room=balance.room,
            from_storage_location=balance.storage_location,
            to_warehouse=to_room.warehouse,
            to_room=to_room,
            to_storage_location=to_storage_location,
            actor=actor,
            notes=notes,
        )

    @classmethod
    def move(
        cls,
        *,
        active_inventory_id: int,
        to_warehouse_id: int,
        to_storage_location_id: int | None = None,
        quantity: Decimal | None = None,
        actor=None,
        notes: str = "",
    ) -> PartMovement:
        """Inter-room or inter-warehouse transfer. Crossing a warehouse
        boundary always lands the stock unassigned in the destination
        warehouse's Intake Room (part_movements.md §1.3) — any
        `to_storage_location_id` is ignored in that case."""
        balance = cls._source(active_inventory_id)

        if to_warehouse_id != balance.warehouse_id:
            to_room = Room.objects.select_related("warehouse").get(
                warehouse_id=to_warehouse_id, is_intake_room=True
            )
            to_storage_location = None
        else:
            to_storage_location = StorageLocation.objects.select_related(
                "room_location__room__warehouse"
            ).get(pk=to_storage_location_id)
            to_room = to_storage_location.room_location.room

        return MovementManager.execute(
            part=balance.part,
            quantity=quantity if quantity is not None else balance.quantity_on_hand,
            serial=balance.serial_number,
            from_warehouse=balance.warehouse,
            from_room=balance.room,
            from_storage_location=balance.storage_location,
            to_warehouse=to_room.warehouse,
            to_room=to_room,
            to_storage_location=to_storage_location,
            actor=actor,
            notes=notes,
        )

    @classmethod
    def adjust_bin(
        cls,
        *,
        active_inventory_id: int,
        to_storage_location_id: int,
        quantity: Decimal | None = None,
        actor=None,
        notes: str = "",
    ) -> PartMovement:
        """Relocate within the same room — a `move()` whose destination
        warehouse always matches the source, so it classifies as
        BIN_ADJUSTMENT."""
        balance = cls._source(active_inventory_id)
        return cls.move(
            active_inventory_id=active_inventory_id,
            to_warehouse_id=balance.warehouse_id,
            to_storage_location_id=to_storage_location_id,
            quantity=quantity,
            actor=actor,
            notes=notes,
        )

    # ------------------------------------------------------------------ #
    # Reads
    # ------------------------------------------------------------------ #

    @staticmethod
    def list_movements():
        return PartMovement.objects.select_related(
            "part", "from_warehouse", "from_room", "from_storage_location",
            "to_warehouse", "to_room", "to_storage_location", "moved_by",
        )

    @staticmethod
    def get_movement(movement_id: int) -> PartMovement:
        return MovementContext.list_movements().get(pk=movement_id)
