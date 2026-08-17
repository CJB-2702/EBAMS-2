"""Phase 6 — Movement portal (single-stock relocation, `?stock=<id>`),
Putaway worklist (batch relocation of unassigned Intake Room stock), and the
Movements ledger (list/detail).

Destination selection state lives entirely in GET query params
(`warehouse_id`, `room_id`, `loc`, `sloc`) — F5-safe, one canonical URL per
route, no bespoke drawer routes (FD-17). The Room-tier SVG map is offered as
a `format=htmx-putaway-target` enhancement on top of a plain, always-rendered
location list, which is the no-JS fallback and the thing that actually makes
the flow F5-safe end to end.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.inventory.control_layer.adapters.room_svg_adapter import RoomSvgAdapter
from app.inventory.control_layer.constants import ROOM_SVG_GROUP_LABEL
from app.inventory.control_layer.errors import InventoryValidationError
from app.inventory.control_layer.movement_context import MovementContext
from app.inventory.models.movements.enums import MovementType
from app.inventory.models.movements.part_movement import PartMovement
from app.inventory.models.stock.active_inventory import ActiveInventory
from app.inventory.models.topography.room import Room
from app.inventory.models.topography.warehouse import Warehouse
from app.inventory.presentation_layer.search.movement_search import MovementSearch
from app.inventory.presentation_layer.tools.inventory_access import (
    accessible_domain_ids,
    can_move,
)

TEMPLATE_DIR = "inventory/movements"
PAGE_SIZE = 50


def _decimal(raw) -> Decimal | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def _int_or_none(raw) -> int | None:
    raw = (raw or "").strip()
    return int(raw) if raw.isdigit() else None


def _report(request: HttpRequest, exc: InventoryValidationError) -> None:
    for error in exc.errors:
        messages.error(request, error)


# --------------------------------------------------------------------------- #
# Destination selector — shared between the movement portal and the putaway
# worklist template fragments.
# --------------------------------------------------------------------------- #


def _destination_state(
    request: HttpRequest, *, source_warehouse_id: int, part_id: int | None = None
) -> dict:
    warehouse_id = _int_or_none(request.GET.get("warehouse_id", ""))
    room_id = _int_or_none(request.GET.get("room_id", ""))
    loc = request.GET.get("loc", "").strip()
    sloc = _int_or_none(request.GET.get("sloc", ""))

    warehouses = Warehouse.objects.filter(is_active=True).order_by("name")
    selected_warehouse = warehouses.filter(pk=warehouse_id).first() if warehouse_id else None
    crosses_warehouse = bool(
        selected_warehouse and selected_warehouse.pk != source_warehouse_id
    )

    rooms = []
    selected_room = None
    room_locations = []
    map_svg = None
    selected_storage_location = None

    if selected_warehouse and not crosses_warehouse:
        rooms = list(
            Room.objects.filter(warehouse=selected_warehouse, is_active=True)
            .exclude(is_intake_room=True)
            .select_related("current_layout")
            .order_by("room_name")
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


def _destination_target_fragment(request: HttpRequest, *, room_locations, loc: str) -> HttpResponse:
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
    return render(
        request,
        f"{TEMPLATE_DIR}/_destination_target.html",
        {
            "room_location": room_location,
            "storage_locations": storage_locations,
            "base_qs": base_qs,
        },
    )


# --------------------------------------------------------------------------- #
# Movement portal — single-stock relocation.
# --------------------------------------------------------------------------- #


@require_http_methods(["GET", "POST"])
def movement_portal(request: HttpRequest) -> HttpResponse:
    stock_id = request.GET.get("stock", "").strip() or request.POST.get("stock", "").strip()
    if not stock_id:
        messages.error(request, "Select a stock row to move first.")
        return redirect(reverse("active_inventory_index"))

    balance = get_object_or_404(
        ActiveInventory.objects.select_related("warehouse", "room", "storage_location", "part"),
        pk=stock_id,
    )

    if request.method == "POST":
        if not can_move(request):
            messages.error(request, "You do not have permission to move stock.")
            return redirect(f"{reverse('inventory_movement_portal')}?stock={stock_id}")
        try:
            warehouse_id = int(request.POST.get("warehouse_id", "0") or 0)
            storage_location_id = _int_or_none(request.POST.get("storage_location_id", ""))
            quantity = _decimal(request.POST.get("quantity")) or balance.quantity_on_hand
            if not warehouse_id:
                raise InventoryValidationError(["Choose a destination warehouse."])
            MovementContext.move(
                active_inventory_id=balance.pk,
                to_warehouse_id=warehouse_id,
                to_storage_location_id=storage_location_id,
                quantity=quantity,
                actor=request.user,
                notes=request.POST.get("notes", ""),
            )
            messages.success(request, "Stock moved.")
            return redirect(reverse("active_inventory_index"))
        except InventoryValidationError as exc:
            _report(request, exc)
        except Exception as exc:  # StockLedgerManager/guard errors surface as text
            messages.error(request, str(exc))
        return redirect(f"{reverse('inventory_movement_portal')}?stock={stock_id}")

    destination = _destination_state(
        request, source_warehouse_id=balance.warehouse_id, part_id=balance.part_id
    )

    if request.GET.get("format") == "htmx-putaway-target":
        return _destination_target_fragment(
            request, room_locations=destination["room_locations"], loc=destination["loc"]
        )

    context = {"stock_id": stock_id, "balance": balance, "can_move": can_move(request)}
    context.update(destination)
    return render(request, f"{TEMPLATE_DIR}/create.html", context)


# --------------------------------------------------------------------------- #
# Putaway worklist — batch relocation of unassigned Intake Room stock.
# --------------------------------------------------------------------------- #


@require_http_methods(["GET", "POST"])
def putaway_worklist(request: HttpRequest) -> HttpResponse:
    domain_ids = accessible_domain_ids(request)
    warehouses = Warehouse.objects.filter(is_active=True).order_by("name")
    warehouse_id = _int_or_none(request.GET.get("warehouse_id", "")) or _int_or_none(
        request.POST.get("warehouse_id", "")
    )
    selected_warehouse = warehouses.filter(pk=warehouse_id).first() if warehouse_id else None

    if request.method == "POST":
        if not can_move(request):
            messages.error(request, "You do not have permission to move stock.")
            return redirect(f"{reverse('inventory_putaway_worklist')}?warehouse_id={warehouse_id or ''}")
        row_ids = request.POST.getlist("row_id")
        sloc = _int_or_none(request.POST.get("storage_location_id", ""))
        moved = 0
        errors = []
        for row_id in row_ids:
            try:
                MovementContext.putaway(
                    active_inventory_id=int(row_id),
                    to_storage_location_id=sloc,
                    actor=request.user,
                )
                moved += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(str(exc))
        if moved:
            messages.success(request, f"Put away {moved} row(s).")
        for error in errors:
            messages.error(request, error)
        return redirect(f"{reverse('inventory_putaway_worklist')}?warehouse_id={warehouse_id or ''}")

    unassigned_rows = []
    if selected_warehouse is not None:
        unassigned_rows = list(
            ActiveInventory.objects.filter(
                warehouse=selected_warehouse, is_unassigned=True
            )
            .select_related("part")
            .order_by("part__part_number")
        )

    destination = (
        _destination_state(request, source_warehouse_id=selected_warehouse.pk)
        if selected_warehouse is not None
        else {
            "rooms": [], "room_id": None, "selected_room": None,
            "room_locations": [], "map_svg": None, "loc": "", "sloc": None,
            "selected_storage_location": None,
        }
    )

    if request.GET.get("format") == "htmx-putaway-target":
        return _destination_target_fragment(
            request, room_locations=destination.get("room_locations", []),
            loc=destination.get("loc", ""),
        )

    context = {
        "warehouses": warehouses,
        "warehouse_id": warehouse_id,
        "selected_warehouse": selected_warehouse,
        "unassigned_rows": unassigned_rows,
        "can_move": can_move(request),
    }
    context.update(destination)
    return render(request, f"{TEMPLATE_DIR}/putaway.html", context)


# --------------------------------------------------------------------------- #
# Movements ledger.
# --------------------------------------------------------------------------- #


@require_http_methods(["GET"])
def movements_index(request: HttpRequest) -> HttpResponse:
    domain_ids = accessible_domain_ids(request)
    filters = {
        "movement_type": request.GET.get("movement_type", "").strip(),
        "part_q": request.GET.get("part_q", "").strip(),
        "warehouse_id": request.GET.get("warehouse_id", "").strip(),
    }
    qs = MovementSearch.index_list(domain_ids=domain_ids, **filters)
    paginator = Paginator(qs, PAGE_SIZE)
    page = paginator.get_page(request.GET.get("page", "1"))

    context = {
        "page": page,
        "rows": page.object_list,
        "filters": filters,
        "movement_types": MovementType.choices,
    }
    if request.GET.get("format") == "htmx-search-results":
        return render(request, f"{TEMPLATE_DIR}/_results_card.html", context)
    return render(request, f"{TEMPLATE_DIR}/index.html", context)


@require_http_methods(["GET"])
def movement_detail(request: HttpRequest, pk: int) -> HttpResponse:
    movement = get_object_or_404(MovementContext.list_movements(), pk=pk)
    return render(request, f"{TEMPLATE_DIR}/detail.html", {"movement": movement})
