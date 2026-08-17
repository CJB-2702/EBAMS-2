"""Phase 3 — Warehouse/Room/RoomLocation topography pages and the three-tier
SVG spatial engine (FD-29): warehouse index/detail, the Room-tier spatial map
+ layout builder, and the RoomLocation-tier Z-picker + its own layout
builder. Every drawer/map fragment is served off its own canonical detail
URL with a `format=` query parameter (FD-17) — no bespoke drawer routes.

Row-level access: a Room/RoomLocation outside the user's effective data
domains 404s (`RoomDomainPolicy.user_covers_room`), mirroring D5 elsewhere
in the project.
"""

from __future__ import annotations

from django.contrib import messages
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.inventory.control_layer.adapters.room_svg_adapter import RoomSvgAdapter
from app.inventory.control_layer.constants import (
    ROOM_LOCATION_SVG_GROUP_LABEL,
    ROOM_SVG_GROUP_LABEL,
)
from app.inventory.control_layer.domain_structs.room_struct import RoomStruct
from app.inventory.control_layer.domain_structs.warehouse_struct import WarehouseStruct
from app.inventory.control_layer.errors import InventoryValidationError
from app.inventory.control_layer.guards.room_guard import RoomDomainPolicy
from app.inventory.control_layer.topography_context import TopographyContext
from app.inventory.models.stock.active_inventory import ActiveInventory
from app.inventory.models.topography.room import Room
from app.inventory.models.topography.room_location import RoomLocation
from app.inventory.models.topography.storage_location import StorageLocation
from app.inventory.models.topography.warehouse import Warehouse
from app.inventory.presentation_layer.search.active_inventory_search import (
    domain_visible_room_ids,
)
from app.inventory.presentation_layer.tools.inventory_access import accessible_domain_ids

TEMPLATE_DIR = "inventory/topography"


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #


def _room_or_404_in_domain(request: HttpRequest, pk: int) -> Room:
    room = get_object_or_404(
        Room.objects.select_related("warehouse").filter(is_active=True), pk=pk
    )
    if not RoomDomainPolicy.user_covers_room(request.user, room):
        raise Http404
    return room


def _room_location_or_404_in_domain(request: HttpRequest, pk: int) -> RoomLocation:
    room_location = get_object_or_404(
        RoomLocation.objects.select_related("room__warehouse").filter(is_active=True),
        pk=pk,
    )
    if not RoomDomainPolicy.user_covers_room(request.user, room_location.room):
        raise Http404
    return room_location


def _report(request: HttpRequest, exc: InventoryValidationError) -> None:
    for error in exc.errors:
        messages.error(request, error)


def _stock_rows(*, storage_location_ids: list[int]) -> list[ActiveInventory]:
    return list(
        ActiveInventory.objects.filter(storage_location_id__in=storage_location_ids)
        .select_related("part")
        .order_by("storage_location_id", "part__part_number")
    )


# --------------------------------------------------------------------------- #
# Warehouses
# --------------------------------------------------------------------------- #


@require_http_methods(["GET"])
def warehouse_index(request: HttpRequest) -> HttpResponse:
    warehouses = Warehouse.objects.filter(is_active=True).select_related("division").order_by("name")
    return render(request, f"{TEMPLATE_DIR}/warehouses/index.html", {"warehouses": warehouses})


@require_http_methods(["GET"])
def warehouse_detail(request: HttpRequest, pk: int) -> HttpResponse:
    get_object_or_404(Warehouse.objects.filter(is_active=True), pk=pk)
    struct = WarehouseStruct.load(warehouse_id=pk)

    layouts = {
        attachment.id: attachment
        for attachment in _attachments_for(
            [r.current_layout_id for r in struct.rooms if r.current_layout_id]
        )
    }
    rooms = []
    for room in struct.rooms:
        thumbnail_svg = None
        attachment = layouts.get(room.current_layout_id)
        if attachment is not None:
            raw_svg = RoomSvgAdapter.read_svg_from_attachment(attachment)
            thumbnail_svg = (
                RoomSvgAdapter.normalize_viewbox(raw_svg) if raw_svg else None
            )
        rooms.append({"room": room, "thumbnail_svg": thumbnail_svg})

    return render(
        request,
        f"{TEMPLATE_DIR}/warehouses/detail.html",
        {"warehouse": struct, "rooms": rooms},
    )


def _attachments_for(attachment_ids: list[int]):
    from app.events.models import Attachment

    if not attachment_ids:
        return []
    return list(
        Attachment.objects.filter(id__in=attachment_ids, deleted_at__isnull=True).select_related(
            "file"
        )
    )


# --------------------------------------------------------------------------- #
# Room detail / spatial map (Tier 1 -> Tier 2)
# --------------------------------------------------------------------------- #


@require_http_methods(["GET"])
def room_detail(request: HttpRequest, pk: int) -> HttpResponse:
    room = _room_or_404_in_domain(request, pk)
    struct = RoomStruct.load(room_id=pk)

    loc_code = request.GET.get("loc", "").strip()
    drawer_context = _location_drawer_context(struct, loc_code) if loc_code else None

    if request.GET.get("format") == "htmx-location-drawer":
        return render(
            request,
            f"{TEMPLATE_DIR}/rooms/_location_drawer.html",
            {"drawer": drawer_context, "loc_code": loc_code},
        )

    map_svg = None
    raw_svg = RoomSvgAdapter.read_svg_from_attachment(room.current_layout)
    if raw_svg is not None:
        shape_targets = {rl.display_code: rl.display_code for rl in struct.room_locations}
        map_svg = RoomSvgAdapter.render_interactive_svg(
            raw_svg,
            group_label=ROOM_SVG_GROUP_LABEL,
            shape_targets=shape_targets,
            canonical_url=reverse("inventory_room_detail", kwargs={"pk": pk}),
            format_param="htmx-location-drawer",
            drawer_target="location-detail-drawer",
        )

    return render(
        request,
        f"{TEMPLATE_DIR}/rooms/detail.html",
        {
            "room": struct,
            "map_svg": map_svg,
            "loc_code": loc_code,
            "drawer": drawer_context,
        },
    )


def _location_drawer_context(struct: RoomStruct, loc_code: str) -> dict:
    room_location_slice = next(
        (rl for rl in struct.room_locations if rl.display_code == loc_code), None
    )
    if room_location_slice is None:
        return {"loc_code": loc_code, "not_found": True}

    single_storage_location = None
    if not room_location_slice.has_layout and len(room_location_slice.storage_locations) == 1:
        single_storage_location = room_location_slice.storage_locations[0]

    stock = []
    if single_storage_location is not None:
        stock = _stock_rows(storage_location_ids=[single_storage_location.storage_location_id])

    return {
        "room_id": struct.room_id,
        "room_location": room_location_slice,
        "single_storage_location": single_storage_location,
        "stock": stock,
    }


# --------------------------------------------------------------------------- #
# Room-tier layout builder (upload + reconciliation)
# --------------------------------------------------------------------------- #


@require_http_methods(["GET", "POST"])
def room_layout(request: HttpRequest, pk: int) -> HttpResponse:
    room = _room_or_404_in_domain(request, pk)
    draft_key = f"room_layout_reconciliation_{pk}"

    if request.method == "POST":
        return _room_layout_post(request, room, draft_key)

    struct = RoomStruct.load(room_id=pk)
    return render(
        request,
        f"{TEMPLATE_DIR}/rooms/layout.html",
        {"room": struct, "reconciliation": request.session.get(draft_key)},
    )


def _room_layout_post(request: HttpRequest, room: Room, draft_key: str) -> HttpResponse:
    action = request.POST.get("action", "")
    back = reverse("inventory_room_layout", kwargs={"pk": room.pk})
    context = TopographyContext(room.warehouse_id)

    try:
        if action == "upload":
            uploaded = request.FILES.get("svg_file")
            if uploaded is None:
                messages.error(request, "Choose an SVG file to upload.")
                return redirect(back)
            reconciliation = context.upload_room_layout(
                room_id=room.pk, uploaded_file=uploaded, actor=request.user
            )
            request.session[draft_key] = reconciliation.to_dict()
            request.session.modified = True
            messages.success(request, "Layout uploaded. Review the reconciliation below.")
        elif action == "create_selected":
            selected = request.POST.getlist("unmatched_code")
            coordinates = [tuple(code.split("-", 1)) for code in selected if "-" in code]
            created = context.bulk_add_room_locations(
                room_id=room.pk, coordinates=coordinates, actor=request.user
            )
            messages.success(request, f"Created {len(created)} location(s).")
            request.session.pop(draft_key, None)
        elif action == "dismiss":
            request.session.pop(draft_key, None)
        else:
            messages.error(request, "Unrecognised action.")
    except InventoryValidationError as exc:
        _report(request, exc)

    return redirect(back)


# --------------------------------------------------------------------------- #
# RoomLocation Z-picker (Tier 2 -> Tier 3)
# --------------------------------------------------------------------------- #


@require_http_methods(["GET"])
def room_location_detail(request: HttpRequest, pk: int) -> HttpResponse:
    room_location = _room_location_or_404_in_domain(request, pk)
    storage_locations = list(
        room_location.storage_locations.filter(is_active=True).order_by("atomic_coord")
    )

    atomic_code = request.GET.get("loc", "").strip()
    drawer_context = (
        _storage_drawer_context(room_location, storage_locations, atomic_code)
        if atomic_code
        else None
    )

    if request.GET.get("format") == "htmx-storage-drawer":
        return render(
            request,
            f"{TEMPLATE_DIR}/room_locations/_storage_drawer.html",
            {"drawer": drawer_context, "loc_code": atomic_code},
        )

    map_svg = None
    raw_svg = RoomSvgAdapter.read_svg_from_attachment(room_location.current_layout)
    if raw_svg is not None:
        shape_targets = {loc.atomic_coord: loc.atomic_coord for loc in storage_locations}
        map_svg = RoomSvgAdapter.render_interactive_svg(
            raw_svg,
            group_label=ROOM_LOCATION_SVG_GROUP_LABEL,
            shape_targets=shape_targets,
            canonical_url=reverse("inventory_room_location_detail", kwargs={"pk": pk}),
            format_param="htmx-storage-drawer",
            drawer_target="storage-detail-drawer",
        )

    return render(
        request,
        f"{TEMPLATE_DIR}/room_locations/detail.html",
        {
            "room_location": room_location,
            "storage_locations": storage_locations,
            "map_svg": map_svg,
            "loc_code": atomic_code,
            "drawer": drawer_context,
        },
    )


def _storage_drawer_context(room_location, storage_locations, atomic_code: str) -> dict:
    storage_location = next(
        (loc for loc in storage_locations if loc.atomic_coord == atomic_code), None
    )
    if storage_location is None:
        return {"loc_code": atomic_code, "not_found": True}
    stock = _stock_rows(storage_location_ids=[storage_location.pk])
    return {
        "room_location": room_location,
        "storage_location": storage_location,
        "stock": stock,
    }


# --------------------------------------------------------------------------- #
# RoomLocation-tier layout builder (upload + reconciliation)
# --------------------------------------------------------------------------- #


@require_http_methods(["GET", "POST"])
def room_location_layout(request: HttpRequest, pk: int) -> HttpResponse:
    room_location = _room_location_or_404_in_domain(request, pk)
    draft_key = f"room_location_layout_reconciliation_{pk}"

    if request.method == "POST":
        return _room_location_layout_post(request, room_location, draft_key)

    storage_locations = list(
        room_location.storage_locations.filter(is_active=True).order_by("atomic_coord")
    )
    return render(
        request,
        f"{TEMPLATE_DIR}/room_locations/layout.html",
        {
            "room_location": room_location,
            "storage_locations": storage_locations,
            "reconciliation": request.session.get(draft_key),
        },
    )


def _room_location_layout_post(request: HttpRequest, room_location: RoomLocation, draft_key: str) -> HttpResponse:
    action = request.POST.get("action", "")
    back = reverse("inventory_room_location_layout", kwargs={"pk": room_location.pk})
    context = TopographyContext(room_location.room.warehouse_id)

    try:
        if action == "upload":
            uploaded = request.FILES.get("svg_file")
            if uploaded is None:
                messages.error(request, "Choose an SVG file to upload.")
                return redirect(back)
            reconciliation = context.upload_room_location_layout(
                room_location_id=room_location.pk, uploaded_file=uploaded, actor=request.user
            )
            request.session[draft_key] = reconciliation.to_dict()
            request.session.modified = True
            messages.success(request, "Layout uploaded. Review the reconciliation below.")
        elif action == "create_selected":
            selected = request.POST.getlist("unmatched_code")
            created = context.bulk_add_storage_locations(
                room_location_id=room_location.pk, atomic_coords=selected, actor=request.user
            )
            messages.success(request, f"Created {len(created)} location(s).")
            request.session.pop(draft_key, None)
        elif action == "dismiss":
            request.session.pop(draft_key, None)
        else:
            messages.error(request, "Unrecognised action.")
    except InventoryValidationError as exc:
        _report(request, exc)

    return redirect(back)


@require_http_methods(["GET"])
def storage_location_search(request: HttpRequest) -> HttpResponse:
    domain_ids = accessible_domain_ids(request)
    visible_room_ids = domain_visible_room_ids(domain_ids=domain_ids)

    qs = StorageLocation.objects.filter(
        room_location__room_id__in=visible_room_ids, is_active=True
    ).select_related("room_location__room__warehouse")

    warehouse_id = request.GET.get("warehouse_id", "").strip()
    if warehouse_id:
        qs = qs.filter(room_location__room__warehouse_id=warehouse_id)

    room_id = request.GET.get("room_id", "").strip()
    if room_id:
        qs = qs.filter(room_location__room_id=room_id)

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(display_code__icontains=q)

    qs = qs.order_by("display_code")[:50]

    results = [
        f'<li data-value="{loc.id}">{loc.display_code} <span class="has-text-grey is-size-7">({loc.room_location.room.warehouse.code} / {loc.room_location.room.room_name})</span></li>'
        for loc in qs
    ]

    if not results:
        return HttpResponse('<li class="is-disabled">No matching locations.</li>')
    return HttpResponse("\n".join(results))

