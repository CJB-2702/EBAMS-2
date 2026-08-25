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
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.inventory.control_layer.destination_picker import DestinationPickerContext
from app.inventory.control_layer.errors import InventoryValidationError
from app.inventory.control_layer.movement_context import MovementContext
from app.inventory.models.movements.enums import MovementType
from app.inventory.models.movements.part_movement import PartMovement
from app.inventory.models.stock.active_inventory import ActiveInventory
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

            original_quantity = balance.quantity_on_hand
            movement = MovementContext.move(
                active_inventory_id=balance.pk,
                to_warehouse_id=warehouse_id,
                to_storage_location_id=storage_location_id,
                quantity=quantity,
                actor=request.user,
                notes=request.POST.get("notes", ""),
            )

            # Build message based on whether it's a full or partial move
            if quantity == original_quantity:
                # Full move
                dest_location = movement.to_storage_location
                if dest_location:
                    msg = f"Stock moved to {dest_location.display_code}."
                else:
                    msg = f"Stock moved to {movement.to_room.room_name}."
            else:
                # Partial move
                remaining_qty = original_quantity - quantity
                dest_location = movement.to_storage_location
                from_location = balance.storage_location

                if dest_location:
                    dest_name = dest_location.display_code
                else:
                    dest_name = movement.to_room.room_name

                from_name = from_location.display_code if from_location else balance.room.room_name
                msg = f"{quantity} stock moved to {dest_name}, {remaining_qty} stock remains at {from_name}."

            messages.success(request, msg)
            return redirect(reverse("active_inventory_index"))
        except InventoryValidationError as exc:
            _report(request, exc)
        except Exception as exc:  # StockLedgerManager/guard errors surface as text
            messages.error(request, str(exc))
        return redirect(f"{reverse('inventory_movement_portal')}?stock={stock_id}")

    destination = DestinationPickerContext.build_state(
        request, source_warehouse_id=balance.warehouse_id, part_id=balance.part_id
    )

    if request.GET.get("format") == "htmx-putaway-target":
        fragment_state = DestinationPickerContext.build_location_table_fragment(
            request, room_locations=destination["room_locations"], loc=destination["loc"]
        )
        return render(
            request,
            f"{TEMPLATE_DIR}/_destination_target.html",
            fragment_state,
        )

    context = {"stock_id": stock_id, "balance": balance, "can_move": can_move(request)}
    context.update(destination)
    return render(request, f"{TEMPLATE_DIR}/create.html", context)


# --------------------------------------------------------------------------- #
# Putaway worklist — batch relocation of unassigned Intake Room stock.
#
# Entirely static-reload driven (no HTMX, no client-side state sync): every
# control is a plain link or an auto-submitting <select>, and warehouse_id /
# room_id / sloc GET params are the single source of truth rendered into
# every control on the page each request. Checked stock rows would normally
# be lost across those reloads, so they're mirrored into the session instead
# — the browse form re-syncs the session on every explicit checkbox/selector
# submission (`sync=1`), while pure destination-card link navigation leaves
# the session (and therefore the checked rows) untouched.
# --------------------------------------------------------------------------- #

SESSION_SELECTED_ROWS_KEY = "putaway_selected_row_ids"
SESSION_SELECTED_WAREHOUSE_KEY = "putaway_selected_rows_warehouse_id"


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
            warehouse_id = _int_or_none(request.POST.get("warehouse_id", ""))
            return redirect(f"{reverse('inventory_putaway_worklist')}?warehouse_id={warehouse_id or ''}")
        row_ids = request.POST.getlist("row_id")
        sloc = _int_or_none(request.POST.get("storage_location_id", ""))
        warehouse_id = _int_or_none(request.POST.get("warehouse_id", ""))
        moved = 0
        errors = []
        moved_details = []
        for row_id in row_ids:
            try:
                balance = ActiveInventory.objects.select_related(
                    "part", "storage_location"
                ).get(pk=int(row_id))
                movement = MovementContext.putaway(
                    active_inventory_id=int(row_id),
                    to_storage_location_id=sloc,
                    actor=request.user,
                )
                moved_details.append({
                    "quantity": movement.quantity,
                    "part_number": balance.part.part_number,
                    "dest_location": movement.to_storage_location.display_code if movement.to_storage_location else "—",
                })
                moved += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(str(exc))
        if moved:
            if moved == 1:
                detail = moved_details[0]
                msg = f"Put away {detail['quantity']} × {detail['part_number']} to {detail['dest_location']}."
            else:
                msg = f"Put away {moved} row(s)."
            messages.success(request, msg)
        for error in errors:
            messages.error(request, error)

        # Moved rows are no longer unassigned — drop the stale session selection.
        request.session[SESSION_SELECTED_ROWS_KEY] = []

        # Preserve destination selection state on redirect for "continue putting away"
        redirect_url = f"{reverse('inventory_putaway_worklist')}?warehouse_id={warehouse_id or ''}"
        room_id = _int_or_none(request.POST.get("room_id", ""))
        if room_id:
            redirect_url += f"&room_id={room_id}"
        if sloc:
            redirect_url += f"&sloc={sloc}"
        return redirect(redirect_url)

    # GET — reconcile the session-backed row selection against the current
    # warehouse. A warehouse switch invalidates it outright (the checked
    # pks belong to a different unassigned-stock list); an explicit
    # `sync=1` submission (the browse form, on any checkbox/selector
    # change) replaces it with whatever was just checked; anything else
    # (a plain destination-card link click) leaves it alone.
    if selected_warehouse is None:
        request.session.pop(SESSION_SELECTED_ROWS_KEY, None)
        request.session.pop(SESSION_SELECTED_WAREHOUSE_KEY, None)
        selected_row_ids: set[int] = set()
    else:
        if request.session.get(SESSION_SELECTED_WAREHOUSE_KEY) != selected_warehouse.pk:
            request.session[SESSION_SELECTED_WAREHOUSE_KEY] = selected_warehouse.pk
            request.session[SESSION_SELECTED_ROWS_KEY] = []
        elif "sync" in request.GET:
            request.session[SESSION_SELECTED_ROWS_KEY] = [
                int(v) for v in request.GET.getlist("row_id") if v.isdigit()
            ]
        selected_row_ids = set(request.session.get(SESSION_SELECTED_ROWS_KEY, []))

    unassigned_rows = []
    if selected_warehouse is not None:
        unassigned_rows = list(
            ActiveInventory.objects.filter(
                warehouse=selected_warehouse, is_unassigned=True
            )
            .select_related("part")
            .order_by("part__part_number")
        )
        selected_row_ids &= {row.pk for row in unassigned_rows}
        request.session[SESSION_SELECTED_ROWS_KEY] = sorted(selected_row_ids)
        for row in unassigned_rows:
            row.is_checked = row.pk in selected_row_ids

    destination = (
        DestinationPickerContext.build_state(request, source_warehouse_id=selected_warehouse.pk)
        if selected_warehouse is not None
        else {
            "warehouses": warehouses,
            "warehouse_id": warehouse_id,
            "selected_warehouse": None,
            "crosses_warehouse": False,
            "rooms": [],
            "room_id": None,
            "selected_room": None,
            "room_locations": [],
            "map_svg": None,
            "loc": "",
            "sloc": None,
            "selected_storage_location": None,
        }
    )

    context = {
        "warehouses": warehouses,
        "warehouse_id": warehouse_id,
        "selected_warehouse": selected_warehouse,
        "unassigned_rows": unassigned_rows,
        "selected_row_ids": sorted(selected_row_ids),
        "can_move": can_move(request),
    }
    context.update(destination)
    return render(request, f"{TEMPLATE_DIR}/putaway.html", context)


# --------------------------------------------------------------------------- #
# Movements ledger.
# --------------------------------------------------------------------------- #


@require_http_methods(["GET"])
def bulk_movements_portal(request: HttpRequest) -> HttpResponse:
    return render(request, f"{TEMPLATE_DIR}/bulk_coming_soon.html")


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
