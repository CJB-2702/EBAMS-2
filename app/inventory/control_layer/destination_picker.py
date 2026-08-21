"""Context: Reusable destination-picker state builder for movement workflows.

Centralizes warehouse → room → location selection logic, replacing inline
`_destination_state()` calls in movement_portal and putaway_worklist.
F5-safe: all state lives in URL query params, returned in context dict.
"""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Sum
from django.http import HttpRequest

from app.inventory.control_layer.adapters.room_svg_adapter import RoomSvgAdapter
from app.inventory.control_layer.constants import ROOM_SVG_GROUP_LABEL
from app.inventory.models.stock.active_inventory import ActiveInventory
from app.inventory.models.topography.room import Room
from app.inventory.models.topography.warehouse import Warehouse


def _int_or_none(raw) -> int | None:
    raw = (raw or "").strip()
    return int(raw) if raw.isdigit() else None


class DestinationPickerContext:
    """Single source of truth for destination selection state assembly.

    Used by any page needing warehouse → room → location picker
    (movement_portal, putaway_worklist, audits, issuance, etc.).

    State lives entirely in GET params (warehouse_id, room_id, loc, sloc) —
    F5-safe, one canonical URL per route, bookmarks work.
    """

    @classmethod
    def build_state(
        cls,
        request: HttpRequest,
        *,
        source_warehouse_id: int | None = None,
        part_id: int | None = None,
        include_intake_rooms: bool = False,
    ) -> dict:
        """Assemble full destination-picker state from query params.

        Args:
            request: Django request (to read GET params).
            source_warehouse_id: Active inventory's warehouse (to detect
                inter-warehouse moves). `None` for read-only browsing, where
                there is no source and nothing can "cross" warehouses.
            part_id: Optional part ID for stock-level display on location rows.
            include_intake_rooms: Keep Intake Rooms in the room list. Movement
                flows exclude them (you never put stock away *into* Intake),
                but browsing flows must show them — Intake holds real stock.

        Returns:
            {
                warehouses: [Warehouse, ...],
                warehouse_id: int | None,
                selected_warehouse: Warehouse | None,
                crosses_warehouse: bool (destination != source warehouse),
                rooms: [Room, ...] (non-intake rooms in selected warehouse),
                room_id: int | None,
                selected_room: Room | None,
                room_locations: [RoomLocation, ...] (with stock_qty annotations),
                map_svg: str | None (interactive SVG for selected room),
                loc: str (display_code filter from query param),
                sloc: int | None (selected StorageLocation.pk),
                selected_storage_location: StorageLocation | None,
            }
        """
        warehouse_id = _int_or_none(request.GET.get("warehouse_id", ""))
        room_id = _int_or_none(request.GET.get("room_id", ""))
        loc = request.GET.get("loc", "").strip()
        sloc = _int_or_none(request.GET.get("sloc", ""))

        warehouses = Warehouse.objects.filter(is_active=True).order_by("name")
        selected_warehouse = warehouses.filter(pk=warehouse_id).first() if warehouse_id else None
        crosses_warehouse = bool(
            source_warehouse_id is not None
            and selected_warehouse
            and selected_warehouse.pk != source_warehouse_id
        )

        rooms = []
        selected_room = None
        room_locations = []
        map_svg = None
        selected_storage_location = None

        if selected_warehouse and not crosses_warehouse:
            room_qs = Room.objects.filter(warehouse=selected_warehouse, is_active=True)
            if not include_intake_rooms:
                room_qs = room_qs.exclude(is_intake_room=True)
            rooms = list(
                room_qs.select_related("current_layout").order_by("room_name")
            )

            for room in rooms:
                if room.current_layout_id is not None:
                    raw_svg = RoomSvgAdapter.read_svg_from_attachment(room.current_layout)
                    room.thumbnail_svg = (
                        RoomSvgAdapter.normalize_viewbox(raw_svg) if raw_svg else None
                    )
                else:
                    room.thumbnail_svg = None

            if room_id:
                selected_room = next((r for r in rooms if r.pk == room_id), None)

            if selected_room is not None:
                room_locations = list(
                    selected_room.room_locations.filter(is_active=True)
                    .prefetch_related("storage_locations")
                    .order_by("display_code")
                )

                stock_map: dict[int, Decimal] = {}
                if part_id:
                    stock_qs = (
                        ActiveInventory.objects.filter(
                            room=selected_room,
                            part_id=part_id,
                            storage_location_id__isnull=False,
                        )
                        .values("storage_location_id")
                        .annotate(total_qty=Sum("quantity_on_hand"))
                    )
                    stock_map = {
                        item["storage_location_id"]: item["total_qty"] for item in stock_qs
                    }

                for rl in room_locations:
                    for sl in rl.storage_locations.all():
                        sl.part_stock_qty = stock_map.get(sl.pk, Decimal("0"))

                raw_svg = RoomSvgAdapter.read_svg_from_attachment(selected_room.current_layout)
                if raw_svg is not None:
                    shape_targets = {
                        rl.display_code: rl.display_code
                        for rl in room_locations
                        if rl.storage_locations.filter(is_active=True).exists()
                    }
                    clean_get = request.GET.copy()
                    clean_get.pop("format", None)
                    clean_get.pop("loc", None)
                    qs = clean_get.urlencode()
                    canonical_url = f"{request.path}?{qs}" if qs else request.path

                    map_svg = RoomSvgAdapter.render_interactive_svg(
                        raw_svg,
                        group_label=ROOM_SVG_GROUP_LABEL,
                        shape_targets=shape_targets,
                        canonical_url="",
                        format_param="",
                        drawer_target="",
                    )

                if sloc:
                    for rl in room_locations:
                        match = next(
                            (s for s in rl.storage_locations.all() if s.pk == sloc), None
                        )
                        if match is not None:
                            selected_storage_location = match
                            break

        return {
            "warehouses": warehouses,
            "warehouse_id": warehouse_id,
            "selected_warehouse": selected_warehouse,
            "crosses_warehouse": crosses_warehouse,
            "rooms": rooms,
            "room_id": room_id,
            "selected_room": selected_room,
            "room_locations": room_locations,
            "map_svg": map_svg,
            "loc": loc,
            "sloc": sloc,
            "selected_storage_location": selected_storage_location,
        }

    @classmethod
    def build_location_table_fragment(
        cls, request: HttpRequest, *, room_locations, loc: str
    ) -> dict:
        """Build state for location table fragment (location picker tier).

        Used by HTMX re-fetch when user selects a new room or filters locations.
        """
        room_location = next((rl for rl in room_locations if rl.display_code == loc), None)
        storage_locations = (
            list(room_location.storage_locations.filter(is_active=True))
            if room_location is not None
            else []
        )

        clean_get = request.GET.copy()
        clean_get.pop("format", None)
        clean_get.pop("sloc", None)
        base_qs = clean_get.urlencode()

        return {
            "room_location": room_location,
            "storage_locations": storage_locations,
            "base_qs": base_qs,
        }
