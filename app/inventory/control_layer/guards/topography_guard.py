"""Guard type: Validator. Input and uniqueness pre-checks for warehouses and
storage locations, so a bad coordinate or duplicate code surfaces as a
friendly `InventoryValidationError` instead of an `IntegrityError`.
"""

from __future__ import annotations

from app.inventory.control_layer.errors import InventoryValidationError
from app.inventory.models.topography.room_location import RoomLocation
from app.inventory.models.topography.storage_location import StorageLocation
from app.inventory.models.topography.warehouse import Warehouse


class WarehouseValidator:
    @classmethod
    def check_code_unique(cls, *, code: str, exclude_id: int | None = None) -> None:
        qs = Warehouse.objects.filter(code=code)
        if exclude_id is not None:
            qs = qs.exclude(pk=exclude_id)
        if qs.exists():
            raise InventoryValidationError(
                [f"Warehouse code '{code}' is already in use."]
            )


class RoomLocationValidator:
    @classmethod
    def check_coordinates_non_empty(cls, *, major_coord: str, minor_coord: str) -> None:
        errors = []
        for label, value in (("Major", major_coord), ("Minor", minor_coord)):
            if not (value or "").strip():
                errors.append(f"{label} coordinate cannot be blank.")
        if errors:
            raise InventoryValidationError(errors)

    @classmethod
    def check_unique(
        cls,
        *,
        room_id: int,
        major_coord: str,
        minor_coord: str,
        exclude_id: int | None = None,
    ) -> None:
        qs = RoomLocation.objects.filter(
            room_id=room_id, major_coord=major_coord, minor_coord=minor_coord
        )
        if exclude_id is not None:
            qs = qs.exclude(pk=exclude_id)
        if qs.exists():
            raise InventoryValidationError(
                [f"{major_coord}-{minor_coord} already exists in this room."]
            )


class StorageLocationValidator:
    @classmethod
    def check_atomic_coord_non_empty(cls, *, atomic_coord: str) -> None:
        if not (atomic_coord or "").strip():
            raise InventoryValidationError(["Atomic coordinate cannot be blank."])

    @classmethod
    def check_unique(
        cls,
        *,
        room_location_id: int,
        atomic_coord: str,
        exclude_id: int | None = None,
    ) -> None:
        qs = StorageLocation.objects.filter(
            room_location_id=room_location_id, atomic_coord=atomic_coord
        )
        if exclude_id is not None:
            qs = qs.exclude(pk=exclude_id)
        if qs.exists():
            raise InventoryValidationError(
                [f"Atomic coordinate '{atomic_coord}' already exists at this location."]
            )
