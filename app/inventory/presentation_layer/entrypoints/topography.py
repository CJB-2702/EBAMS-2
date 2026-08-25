"""Warehouse/Room/RoomLocation topography pages and the three-tier
SVG spatial engine (FD-29): warehouse index/detail, the Room-tier spatial map
+ layout builder, and the RoomLocation-tier Z-picker + its own layout
builder. Every drawer/map fragment is served off its own canonical detail
URL with a `format=` query parameter (FD-17) — no bespoke drawer routes.

Row-level access: a Room/RoomLocation outside the user's effective data
domains 404s (`RoomDomainPolicy.user_covers_room`), mirroring D5 elsewhere
in the project.

The storeroom-designer port (legacy `/inventory/storeroom/*`) lands here
rather than as a new sub-app: legacy `Storeroom` is this app's `Room`,
legacy `Location` is `RoomLocation`, legacy `Bin` is `StorageLocation`.
The legacy `/build` page splits along the read/write seam already in
place — the map lives on the detail route, every mutation lives on the
`/layout/` builder route. Warehouses are never hard-deleted; `Retire`
flips `is_active` and the index can list retired rows back.
"""

from __future__ import annotations

from django.contrib import messages
from django.db.models import Count, Q
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.inventory.control_layer.adapters.room_svg_adapter import RoomSvgAdapter
from app.inventory.control_layer.adapters.topography_form_adaptor import (
    RoomFormAdaptor,
    RoomLocationFormAdaptor,
    StorageLocationFormAdaptor,
    WarehouseFormAdaptor,
)
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
from app.administration.models import Division, Domain
from app.inventory.presentation_layer.search.active_inventory_search import (
    domain_visible_room_ids,
)
from app.inventory.presentation_layer.tools.inventory_access import (
    accessible_domain_ids,
    can_manage_topography,
    require_manage_topography,
)

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
    """`?show=active` (default) / `inactive` / `all`. Retired warehouses stay
    listable because retirement is reversible — there is no hard delete."""
    show = request.GET.get("show", "active")
    qs = Warehouse.objects.select_related("division").order_by("name")
    if show == "active":
        qs = qs.filter(is_active=True)
    elif show == "inactive":
        qs = qs.filter(is_active=False)

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))

    warehouses = list(qs.annotate(room_count=Count("rooms", distinct=True)))
    return render(
        request,
        f"{TEMPLATE_DIR}/warehouses/index.html",
        {
            "warehouses": warehouses,
            "show": show,
            "q": q,
            "can_manage": can_manage_topography(request),
        },
    )


@require_http_methods(["GET", "POST"])
def warehouse_create(request: HttpRequest) -> HttpResponse:
    require_manage_topography(request)

    if request.method == "POST":
        data = WarehouseFormAdaptor.from_post(request.POST)
        try:
            if not data["name"] or not data["code"] or not data["division_id"]:
                raise InventoryValidationError(
                    ["Name, code, and division are all required."]
                )
            context = TopographyContext.create_warehouse(
                name=data["name"],
                code=data["code"],
                division_id=int(data["division_id"]),
                address=data["address"],
                domain_ids=[int(d) for d in data["domain_ids"]],
                actor=request.user,
            )
        except InventoryValidationError as exc:
            _report(request, exc)
            return render(
                request,
                f"{TEMPLATE_DIR}/warehouses/form.html",
                _warehouse_form_context(warehouse=None, data=data),
            )
        messages.success(
            request,
            f"Warehouse '{data['name']}' created with its protected Intake Room.",
        )
        return redirect(
            reverse("inventory_warehouse_detail", kwargs={"pk": context.warehouse_id})
        )

    return render(
        request,
        f"{TEMPLATE_DIR}/warehouses/form.html",
        _warehouse_form_context(warehouse=None, data=None),
    )


@require_http_methods(["GET", "POST"])
def warehouse_edit(request: HttpRequest, pk: int) -> HttpResponse:
    """Edit, retire, and un-retire in one surface. `Retire` is a soft delete
    (`is_active = False`) — the legacy designer's hard `db.session.delete()`
    of a storeroom and its whole location/bin tree is deliberately not ported.
    """
    require_manage_topography(request)
    warehouse = get_object_or_404(Warehouse, pk=pk)
    context = TopographyContext(warehouse.pk)

    if request.method == "POST":
        action = request.POST.get("action", "save")
        try:
            if action == "retire":
                context.deactivate_warehouse(actor=request.user)
                messages.success(request, f"Warehouse '{warehouse.name}' retired.")
                return redirect(reverse("inventory_warehouse_index"))
            if action == "reactivate":
                context.reactivate_warehouse(actor=request.user)
                messages.success(request, f"Warehouse '{warehouse.name}' reactivated.")
                return redirect(
                    reverse("inventory_warehouse_detail", kwargs={"pk": warehouse.pk})
                )

            data = WarehouseFormAdaptor.from_post(request.POST)
            if not data["name"] or not data["code"]:
                raise InventoryValidationError(["Name and code are both required."])
            context.update_warehouse(
                name=data["name"],
                code=data["code"],
                address=data["address"],
                domain_ids=[int(d) for d in data["domain_ids"]],
                actor=request.user,
            )
        except InventoryValidationError as exc:
            _report(request, exc)
            return render(
                request,
                f"{TEMPLATE_DIR}/warehouses/form.html",
                _warehouse_form_context(
                    warehouse=warehouse, data=WarehouseFormAdaptor.from_post(request.POST)
                ),
            )
        messages.success(request, f"Warehouse '{warehouse.name}' updated.")
        return redirect(reverse("inventory_warehouse_detail", kwargs={"pk": warehouse.pk}))

    return render(
        request,
        f"{TEMPLATE_DIR}/warehouses/form.html",
        _warehouse_form_context(warehouse=warehouse, data=None),
    )


def _warehouse_form_context(*, warehouse: Warehouse | None, data: dict | None) -> dict:
    """Re-renders the form with the operator's own POST values on failure,
    rather than silently reverting to the stored row."""
    if data is not None:
        selected_domain_ids = [int(d) for d in data["domain_ids"]]
        if data["division_id"]:
            division_id = int(data["division_id"])
        else:
            division_id = warehouse.division_id if warehouse is not None else None
        values = {
            "name": data["name"],
            "code": data["code"],
            "address": data["address"],
        }
    elif warehouse is not None:
        selected_domain_ids = list(warehouse.domains.values_list("id", flat=True))
        division_id = warehouse.division_id
        values = {
            "name": warehouse.name,
            "code": warehouse.code,
            "address": warehouse.address,
        }
    else:
        selected_domain_ids, division_id, values = [], None, {
            "name": "", "code": "", "address": "",
        }

    return {
        "warehouse": warehouse,
        "values": values,
        "divisions": Division.objects.order_by("name"),
        "domains": Domain.objects.order_by("name"),
        "selected_domain_ids": selected_domain_ids,
        "selected_division_id": division_id,
    }


@require_http_methods(["GET", "POST"])
def warehouse_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Retired warehouses still render here so they can be inspected and
    un-retired; only the room-add form is hidden while retired."""
    warehouse = get_object_or_404(Warehouse, pk=pk)

    if request.method == "POST":
        return _warehouse_detail_post(request, warehouse)

    struct = WarehouseStruct.load(warehouse_id=pk)

    layouts = {
        attachment.id: attachment
        for attachment in _attachments_for(
            [r.current_layout_id for r in struct.rooms if r.current_layout_id]
        )
    }
    rooms, retired_rooms = [], []
    for room in struct.rooms:
        if not room.is_active:
            retired_rooms.append(room)
            continue
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
        {
            "warehouse": struct,
            "rooms": rooms,
            "retired_rooms": retired_rooms,
            "can_manage": can_manage_topography(request),
        },
    )


def _warehouse_detail_post(request: HttpRequest, warehouse: Warehouse) -> HttpResponse:
    require_manage_topography(request)
    back = reverse("inventory_warehouse_detail", kwargs={"pk": warehouse.pk})
    context = TopographyContext(warehouse.pk)
    try:
        if request.POST.get("action") == "add_room":
            data = RoomFormAdaptor.from_post(request.POST)
            room = context.add_room(
                room_name=data["room_name"],
                description=data["description"],
                excluded_domain_ids=[int(d) for d in data["excluded_domain_ids"]],
                actor=request.user,
            )
            messages.success(request, f"Room '{room.room_name}' added.")
            return redirect(reverse("inventory_room_layout", kwargs={"pk": room.pk}))
        messages.error(request, "Unrecognised action.")
    except InventoryValidationError as exc:
        _report(request, exc)
    return redirect(back)


@require_http_methods(["GET", "POST"])
def room_edit(request: HttpRequest, pk: int) -> HttpResponse:
    """Rename/describe a room, or retire it. `RoomPolicy` refuses both on the
    protected Intake Room and refuses retirement while the room still holds
    locations or stock."""
    require_manage_topography(request)
    room = get_object_or_404(Room.objects.select_related("warehouse"), pk=pk)
    if not RoomDomainPolicy.user_covers_room(request.user, room):
        raise Http404
    context = TopographyContext(room.warehouse_id)

    if request.method == "POST":
        try:
            action = request.POST.get("action", "save")
            if action == "retire":
                context.deactivate_room(room=room, actor=request.user)
                messages.success(request, f"Room '{room.room_name}' retired.")
                return redirect(
                    reverse(
                        "inventory_warehouse_detail", kwargs={"pk": room.warehouse_id}
                    )
                )
            if action == "reactivate":
                context.reactivate_room(room=room, actor=request.user)
                messages.success(request, f"Room '{room.room_name}' reactivated.")
                return redirect(
                    reverse("inventory_room_detail", kwargs={"pk": room.pk})
                )
            data = RoomFormAdaptor.from_post(request.POST)
            context.update_room(
                room=room,
                room_name=data["room_name"],
                description=data["description"],
                excluded_domain_ids=[int(d) for d in data["excluded_domain_ids"]],
                actor=request.user,
            )
            messages.success(request, f"Room '{data['room_name']}' updated.")
            if not room.is_active:
                return redirect(
                    reverse(
                        "inventory_warehouse_detail", kwargs={"pk": room.warehouse_id}
                    )
                )
            return redirect(reverse("inventory_room_detail", kwargs={"pk": room.pk}))
        except InventoryValidationError as exc:
            _report(request, exc)

    return render(
        request,
        f"{TEMPLATE_DIR}/rooms/form.html",
        {
            "room": room,
            "domains": Domain.objects.order_by("name"),
            "excluded_domain_ids": list(
                room.excluded_domains.values_list("id", flat=True)
            ),
        },
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
            "can_manage": can_manage_topography(request),
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
    map_svg = None
    raw_svg = RoomSvgAdapter.read_svg_from_attachment(room.current_layout)
    if raw_svg is not None:
        map_svg = RoomSvgAdapter.normalize_viewbox(raw_svg)

    return render(
        request,
        f"{TEMPLATE_DIR}/rooms/layout.html",
        {
            "room": struct,
            "map_svg": map_svg,
            "stocked_codes": _stocked_room_location_codes(room),
            "reconciliation": request.session.get(draft_key),
            "can_manage": can_manage_topography(request),
        },
    )


def _stocked_room_location_codes(room: Room) -> set[str]:
    """XY codes with at least one stock row underneath — the builder greys out
    their Retire buttons instead of offering an action the guard will refuse."""
    return set(
        RoomLocation.objects.filter(
            room=room, storage_locations__stock__isnull=False
        )
        .values_list("display_code", flat=True)
        .distinct()
    )


def _room_layout_post(request: HttpRequest, room: Room, draft_key: str) -> HttpResponse:
    require_manage_topography(request)
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
        elif action == "add_location":
            data = RoomLocationFormAdaptor.from_post(request.POST)
            location = context.add_room_location(
                room_id=room.pk,
                major_coord=data["major_coord"],
                minor_coord=data["minor_coord"],
                actor=request.user,
            )
            messages.success(request, f"Location '{location.display_code}' added.")
        elif action == "retire_location":
            location = get_object_or_404(
                RoomLocation, pk=request.POST.get("room_location_id"), room=room
            )
            context.deactivate_room_location(
                room_location=location, actor=request.user
            )
            messages.success(request, f"Location '{location.display_code}' retired.")
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
            "can_manage": can_manage_topography(request),
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
    map_svg = None
    raw_svg = RoomSvgAdapter.read_svg_from_attachment(room_location.current_layout)
    if raw_svg is not None:
        map_svg = RoomSvgAdapter.normalize_viewbox(raw_svg)

    stocked_ids = set(
        ActiveInventory.objects.filter(
            storage_location__room_location=room_location
        ).values_list("storage_location_id", flat=True)
    )
    return render(
        request,
        f"{TEMPLATE_DIR}/room_locations/layout.html",
        {
            "room_location": room_location,
            "storage_locations": [
                {"location": loc, "has_stock": loc.pk in stocked_ids}
                for loc in storage_locations
            ],
            "map_svg": map_svg,
            "reconciliation": request.session.get(draft_key),
            "can_manage": can_manage_topography(request),
        },
    )


def _room_location_layout_post(request: HttpRequest, room_location: RoomLocation, draft_key: str) -> HttpResponse:
    require_manage_topography(request)
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
            messages.success(request, f"Created {len(created)} bin(s).")
            request.session.pop(draft_key, None)
        elif action == "dismiss":
            request.session.pop(draft_key, None)
        elif action == "add_bin":
            data = StorageLocationFormAdaptor.from_post(request.POST)
            storage_location = context.add_storage_location(
                room_location_id=room_location.pk,
                atomic_coord=data["atomic_coord"],
                actor=request.user,
            )
            messages.success(request, f"Bin '{storage_location.display_code}' added.")
        elif action == "retire_bin":
            storage_location = get_object_or_404(
                StorageLocation,
                pk=request.POST.get("storage_location_id"),
                room_location=room_location,
            )
            context.deactivate_storage_location(
                storage_location=storage_location, actor=request.user
            )
            messages.success(request, f"Bin '{storage_location.display_code}' retired.")
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

