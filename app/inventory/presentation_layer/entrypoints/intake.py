"""Intake Portal Presentation Entrypoints (Phase 3).

Implements the seven addressable surfaces (§2) plus the Global Allocation Portal (§7.3):
1. Create (/inventory/intake/create/)
2. Record (/inventory/intake/<pk>/record/)
3. Associate (/inventory/intake/<pk>/associate/)
4. Discrepancies (/inventory/intake/<pk>/discrepancies/)
5. Review (/inventory/intake/<pk>/)
6. Index (/inventory/intake/)
7. Print (/inventory/intake/<pk>/print/)
Global Allocation Portal (/inventory/intake/allocate/)
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Sum
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect

class HttpResponseSeeOther(HttpResponseRedirect):
    status_code = 303
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.inventory.control_layer.domain_structs.shipment_line_truth_struct import (
    AssociateProgressStruct,
    PartProgressStruct,
    ShipmentLineTruthStruct,
)
from app.inventory.control_layer.errors import InventoryValidationError, RecordingLocked
from app.inventory.control_layer.intake_context import IntakeContext
from app.inventory.control_layer.managers.allocation_link_manager import AllocationLinkManager
from app.inventory.control_layer.managers.auto_intake_manager import AutoIntakeManager
from app.inventory.control_layer.managers.scan_command_manager import ScanCommandHandler
from app.inventory.control_layer.managers.shipment_graph_manager import ShipmentGraphManager
from app.inventory.control_layer.session_thread import session_thread
from app.inventory.models.intake.enums import (
    AllocationCondition,
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
from app.inventory.presentation_layer.tools.code128_svg import generate_code128_svg
from app.inventory.presentation_layer.tools.inventory_access import (
    accessible_domain_ids,
    require_intake,
)
from app.procurement.models import Shipment, ShipmentLine

TEMPLATE_DIR = "inventory/intake"


def _int(raw) -> int | None:
    text = str(raw or "").strip()
    return int(text) if text.lstrip("-").isdigit() else None


def _decimal(raw) -> Decimal | None:
    text = str(raw or "").strip()
    try:
        return Decimal(text) if text else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def _report(request: HttpRequest, exc: Exception) -> None:
    if isinstance(exc, InventoryValidationError):
        for error in exc.errors:
            messages.error(request, error)
    else:
        messages.error(request, str(exc))


# ---------------------------------------------------------------------- #
# 6. INDEX (/inventory/intake/)
# ---------------------------------------------------------------------- #

@require_http_methods(["GET"])
def intake_index(request: HttpRequest) -> HttpResponse:
    require_intake(request)
    domain_ids = accessible_domain_ids(request)
    search = IntakeSessionSearch.build(request.GET, domain_ids=domain_ids)

    # Filter waiting on me
    waiting_on_me = request.GET.get("waiting_on_me") == "1"
    sessions_qs = IntakeSession.objects.filter(
        deleted_at__isnull=True
    ).select_related("warehouse", "room", "created_by").order_by("-id")

    if domain_ids:
        sessions_qs = sessions_qs.filter(
            warehouse__domains__id__in=domain_ids
        ).distinct()

    if search.query:
        q = search.query
        sessions_qs = sessions_qs.filter(
            Q(pk__icontains=q)
            | Q(warehouse__name__icontains=q)
            | Q(notes__icontains=q)
        )

    if search.status:
        sessions_qs = sessions_qs.filter(status=search.status)

    if waiting_on_me:
        sessions_qs = sessions_qs.filter(
            status__in=[IntakeSessionStatus.OPEN, IntakeSessionStatus.RECORDING_LOCKED],
            stock_posted_at__isnull=True,
        )

    sessions_list = list(sessions_qs[:50])

    context = {
        "sessions": sessions_list,
        "search": search,
        "waiting_on_me": waiting_on_me,
        "status_choices": IntakeSessionStatus.choices,
    }
    return render(request, f"{TEMPLATE_DIR}/index.html", context)


# ---------------------------------------------------------------------- #
# 1. CREATE (/inventory/intake/create/)
# ---------------------------------------------------------------------- #

@require_http_methods(["GET", "POST"])
def intake_create(request: HttpRequest) -> HttpResponse:
    require_intake(request)
    domain_ids = accessible_domain_ids(request)

    if request.method == "POST":
        warehouse_id = _int(request.POST.get("warehouse_id"))
        room_id = _int(request.POST.get("room_id"))
        shipment_ids = [
            _int(sid) for sid in request.POST.getlist("shipment_ids") if _int(sid) is not None
        ]
        notes = request.POST.get("notes", "").strip()

        if not warehouse_id:
            messages.error(request, "Warehouse selection is required.")
            return redirect("inventory_intake_create")
        elif not shipment_ids:
            messages.error(request, "Select at least one unfulfilled shipment to receive.")
            return redirect("inventory_intake_create")
        else:
            try:
                ctx = IntakeContext.start_session(
                    operator=request.user,
                    warehouse_id=warehouse_id,
                    room_id=room_id,
                    actor=request.user,
                )
                for sid in shipment_ids:
                    ctx.associate_shipment(shipment_id=sid, actor=request.user)
                session = ctx.session
                if notes:
                    session.notes = notes
                    session.save(update_fields=["notes", "updated_at"])
                messages.success(request, f"Intake session INTAKE-{session.pk} created.")
                return HttpResponseSeeOther(reverse("inventory_intake_session_detail", kwargs={"pk": session.pk}))
            except Exception as exc:
                _report(request, exc)
                return redirect("inventory_intake_create")

    warehouses_qs = Warehouse.objects.filter(deleted_at__isnull=True, is_active=True)
    if domain_ids:
        warehouses_qs = warehouses_qs.filter(domains__id__in=domain_ids).distinct()
    warehouses = list(warehouses_qs.order_by("name"))
    
    selected_wh_id = _int(request.GET.get("warehouse_id")) or (warehouses[0].pk if warehouses else None)
    rooms = (
        Room.objects.filter(warehouse_id=selected_wh_id, deleted_at__isnull=True).order_by("name")
        if selected_wh_id
        else []
    )

    unfulfilled_shipments = UnfulfilledShipmentSearch.index_list(domain_ids=domain_ids)

    if request.GET.get("format") == "htmx-search-results":
        return render(
            request,
            f"{TEMPLATE_DIR}/_shipment_search_results.html",
            {"unfulfilled_shipments": unfulfilled_shipments},
        )

    context = {
        "warehouses": warehouses,
        "selected_wh_id": selected_wh_id,
        "rooms": rooms,
        "unfulfilled_shipments": unfulfilled_shipments,
    }
    return render(request, f"{TEMPLATE_DIR}/create.html", context)


# ---------------------------------------------------------------------- #
# 2. RECORD (/inventory/intake/<pk>/record/)
# ---------------------------------------------------------------------- #

@require_http_methods(["GET", "POST"])
def intake_record(request: HttpRequest, pk: int) -> HttpResponse:
    require_intake(request)
    session = get_object_or_404(
        IntakeSession.objects.select_related("warehouse", "room", "active_shipment"),
        pk=pk,
        deleted_at__isnull=True,
    )
    ctx = IntakeContext(intake_session_id=session.pk)
    format_param = request.GET.get("format", "")

    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "scan":
            raw_payload = request.POST.get("raw_payload", "").strip()
            serial_number = request.POST.get("serial_number", "").strip()
            try:
                alloc, msg = ctx.process_scan(
                    raw_payload=raw_payload,
                    serial_number_override=serial_number,
                    actor=request.user,
                )
                if msg:
                    messages.success(request, msg)
            except Exception as exc:
                _report(request, exc)

        elif action == "set_active_shipment":
            shipment_id = _int(request.POST.get("shipment_id"))
            try:
                ctx.set_active_shipment(shipment_id=shipment_id, actor=request.user)
                messages.info(request, "Active shipment updated.")
            except Exception as exc:
                _report(request, exc)

        elif action == "finish_option1":
            # Post stock now
            try:
                ctx.lock_recording(actor=request.user)
                ctx.post_stock(actor=request.user)
                messages.success(request, f"Stock posted for session INTAKE-{session.pk}.")
                return redirect("inventory_intake_detail", pk=session.pk)
            except Exception as exc:
                _report(request, exc)

        elif action == "finish_option2":
            # Lock recording & continue to associate
            try:
                ctx.lock_recording(actor=request.user)
                messages.info(request, "Recording locked. Proceeding to shipment line association.")
                return redirect("inventory_intake_associate", pk=session.pk)
            except Exception as exc:
                _report(request, exc)

        if format_param == "htmx-scan-feed":
            session.refresh_from_db()
            part_progress = PartProgressStruct.for_session(session=session)
            truths = ShipmentLineTruthStruct.for_session(session=session)
            allocations = list(
                session.allocations.filter(deleted_at__isnull=True)
                .select_related("part", "shipment_line")
                .order_by("-id")
            )
            context = {
                "session": session,
                "part_progress": part_progress,
                "truths": truths,
                "allocations": allocations,
            }
            return render(request, f"{TEMPLATE_DIR}/_scan_live_region.html", context)

        return redirect("inventory_intake_record", pk=session.pk)

    # GET
    part_progress = PartProgressStruct.for_session(session=session)
    allocations = list(
        session.allocations.filter(deleted_at__isnull=True)
        .select_related("part", "shipment_line", "shipment_line__shipment")
        .order_by("-id")
    )
    shipment_links = list(
        session.shipment_associations.filter(deleted_at__isnull=True).select_related("shipment")
    )
    truths = ShipmentLineTruthStruct.for_session(session=session)

    context = {
        "session": session,
        "part_progress": part_progress,
        "allocations": allocations,
        "shipment_links": shipment_links,
        "truths": truths,
        "is_locked": session.recording_locked_at is not None,
    }
    return render(request, f"{TEMPLATE_DIR}/record.html", context)


# ---------------------------------------------------------------------- #
# 3. ASSOCIATE (/inventory/intake/<pk>/associate/)
# ---------------------------------------------------------------------- #

@require_http_methods(["GET", "POST"])
def intake_associate(request: HttpRequest, pk: int) -> HttpResponse:
    require_intake(request)
    session = get_object_or_404(
        IntakeSession.objects.select_related("warehouse", "room"),
        pk=pk,
        deleted_at__isnull=True,
    )

    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "link":
            allocation_id = _int(request.POST.get("allocation_id"))
            shipment_line_id = _int(request.POST.get("shipment_line_id"))
            if allocation_id and shipment_line_id:
                try:
                    alloc = ItemAllocation.objects.get(pk=allocation_id, intake_session=session)
                    AllocationLinkManager.link(
                        allocation=alloc, shipment_line_id=shipment_line_id, actor=request.user
                    )
                    messages.success(request, f"Linked {alloc.part.part_number} to shipment line.")
                except Exception as exc:
                    _report(request, exc)

        elif action == "unlink":
            allocation_id = _int(request.POST.get("allocation_id"))
            if allocation_id:
                try:
                    alloc = ItemAllocation.objects.get(pk=allocation_id, intake_session=session)
                    AllocationLinkManager.unlink(allocation=alloc, actor=request.user)
                    messages.info(request, f"Unlinked {alloc.part.part_number}.")
                except Exception as exc:
                    _report(request, exc)

        elif action == "finish":
            return redirect("inventory_intake_detail", pk=session.pk)

        return redirect("inventory_intake_associate", pk=session.pk)

    associate_progress = AssociateProgressStruct.for_session(session=session)
    truths = ShipmentLineTruthStruct.for_session(session=session)
    allocations = list(
        session.allocations.filter(deleted_at__isnull=True)
        .select_related("part", "shipment_line", "shipment_line__shipment")
        .order_by("part__part_number", "-id")
    )

    # Group truths and allocations by part for clear card pairing
    parts_map = {}
    for p in associate_progress:
        parts_map[p.part_id] = {
            "progress": p,
            "truths": [t for t in truths if t.part_id == p.part_id],
            "allocations": [a for a in allocations if a.part_id == p.part_id],
        }

    context = {
        "session": session,
        "associate_progress": associate_progress,
        "parts_map": parts_map,
        "is_locked": session.recording_locked_at is not None,
    }
    return render(request, f"{TEMPLATE_DIR}/associate.html", context)


# ---------------------------------------------------------------------- #
# 4. DISCREPANCIES (/inventory/intake/<pk>/discrepancies/)
# ---------------------------------------------------------------------- #

@require_http_methods(["GET"])
def intake_discrepancies(request: HttpRequest, pk: int) -> HttpResponse:
    require_intake(request)
    session = get_object_or_404(
        IntakeSession.objects.select_related("warehouse", "room"),
        pk=pk,
        deleted_at__isnull=True,
    )

    truths = ShipmentLineTruthStruct.for_session(session=session)
    shortages = [t for t in truths if t.shortage > 0]

    unlinked_allocations = list(
        session.allocations.filter(deleted_at__isnull=True, shipment_line__isnull=True)
        .select_related("part")
        .order_by("part__part_number")
    )

    rejected_allocations = list(
        session.allocations.filter(deleted_at__isnull=True)
        .exclude(condition=AllocationCondition.GOOD)
        .select_related("part", "shipment_line")
        .order_by("part__part_number")
    )

    closure = ShipmentGraphManager.closure_for(session=session)
    closure_shipments = []
    if closure.reaches_beyond_session:
        labels = ShipmentGraphManager.labels(closure=closure)
        for sh_id in closure.shipment_ids:
            closure_shipments.append({
                "id": sh_id,
                "number": labels["shipments"].get(sh_id, f"SHIP-{sh_id}"),
                "is_own": sh_id in closure.own_shipment_ids,
            })

    context = {
        "session": session,
        "shortages": shortages,
        "unlinked_allocations": unlinked_allocations,
        "rejected_allocations": rejected_allocations,
        "closure": closure,
        "closure_shipments": closure_shipments,
    }
    return render(request, f"{TEMPLATE_DIR}/discrepancies.html", context)


# ---------------------------------------------------------------------- #
# 5. DETAIL / REVIEW (/inventory/intake/<pk>/)
# ---------------------------------------------------------------------- #

@require_http_methods(["GET", "POST"])
def intake_detail(request: HttpRequest, pk: int) -> HttpResponse:
    require_intake(request)
    session = get_object_or_404(
        IntakeSession.objects.select_related("warehouse", "room", "stock_posted_by", "created_by"),
        pk=pk,
        deleted_at__isnull=True,
    )
    ctx = IntakeContext(intake_session_id=session.pk)
    thread_mgr = session_thread(session, request.user)
    format_param = request.GET.get("format", "")

    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "scan":
            raw_payload = request.POST.get("raw_payload", "").strip()
            serial_number = request.POST.get("serial_number", "").strip()
            err_msg = None
            try:
                alloc, msg = ctx.process_scan(
                    raw_payload=raw_payload,
                    serial_number_override=serial_number,
                    actor=request.user,
                )
                if msg:
                    messages.success(request, msg)
            except Exception as exc:
                err_msg = str(exc)
                _report(request, exc)

            if format_param == "htmx-scan-feed":
                session.refresh_from_db()
                part_progress = PartProgressStruct.for_session(session=session)
                truths = ShipmentLineTruthStruct.for_session(session=session)
                allocations = list(
                    session.allocations.filter(deleted_at__isnull=True)
                    .select_related("part", "shipment_line")
                    .order_by("-id")
                )
                context = {
                    "session": session,
                    "part_progress": part_progress,
                    "truths": truths,
                    "allocations": allocations,
                    "error": err_msg,
                }
                return render(request, f"{TEMPLATE_DIR}/_scan_live_region.html", context)

            return HttpResponseSeeOther(reverse("inventory_intake_session_detail", kwargs={"pk": session.pk}))

        elif action == "split":
            allocation_id = _int(request.POST.get("allocation_id"))
            good_qty = _decimal(request.POST.get("good_qty", "0")) or Decimal("0")
            rejected_qty = _decimal(request.POST.get("rejected_qty", "0")) or Decimal("0")
            if allocation_id:
                try:
                    alloc = ItemAllocation.objects.get(pk=allocation_id, intake_session=session)
                    alloc.split(good_quantity=good_qty, rejected_quantity=rejected_qty, actor=request.user)
                    messages.success(request, "Allocation split successfully.")
                except Exception as exc:
                    _report(request, exc)
            return HttpResponseSeeOther(reverse("inventory_intake_session_detail", kwargs={"pk": session.pk}))

        elif action in ("close", "post_stock", "finish_option1"):
            try:
                ctx.lock_recording(actor=request.user)
                ctx.post_stock(actor=request.user)
                messages.success(request, f"Stock posted for session INTAKE-{session.pk}.")
            except Exception as exc:
                _report(request, exc)
            return HttpResponseSeeOther(reverse("inventory_intake_session_detail", kwargs={"pk": session.pk}))

        elif action == "add_comment":
            comment_text = request.POST.get("comment", "").strip()
            if comment_text:
                thread_mgr.add_comment(comment_text, is_human_made=True)
                messages.success(request, "Comment added.")
            return HttpResponseSeeOther(reverse("inventory_intake_session_detail", kwargs={"pk": session.pk}))

    # GET
    part_progress = PartProgressStruct.for_session(session=session)
    truths = ShipmentLineTruthStruct.for_session(session=session)
    allocations = list(
        session.allocations.filter(deleted_at__isnull=True)
        .select_related("part", "shipment_line", "shipment_line__shipment")
        .order_by("-id")
    )
    shipment_links = list(
        session.shipment_associations.filter(deleted_at__isnull=True).select_related("shipment")
    )
    comments = thread_mgr.comments()

    context = {
        "session": session,
        "part_progress": part_progress,
        "truths": truths,
        "allocations": allocations,
        "shipment_links": shipment_links,
        "comments": comments,
        "is_locked": session.recording_locked_at is not None,
    }

    if session.status in (IntakeSessionStatus.DRAFT, IntakeSessionStatus.ACTIVE) and not session.recording_locked_at:
        return render(request, f"{TEMPLATE_DIR}/record.html", context)

    return render(request, f"{TEMPLATE_DIR}/detail.html", context)


# ---------------------------------------------------------------------- #
# 7. PRINT (/inventory/intake/<pk>/print/)
# ---------------------------------------------------------------------- #

@require_http_methods(["GET"])
def intake_print(request: HttpRequest, pk: int) -> HttpResponse:
    require_intake(request)
    session = get_object_or_404(
        IntakeSession.objects.select_related("warehouse", "room"),
        pk=pk,
        deleted_at__isnull=True,
    )
    mode = request.GET.get("mode", "pick")  # 'pick' or 'receipt'

    session_barcode_svg = generate_code128_svg(f"INTAKE-{session.pk}", height=45)

    shipment_links = list(
        session.shipment_associations.filter(deleted_at__isnull=True).select_related("shipment")
    )

    shipments_data = []
    for link in shipment_links:
        shipment = link.shipment
        ship_barcode_svg = generate_code128_svg(f"SHIP-{shipment.pk}", height=40)
        lines = list(
            ShipmentLine.objects.filter(shipment=shipment, deleted_at__isnull=True).select_related("part")
        )
        shipments_data.append({
            "shipment": shipment,
            "barcode_svg": ship_barcode_svg,
            "lines": lines,
        })

    context = {
        "session": session,
        "session_barcode_svg": session_barcode_svg,
        "shipments_data": shipments_data,
        "mode": mode,
    }
    return render(request, f"{TEMPLATE_DIR}/print.html", context)


# ---------------------------------------------------------------------- #
# GLOBAL ALLOCATION PORTAL (/inventory/intake/allocate/)
# ---------------------------------------------------------------------- #

@require_http_methods(["GET", "POST"])
def intake_allocate(request: HttpRequest) -> HttpResponse:
    require_intake(request)
    domain_ids = accessible_domain_ids(request)

    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "link":
            allocation_id = _int(request.POST.get("allocation_id"))
            shipment_line_id = _int(request.POST.get("shipment_line_id"))
            if allocation_id and shipment_line_id:
                try:
                    alloc = ItemAllocation.objects.get(pk=allocation_id, deleted_at__isnull=True)
                    AllocationLinkManager.link(
                        allocation=alloc, shipment_line_id=shipment_line_id, actor=request.user
                    )
                    messages.success(request, f"Linked allocation to shipment line.")
                except Exception as exc:
                    _report(request, exc)

        elif action == "unlink":
            allocation_id = _int(request.POST.get("allocation_id"))
            if allocation_id:
                try:
                    alloc = ItemAllocation.objects.get(pk=allocation_id, deleted_at__isnull=True)
                    AllocationLinkManager.unlink(allocation=alloc, actor=request.user)
                    messages.info(request, "Allocation unlinked.")
                except Exception as exc:
                    _report(request, exc)

        return redirect("inventory_intake_allocate")

    unlinked_qs = ItemAllocation.objects.filter(
        deleted_at__isnull=True,
        shipment_line__isnull=True,
        intake_session__deleted_at__isnull=True,
    ).exclude(intake_session__status=IntakeSessionStatus.CANCELLED)

    if domain_ids:
        unlinked_qs = unlinked_qs.filter(
            intake_session__warehouse__domains__id__in=domain_ids
        ).distinct()

    unlinked_allocations = list(
        unlinked_qs.select_related("part", "intake_session")
        .order_by("part__part_number", "-id")
    )

    open_lines = list(
        ShipmentLine.objects.filter(
            deleted_at__isnull=True,
            shipment__deleted_at__isnull=True,
        )
        .select_related("shipment", "part")
        .order_by("part__part_number", "id")
    )
    
    # Calculate truth for open lines
    truths = [ShipmentLineTruthStruct.for_line(line=line) for line in open_lines]
    unmet_truths = [t for t in truths if t.remaining_capacity > 0]

    context = {
        "unlinked_allocations": unlinked_allocations,
        "unmet_truths": unmet_truths,
    }
    return render(request, f"{TEMPLATE_DIR}/allocate.html", context)


# ---------------------------------------------------------------------- #
# AUTO INTAKE PORTAL (/inventory/intake/auto/)
# ---------------------------------------------------------------------- #

@require_http_methods(["GET", "POST"])
def auto_intake_portal(request: HttpRequest) -> HttpResponse:
    require_intake(request)
    domain_ids = accessible_domain_ids(request)

    if request.method == "POST":
        warehouse_id = _int(request.POST.get("warehouse_id"))
        room_id = _int(request.POST.get("room_id"))
        shipment_id = _int(request.POST.get("shipment_id"))
        hardware_device_id = request.POST.get("hardware_device_id", "").strip()

        line_targets: dict[int, tuple[Decimal, Decimal]] = {}
        for key, val in request.POST.items():
            if key.startswith("accepted_"):
                line_id = _int(key.split("_")[1])
                if line_id is not None:
                    good = _decimal(val)
                    rejected = _decimal(request.POST.get(f"rejected_{line_id}", "0"))
                    line_targets[line_id] = (good, rejected)

        if not warehouse_id or not shipment_id:
            messages.error(request, "Warehouse and shipment selection are required.")
        else:
            try:
                ctx = IntakeContext.commit_auto_intake(
                    operator=request.user,
                    warehouse_id=warehouse_id,
                    room_id=room_id,
                    shipment_id=shipment_id,
                    line_targets=line_targets,
                    hardware_device_id=hardware_device_id,
                    actor=request.user,
                )
                messages.success(request, "Auto Intake completed successfully.")
                return redirect("inventory_intake_detail", pk=ctx.intake_session_id)
            except Exception as exc:
                _report(request, exc)

    warehouses_qs = Warehouse.objects.filter(deleted_at__isnull=True, is_active=True)
    if domain_ids:
        warehouses_qs = warehouses_qs.filter(domains__id__in=domain_ids).distinct()
    warehouses = list(warehouses_qs.order_by("name"))
    selected_wh_id = _int(request.GET.get("warehouse_id")) or (warehouses[0].pk if warehouses else None)
    rooms = Room.objects.filter(warehouse_id=selected_wh_id, deleted_at__isnull=True).order_by("name") if selected_wh_id else []
    shipments = Shipment.objects.filter(deleted_at__isnull=True).order_by("-id")[:50]

    context = {
        "warehouses": warehouses,
        "selected_wh_id": selected_wh_id,
        "rooms": rooms,
        "shipments": shipments,
    }
    return render(request, f"{TEMPLATE_DIR}/auto.html", context)
