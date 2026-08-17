"""Phase 2 — the browsable stock list. Read-only this phase: movement,
issuance, and audit actions arrive in later phases and reuse this same
route's Actions column stub.
"""

from __future__ import annotations

from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect

from app.inventory.control_layer.audit_session_context import AuditSessionContext
from app.inventory.control_layer.errors import InventoryValidationError
from app.inventory.models.stock.active_inventory import ActiveInventory
from app.inventory.models.topography.warehouse import Warehouse
from app.inventory.models.topography.room import Room
from app.inventory.models.topography.storage_location import StorageLocation
from app.inventory.presentation_layer.search.active_inventory_search import (
    ActiveInventorySearch,
    domain_visible_room_ids,
)
from app.inventory.presentation_layer.tools.inventory_access import (
    accessible_domain_ids,
    require_audit,
    can_audit,
)
from decimal import Decimal, InvalidOperation

TEMPLATE_DIR = "inventory/active_inventory"
PAGE_SIZE = 50


@require_http_methods(["GET"])
def active_inventory_index(request: HttpRequest) -> HttpResponse:
    domain_ids = accessible_domain_ids(request)

    stale_days_raw = request.GET.get("stale_days", "").strip()
    stale_days = int(stale_days_raw) if stale_days_raw.isdigit() else None

    filters = {
        "warehouse_id": request.GET.get("warehouse_id", "").strip(),
        "room_id": request.GET.get("room_id", "").strip(),
        "storage_location_id": request.GET.get("storage_location_id", "").strip(),
        "part_q": request.GET.get("part_q", "").strip(),
        "serial": request.GET.get("serial", "").strip(),
        "stock_status": request.GET.get("stock_status", "").strip(),
        "stale_days": stale_days_raw,
        "unassigned_only": "on" if request.GET.get("unassigned_only", "") in ("on", "1", "true") else "",
        "low_stock_only": "on" if request.GET.get("low_stock_only", "") in ("on", "1", "true") else "",
        "out_of_stock_only": "on" if request.GET.get("out_of_stock_only", "") in ("on", "1", "true") else "",
        "has_stock_only": "on" if request.GET.get("has_stock_only", "") in ("on", "1", "true") else "",
    }

    qs = ActiveInventorySearch.index_list(
        domain_ids=domain_ids,
        warehouse_id=filters["warehouse_id"],
        room_id=filters["room_id"],
        storage_location_id=filters["storage_location_id"],
        part_q=filters["part_q"],
        serial=filters["serial"],
        stock_status=filters["stock_status"],
        low_stock_only=filters["low_stock_only"],
        out_of_stock_only=filters["out_of_stock_only"],
        has_stock_only=filters["has_stock_only"],
        unassigned_only=filters["unassigned_only"],
        stale_days=stale_days,
    )

    paginator = Paginator(qs, PAGE_SIZE)
    page = paginator.get_page(request.GET.get("page", "1"))

    visible_room_ids = domain_visible_room_ids(domain_ids=domain_ids)
    warehouses = Warehouse.objects.filter(is_active=True).order_by("name")
    
    rooms_qs = Room.objects.filter(id__in=visible_room_ids, is_active=True).select_related("warehouse")
    if filters["warehouse_id"]:
        rooms_qs = rooms_qs.filter(warehouse_id=filters["warehouse_id"])
    rooms = rooms_qs.order_by("warehouse__name", "room_name")

    if filters["room_id"]:
        storage_locations = StorageLocation.objects.filter(room_location__room_id=filters["room_id"], is_active=True).order_by("display_code")
    elif filters["warehouse_id"]:
        storage_locations = StorageLocation.objects.filter(room_location__room__warehouse_id=filters["warehouse_id"], room_location__room_id__in=visible_room_ids, is_active=True).order_by("display_code")
    else:
        storage_locations = StorageLocation.objects.filter(room_location__room_id__in=visible_room_ids, is_active=True).order_by("display_code")[:200]

    selected_storage_location = None
    if filters["storage_location_id"] and filters["storage_location_id"].isdigit():
        selected_storage_location = StorageLocation.objects.filter(
            pk=int(filters["storage_location_id"]),
            room_location__room_id__in=visible_room_ids,
            is_active=True,
        ).first()

    context = {
        "page": page,
        "rows": page.object_list,
        "filters": filters,
        "stale_days": stale_days_raw,
        "warehouses": warehouses,
        "rooms": rooms,
        "storage_locations": storage_locations,
        "selected_storage_location": selected_storage_location,
        "can_audit": can_audit(request),
    }

    if request.GET.get("format") == "htmx-search-results":
        return render(request, f"{TEMPLATE_DIR}/_results_card.html", context)
    return render(request, f"{TEMPLATE_DIR}/index.html", context)



@require_http_methods(["POST"])
def active_inventory_inline_edit(request: HttpRequest, pk: int) -> HttpResponse:
    require_audit(request)
    balance = get_object_or_404(ActiveInventory, pk=pk)

    raw_qty = request.POST.get("quantity", "").strip()
    try:
        new_qty = Decimal(raw_qty) if raw_qty else Decimal("0")
    except InvalidOperation:
        new_qty = Decimal("0")

    try:
        AuditSessionContext.inline_edit(
            active_inventory_id=balance.pk,
            new_qty=new_qty,
            actor=request.user,
            notes="Inline edit from Active Inventory.",
        )
        messages.success(request, f"Updated quantity for {balance.part.part_number}.")
    except InventoryValidationError as exc:
        for error in exc.errors:
            messages.error(request, error)

    # Re-fetch for updated state
    balance.refresh_from_db()
    
    if request.GET.get("format") == "htmx-row":
        return render(request, f"{TEMPLATE_DIR}/_row.html", {"row": balance, "can_audit": can_audit(request)})
    
    response = redirect("active_inventory_index")
    response.status_code = 303
    return response
