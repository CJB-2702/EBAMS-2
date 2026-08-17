"""Factory + BulkFactory for `RoomLocation` root items (Tier 2 of the SVG
spatial engine, FD-29). Both route coordinates through `coordinate_adaptor`
so `display_code` is never hand-assembled elsewhere (FD-16).
`RoomLocationBulkFactory` is the seam the Room-tier layout builder
reconciles unmatched shapes against.
"""

from __future__ import annotations

from app.inventory.control_layer.adapters.coordinate_adaptor import (
    build_room_location_display_code,
    format_xyz_coordinate,
)
from app.inventory.control_layer.guards.topography_guard import RoomLocationValidator
from app.inventory.models.topography.room_location import RoomLocation


class RoomLocationFactory:
    @classmethod
    def create(
        cls,
        *,
        room_id: int,
        major_coord: str,
        minor_coord: str,
        actor=None,
    ) -> RoomLocation:
        major = format_xyz_coordinate(major_coord)
        minor = format_xyz_coordinate(minor_coord)

        RoomLocationValidator.check_coordinates_non_empty(
            major_coord=major, minor_coord=minor
        )
        RoomLocationValidator.check_unique(
            room_id=room_id, major_coord=major, minor_coord=minor
        )

        return RoomLocation.objects.create(
            room_id=room_id,
            major_coord=major,
            minor_coord=minor,
            display_code=build_room_location_display_code(major, minor),
            created_by=actor,
            updated_by=actor,
        )


class RoomLocationBulkFactory:
    @classmethod
    def create_many(
        cls,
        *,
        room_id: int,
        coordinates: list[tuple[str, str]],
        actor=None,
    ) -> list[RoomLocation]:
        """Batch creation; returns only the created `RoomLocation` rows — no
        nested structs (BulkFactory convention). Skips any coordinate pair
        that already exists in the room instead of failing the whole batch,
        so a reconciliation pass over partially-seeded topography is
        idempotent."""
        created: list[RoomLocation] = []
        for major_coord, minor_coord in coordinates:
            major = format_xyz_coordinate(major_coord)
            minor = format_xyz_coordinate(minor_coord)
            if RoomLocation.objects.filter(
                room_id=room_id, major_coord=major, minor_coord=minor
            ).exists():
                continue
            created.append(
                RoomLocation.objects.create(
                    room_id=room_id,
                    major_coord=major,
                    minor_coord=minor,
                    display_code=build_room_location_display_code(major, minor),
                    created_by=actor,
                    updated_by=actor,
                )
            )
        return created
