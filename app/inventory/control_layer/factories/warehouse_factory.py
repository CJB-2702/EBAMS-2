"""Factory: stateless creation of the root topography item. Creates the
warehouse and its protected Intake Room together, in one transaction, so a
`Warehouse` never exists without one (FD-14) — Django admin/shell creation
that skips this factory is treated as an invalid state the seed and every
control-layer path never produce.
"""

from __future__ import annotations

from django.db import transaction

from app.inventory.control_layer.errors import InventoryValidationError
from app.inventory.control_layer.guards.topography_guard import WarehouseValidator
from app.inventory.models.topography.room import Room
from app.inventory.models.topography.warehouse import Warehouse


class WarehouseFactory:
    @classmethod
    def create(
        cls,
        *,
        name: str,
        code: str,
        division_id: int,
        address: str = "",
        domain_ids: list[int] | None = None,
        actor=None,
    ) -> Warehouse:
        WarehouseValidator.check_code_unique(code=code)

        with transaction.atomic():
            warehouse = Warehouse.objects.create(
                name=name,
                code=code,
                division_id=division_id,
                address=address,
                created_by=actor,
                updated_by=actor,
            )
            if domain_ids:
                warehouse.domains.set(domain_ids)

            Room.objects.create(
                warehouse=warehouse,
                room_name="Intake",
                is_intake_room=True,
                is_deletable=False,
                is_renamable=False,
                created_by=actor,
                updated_by=actor,
            )

        return warehouse

    @classmethod
    def intake_room(cls, *, warehouse: Warehouse) -> Room:
        room = warehouse.rooms.filter(is_intake_room=True).first()
        if room is None:
            raise InventoryValidationError(
                [f"Warehouse '{warehouse.code}' has no Intake Room — invalid state."]
            )
        return room
