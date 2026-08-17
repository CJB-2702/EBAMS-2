"""Struct: aggregated read model for one StorageLocation and its room/
warehouse context."""

from __future__ import annotations

from dataclasses import dataclass

from app.inventory.models.topography.storage_location import StorageLocation


@dataclass(frozen=True)
class StorageLocationStruct:
    storage_location_id: int
    room_location_id: int
    room_location_display_code: str
    room_id: int
    room_name: str
    warehouse_id: int
    warehouse_code: str
    atomic_coord: str
    display_code: str
    is_active: bool

    @classmethod
    def load(cls, *, storage_location_id: int) -> "StorageLocationStruct":
        location = StorageLocation.objects.select_related(
            "room_location__room__warehouse"
        ).get(pk=storage_location_id)
        return cls.from_model(location)

    @classmethod
    def from_model(cls, location: StorageLocation) -> "StorageLocationStruct":
        room_location = location.room_location
        room = room_location.room
        return cls(
            storage_location_id=location.pk,
            room_location_id=room_location.pk,
            room_location_display_code=room_location.display_code,
            room_id=room.pk,
            room_name=room.room_name,
            warehouse_id=room.warehouse_id,
            warehouse_code=room.warehouse.code,
            atomic_coord=location.atomic_coord,
            display_code=location.display_code,
            is_active=location.is_active,
        )

    def to_dict(self) -> dict:
        return {
            "storage_location_id": self.storage_location_id,
            "room_location_id": self.room_location_id,
            "room_location_display_code": self.room_location_display_code,
            "room_id": self.room_id,
            "room_name": self.room_name,
            "warehouse_id": self.warehouse_id,
            "warehouse_code": self.warehouse_code,
            "atomic_coord": self.atomic_coord,
            "display_code": self.display_code,
            "is_active": self.is_active,
        }
