"""Intake dashboard + Auto Intake portal + session detail
(`inventory_build_kit/build_plan/04_phase_intake_engine.md`, FD-13).

Entrypoints stay thin: parse the request, call `IntakeContext`/
`AutoIntakeManager`/search modules, render. Every write goes through
`IntakeContext.commit_auto_intake` — never a raw `ItemAllocation.objects.create`
here.

Templates are minimal Bulma tables/cards — a frontend-engineer pass follows
this one and will restyle per `auto_intake_workflow_guide.md`'s mockup; the
request/response contract (format= fragments, 303-on-submit) is real and
should not be re-plumbed.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.inventory.control_layer.errors import InventoryValidationError
from app.inventory.control_layer.intake_context import IntakeContext
from app.inventory.control_layer.managers.auto_intake_manager import AutoIntakeManager
from app.inventory.control_layer.domain_structs.intake_session_struct import (
    IntakeSessionStruct,
)
from app.inventory.models.intake.enums import (
    AllocationCondition,
    IntakeSessionMethod,
    IntakeSessionStatus,
)
from app.inventory.models.intake.intake_session import IntakeSession
from app.inventory.models.intake.item_allocation import ItemAllocation
from app.inventory.models.topography.room import Room
from app.inventory.models.topography.warehouse import Warehouse
from app.inventory.presentation_layer.search.intake_search import (
    IntakeSessionSearch,
    UnfulfilledShipmentSearch,
)
from app.inventory.presentation_layer.tools.inventory_access import (
    accessible_domain_ids,
    can_intake,
    require_intake,
)
from app.procurement.models import Shipment

TEMPLATE_DIR = "inventory/intake"


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


def _build_line_rows(*, shipment_id: int, get_params) -> list[dict]:
    """One row per shipment line, with a live target/delta/validity preview.

    Target quantities come from `accepted_<line_id>` / `rejected_<line_id>`
    in `get_params` when present (the lines-matrix HTMX re-render on
    `hx-trigger="change"`); otherwise they default to the line's existing
    balances, matching first paint. `AutoIntakeManager.compute_delta` is the
    single source of truth for the floor/cap math (guard-backed) — this
    helper only catches its validation error per-row so one bad row doesn't
    blank the rest of the matrix, and formats the preview for the template.
    """
    rows: list[dict] = []
    for line in UnfulfilledShipmentSearch.lines_for_shipment(shipment_id=shipment_id):
        existing_good, existing_rejected = AutoIntakeManager.existing_balances(
            shipment_line_id=line.pk
        )
        existing_allocations = list(
            ItemAllocation.objects.filter(
                shipment_line_id=line.pk, deleted_at__isnull=True
            )
            .select_related("intake_session")
            .order_by("id")
        )
        has_input = (
            f"accepted_{line.pk}" in get_params or f"rejected_{line.pk}" in get_params
        )
        accepted_target = (
            _decimal(get_params.get(f"accepted_{line.pk}"))
            if has_input
            else max(existing_good, line.quantity - existing_rejected)
        )
        rejected_target = (
            _decimal(get_params.get(f"rejected_{line.pk}"))
            if has_input
            else existing_rejected
        )
        try:
            delta = AutoIntakeManager.compute_delta(
                shipment_line=line,
                accepted_target=accepted_target,
                rejected_target=rejected_target,
            )
            errors: list[str] = []
        except InventoryValidationError as exc:
            delta = {
                "delta_good": accepted_target - existing_good,
                "delta_rejected": rejected_target - existing_rejected,
            }
            errors = list(exc.errors)
        rows.append(
            {
                "line": line,
                "existing_good": existing_good,
                "existing_rejected": existing_rejected,
                "existing_allocations": existing_allocations,
                "accepted_target": accepted_target,
                "rejected_target": rejected_target,
                "delta_good": delta["delta_good"],
                "delta_rejected": delta["delta_rejected"],
                "errors": errors,
                "is_valid": not errors,
            }
        )
    return rows


# --------------------------------------------------------------------------- #
# intake_dashboard
# --------------------------------------------------------------------------- #


@require_http_methods(["GET"])
def intake_dashboard(request: HttpRequest) -> HttpResponse:
    """Two action cards (Auto Intake live, Scan Session 'coming') plus a
    recent-sessions table. Both cards render unconditionally (rule 5)."""
    sessions = IntakeSessionSearch.recent(limit=25)
    context = {
        "sessions": sessions,
        "can_intake": can_intake(request),
    }
    return render(request, f"{TEMPLATE_DIR}/dashboard.html", context)


# --------------------------------------------------------------------------- #
# auto_intake_portal
# --------------------------------------------------------------------------- #


@require_http_methods(["GET", "POST"])
def auto_intake_portal(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        return _auto_intake_commit(request)

    domain_ids = accessible_domain_ids(request)
    q = request.GET.get("q", "").strip()
    shipment_id = _int(request.GET.get("shipment_id"))
    warehouse_id = _int(request.GET.get("warehouse_id"))
    room_id = _int(request.GET.get("room_id"))

    if request.GET.get("format") == "htmx-room-select":
        rooms = (
            Room.objects.filter(warehouse_id=warehouse_id, is_active=True).order_by(
                "room_name"
            )
            if warehouse_id
            else Room.objects.none()
        )
        return render(
            request,
            f"{TEMPLATE_DIR}/_room_select.html",
            {"rooms": rooms, "warehouse_id": warehouse_id, "room_id": room_id},
        )

    shipments = UnfulfilledShipmentSearch.index_list(domain_ids=domain_ids, q=q)

    if request.GET.get("format") == "htmx-search-results":
        return render(
            request,
            f"{TEMPLATE_DIR}/_shipment_search_results.html",
            {
                "shipments": shipments,
                "shipment_id": shipment_id,
                "can_intake": can_intake(request),
            },
        )

    selected_shipment = None
    line_rows: list[dict] = []
    if shipment_id:
        selected_shipment = (
            Shipment.objects.filter(
                pk=shipment_id, domain_id__in=domain_ids, deleted_at__isnull=True
            )
            .select_related("purchase_order", "purchase_order__vendor")
            .first()
        )
        if selected_shipment is not None:
            line_rows = _build_line_rows(
                shipment_id=selected_shipment.pk, get_params=request.GET
            )

    if request.GET.get("format") == "htmx-shipment-lines":
        return render(
            request,
            f"{TEMPLATE_DIR}/_shipment_lines.html",
            {
                "selected_shipment": selected_shipment,
                "line_rows": line_rows,
                "can_intake": can_intake(request),
            },
        )

    rooms = (
        Room.objects.filter(warehouse_id=warehouse_id, is_active=True).order_by(
            "room_name"
        )
        if warehouse_id
        else Room.objects.none()
    )

    context = {
        "warehouses": Warehouse.objects.filter(is_active=True).order_by("code"),
        "shipments": shipments,
        "q": q,
        "shipment_id": shipment_id,
        "warehouse_id": warehouse_id,
        "room_id": room_id,
        "rooms": rooms,
        "selected_shipment": selected_shipment,
        "line_rows": line_rows,
        "can_intake": can_intake(request),
    }
    return render(request, f"{TEMPLATE_DIR}/auto.html", context)


def _auto_intake_commit(request: HttpRequest) -> HttpResponse:
    require_intake(request)

    warehouse_id = _int(request.POST.get("warehouse_id"))
    room_id = _int(request.POST.get("room_id"))
    shipment_id = _int(request.POST.get("shipment_id"))
    hardware_device_id = request.POST.get("hardware_device_id", "").strip()

    back = f"{reverse('inventory_auto_intake_portal')}"
    if shipment_id:
        back = f"{back}?shipment_id={shipment_id}"

    if warehouse_id is None or shipment_id is None:
        messages.error(request, "Select a warehouse and a shipment before submitting.")
        return redirect(back)

    line_targets: dict[int, tuple[Decimal, Decimal]] = {}
    for key in request.POST:
        if not key.startswith("accepted_"):
            continue
        line_id = _int(key[len("accepted_"):])
        if line_id is None:
            continue
        accepted = _decimal(request.POST.get(key))
        rejected = _decimal(request.POST.get(f"rejected_{line_id}"))
        if accepted == 0 and rejected == 0:
            continue
        line_targets[line_id] = (accepted, rejected)

    try:
        context = IntakeContext.commit_auto_intake(
            operator=request.user,
            warehouse_id=warehouse_id,
            room_id=room_id,
            shipment_id=shipment_id,
            line_targets=line_targets,
            hardware_device_id=hardware_device_id,
            actor=request.user,
        )
    except InventoryValidationError as exc:
        _report(request, exc)
        return redirect(back)

    messages.success(request, "Intake session committed.")
    response = redirect(
        "inventory_intake_session_detail", pk=context.intake_session_id
    )
    response.status_code = 303
    return response


# --------------------------------------------------------------------------- #
# scan_intake_start (Phase 5) — pick a warehouse + associate one or more
# unfulfilled shipments, in-page (FD-18 — not a modal), then create the SCAN
# session and hand off to intake_session_detail's ACTIVE/SCAN face.
# --------------------------------------------------------------------------- #


@require_http_methods(["GET", "POST"])
def scan_intake_start(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        return _scan_intake_commit(request)

    domain_ids = accessible_domain_ids(request)
    q = request.GET.get("q", "").strip()
    warehouse_id = _int(request.GET.get("warehouse_id"))
    room_id = _int(request.GET.get("room_id"))
    selected_ids = sorted(
        {i for i in (_int(v) for v in request.GET.getlist("shipment_ids")) if i is not None}
    )

    if request.GET.get("format") == "htmx-room-select":
        rooms = (
            Room.objects.filter(warehouse_id=warehouse_id, is_active=True).order_by(
                "room_name"
            )
            if warehouse_id
            else Room.objects.none()
        )
        return render(
            request,
            f"{TEMPLATE_DIR}/_room_select.html",
            {"rooms": rooms, "warehouse_id": warehouse_id, "room_id": room_id},
        )

    shipments = UnfulfilledShipmentSearch.index_list(domain_ids=domain_ids, q=q)
    selected_shipments = list(
        Shipment.objects.filter(pk__in=selected_ids, domain_id__in=domain_ids)
        .select_related("purchase_order", "purchase_order__vendor")
    )

    if request.GET.get("format") == "htmx-search-results":
        return render(
            request,
            f"{TEMPLATE_DIR}/_scan_shipment_search_results.html",
            {
                "shipments": shipments,
                "selected_ids": selected_ids,
                "selected_shipments": selected_shipments,
            },
        )

    rooms = (
        Room.objects.filter(warehouse_id=warehouse_id, is_active=True).order_by(
            "room_name"
        )
        if warehouse_id
        else Room.objects.none()
    )

    context = {
        "warehouses": Warehouse.objects.filter(is_active=True).order_by("code"),
        "shipments": shipments,
        "q": q,
        "warehouse_id": warehouse_id,
        "room_id": room_id,
        "rooms": rooms,
        "selected_ids": selected_ids,
        "selected_shipments": selected_shipments,
        "can_intake": can_intake(request),
    }
    return render(request, f"{TEMPLATE_DIR}/scan_start.html", context)


def _scan_intake_commit(request: HttpRequest) -> HttpResponse:
    require_intake(request)

    warehouse_id = _int(request.POST.get("warehouse_id"))
    room_id = _int(request.POST.get("room_id"))
    hardware_device_id = request.POST.get("hardware_device_id", "").strip()
    shipment_ids = sorted(
        {
            i
            for i in (_int(v) for v in request.POST.getlist("shipment_ids"))
            if i is not None
        }
    )

    back = reverse("inventory_scan_intake_start")
    if warehouse_id is None or not shipment_ids:
        messages.error(
            request, "Select a warehouse and at least one unfulfilled shipment."
        )
        return redirect(back)

    try:
        with transaction.atomic():
            context = IntakeContext.start_session(
                operator=request.user,
                warehouse_id=warehouse_id,
                room_id=room_id,
                intake_method=IntakeSessionMethod.SCAN,
                hardware_device_id=hardware_device_id,
                actor=request.user,
            )
            for shipment_id in shipment_ids:
                context.associate_shipment(shipment_id=shipment_id, actor=request.user)
    except InventoryValidationError as exc:
        _report(request, exc)
        return redirect(back)

    messages.success(request, "Scan session started.")
    response = redirect(
        "inventory_intake_session_detail", pk=context.intake_session_id
    )
    response.status_code = 303
    return response


# --------------------------------------------------------------------------- #
# intake_session_detail
# --------------------------------------------------------------------------- #


def _scan_portal_context(session: IntakeSession) -> dict:
    """Live read-model for the ACTIVE/SCAN face of the session portal: per
    shipment-line progress, the staged/unlinked pool, and the distinct parts
    on this session's linked shipments (for the manual-entry fallback's part
    picker).

    KNOWN WRONG, REBUILT IN PHASE 2. THE SHIPMENT LINE IS THE UNIT OF TRUTH;
    THE SESSION IS A LENS ONTO IT (intake_portal_workflow.md §5.5). The
    per-line aggregate below filters on `intake_session=session`, so it
    reports a line at 0% received when another session already took 40 of
    50 — the phantom-shortage bug §5.5 exists to kill. It is left as-is
    because Phase 2 replaces this whole surface with the record page (§2.2),
    where progress aggregates by part number across every live session.
    Do not build anything new on it.
    """
    from app.procurement.models import ShipmentLine

    linked_shipment_ids = list(
        session.shipment_associations.filter(deleted_at__isnull=True).values_list(
            "shipment_id", flat=True
        )
    )
    lines = list(
        ShipmentLine.objects.filter(
            shipment_id__in=linked_shipment_ids, deleted_at__isnull=True
        )
        .select_related("part", "shipment")
        .order_by("shipment_id", "id")
    )

    line_progress = []
    for line in lines:
        totals = ItemAllocation.objects.filter(
            intake_session=session, shipment_line=line, deleted_at__isnull=True
        ).aggregate(
            good=Sum("quantity", filter=Q(condition=AllocationCondition.GOOD)),
            rejected=Sum("quantity", filter=Q(condition=AllocationCondition.REJECTED)),
        )
        good = totals["good"] or Decimal("0")
        rejected = totals["rejected"] or Decimal("0")
        expected = line.quantity or Decimal("0")
        remaining = expected - good - rejected
        allocated_pct = float(min(good / expected, Decimal("1")) * 100) if expected else 0
        rejected_pct = float(min(rejected / expected, Decimal("1")) * 100) if expected else 0
        line_progress.append(
            {
                "line": line,
                "expected": expected,
                "good": good,
                "rejected": rejected,
                "remaining": remaining,
                "allocated_pct": allocated_pct,
                "rejected_pct": rejected_pct,
            }
        )

    staged_allocations = list(
        ItemAllocation.objects.filter(
            intake_session=session, shipment_line__isnull=True, deleted_at__isnull=True
        )
        .select_related("part")
        .order_by("id")
    )
    session_parts = sorted(
        {row["line"].part for row in line_progress}, key=lambda p: p.part_number
    )

    return {
        "line_progress": line_progress,
        "staged_allocations": staged_allocations,
        "session_parts": session_parts,
    }


@require_http_methods(["GET", "POST"])
def intake_session_detail(request: HttpRequest, pk: int) -> HttpResponse:
    session = get_object_or_404(
        IntakeSession.objects.select_related("operator", "warehouse", "room"), pk=pk
    )

    if request.method == "POST":
        return _session_action(request, session)

    struct = IntakeSessionStruct.from_model(session)

    allocations = list(
        session.allocations.filter(deleted_at__isnull=True)
        .select_related("part", "shipment_line")
        .order_by("-id")
    )
    context = {
        "session": session,
        "struct": struct,
        "allocations": allocations,
        "can_intake": can_intake(request),
    }

    is_scan_active = (
        session.status == IntakeSessionStatus.ACTIVE
        and session.intake_method == IntakeSessionMethod.SCAN
    )
    if is_scan_active:
        context.update(_scan_portal_context(session))

    if request.GET.get("format") == "htmx-scan-feed":
        return render(request, f"{TEMPLATE_DIR}/_scan_live_region.html", context)

    return render(request, f"{TEMPLATE_DIR}/session_detail.html", context)


def _session_action(request: HttpRequest, session: IntakeSession) -> HttpResponse:
    """Dispatches every session-portal POST action (scan, manual allocation,
    reassignment, split, close) through
    `IntakeContext` — never a raw model write here. Same canonical detail
    URL for every action (FD-17); `format=htmx-scan-feed` on the query
    string (present on both GET and POST) selects the fragment response the
    scan card's `hx-post` swaps into `#scan-live-region`, while a plain
    `<form>` submit (no query string) falls back to a 303 redirect + full
    page reload — the F5 baseline."""
    require_intake(request)
    action = request.POST.get("action", "")
    ctx = IntakeContext(session.pk)
    wants_fragment = request.GET.get("format") == "htmx-scan-feed"
    detail_url = reverse("inventory_intake_session_detail", kwargs={"pk": session.pk})

    flash_errors: list[str] = []
    flash_success = ""

    try:
        if action == "scan":
            raw_payload = request.POST.get("raw_payload", "").strip()
            condition = request.POST.get("condition", AllocationCondition.GOOD)
            allocation = ctx.process_scan(
                raw_payload=raw_payload, condition=condition, actor=request.user
            )
            flash_success = (
                f"Scanned {allocation.part.part_number} x{allocation.quantity} "
                f"({allocation.get_condition_display()})."
            )
        elif action == "manual_allocation":
            shipment_line_raw = request.POST.get("shipment_line_id", "")
            allocation = ctx.create_manual_allocation(
                shipment_line_id=_int(shipment_line_raw) if shipment_line_raw else None,
                part_id=_int(request.POST.get("part_id")),
                quantity=_decimal(request.POST.get("quantity")),
                serial_number=request.POST.get("serial_number", "").strip(),
                condition=request.POST.get("condition", AllocationCondition.GOOD),
                actor=request.user,
            )
            flash_success = (
                f"Manual allocation recorded: {allocation.part.part_number} "
                f"x{allocation.quantity}."
            )
        elif action == "split":
            ctx.split_allocation(
                allocation_id=_int(request.POST.get("allocation_id")),
                good_qty=_decimal(request.POST.get("good_qty")),
                rejected_qty=_decimal(request.POST.get("rejected_qty")),
                actor=request.user,
            )
            flash_success = "Allocation split."
        elif action == "close":
            ctx.close_session(actor=request.user, notes=request.POST.get("notes", ""))
            flash_success = "Stock posted; session closed."
        else:
            flash_errors = [f"Unknown session action '{action}'."]
    except InventoryValidationError as exc:
        flash_errors = list(exc.errors)

    for error in flash_errors:
        messages.error(request, error)
    if flash_success:
        messages.success(request, flash_success)

    if wants_fragment:
        session.refresh_from_db()
        struct = IntakeSessionStruct.from_model(session)
        allocations = list(
            session.allocations.filter(deleted_at__isnull=True)
            .select_related("part", "shipment_line")
            .order_by("-id")
        )
        fragment_context = {
            "session": session,
            "struct": struct,
            "allocations": allocations,
            "flash_errors": flash_errors,
            "flash_success": flash_success,
            "can_intake": can_intake(request),
        }
        fragment_context.update(_scan_portal_context(session))
        return render(request, f"{TEMPLATE_DIR}/_scan_live_region.html", fragment_context)

    response = redirect(detail_url)
    response.status_code = 303
    return response
