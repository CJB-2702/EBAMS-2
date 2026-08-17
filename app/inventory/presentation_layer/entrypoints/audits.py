"""Audit dashboards and count portal (Phase 7)."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.inventory.control_layer.audit_session_context import AuditSessionContext
from app.inventory.control_layer.errors import InventoryValidationError
from app.inventory.models.audit.audit_session import AuditSession
from app.inventory.models.audit.enums import AuditReasonCode, AuditSessionType
from app.inventory.models.topography.warehouse import Warehouse
from app.inventory.models.topography.room import Room
from app.inventory.presentation_layer.search.audit_search import AuditSearch
from app.inventory.presentation_layer.tools.inventory_access import (
    accessible_domain_ids,
    can_audit,
    require_audit,
)

TEMPLATE_DIR = "inventory/audits"
PAGE_SIZE = 50


def _int(raw) -> int | None:
    text = str(raw or "").strip()
    return int(text) if text.lstrip("-").isdigit() else None


def _decimal(raw) -> Decimal:
    text = str(raw or "").strip()
    if not text:
        return Decimal("0")
    try:
        return Decimal(text)
    except InvalidOperation:
        return Decimal("0")


def _report(request: HttpRequest, exc: InventoryValidationError) -> None:
    for error in exc.errors:
        messages.error(request, error)


# --------------------------------------------------------------------------- #
# audit_session_index
# --------------------------------------------------------------------------- #


@require_http_methods(["GET"])
def audit_session_index(request: HttpRequest) -> HttpResponse:
    domain_ids = accessible_domain_ids(request)

    filters = {
        "status": request.GET.get("status", "").strip(),
        "session_type": request.GET.get("session_type", "").strip(),
        "warehouse_id": request.GET.get("warehouse_id", "").strip(),
    }

    qs = AuditSearch.session_list(
        domain_ids=domain_ids,
        status=filters["status"],
        session_type=filters["session_type"],
        warehouse_id=filters["warehouse_id"],
    )

    paginator = Paginator(qs, PAGE_SIZE)
    page = paginator.get_page(request.GET.get("page", "1"))

    # Need rooms for the start audit card
    warehouse_id_for_start = _int(request.GET.get("start_warehouse_id"))
    rooms = (
        Room.objects.filter(warehouse_id=warehouse_id_for_start, is_active=True).order_by("room_name")
        if warehouse_id_for_start
        else Room.objects.none()
    )

    context = {
        "page": page,
        "rows": page.object_list,
        "filters": filters,
        "warehouses": Warehouse.objects.filter(is_active=True).order_by("code"),
        "start_warehouse_id": warehouse_id_for_start,
        "rooms": rooms,
        "can_audit": can_audit(request),
    }

    if request.GET.get("format") == "htmx-room-select":
        return render(request, f"{TEMPLATE_DIR}/_room_select.html", context)

    return render(request, f"{TEMPLATE_DIR}/index.html", context)


# --------------------------------------------------------------------------- #
# audit_session_start
# --------------------------------------------------------------------------- #


@require_http_methods(["POST"])
def audit_session_start(request: HttpRequest) -> HttpResponse:
    require_audit(request)

    warehouse_id = _int(request.POST.get("start_warehouse_id"))
    room_id = _int(request.POST.get("start_room_id"))
    session_type = request.POST.get("session_type", AuditSessionType.SPOT_CHECK)
    notes = request.POST.get("notes", "").strip()

    if not warehouse_id:
        messages.error(request, "Warehouse is required to start an audit session.")
        return redirect("inventory_audit_session_index")

    try:
        ctx = AuditSessionContext.start(
            warehouse_id=warehouse_id,
            room_id=room_id,
            session_type=session_type,
            conducted_by=request.user,
            actor=request.user,
            notes=notes,
        )
    except InventoryValidationError as exc:
        _report(request, exc)
        return redirect("inventory_audit_session_index")

    messages.success(request, f"Audit session {ctx.session.session_number} started.")
    return redirect("inventory_audit_session_detail", pk=ctx.audit_session_id)


# --------------------------------------------------------------------------- #
# audit_session_detail
# --------------------------------------------------------------------------- #


@require_http_methods(["GET", "POST"])
def audit_session_detail(request: HttpRequest, pk: int) -> HttpResponse:
    session = get_object_or_404(
        AuditSession.objects.select_related("warehouse", "room", "conducted_by"), pk=pk
    )

    if request.method == "POST":
        return _session_action(request, session)

    lines = list(
        session.lines.filter(deleted_at__isnull=True)
        .select_related("part", "storage_location__room_location__room")
        .order_by("-id")
    )

    context = {
        "session": session,
        "lines": lines,
        "can_audit": can_audit(request),
    }

    if request.GET.get("format") == "htmx-lines-table":
        return render(request, f"{TEMPLATE_DIR}/_lines_table.html", context)

    return render(request, f"{TEMPLATE_DIR}/detail.html", context)


def _session_action(request: HttpRequest, session: AuditSession) -> HttpResponse:
    require_audit(request)
    action = request.POST.get("action", "")
    ctx = AuditSessionContext(session.pk)
    wants_fragment = request.GET.get("format") == "htmx-lines-table"

    flash_errors: list[str] = []
    flash_success = ""

    try:
        if action == "record_count":
            line = ctx.record_line(
                part_id=_int(request.POST.get("part_id")),
                storage_location_id=_int(request.POST.get("storage_location_id")),
                serial_number=request.POST.get("serial_number", "").strip(),
                counted_qty=_decimal(request.POST.get("counted_qty")),
                actor=request.user,
            )
            flash_success = f"Recorded count for {line.part.part_number}."
        elif action == "set_resolution":
            ctx.set_resolution(
                line_id=_int(request.POST.get("line_id")),
                resolution_type=request.POST.get("resolution_type", ""),
                actor=request.user,
            )
            flash_success = "Resolution updated."
        elif action == "finalize":
            ctx.finalize(actor=request.user)
            flash_success = "Session finalized and variances committed."
        elif action == "cancel":
            ctx.cancel(actor=request.user)
            flash_success = "Session cancelled."
        else:
            flash_errors = [f"Unknown session action '{action}'."]
    except InventoryValidationError as exc:
        flash_errors = list(exc.errors)

    for error in flash_errors:
        messages.error(request, error)
    if flash_success:
        messages.success(request, flash_success)

    if wants_fragment and action in ("record_count", "set_resolution"):
        lines = list(
            session.lines.filter(deleted_at__isnull=True)
            .select_related("part", "storage_location__room_location__room")
            .order_by("-id")
        )
        fragment_context = {
            "session": session,
            "lines": lines,
            "can_audit": can_audit(request),
        }
        response = render(request, f"{TEMPLATE_DIR}/_lines_table.html", fragment_context)
        # Clear out HTMX trigger on error to avoid double alerts, HTMX will handle it with the fragment
        if flash_errors or flash_success:
            pass # Keep it simple and just let fragment render the messages if possible, or trigger event.
            # actually we don't have an htmx event system setup uniformly, let's just use redirect on actions 
            # if we aren't returning the full page with messages.
            # wait, the intake portal returns a fragment for the live region. Let's return the fragment.
        return response

    response = redirect("inventory_audit_session_detail", pk=session.pk)
    response.status_code = 303
    return response


# --------------------------------------------------------------------------- #
# audit_log_index
# --------------------------------------------------------------------------- #


@require_http_methods(["GET"])
def audit_log_index(request: HttpRequest) -> HttpResponse:
    domain_ids = accessible_domain_ids(request)

    filters = {
        "reason_code": request.GET.get("reason_code", "").strip(),
        "part_q": request.GET.get("part_q", "").strip(),
        "warehouse_id": request.GET.get("warehouse_id", "").strip(),
    }

    qs = AuditSearch.log_list(
        domain_ids=domain_ids,
        reason_code=filters["reason_code"],
        part_q=filters["part_q"],
        warehouse_id=filters["warehouse_id"],
    )

    paginator = Paginator(qs, PAGE_SIZE)
    page = paginator.get_page(request.GET.get("page", "1"))

    context = {
        "page": page,
        "rows": page.object_list,
        "filters": filters,
        "warehouses": Warehouse.objects.filter(is_active=True).order_by("code"),
    }

    if request.GET.get("format") == "htmx-search-results":
        return render(request, f"{TEMPLATE_DIR}/_log_results_card.html", context)

    return render(request, f"{TEMPLATE_DIR}/logs.html", context)
