"""The Demand Loop — list / create / edit / detail entrypoints (Phase 1).

Every list query here is domain-scoped (D5) through
``procurement_access.accessible_domain_ids``. Every permission gate is
enforced here, at the entrypoint, not left to the template (Phase 0 §5 /
shared_workflows.md §3) — this build is D62's "no permission checks anywhere"
becoming false for the first time on the demand sector.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date, parse_datetime
from django.views.decorators.http import require_http_methods

from app.administration.models import Domain
from app.parts.models import Part
from app.procurement.control_layer.adapters.part_demand_create_adaptor import (
    PartDemandCreateAdaptor,
)
from app.procurement.control_layer.domain_structs.part_demand_struct import (
    PartDemandDetailStruct,
)
from app.procurement.control_layer.errors import (
    ProcurementValidationError,
    TransitionRefused,
)
from app.procurement.control_layer.factories.part_demand_factory import (
    PartDemandFactory,
)
from app.procurement.control_layer.part_demand_context import PartDemandContext
from app.procurement.models import (
    DemandPriority,
    DemandSourceModule,
    DemandState,
    IssuanceState,
    PartDemand,
    PurchaseOrderStatus,
    PurchasingState,
    ShipmentState,
)
from app.procurement.presentation_layer.metrics.demand_metrics import DemandMetrics
from app.procurement.presentation_layer.search.open_demand_search import (
    ALLOCATABLE_DEMAND_STATE_CHOICES,
    OpenDemandSearch,
)
from app.procurement.presentation_layer.tools.procurement_access import (
    accessible_domain_ids,
    can_buy,
    can_cancel_demand,
    can_edit_demand,
    can_manage_demand,
    can_request,
    is_in_domain,
    require_request,
)

PAGE_SIZE = 50

#: The two consumers of the shared left-heavy assignment search
#: (procurement/demands/components/server_side_search_left_heavy_assignment.html).
#: Whitelisted rather than accepting an arbitrary URL/field name from the
#: query string — this view resolves the per-row Allocate form's target
#: itself, it never trusts the client for it.
_LEFT_HEAVY_CONSUMERS = {
    "po_create": {"url_name": "purchase_order_create", "line_field": "line_index"},
    "po_detail": {"url_name": "purchase_order_detail", "line_field": "line_id"},
}


def _int(raw) -> int | None:
    raw = (raw or "").strip()
    return int(raw) if raw.isdigit() else None


def _demand_or_404_in_domain(request: HttpRequest, pk: int) -> PartDemand:
    """D5: a demand outside the user's domain access is not reachable at all —
    distinct from the cross-domain PO-reference rule (Phase 0 §5), which is
    about a foreign record surfaced *on* a page the user already has access
    to. This gate is the page itself."""
    demand = get_object_or_404(
        PartDemand.objects.select_related("part", "domain", "requested_by"),
        pk=pk,
    )
    if not is_in_domain(request, demand.domain_id):
        raise Http404
    return demand


def _part_search_fragment(request: HttpRequest) -> HttpResponse:
    """`<search-dropdown>` results for the `part` field on the create form —
    same canonical URL (`demand_create`) as the form itself, per the
    format= contract, not a dedicated route."""
    q = request.GET.get("q", "").strip()
    qs = Part.objects.all()
    if q:
        qs = qs.filter(Q(part_number__icontains=q) | Q(name__icontains=q))
    parts = qs.order_by("part_number")[:25]
    return render(
        request, "procurement/demands/_part_search_results.html", {"parts": parts}
    )


#: `mode=` -> which component this response renders. Default is "client" —
#: hitting this endpoint with no mode returns the fast, default-filtered
#: search, same as a fresh page load would show.
_LEFT_HEAVY_COMPONENT_TEMPLATES = {
    "client": "procurement/demands/components/client_side_filtered_demand_left_heavy_assignment.html",
    "server": "procurement/demands/components/server_side_search_left_heavy_assignment.html",
}


def _left_heavy_pool_fragment(request: HttpRequest, *, domain_ids) -> HttpResponse:
    """The shared search behind both left-heavy assignment components
    (procurement/demands/components/*_left_heavy_assignment.html) — one
    canonical URL (`demand_index`) branching on `format=`, per
    harness/UX_UI.md's rule against parallel fragment-only routes.

    `render=rows` (used by the server-side card's own filter form, targeting
    just its `<tbody>`) returns bare `<tr>` rows. Anything else returns the
    full component card — `mode=server` for the "search demands with existing
    purchase order linkages" swap-in, `mode=client` (the default) for the
    fast path and the server card's "Back" swap-out.
    """
    part_id = _int(request.GET.get("part_id"))
    consumer = request.GET.get("consumer", "")
    consumer_spec = _LEFT_HEAVY_CONSUMERS.get(consumer)
    part = Part.objects.filter(pk=part_id).first() if part_id else None
    if part is None or consumer_spec is None:
        return HttpResponse(status=400)

    mode = request.GET.get("mode", "client")
    exclude_purchase_order = _int(request.GET.get("exclude_purchase_order"))
    exclude_ids_raw = request.GET.get("exclude_ids", "")
    exclude_ids = [int(v) for v in exclude_ids_raw.split(",") if v.strip().isdigit()]
    unique_id = request.GET.get("unique_id", "")
    line_ref = request.GET.get("line_ref", "")

    allocate_url = (
        reverse(consumer_spec["url_name"], args=[exclude_purchase_order])
        if consumer == "po_detail"
        else reverse(consumer_spec["url_name"])
    )

    shared_ctx = {
        "unique_id": unique_id,
        "part": part,
        "consumer": consumer,
        "line_ref": line_ref,
        "line_field_name": consumer_spec["line_field"],
        "allocate_url": allocate_url,
        "exclude_purchase_order": exclude_purchase_order or "",
        "exclude_ids": exclude_ids_raw,
        "demand_status_choices": ALLOCATABLE_DEMAND_STATE_CHOICES,
        "po_status_choices": PurchaseOrderStatus.choices,
    }

    pool = OpenDemandSearch.for_part(
        part_id=part_id,
        domain_ids=domain_ids,
        exclude_purchase_order=exclude_purchase_order,
        exclude_ids=exclude_ids,
        include_linked=mode == "server",
        demand_id=_int(request.GET.get("demand_id")),
        demand_state=request.GET.get("demand_state", "").strip(),
        created_from=parse_date(request.GET.get("created_from", "") or ""),
        created_to=parse_date(request.GET.get("created_to", "") or ""),
        po_status=request.GET.get("po_status", "").strip() if mode == "server" else "",
    )[:100]

    if request.GET.get("render") == "rows":
        return render(
            request,
            "procurement/demands/components/_left_heavy_pool_rows.html",
            {
                "pool": pool,
                "allocate_url": allocate_url,
                "line_field_name": consumer_spec["line_field"],
                "line_ref": line_ref,
            },
        )

    return render(
        request,
        _LEFT_HEAVY_COMPONENT_TEMPLATES.get(mode, _LEFT_HEAVY_COMPONENT_TEMPLATES["client"]),
        {"pool": pool, **shared_ctx},
    )


@require_http_methods(["GET"])
def demand_index(request: HttpRequest) -> HttpResponse:
    """Search/list page (part_demand_workflows.md §2.1). One canonical list —
    the Approver's queue is `?demand_state=required`, the Buyer's "what needs
    buying" view is a sparse `purchasing_state` filter. No saved presets."""
    domain_ids = accessible_domain_ids(request)

    if request.GET.get("format") == "htmx-left-heavy":
        return _left_heavy_pool_fragment(request, domain_ids=domain_ids)

    demand_state = request.GET.get("demand_state", "").strip()
    purchasing_state = request.GET.get("purchasing_state", "").strip()
    shipment_state = request.GET.get("shipment_state", "").strip()
    issuance_state = request.GET.get("issuance_state", "").strip()
    priority = request.GET.get("priority", "").strip()
    source = request.GET.get("source", "").strip() or request.GET.get("source_module", "").strip()
    event_id_raw = request.GET.get("event_id", "").strip()
    event_id = int(event_id_raw) if event_id_raw.isdigit() else None
    q = request.GET.get("q", "").strip()
    part_id_raw = request.GET.get("part_id", "").strip()
    part_id = int(part_id_raw) if part_id_raw.isdigit() else None
    domain_id_raw = request.GET.get("domain_id", "").strip()
    domain_id = int(domain_id_raw) if domain_id_raw.isdigit() else None
    needed_by_from = (
        parse_datetime(request.GET.get("needed_by_from", ""))
        or parse_date(request.GET.get("needed_by_from", ""))
        if request.GET.get("needed_by_from")
        else None
    )
    needed_by_to = (
        parse_datetime(request.GET.get("needed_by_to", ""))
        or parse_date(request.GET.get("needed_by_to", ""))
        if request.GET.get("needed_by_to")
        else None
    )
    created_from = (
        parse_datetime(request.GET.get("created_from", ""))
        or parse_date(request.GET.get("created_from", ""))
        if request.GET.get("created_from")
        else None
    )
    created_to = (
        parse_datetime(request.GET.get("created_to", ""))
        or parse_date(request.GET.get("created_to", ""))
        if request.GET.get("created_to")
        else None
    )
    requested_by = request.GET.get("requested_by", "").strip()
    po_number = request.GET.get("po_number", "").strip()

    qs = OpenDemandSearch.index_list(
        domain_ids=domain_ids,
        demand_state=demand_state,
        purchasing_state=purchasing_state,
        shipment_state=shipment_state,
        issuance_state=issuance_state,
        priority=priority,
        source=source,
        event_id=event_id,
        part_id=part_id,
        domain_id=domain_id,
        needed_by_from=needed_by_from,
        needed_by_to=needed_by_to,
        created_from=created_from,
        created_to=created_to,
        requested_by=requested_by,
        po_number=po_number,
        q=q,
    )

    stats = DemandMetrics.summarize(qs)

    paginator = Paginator(qs, PAGE_SIZE)
    page = paginator.get_page(request.GET.get("page", "1"))

    context = {
        "page": page,
        "demands": page.object_list,
        "stats": stats,
        "filters": {
            "demand_state": demand_state,
            "purchasing_state": purchasing_state,
            "shipment_state": shipment_state,
            "issuance_state": issuance_state,
            "priority": priority,
            "source": source,
            "event_id": event_id_raw,
            "q": q,
            "part_id": part_id_raw,
            "domain_id": domain_id_raw,
            "needed_by_from": request.GET.get("needed_by_from", ""),
            "needed_by_to": request.GET.get("needed_by_to", ""),
            "created_from": request.GET.get("created_from", ""),
            "created_to": request.GET.get("created_to", ""),
            "requested_by": requested_by,
            "po_number": po_number,
        },
        "demand_states": DemandState.choices,
        "purchasing_states": PurchasingState.choices,
        "shipment_states": ShipmentState.choices,
        "issuance_states": IssuanceState.choices,
        "priorities": DemandPriority.choices,
        "sources": DemandSourceModule.choices,
        "domains": Domain.objects.filter(pk__in=domain_ids).order_by("name"),
        "can_request": can_request(request),
    }

    if request.GET.get("format") == "htmx-search-results":
        return render(request, "procurement/demands/_index_results.html", context)
    return render(request, "procurement/demands/index.html", context)


@require_http_methods(["GET", "POST"])
def demand_create(request: HttpRequest) -> HttpResponse:
    """Simple single-card form (part_demand_workflows.md §2.2) — PartDemand has
    zero qualifying reverse FKs, so this is deliberately not a wizard."""
    if request.method == "GET" and request.GET.get("format") == "htmx-search-results":
        return _part_search_fragment(request)

    require_request(request)

    user_domain_ids = list(request.user.get_all_domain_ids())

    if request.method == "POST":
        try:
            data = PartDemandCreateAdaptor.adapt(
                request.POST, requested_by=request.user
            )
        except ProcurementValidationError as exc:
            for error in exc.errors:
                messages.error(request, error)
            return redirect(reverse("demand_create"))

        if data.domain_id not in user_domain_ids:
            messages.error(
                request,
                "You may only raise a demand against a domain you are assigned to.",
            )
            return redirect(reverse("demand_create"))

        demand = PartDemandFactory.create(
            part_id=data.part_id,
            domain_id=data.domain_id,
            quantity_requested=data.quantity_requested,
            demand_state=data.demand_state,
            priority=data.priority,
            needed_by=data.needed_by,
            notes=data.notes,
            expected_cost=data.expected_cost,
            source=data.source,
            serial_number_tracking_required=data.serial_number_tracking_required,
            requested_by=request.user,
            actor=request.user,
        )
        messages.success(request, f"Demand #{demand.pk} created.")
        return redirect(reverse("demand_detail", kwargs={"pk": demand.pk}))

    from django.utils import timezone

    domains = Domain.objects.filter(pk__in=user_domain_ids).order_by("name")
    default_needed_by = timezone.now().strftime("%Y-%m-%dT%H:%M")
    return render(
        request,
        "procurement/demands/create.html",
        {
            "domains": domains,
            "show_domain_picker": domains.count() > 1,
            "single_domain": domains.first() if domains.count() == 1 else None,
            "default_needed_by": default_needed_by,
            "priorities": DemandPriority.choices,
        },
    )


@require_http_methods(["GET", "POST"])
def demand_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Read-only work portal (part_demand_workflows.md §2.4). Nothing here
    writes except Cancel/Delete on the header — every other mutation links out
    to the edit page. Both actions post back to this same canonical URL
    (endpoint_patterns.md §3.3: POST performs a state-changing action)."""
    demand = _demand_or_404_in_domain(request, pk)

    if request.method == "POST":
        action = request.POST.get("action")
        ctx = PartDemandContext(pk)

        if action == "cancel":
            if not can_cancel_demand(request, demand):
                raise PermissionDenied("You may not cancel this demand.")
            try:
                ctx.cancel(actor=request.user, notes=request.POST.get("notes", ""))
                messages.success(request, "Demand cancelled.")
            except TransitionRefused as exc:
                for error in exc.errors:
                    messages.error(request, error)
            return redirect(reverse("demand_detail", kwargs={"pk": pk}))

        if action == "delete":
            if not can_cancel_demand(request, demand):
                raise PermissionDenied("You may not delete this demand.")
            verdict = ctx.delete(actor=request.user)
            if verdict.hard_delete:
                messages.success(request, "Demand deleted.")
            else:
                messages.success(request, f"Demand deactivated — {verdict.reason}")
            return redirect(reverse("demand_index"))

        messages.error(request, "Unknown action.")
        return redirect(reverse("demand_detail", kwargs={"pk": pk}))

    detail = PartDemandDetailStruct.load(demand_id=pk)
    can_cancel = can_cancel_demand(request, demand)
    # Deliberate UI anti-pattern (serialized_inventory_tracking.md §3): the
    # full issue-row history renders directly here, un-nested, rather than
    # behind an aggregated progress bar. `issues` is inventory's reverse FK
    # (PartIssue.part_demand) — read only, no import of inventory across the
    # app boundary (D7).
    issue_rows = list(
        demand.issues.select_related(
            "created_by", "from_room__warehouse", "from_room",
            "from_storage_location", "issued_to_asset",
        ).order_by("-issued_at")
    )
    context = {
        "demand": demand,
        "detail": detail,
        "can_cancel": can_cancel,
        "issue_rows": issue_rows,
        # Same actor set as cancel (Requester-own or demand_manage), D4/D6.
        "can_delete": can_cancel,
        "delete_confirm_copy": (
            "This demand has no purchase order allocations and no journal "
            "activity beyond creation — deleting it removes the row entirely."
            if detail.deletion_verdict.hard_delete
            else f"{detail.deletion_verdict.reason} This deactivates the demand rather than removing it."
        ),
    }
    return render(request, "procurement/demands/detail.html", context)


@require_http_methods(["GET", "POST"])
def demand_edit(request: HttpRequest, pk: int) -> HttpResponse:
    """Full-width edit page (part_demand_workflows.md §2.3) — the only place
    every status-changing action lives. Each of the four cards posts back to
    this same canonical URL with a distinct `action`, since Phase 0's URL
    contract declares no sub-paths for these transitions."""
    demand = _demand_or_404_in_domain(request, pk)
    if not can_edit_demand(request, demand):
        raise PermissionDenied("You may not edit this demand.")

    ctx = PartDemandContext(pk)

    if request.method == "POST":
        action = request.POST.get("action", "save_fields")
        try:
            if action == "save_fields":
                _handle_save_fields(request, ctx, demand)
                messages.success(request, "Demand fields updated.")
            elif action == "approve":
                if not can_manage_demand(request):
                    raise PermissionDenied(
                        "Approving requires the 'demand_manage' permission."
                    )
                ctx.approve(actor=request.user, notes=request.POST.get("notes", ""))
                messages.success(request, "Demand approved.")
            elif action == "reject":
                if not can_manage_demand(request):
                    raise PermissionDenied(
                        "Rejecting requires the 'demand_manage' permission."
                    )
                ctx.reject(actor=request.user, notes=request.POST.get("notes", ""))
                messages.success(request, "Demand rejected.")
            elif action == "advance_shipment":
                if not can_buy(request):
                    raise PermissionDenied(
                        "Advancing shipment requires the 'buy' permission."
                    )
                to_stage = request.POST.get("to_stage", "")
                ctx.advance_shipment(
                    to_stage=to_stage,
                    actor=request.user,
                    notes=request.POST.get("notes", ""),
                )
                messages.success(request, "Shipment status updated.")
            elif action == "issuance":
                is_owner = demand.requested_by_id == request.user.pk
                if not (can_manage_demand(request) or (can_request(request) and is_owner)):
                    raise PermissionDenied(
                        "Updating issuance requires ownership of this demand or "
                        "the 'demand_manage' permission."
                    )
                to_stage = request.POST.get("to_stage", "")
                ctx.set_issuance_state(
                    to_stage=to_stage,
                    actor=request.user,
                    notes=request.POST.get("notes", ""),
                )
                messages.success(request, "Issuance status updated.")
            else:
                messages.error(request, "Unknown action.")
        except TransitionRefused as exc:
            # D9-D11's gates: name the reason (e.g. the PO that must be
            # cancelled first), never a generic failure (shared_workflows.md §3).
            for error in exc.errors:
                messages.error(request, error)
        except ProcurementValidationError as exc:
            for error in exc.errors:
                messages.error(request, error)
        return redirect(reverse("demand_edit", kwargs={"pk": pk}))

    struct = ctx.struct()
    detail = PartDemandDetailStruct.load(demand_id=pk)
    context = {
        "demand": demand,
        "struct": struct,
        "history": detail.journal,
        "priorities": DemandPriority.choices,
        "shipment_states": ShipmentState.choices,
        "issuance_states": IssuanceState.choices,
        "can_manage_demand": can_manage_demand(request),
        "can_buy": can_buy(request),
        "is_owner": demand.requested_by_id == request.user.pk,
        "can_request": can_request(request),
    }
    return render(request, "procurement/demands/edit.html", context)


def _handle_save_fields(request: HttpRequest, ctx: PartDemandContext, demand: PartDemand) -> None:
    priority = request.POST.get("priority") or demand.priority
    needed_by_raw = (request.POST.get("needed_by") or "").strip()
    needed_by = parse_datetime(needed_by_raw) if needed_by_raw else None
    notes = request.POST.get("notes", "")
    serial_tracking = request.POST.get("serial_number_tracking_required") in {
        "on",
        "1",
        "true",
    }
    quantity_requested = None
    raw_qty = str(request.POST.get("quantity_requested", "")).strip()
    if raw_qty:
        try:
            quantity_requested = Decimal(raw_qty)
        except InvalidOperation:
            quantity_requested = None

    ctx.update_fields(
        priority=priority,
        needed_by=needed_by,
        notes=notes,
        quantity_requested=quantity_requested,
        serial_number_tracking_required=serial_tracking,
        actor=request.user,
    )
