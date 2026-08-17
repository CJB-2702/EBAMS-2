"""Struct: aggregated read model for one Warehouse — its own fields plus the
rooms hanging off it."""

from __future__ import annotations

from dataclasses import dataclass

from app.inventory.models.topography.warehouse import Warehouse


@dataclass(frozen=True)
class WarehouseRoomSlice:
    room_id: int
    room_name: str
    is_intake_room: bool
    is_active: bool
    room_location_count: int
    has_layout: bool
    current_layout_id: int | None


@dataclass(frozen=True)
class WarehouseStruct:
    warehouse_id: int
    name: str
    code: str
    division_id: int
    division_name: str
    address: str
    is_active: bool
    domain_ids: tuple[int, ...]
    rooms: tuple[WarehouseRoomSlice, ...] = ()

    @classmethod
    def load(cls, *, warehouse_id: int) -> "WarehouseStruct":
        warehouse = (
            Warehouse.objects.select_related("division")
            .prefetch_related("domains", "rooms__room_locations")
            .get(pk=warehouse_id)
        )
        return cls.from_model(warehouse)

    @classmethod
    def from_model(cls, warehouse: Warehouse) -> "WarehouseStruct":
        rooms = tuple(
            WarehouseRoomSlice(
                room_id=room.pk,
                room_name=room.room_name,
                is_intake_room=room.is_intake_room,
                is_active=room.is_active,
                room_location_count=len(room.room_locations.all()),
                has_layout=room.current_layout_id is not None,
                current_layout_id=room.current_layout_id,
            )
            for room in warehouse.rooms.all()
        )
        return cls(
            warehouse_id=warehouse.pk,
            name=warehouse.name,
            code=warehouse.code,
            division_id=warehouse.division_id,
            division_name=warehouse.division.name,
            address=warehouse.address,
            is_active=warehouse.is_active,
            domain_ids=tuple(warehouse.domains.values_list("id", flat=True)),
            rooms=rooms,
        )

    def to_dict(self) -> dict:
        return {
            "warehouse_id": self.warehouse_id,
            "name": self.name,
            "code": self.code,
            "division_id": self.division_id,
            "division_name": self.division_name,
            "address": self.address,
            "is_active": self.is_active,
            "domain_ids": list(self.domain_ids),
            "rooms": [
                {
                    "room_id": r.room_id,
                    "room_name": r.room_name,
                    "is_intake_room": r.is_intake_room,
                    "is_active": r.is_active,
                    "room_location_count": r.room_location_count,
                    "has_layout": r.has_layout,
                    "current_layout_id": r.current_layout_id,
                }
                for r in self.rooms
            ],
        }
