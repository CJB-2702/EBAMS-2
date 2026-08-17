"""Struct: aggregated read model for one Room, with the effective-domain
slice computed by `RoomDomainPolicy` rather than a model method (FD-14).

FD-29: a Room's direct children are `RoomLocation`s (Tier 2, XY); each one
nests its own `StorageLocation`s (Tier 3, Z) rather than Room holding a flat
storage-location list.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.inventory.control_layer.guards.room_guard import RoomDomainPolicy
from app.inventory.models.topography.room import Room


@dataclass(frozen=True)
class RoomLocationStorageSlice:
    storage_location_id: int
    display_code: str
    is_active: bool


@dataclass(frozen=True)
class RoomRoomLocationSlice:
    room_location_id: int
    display_code: str
    is_active: bool
    has_layout: bool
    storage_locations: tuple[RoomLocationStorageSlice, ...] = ()


@dataclass(frozen=True)
class RoomStruct:
    room_id: int
    warehouse_id: int
    warehouse_code: str
    room_name: str
    description: str
    is_intake_room: bool
    is_deletable: bool
    is_renamable: bool
    is_active: bool
    has_layout: bool
    effective_domain_ids: tuple[int, ...]
    room_locations: tuple[RoomRoomLocationSlice, ...] = ()

    @classmethod
    def load(cls, *, room_id: int) -> "RoomStruct":
        room = (
            Room.objects.select_related("warehouse")
            .prefetch_related(
                "room_locations__storage_locations",
                "warehouse__domains",
                "excluded_domains",
            )
            .get(pk=room_id)
        )
        return cls.from_model(room)

    @classmethod
    def from_model(cls, room: Room) -> "RoomStruct":
        room_locations = tuple(
            RoomRoomLocationSlice(
                room_location_id=rl.pk,
                display_code=rl.display_code,
                is_active=rl.is_active,
                has_layout=rl.current_layout_id is not None,
                storage_locations=tuple(
                    RoomLocationStorageSlice(
                        storage_location_id=loc.pk,
                        display_code=loc.display_code,
                        is_active=loc.is_active,
                    )
                    for loc in rl.storage_locations.all()
                ),
            )
            for rl in room.room_locations.all()
        )
        return cls(
            room_id=room.pk,
            warehouse_id=room.warehouse_id,
            warehouse_code=room.warehouse.code,
            room_name=room.room_name,
            description=room.description,
            is_intake_room=room.is_intake_room,
            is_deletable=room.is_deletable,
            is_renamable=room.is_renamable,
            is_active=room.is_active,
            has_layout=room.current_layout_id is not None,
            effective_domain_ids=tuple(RoomDomainPolicy.effective_domains(room)),
            room_locations=room_locations,
        )

    def to_dict(self) -> dict:
        return {
            "room_id": self.room_id,
            "warehouse_id": self.warehouse_id,
            "warehouse_code": self.warehouse_code,
            "room_name": self.room_name,
            "description": self.description,
            "is_intake_room": self.is_intake_room,
            "is_deletable": self.is_deletable,
            "is_renamable": self.is_renamable,
            "is_active": self.is_active,
            "has_layout": self.has_layout,
            "effective_domain_ids": list(self.effective_domain_ids),
            "room_locations": [
                {
                    "room_location_id": rl.room_location_id,
                    "display_code": rl.display_code,
                    "is_active": rl.is_active,
                    "has_layout": rl.has_layout,
                    "storage_locations": [
                        {
                            "storage_location_id": s.storage_location_id,
                            "display_code": s.display_code,
                            "is_active": s.is_active,
                        }
                        for s in rl.storage_locations
                    ],
                }
                for rl in self.room_locations
            ],
        }
