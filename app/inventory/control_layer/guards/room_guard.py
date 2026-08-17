"""Guard types: Policy. `RoomPolicy` protects the intake room's special
status and blocks deleting a room that still holds topography or stock.
`RoomDomainPolicy` computes a room's effective data-domain scope (warehouse
domains minus room-level exclusions) and gates a user against it — the
two-tier authorization surface FD-14 moves off `Room.get_effective_data_domains()`
and out of the model entirely.
"""

from __future__ import annotations

from app.administration.models.data_ownership.user_assignments.user_domains import (
    UserDomain,
)
from app.inventory.control_layer.errors import InventoryValidationError


class RoomPolicy:
    @classmethod
    def check_rename(cls, *, room) -> None:
        if room.is_intake_room or not room.is_renamable:
            raise InventoryValidationError(
                [f"'{room.room_name}' is a protected room and cannot be renamed."]
            )

    @classmethod
    def check_delete(cls, *, room) -> None:
        if room.is_intake_room or not room.is_deletable:
            raise InventoryValidationError(
                [f"'{room.room_name}' is a protected room and cannot be deleted."]
            )
        if room.room_locations.filter(is_active=True).exists():
            raise InventoryValidationError(
                [f"'{room.room_name}' still has storage locations and cannot be deleted."]
            )
        if room.stock.exists():
            raise InventoryValidationError(
                [f"'{room.room_name}' still holds stock and cannot be deleted."]
            )


class RoomDomainPolicy:
    @classmethod
    def effective_domains(cls, room) -> set[int]:
        """Warehouse domains minus this room's excluded domains."""
        warehouse_domain_ids = set(
            room.warehouse.domains.values_list("id", flat=True)
        )
        excluded_domain_ids = set(room.excluded_domains.values_list("id", flat=True))
        return warehouse_domain_ids - excluded_domain_ids

    @classmethod
    def user_covers_room(cls, user, room) -> bool:
        """True when the room carries no domain scope at all (open to every
        authenticated user, matching Part.is_domain_limited's default-open
        convention), or the user has an active membership in at least one of
        the room's effective domains."""
        effective = cls.effective_domains(room)
        if not effective:
            return True
        return UserDomain.objects.filter(
            user=user, domain_id__in=effective, is_active=True
        ).exists()
