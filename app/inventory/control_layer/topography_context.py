"""Context: the single public entrypoint for topography control logic.

Every warehouse/room/storage-location write goes through here — callers use
domain verbs (`create_warehouse`, `add_room`, ...) rather than reaching for
the factories/managers directly.
"""

from __future__ import annotations

from django.core.files.uploadedfile import SimpleUploadedFile

from app.events.control_layer.managers.gallery_manager import GalleryManager
from app.events.models import FileSet
from app.inventory.control_layer.adapters.room_svg_adapter import RoomSvgAdapter
from app.inventory.control_layer.constants import (
    ROOM_LOCATION_SVG_GROUP_LABEL,
    ROOM_SVG_GROUP_LABEL,
)
from app.inventory.control_layer.domain_structs.svg_reconciliation_struct import (
    SvgReconciliationStruct,
)
from app.inventory.control_layer.factories.room_location_factory import (
    RoomLocationBulkFactory,
    RoomLocationFactory,
)
from app.inventory.control_layer.factories.storage_location_factory import (
    StorageLocationBulkFactory,
    StorageLocationFactory,
)
from app.inventory.control_layer.factories.warehouse_factory import WarehouseFactory
from app.inventory.control_layer.guards.topography_guard import (
    LayoutReconciliationPolicy,
    RoomValidator,
)
from app.inventory.control_layer.managers.topography_manager import TopographyManager
from app.inventory.control_layer.thread_domain import default_domain_id_for
from app.inventory.models.topography.room import Room
from app.inventory.models.topography.room_location import RoomLocation
from app.inventory.models.topography.storage_location import StorageLocation
from app.inventory.models.topography.warehouse import Warehouse


class TopographyContext:
    def __init__(self, warehouse_id: int) -> None:
        self.warehouse_id = warehouse_id
        self._warehouse: Warehouse | None = None

    @property
    def warehouse(self) -> Warehouse:
        if self._warehouse is None:
            self._warehouse = Warehouse.objects.get(pk=self.warehouse_id)
        return self._warehouse

    # ------------------------------------------------------------------ #
    # Root creation
    # ------------------------------------------------------------------ #

    @classmethod
    def create_warehouse(
        cls,
        *,
        name: str,
        code: str,
        division_id: int,
        address: str = "",
        domain_ids: list[int] | None = None,
        actor=None,
    ) -> "TopographyContext":
        warehouse = WarehouseFactory.create(
            name=name,
            code=code,
            division_id=division_id,
            address=address,
            domain_ids=domain_ids,
            actor=actor,
        )
        return cls(warehouse.pk)

    # ------------------------------------------------------------------ #
    # Rooms
    # ------------------------------------------------------------------ #

    def add_room(
        self,
        *,
        room_name: str,
        description: str = "",
        excluded_domain_ids: list[int] | None = None,
        actor=None,
    ) -> Room:
        RoomValidator.check_name_non_empty(room_name=room_name)
        RoomValidator.check_name_unique(
            warehouse_id=self.warehouse_id, room_name=room_name
        )
        room = Room.objects.create(
            warehouse=self.warehouse,
            room_name=room_name,
            description=description,
            created_by=actor,
            updated_by=actor,
        )
        if excluded_domain_ids:
            room.excluded_domains.set(excluded_domain_ids)
        return room

    def update_room(self, *, room: Room, room_name: str, description: str = "",
                     excluded_domain_ids: list[int] | None = None, actor=None) -> Room:
        RoomValidator.check_name_non_empty(room_name=room_name)
        RoomValidator.check_name_unique(
            warehouse_id=room.warehouse_id, room_name=room_name, exclude_id=room.pk
        )
        return TopographyManager.update_room(
            room=room,
            room_name=room_name,
            description=description,
            excluded_domain_ids=excluded_domain_ids,
            actor=actor,
        )

    def deactivate_room(self, *, room: Room, actor=None) -> Room:
        return TopographyManager.deactivate_room(room=room, actor=actor)

    def reactivate_room(self, *, room: Room, actor=None) -> Room:
        return TopographyManager.reactivate_room(room=room, actor=actor)

    # ------------------------------------------------------------------ #
    # Room locations (Tier 2 — XY)
    # ------------------------------------------------------------------ #

    def add_room_location(
        self,
        *,
        room_id: int,
        major_coord: str,
        minor_coord: str,
        actor=None,
    ) -> RoomLocation:
        return RoomLocationFactory.create(
            room_id=room_id, major_coord=major_coord, minor_coord=minor_coord, actor=actor
        )

    def bulk_add_room_locations(
        self,
        *,
        room_id: int,
        coordinates: list[tuple[str, str]],
        actor=None,
    ) -> list[RoomLocation]:
        return RoomLocationBulkFactory.create_many(
            room_id=room_id, coordinates=coordinates, actor=actor
        )

    # ------------------------------------------------------------------ #
    # Storage locations (Tier 3 — Z)
    # ------------------------------------------------------------------ #

    def add_storage_location(
        self,
        *,
        room_location_id: int,
        atomic_coord: str,
        actor=None,
    ) -> StorageLocation:
        return StorageLocationFactory.create(
            room_location_id=room_location_id, atomic_coord=atomic_coord, actor=actor
        )

    def bulk_add_storage_locations(
        self,
        *,
        room_location_id: int,
        atomic_coords: list[str],
        actor=None,
    ) -> list[StorageLocation]:
        return StorageLocationBulkFactory.create_many(
            room_location_id=room_location_id, atomic_coords=atomic_coords, actor=actor
        )

    # ------------------------------------------------------------------ #
    # Updates / deactivation
    # ------------------------------------------------------------------ #

    def update_warehouse(
        self,
        *,
        name: str,
        code: str,
        address: str = "",
        domain_ids: list[int] | None = None,
        actor=None,
    ) -> Warehouse:
        self._warehouse = TopographyManager.update_warehouse(
            warehouse=self.warehouse,
            name=name,
            code=code,
            address=address,
            domain_ids=domain_ids,
            actor=actor,
        )
        return self._warehouse

    def deactivate_warehouse(self, *, actor=None) -> Warehouse:
        self._warehouse = TopographyManager.deactivate_warehouse(
            warehouse=self.warehouse, actor=actor
        )
        return self._warehouse

    def reactivate_warehouse(self, *, actor=None) -> Warehouse:
        self._warehouse = TopographyManager.reactivate_warehouse(
            warehouse=self.warehouse, actor=actor
        )
        return self._warehouse

    def deactivate_room_location(
        self, *, room_location: RoomLocation, actor=None
    ) -> RoomLocation:
        return TopographyManager.deactivate_room_location(
            room_location=room_location, actor=actor
        )

    def deactivate_storage_location(
        self, *, storage_location: StorageLocation, actor=None
    ) -> StorageLocation:
        return TopographyManager.deactivate_storage_location(
            storage_location=storage_location, actor=actor
        )

    # ------------------------------------------------------------------ #
    # SVG spatial engine — layout upload + reconciliation (FD-23/FD-29)
    # ------------------------------------------------------------------ #

    @staticmethod
    def _sanitize_upload(uploaded_file) -> str:
        raw_bytes = uploaded_file.read()
        RoomSvgAdapter.check_upload_size(raw_bytes)
        raw_svg = raw_bytes.decode("utf-8")
        return RoomSvgAdapter.sanitize(raw_svg)

    @staticmethod
    def _archive_layout(*, owner, uploaded_file, sanitized_svg: str, actor=None) -> None:
        """Stores the *sanitized* SVG as the owner's `current_layout`
        attachment — the raw upload itself is never persisted (FD-25: only
        sanitized output is ever stored or rendered)."""
        gallery = GalleryManager(
            owner,
            actor,
            primary_attr="current_layout",
            gallery_thread_cls=FileSet,
            domain_id_resolver=lambda: default_domain_id_for(FileSet),
        )
        sanitized_file = SimpleUploadedFile(
            uploaded_file.name,
            sanitized_svg.encode("utf-8"),
            content_type="image/svg+xml",
        )
        gallery.add_image(sanitized_file)

    def upload_room_layout(
        self,
        *,
        room_id: int,
        uploaded_file,
        actor=None,
        allow_orphaned_stock: bool = False,
    ) -> SvgReconciliationStruct:
        room = Room.objects.get(pk=room_id)
        sanitized_svg = self._sanitize_upload(uploaded_file)

        shape_codes = RoomSvgAdapter.extract_shape_codes(
            sanitized_svg, group_label=ROOM_SVG_GROUP_LABEL
        )
        existing_codes = set(
            room.room_locations.filter(is_active=True).values_list(
                "display_code", flat=True
            )
        )
        reconciliation = SvgReconciliationStruct.build(
            shape_codes=shape_codes, existing_codes=existing_codes
        )
        # Reject before archiving: a layout that drops a stock-holding
        # location must not become the room's `current_layout` even briefly.
        LayoutReconciliationPolicy.check_room_orphans(
            room=room,
            orphaned_codes=reconciliation.orphaned,
            allow_orphaned_stock=allow_orphaned_stock,
        )

        self._archive_layout(
            owner=room, uploaded_file=uploaded_file, sanitized_svg=sanitized_svg, actor=actor
        )
        return reconciliation

    def upload_room_location_layout(
        self,
        *,
        room_location_id: int,
        uploaded_file,
        actor=None,
        allow_orphaned_stock: bool = False,
    ) -> SvgReconciliationStruct:
        room_location = RoomLocation.objects.get(pk=room_location_id)
        sanitized_svg = self._sanitize_upload(uploaded_file)

        shape_codes = RoomSvgAdapter.extract_shape_codes(
            sanitized_svg, group_label=ROOM_LOCATION_SVG_GROUP_LABEL
        )
        existing_codes = set(
            room_location.storage_locations.filter(is_active=True).values_list(
                "atomic_coord", flat=True
            )
        )
        reconciliation = SvgReconciliationStruct.build(
            shape_codes=shape_codes, existing_codes=existing_codes
        )
        LayoutReconciliationPolicy.check_room_location_orphans(
            room_location=room_location,
            orphaned_codes=reconciliation.orphaned,
            allow_orphaned_stock=allow_orphaned_stock,
        )

        self._archive_layout(
            owner=room_location,
            uploaded_file=uploaded_file,
            sanitized_svg=sanitized_svg,
            actor=actor,
        )
        return reconciliation
