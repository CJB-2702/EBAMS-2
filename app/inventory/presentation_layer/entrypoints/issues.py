"""Phase 6 — Issuance portal workspace (`/inventory/issues/create/` and
`/inventory/issue-parts/`), location-based issuance portal, and the Issued
Parts ledger (sessions index, line item ledger, session detail, & return action).

The portal keeps a session-backed draft of queued lines so the queue survives
F5 — no client-only state.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date, parse_datetime
from django.views.decorators.http import require_http_methods

from app.administration.models import User
from app.assets.models import Asset
from app.inventory.control_layer.adapters.room_svg_adapter import RoomSvgAdapter
from app.inventory.control_layer.constants import ROOM_SVG_GROUP_LABEL
from app.inventory.control_layer.errors import InventoryValidationError
from app.inventory.control_layer.orchestrators.part_issuance_orchestrator import (
    PartIssuanceOrchestrator,
)
from app.inventory.models import IssueSessionStatus, IssueType, PartIssue, PartIssueSession
from app.inventory.models.stock.active_inventory import ActiveInventory
from app.inventory.models.topography.room import Room
from app.inventory.models.topography.warehouse import Warehouse
from app.inventory.presentation_layer.search.active_inventory_search import (
    domain_visible_room_ids,
)
from app.inventory.presentation_layer.search.issue_search import IssueSearch
from app.inventory.presentation_layer.tools.inventory_access import (
    accessible_domain_ids,
    can_issue,
)
from app.procurement.control_layer.part_demand_context import PartDemandContext
from app.procurement.models import DemandPriority, DemandState, IssuanceState, PartDemand

TEMPLATE_DIR = "inventory/issues"
PAGE_SIZE = 50

_SEARCHABLE_DEMAND_STATES = frozenset(
    {DemandState.REQUIRED, DemandState.APPROVED}
)


def _draft_key(request: HttpRequest) -> str:
    return f"issuance_draft_{request.user.pk}"


def _draft(request: HttpRequest) -> list[dict]:
    return request.session.get(_draft_key(request), [])


def _save_draft(request: HttpRequest, lines: list[dict]) -> None:
    request.session[_draft_key(request)] = lines
    request.session.modified = True


def _decimal(raw) -> Decimal | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def _int_or_none(raw) -> int | None:
    if raw is None:
        return None
    raw = str(raw).strip()
    return int(raw) if raw.isdigit() else None


def _enrich_draft(lines: list[dict]) -> list[dict]:
    balance_ids = [l["active_inventory_id"] for l in lines if l.get("active_inventory_id")]
    demand_ids = [l["demand_id"] for l in lines if l.get("demand_id")]
    user_ids = [l["issued_to_id"] for l in lines if l.get("issued_to_id")]
    asset_ids = [l["issued_to_asset_id"] for l in lines if l.get("issued_to_asset_id")]

    balances = {
        b.pk: b
        for b in ActiveInventory.objects.filter(pk__in=balance_ids).select_related(
            "part", "room", "room__warehouse", "storage_location"
        )
    }
    demands = {
        d.pk: d
        for d in PartDemand.objects.filter(pk__in=demand_ids).select_related("part", "requested_by")
    }
    users = {
        u.pk: u for u in User.objects.filter(pk__in=user_ids)
    }
    assets = {
        a.pk: a for a in Asset.objects.filter(pk__in=asset_ids)
    }

    enriched = []
    for index, line in enumerate(lines):
        balance = balances.get(line.get("active_inventory_id"))
        demand = demands.get(line.get("demand_id"))
        recipient_user = users.get(line.get("issued_to_id"))
        recipient_asset = assets.get(line.get("issued_to_asset_id"))

        match_status = "unmatched"
        if balance and demand:
            if balance.part_id == demand.part_id:
                match_status = "paired"
            else:
                match_status = "mismatch"
        elif balance and not demand:
            match_status = "direct_stock"
        elif demand and not balance:
            match_status = "unmet_demand"

        enriched.append(
            {
                **line,
                "index": index,
                "balance": balance,
                "demand": demand,
                "recipient_user": recipient_user,
                "recipient_asset": recipient_asset,
                "match_status": match_status,
                "is_matched": (match_status == "paired"),
            }
        )
    return enriched


# --------------------------------------------------------------------------- #
# Issuance portal
# --------------------------------------------------------------------------- #


@require_http_methods(["GET", "POST"])
def issuance_portal(request: HttpRequest) -> HttpResponse:
    demand_id = request.GET.get("demand", "").strip() or request.POST.get("demand", "").strip()
    stock_id = request.GET.get("stock", "").strip() or request.POST.get("stock", "").strip()

    demand = (
        get_object_or_404(PartDemand.objects.select_related("part", "requested_by"), pk=demand_id)
        if demand_id
        else None
    )
    balance = (
        get_object_or_404(
            ActiveInventory.objects.select_related("part", "room", "storage_location"),
            pk=stock_id,
        )
        if stock_id
        else None
    )

    if request.method == "POST":
        if not can_issue(request):
            messages.error(request, "You do not have permission to issue parts.")
            return redirect(request.get_full_path())
        action = request.POST.get("action", "")
        lines = _draft(request)

        if action == "add_line":
            try:
                quantity = _decimal(request.POST.get("quantity"))
                if quantity is None or quantity == 0:
                    raise InventoryValidationError(["Enter a non-zero quantity."])
                lines.append(
                    {
                        "issue_type": request.POST.get("issue_type", IssueType.FOR_PART_DEMAND),
                        "demand_id": _int_or_none(request.POST.get("demand_id")),
                        "issued_to_id": _int_or_none(request.POST.get("issued_to_id")),
                        "issued_to_asset_id": _int_or_none(request.POST.get("issued_to_asset_id")),
                        "active_inventory_id": _int_or_none(request.POST.get("active_inventory_id")),
                        "quantity": str(quantity),
                        "notes": request.POST.get("notes", ""),
                    }
                )
                _save_draft(request, lines)
                messages.success(request, "Line added to the active issuance session queue.")
            except InventoryValidationError as exc:
                for error in exc.errors:
                    messages.error(request, error)

        elif action == "add_demand":
            target_demand_id = _int_or_none(request.POST.get("add_demand_id"))
            if target_demand_id:
                dem_obj = PartDemand.objects.filter(pk=target_demand_id).select_related("part").first()
                if dem_obj:
                    visible_room_ids = domain_visible_room_ids(domain_ids=accessible_domain_ids(request))
                    matching_stock = ActiveInventory.objects.filter(
                        part_id=dem_obj.part_id,
                        quantity_on_hand__gt=0,
                        room_id__in=visible_room_ids,
                    ).first()

                    remaining_qty = dem_obj.quantity_requested - dem_obj.issued_qty
                    qty_str = str(max(Decimal("1.000"), remaining_qty)) if remaining_qty > 0 else "1.000"

                    lines.append(
                        {
                            "issue_type": IssueType.FOR_PART_DEMAND,
                            "demand_id": dem_obj.pk,
                            "issued_to_id": dem_obj.requested_by_id,
                            "issued_to_asset_id": None,
                            "active_inventory_id": matching_stock.pk if matching_stock else None,
                            "quantity": qty_str,
                            "notes": f"Staged for Demand #{dem_obj.pk}",
                        }
                    )
                    _save_draft(request, lines)
                    if matching_stock:
                        messages.success(request, f"Demand #{dem_obj.pk} staged and paired with available stock ({matching_stock.part.part_number}).")
                    else:
                        messages.warning(request, f"Demand #{dem_obj.pk} staged in session (no matching stock balance found in visible locations yet).")

        elif action == "auto_match":
            visible_room_ids = domain_visible_room_ids(domain_ids=accessible_domain_ids(request))
            matched_count = 0
            for line in lines:
                if line.get("demand_id") and not line.get("active_inventory_id"):
                    dem_obj = PartDemand.objects.filter(pk=line["demand_id"]).first()
                    if dem_obj:
                        stk = ActiveInventory.objects.filter(
                            part_id=dem_obj.part_id,
                            quantity_on_hand__gt=0,
                            room_id__in=visible_room_ids,
                        ).first()
                        if stk:
                            line["active_inventory_id"] = stk.pk
                            matched_count += 1
            _save_draft(request, lines)
            messages.success(request, f"Auto-matcher paired {matched_count} staged demand line(s) with physical inventory.")

        elif action == "remove_line":
            index = int(request.POST.get("index", "-1"))
            if 0 <= index < len(lines):
                lines.pop(index)
                _save_draft(request, lines)

        elif action in ("submit", "commit_session"):
            if not lines:
                messages.error(request, "Add at least one line to the queue before committing the session.")
            else:
                try:
                    issued_to_id = _int_or_none(request.POST.get("issued_to_id"))
                    issued_to_asset_id = _int_or_none(request.POST.get("issued_to_asset_id"))
                    issue_type = request.POST.get("issue_type", IssueType.FOR_PART_DEMAND)
                    issue_reason = request.POST.get("issue_reason", "").strip()
                    notes = request.POST.get("notes", "").strip()

                    issued_to = User.objects.get(pk=issued_to_id) if issued_to_id else None

                    session_obj = PartIssuanceOrchestrator.commit_session(
                        lines=lines,
                        issued_by=request.user,
                        issued_to=issued_to,
                        issued_to_asset_id=issued_to_asset_id,
                        issue_type=issue_type,
                        issue_reason=issue_reason,
                        notes=notes,
                    )
                    messages.success(
                        request,
                        f"Issue session #{session_obj.session_number} committed successfully with {len(lines)} item(s).",
                    )
                    _save_draft(request, [])
                    return redirect(reverse("inventory_issue_session_detail", kwargs={"pk": session_obj.pk}))
                except Exception as exc:  # noqa: BLE001
                    messages.error(request, str(exc))

        elif action == "cancel_draft":
            _save_draft(request, [])

        redirect_qs = f"?demand={demand_id}" if demand_id else (f"?stock={stock_id}" if stock_id else "")
        return redirect(f"{reverse('inventory_issuance_portal')}{redirect_qs}")

    # Search & Filter Available Inventory for workspace table
    inv_part_number = request.GET.get("part_number", "").strip()
    inv_part_name = request.GET.get("part_name", "").strip()
    inv_warehouse_id = _int_or_none(request.GET.get("location_id", "")) or _int_or_none(request.GET.get("warehouse_id", ""))
    inv_room_id = _int_or_none(request.GET.get("storeroom_id", "")) or _int_or_none(request.GET.get("room_id", ""))
    inv_search = request.GET.get("search", "").strip()

    visible_room_ids = domain_visible_room_ids(domain_ids=accessible_domain_ids(request))
    available_inv_qs = ActiveInventory.objects.filter(
        room_id__in=visible_room_ids,
        quantity_on_hand__gt=0,
    ).select_related("part", "room", "room__warehouse", "storage_location")

    if inv_part_number:
        available_inv_qs = available_inv_qs.filter(part__part_number__icontains=inv_part_number)
    if inv_part_name:
        available_inv_qs = available_inv_qs.filter(part__part_name__icontains=inv_part_name)
    if inv_warehouse_id:
        available_inv_qs = available_inv_qs.filter(room__warehouse_id=inv_warehouse_id)
    if inv_room_id:
        available_inv_qs = available_inv_qs.filter(room_id=inv_room_id)
    if inv_search:
        available_inv_qs = available_inv_qs.filter(
            Q(part__part_number__icontains=inv_search)
            | Q(part__part_name__icontains=inv_search)
            | Q(serial_number__icontains=inv_search)
        )

    available_inv_qs = available_inv_qs.order_by("part__part_number", "-quantity_on_hand")
    inv_paginator = Paginator(available_inv_qs, 15)
    inv_page = inv_paginator.get_page(request.GET.get("inv_page", "1"))

    # Dropdown collections
    warehouses = Warehouse.objects.filter(is_active=True).order_by("name")
    rooms = Room.objects.filter(is_active=True).order_by("room_name")
    users = User.objects.filter(is_active=True).order_by("first_name", "last_name")[:200]
    assets = Asset.objects.filter(is_active=True).order_by("name")[:200]

    # Eligible stock / demand filters
    eligible_stock = []
    if demand is not None:
        eligible_stock = list(
            ActiveInventory.objects.filter(
                part_id=demand.part_id, room_id__in=visible_room_ids, quantity_on_hand__gt=0
            )
            .select_related("room", "storage_location")
            .order_by("-quantity_on_hand")
        )

    demand_q = request.GET.get("demand_q", "").strip()
    created_from_raw = request.GET.get("created_from", "").strip()
    created_to_raw = request.GET.get("created_to", "").strip()
    requested_by = request.GET.get("requested_by", "").strip()
    po_number = request.GET.get("po_number", "").strip()
    demand_state = request.GET.get("demand_state", "").strip()
    priority = request.GET.get("priority", "").strip()

    created_from = (
        parse_datetime(created_from_raw) or parse_date(created_from_raw)
        if created_from_raw
        else None
    )
    created_to = (
        parse_datetime(created_to_raw) or parse_date(created_to_raw)
        if created_to_raw
        else None
    )

    demand_results = []
    has_demand_filter = any([
        demand_q, created_from, created_to, requested_by, po_number, demand_state, priority
    ])

    if balance is not None:
        d_qs = PartDemand.objects.filter(
            part_id=balance.part_id,
            deleted_at__isnull=True,
        )
        if demand_state:
            d_qs = d_qs.filter(demand_state=demand_state)
        else:
            d_qs = d_qs.filter(demand_state__in=_SEARCHABLE_DEMAND_STATES)

        if priority:
            d_qs = d_qs.filter(priority=priority)

        if demand_q:
            d_qs = d_qs.filter(
                Q(notes__icontains=demand_q)
                | Q(pk__iexact=demand_q if demand_q.isdigit() else -1)
            )

        if created_from:
            d_qs = d_qs.filter(created_at__gte=created_from)
        if created_to:
            d_qs = d_qs.filter(created_at__lte=created_to)

        if requested_by:
            if requested_by.isdigit():
                d_qs = d_qs.filter(requested_by_id=int(requested_by))
            else:
                d_qs = d_qs.filter(
                    Q(requested_by__username__icontains=requested_by)
                    | Q(requested_by__first_name__icontains=requested_by)
                    | Q(requested_by__last_name__icontains=requested_by)
                )

        if po_number:
            d_qs = d_qs.filter(
                allocations__is_active=True,
                allocations__deleted_at__isnull=True,
                allocations__purchase_order_line__purchase_order__po_number__icontains=po_number,
            ).distinct()

        demand_results = list(d_qs.select_related("part", "requested_by")[:25])

    context = {
        "demand": demand,
        "balance": balance,
        "eligible_stock": eligible_stock,
        "available_inv_page": inv_page,
        "warehouses": warehouses,
        "storerooms": rooms,
        "locations": warehouses,
        "users": users,
        "assets": assets,
        "current_filters": {
            "part_number": inv_part_number,
            "part_name": inv_part_name,
            "location_id": inv_warehouse_id,
            "storeroom_id": inv_room_id,
            "search": inv_search,
        },
        "demand_q": demand_q,
        "demand_filters": {
            "demand_q": demand_q,
            "created_from": created_from_raw,
            "created_to": created_to_raw,
            "requested_by": requested_by,
            "po_number": po_number,
            "demand_state": demand_state,
            "priority": priority,
        },
        "has_demand_filter": has_demand_filter,
        "demand_states": DemandState.choices,
        "priorities": DemandPriority.choices,
        "demand_results": demand_results,
        "draft": _enrich_draft(_draft(request)),
        "issue_types": IssueType.choices,
        "can_issue": can_issue(request),
    }
    return render(request, f"{TEMPLATE_DIR}/create.html", context)


def _location_filter_state(request: HttpRequest) -> dict:
    warehouse_id = _int_or_none(request.GET.get("warehouse_id", ""))
    room_id = _int_or_none(request.GET.get("room_id", ""))
    loc = request.GET.get("loc", "").strip()
    sloc = _int_or_none(request.GET.get("sloc", ""))

    warehouses = Warehouse.objects.filter(is_active=True).order_by("name")
    selected_warehouse = warehouses.filter(pk=warehouse_id).first() if warehouse_id else None

    rooms = []
    selected_room = None
    room_locations = []
    map_svg = None
    selected_storage_location = None

    if selected_warehouse:
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
            raw_svg = RoomSvgAdapter.read_svg_from_attachment(selected_room.current_layout)
            if raw_svg is not None:
                shape_targets = {
                    rl.display_code: rl.display_code
                    for rl in room_locations
                    if rl.storage_locations.filter(is_active=True).exists()
                }
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
        "rooms": rooms,
        "room_id": room_id,
        "selected_room": selected_room,
        "room_locations": room_locations,
        "map_svg": map_svg,
        "loc": loc,
        "sloc": sloc,
        "selected_storage_location": selected_storage_location,
    }


# --------------------------------------------------------------------------- #
# Issuance from Location Portal
# --------------------------------------------------------------------------- #


@require_http_methods(["GET", "POST"])
def issuance_location_portal(request: HttpRequest) -> HttpResponse:
    stock_id = request.GET.get("stock", "").strip() or request.POST.get("stock", "").strip()

    filter_state = _location_filter_state(request)
    selected_room = filter_state["selected_room"]
    loc = filter_state["loc"]
    sloc = filter_state["sloc"]

    domain_ids = accessible_domain_ids(request)
    visible_room_ids = domain_visible_room_ids(domain_ids=domain_ids)

    # Fetch available stock in selected room / map area / bin
    available_stock = []
    if selected_room is not None and selected_room.pk in visible_room_ids:
        stock_qs = ActiveInventory.objects.filter(
            room=selected_room,
            quantity_on_hand__gt=0,
        ).select_related("part", "room", "storage_location", "storage_location__room_location", "warehouse")

        if sloc:
            stock_qs = stock_qs.filter(storage_location_id=sloc)
        elif loc:
            stock_qs = stock_qs.filter(storage_location__room_location__display_code=loc)

        available_stock = list(stock_qs.order_by("part__part_number", "-quantity_on_hand"))

    # Selected stock row (if stock_id is provided)
    selected_stock = None
    if stock_id:
        selected_stock = ActiveInventory.objects.filter(
            pk=stock_id,
            room_id__in=visible_room_ids,
        ).select_related("part", "room", "storage_location", "warehouse").first()

    if request.method == "POST":
        if not can_issue(request):
            messages.error(request, "You do not have permission to issue parts.")
            return redirect(request.get_full_path())
        action = request.POST.get("action", "")
        lines = _draft(request)

        if action in ("issue_stock", "add_line", "stage_stock"):
            try:
                target_stock_id = _int_or_none(request.POST.get("active_inventory_id", ""))
                quantity = _decimal(request.POST.get("quantity"))
                if quantity is None or quantity <= 0:
                    raise InventoryValidationError(["Enter a valid positive quantity."])

                lines.append(
                    {
                        "issue_type": request.POST.get("issue_type", IssueType.FOR_PART_DEMAND),
                        "demand_id": _int_or_none(request.POST.get("demand_id")),
                        "issued_to_id": _int_or_none(request.POST.get("issued_to_id")),
                        "issued_to_asset_id": _int_or_none(request.POST.get("issued_to_asset_id")),
                        "active_inventory_id": target_stock_id,
                        "quantity": str(quantity),
                        "notes": request.POST.get("notes", ""),
                    }
                )
                _save_draft(request, lines)
                messages.success(request, "Stock line staged into your active issuance session queue.")
                return redirect(request.get_full_path())
            except InventoryValidationError as exc:
                for error in exc.errors:
                    messages.error(request, error)
            except Exception as exc:  # noqa: BLE001
                messages.error(request, str(exc))

        elif action == "remove_line":
            index = int(request.POST.get("index", "-1"))
            if 0 <= index < len(lines):
                lines.pop(index)
                _save_draft(request, lines)

        elif action in ("submit", "commit_session"):
            if not lines:
                messages.error(request, "Add at least one line before issuing.")
            else:
                try:
                    issued_to_id = _int_or_none(request.POST.get("issued_to_id"))
                    issued_to_asset_id = _int_or_none(request.POST.get("issued_to_asset_id"))
                    issue_type = request.POST.get("issue_type", IssueType.FOR_PART_DEMAND)
                    notes = request.POST.get("notes", "")

                    issued_to = User.objects.get(pk=issued_to_id) if issued_to_id else None

                    session_obj = PartIssuanceOrchestrator.commit_session(
                        lines=lines,
                        issued_by=request.user,
                        issued_to=issued_to,
                        issued_to_asset_id=issued_to_asset_id,
                        issue_type=issue_type,
                        notes=notes,
                    )
                    messages.success(request, f"Issue session #{session_obj.session_number} committed successfully.")
                    _save_draft(request, [])
                    return redirect(reverse("inventory_issue_session_detail", kwargs={"pk": session_obj.pk}))
                except Exception as exc:  # noqa: BLE001
                    messages.error(request, str(exc))

        elif action == "cancel_draft":
            _save_draft(request, [])

        return redirect(request.get_full_path())

    demands = []
    if selected_stock is not None:
        demands = list(
            PartDemand.objects.filter(
                part_id=selected_stock.part_id,
                demand_state__in=_SEARCHABLE_DEMAND_STATES,
            ).select_related("part", "requested_by")[:50]
        )

    assets = Asset.objects.filter(is_active=True).order_by("name")[:200]
    users = User.objects.filter(is_active=True).order_by("first_name", "last_name")[:200]

    context = {
        "stock_id": stock_id,
        "selected_stock": selected_stock,
        "available_stock": available_stock,
        "demands": demands,
        "assets": assets,
        "users": users,
        "draft": _enrich_draft(_draft(request)),
        "issue_types": IssueType.choices,
        "can_issue": can_issue(request),
    }
    context.update(filter_state)
    return render(request, f"{TEMPLATE_DIR}/from_location.html", context)


# --------------------------------------------------------------------------- #
# Issued Parts Ledger
# --------------------------------------------------------------------------- #


@require_http_methods(["GET"])
def issues_index(request: HttpRequest) -> HttpResponse:
    domain_ids = accessible_domain_ids(request)
    view_tab = request.GET.get("tab", "sessions").strip()

    filters = {
        "issue_type": request.GET.get("issue_type", "").strip(),
        "part_q": request.GET.get("part_q", "").strip(),
        "demand_id": request.GET.get("demand_id", "").strip(),
        "tab": view_tab,
    }

    if view_tab == "lines":
        search_filters = {k: v for k, v in filters.items() if k != "tab"}
        qs = IssueSearch.index_list(domain_ids=domain_ids, **search_filters)
        paginator = Paginator(qs, PAGE_SIZE)
        page = paginator.get_page(request.GET.get("page", "1"))
        context = {
            "view_tab": "lines",
            "page": page,
            "rows": page.object_list,
            "filters": filters,
            "issue_types": IssueType.choices,
        }
    else:
        sessions_qs = PartIssueSession.objects.filter(
            deleted_at__isnull=True
        ).select_related(
            "issued_by", "issued_to", "issued_to_asset"
        ).prefetch_related(
            "issues", "issues__part_demand", "issues__part_demand__part"
        ).order_by("-issued_at")

        if filters["issue_type"]:
            sessions_qs = sessions_qs.filter(issue_type=filters["issue_type"])

        paginator = Paginator(sessions_qs, PAGE_SIZE)
        page = paginator.get_page(request.GET.get("page", "1"))
        context = {
            "view_tab": "sessions",
            "page": page,
            "sessions": page.object_list,
            "filters": filters,
            "issue_types": IssueType.choices,
        }

    if request.GET.get("format") == "htmx-search-results":
        return render(request, f"{TEMPLATE_DIR}/_results_card.html", context)
    return render(request, f"{TEMPLATE_DIR}/index.html", context)


@require_http_methods(["GET"])
def issue_session_detail(request: HttpRequest, pk: int) -> HttpResponse:
    session_obj = get_object_or_404(
        PartIssueSession.objects.filter(deleted_at__isnull=True).select_related(
            "issued_by", "issued_to", "issued_to_asset"
        ).prefetch_related(
            "issues",
            "issues__part_demand",
            "issues__part_demand__part",
            "issues__from_room",
            "issues__from_storage_location",
            "issues__issued_to",
            "issues__issued_to_asset",
        ),
        pk=pk,
    )
    return render(
        request,
        f"{TEMPLATE_DIR}/session_detail.html",
        {
            "session": session_obj,
            "issues": session_obj.issues.all(),
            "can_issue": can_issue(request),
        },
    )


@require_http_methods(["GET", "POST"])
def issue_detail(request: HttpRequest, pk: int) -> HttpResponse:
    issue = get_object_or_404(
        IssueSearch.index_list(domain_ids=accessible_domain_ids(request)), pk=pk
    )

    if request.method == "POST":
        if not can_issue(request):
            messages.error(request, "You do not have permission to record a return.")
            return redirect(reverse("inventory_issue_detail", kwargs={"pk": pk}))
        action = request.POST.get("action", "")
        if action == "return":
            try:
                quantity = _decimal(request.POST.get("quantity")) or issue.quantity
                active_inv = None
                if issue.from_room and issue.part_demand and issue.part_demand.part:
                    active_inv = ActiveInventory.objects.filter(
                        room=issue.from_room,
                        storage_location=issue.from_storage_location,
                        part=issue.part_demand.part,
                        serial_number=issue.serial_number,
                    ).first()
                PartIssuanceOrchestrator.record_return(
                    quantity=quantity,
                    issue_type=issue.issue_type,
                    demand_id=issue.part_demand_id,
                    issued_to=issue.issued_to,
                    issued_to_asset_id=issue.issued_to_asset_id,
                    active_inventory_id=active_inv.pk if active_inv else None,
                    actor=request.user,
                    notes=request.POST.get("notes", ""),
                )
                messages.success(request, "Return recorded.")
            except Exception as exc:  # noqa: BLE001
                messages.error(request, str(exc))
        return redirect(reverse("inventory_issue_detail", kwargs={"pk": pk}))

    return render(
        request,
        f"{TEMPLATE_DIR}/detail.html",
        {"issue": issue, "can_issue": can_issue(request)},
    )


@require_http_methods(["GET"])
def pending_stock_adjustments_index(request: HttpRequest) -> HttpResponse:
    """List demands that were issued without formal stock adjustment.

    Inventory managers use this to track what needs to be formally recorded
    in the inventory system. Shows demands in ISSUED_WITHOUT_STOCK_ADJUSTMENT
    state that haven't yet been processed through normal issuance.
    """
    domain_ids = accessible_domain_ids(request)

    demands_qs = PartDemand.objects.filter(
        issuance_state=IssuanceState.ISSUED_WITHOUT_STOCK_ADJUSTMENT,
        domain_id__in=domain_ids,
        deleted_at__isnull=True,
    ).select_related(
        "part",
        "domain",
        "requested_by",
    ).order_by("-updated_at")

    paginator = Paginator(demands_qs, PAGE_SIZE)
    page = paginator.get_page(request.GET.get("page", "1"))

    context = {
        "page": page,
        "demands": page.object_list,
    }

    if request.GET.get("format") == "htmx-search-results":
        return render(request, f"{TEMPLATE_DIR}/_pending_adjustments_results.html", context)
    return render(request, f"{TEMPLATE_DIR}/pending_adjustments.html", context)
