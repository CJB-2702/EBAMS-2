"""Factory + BulkFactory for `StorageLocation` root items (Tier 3 of the SVG
spatial engine, FD-29). Coordinates route through `coordinate_adaptor` so
`display_code` is never hand-assembled elsewhere (FD-16).
`StorageLocationBulkFactory` is the seam the RoomLocation-tier layout
builder reconciles unmatched shapes against.
"""

from __future__ import annotations

from app.inventory.control_layer.adapters.coordinate_adaptor import (
    build_storage_location_display_code,
    format_xyz_coordinate,
)
from app.inventory.control_layer.guards.topography_guard import StorageLocationValidator
from app.inventory.models.topography.room_location import RoomLocation
from app.inventory.models.topography.storage_location import StorageLocation


class StorageLocationFactory:
    @classmethod
    def create(
        cls,
        *,
        room_location_id: int,
        atomic_coord: str,
        actor=None,
    ) -> StorageLocation:
        atomic = format_xyz_coordinate(atomic_coord)

        StorageLocationValidator.check_atomic_coord_non_empty(atomic_coord=atomic)
        StorageLocationValidator.check_unique(
            room_location_id=room_location_id, atomic_coord=atomic
        )

        room_location_code = RoomLocation.objects.values_list(
            "display_code", flat=True
        ).get(pk=room_location_id)

        return StorageLocation.objects.create(
            room_location_id=room_location_id,
            atomic_coord=atomic,
            display_code=build_storage_location_display_code(room_location_code, atomic),
            created_by=actor,
            updated_by=actor,
        )


class StorageLocationBulkFactory:
    @classmethod
    def create_many(
        cls,
        *,
        room_location_id: int,
        atomic_coords: list[str],
        actor=None,
    ) -> list[StorageLocation]:
        """Batch creation; returns only the created `StorageLocation` rows —
        no nested structs (BulkFactory convention). Skips any atomic
        coordinate that already exists under this RoomLocation instead of
        failing the whole batch, so a reconciliation pass over partially-
        seeded topography is idempotent."""
        room_location_code = RoomLocation.objects.values_list(
            "display_code", flat=True
        ).get(pk=room_location_id)

        created: list[StorageLocation] = []
        for atomic_coord in atomic_coords:
            atomic = format_xyz_coordinate(atomic_coord)
            if StorageLocation.objects.filter(
                room_location_id=room_location_id, atomic_coord=atomic
            ).exists():
                continue
            created.append(
                StorageLocation.objects.create(
                    room_location_id=room_location_id,
                    atomic_coord=atomic,
                    display_code=build_storage_location_display_code(
                        room_location_code, atomic
                    ),
                    created_by=actor,
                    updated_by=actor,
                )
            )
        return created
