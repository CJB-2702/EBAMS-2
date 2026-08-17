"""Manager: update/deactivate verbs for the topography aggregate. Stable
sub-domain collaborator for `TopographyContext` — one place lifecycle
mutations on warehouses, rooms, and storage locations happen after creation.
"""

from __future__ import annotations

from app.inventory.control_layer.guards.room_guard import RoomPolicy
from app.inventory.control_layer.guards.topography_guard import WarehouseValidator
from app.inventory.models.topography.room import Room
from app.inventory.models.topography.storage_location import StorageLocation
from app.inventory.models.topography.warehouse import Warehouse


class TopographyManager:
    @classmethod
    def update_warehouse(
        cls,
        *,
        warehouse: Warehouse,
        name: str,
        code: str,
        address: str = "",
        domain_ids: list[int] | None = None,
        actor=None,
    ) -> Warehouse:
        WarehouseValidator.check_code_unique(code=code, exclude_id=warehouse.pk)
        warehouse.name = name
        warehouse.code = code
        warehouse.address = address
        warehouse.updated_by = actor
        warehouse.save(update_fields=["name", "code", "address", "updated_by", "updated_at"])
        if domain_ids is not None:
            warehouse.domains.set(domain_ids)
        return warehouse

    @classmethod
    def deactivate_warehouse(cls, *, warehouse: Warehouse, actor=None) -> Warehouse:
        warehouse.is_active = False
        warehouse.updated_by = actor
        warehouse.save(update_fields=["is_active", "updated_by", "updated_at"])
        return warehouse

    @classmethod
    def update_room(
        cls,
        *,
        room: Room,
        room_name: str,
        description: str = "",
        excluded_domain_ids: list[int] | None = None,
        actor=None,
    ) -> Room:
        if room_name != room.room_name:
            RoomPolicy.check_rename(room=room)
        room.room_name = room_name
        room.description = description
        room.updated_by = actor
        room.save(update_fields=["room_name", "description", "updated_by", "updated_at"])
        if excluded_domain_ids is not None:
            room.excluded_domains.set(excluded_domain_ids)
        return room

    @classmethod
    def deactivate_room(cls, *, room: Room, actor=None) -> Room:
        RoomPolicy.check_delete(room=room)
        room.is_active = False
        room.updated_by = actor
        room.save(update_fields=["is_active", "updated_by", "updated_at"])
        return room

    @classmethod
    def update_storage_location(
        cls,
        *,
        storage_location: StorageLocation,
        is_active: bool,
        actor=None,
    ) -> StorageLocation:
        storage_location.is_active = is_active
        storage_location.updated_by = actor
        storage_location.save(update_fields=["is_active", "updated_by", "updated_at"])
        return storage_location

    @classmethod
    def deactivate_storage_location(
        cls, *, storage_location: StorageLocation, actor=None
    ) -> StorageLocation:
        return cls.update_storage_location(
            storage_location=storage_location, is_active=False, actor=actor
        )
