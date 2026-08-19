"""Maintenance-facing part demand queue and detail entrypoints.

Legacy: user_views/manager/part_demands.py (the approval queue and its five
bulk POST routes) and core/part_demand.py (the detail page and its seven
verbs).

D7 in the presentation layer: this app reads procurement.PartDemand and calls
procurement's own PartDemandContext for every write. It never assigns a state
column, never creates a demand here (that is PartDemandManager.create_for_action
from an action), and never reaches into procurement's tables to mutate them.
The maintenance-specific part is the *reach outward* through
MaintenanceDemandLink for the Action / Event / Asset context the legacy queue
showed.

Permission model, deliberately mixed:
  - reaching a demand at all is maintenance's coarse domain fence (D5), same
    as every other page in this app;
  - approving, rejecting and issuing are procurement's `demand_manage`
    permission, because the demand is procurement's record and its approval
    semantics are procurement's to define. Inventing a parallel maintenance
    codename for the same decision would let the two disagree.
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

from app.events.models.event import EventStatus
from app.maintenance.presentation_layer.search.maintenance_demand_search import (
    SCOPE_ALL,
    SCOPE_CHOICES,
    SCOPE_MAINTENANCE,
    MaintenanceDemandSearch,
)
from app.maintenance.presentation_layer.tools.maintenance_access import (
    accessible_domain_ids,
    is_in_domain,
)
from app.parts.models import Part
from app.procurement.control_layer.errors import (
    ProcurementValidationError,
    TransitionRefused,
)
from app.procurement.control_layer.part_demand_context import PartDemandContext
from app.procurement.models import (
    DemandPriority,
    DemandState,
    IssuanceState,
    PartDemand,
    PurchasingState,
)
from app.procurement.presentation_layer.tools.procurement_access import (
    can_manage_demand,
)

PAGE_SIZE = 50

#: Bulk actions cap. A checkbox queue with select-all can post an unbounded id
#: list; each id costs a guard evaluation and a transition, so the page refuses
#: rather than silently truncating.
BULK_LIMIT = 200


def _int(raw) -> int | None:
    raw = (raw or "").strip()
    return int(raw) if raw.isdigit() else None


def _date(raw: str):
    raw = (raw or "").strip()
    if not raw:
        return None
    return parse_datetime(raw) or parse_date(raw)


def _demand_or_404_in_domain(request: HttpRequest, pk: int) -> PartDemand:
    """D5: a demand outside the user's domain access is not reachable at all."""
    demand = get_object_or_404(
        PartDemand.objects.select_related("part", "domain", "requested_by"),
        pk=pk,
        deleted_at__isnull=True,
    )
    if not is_in_domain(request, demand.domain_id):
        raise Http404
    return demand


def _require_manage(request: HttpRequest, verb: str) -> None:
    if not can_manage_demand(request):
        raise PermissionDenied(
            f"{verb} a part demand requires the 'demand_manage' permission."
        )


def _part_search_fragment(request: HttpRequest) -> HttpResponse:
    """`<search-dropdown>` results for the substitute-part picker. Same
    canonical URL as its host page per the `format=` contract, not a
    dedicated fragment route (harness/UX_UI.md)."""
    q = request.GET.get("q", "").strip()
    qs = Part.objects.all()
    if q:
        qs = qs.filter(Q(part_number__icontains=q) | Q(name__icontains=q))
    return render(
        request,
        "maintenance/part_demands/_part_search_results.html",
        {"parts": qs.order_by("part_number")[:25]},
    )


# --------------------------------------------------------------------------- #
# Queue
# --------------------------------------------------------------------------- #


@require_http_methods(["GET", "POST"])
def part_demand_index(request: HttpRequest) -> HttpResponse:
    """The approval queue (legacy /maintenance/manager/part-demands).

    Bulk actions post back to this same canonical URL with a distinct `action`
    (endpoint_patterns.md §3.3) rather than the five sub-paths the legacy app
    used.
    """
    domain_ids = accessible_domain_ids(request)

    if request.method == "POST":
        return _handle_bulk(request, domain_ids=domain_ids)

    if request.GET.get("format") == "htmx-part-search":
        return _part_search_fragment(request)

    scope = request.GET.get("scope", SCOPE_MAINTENANCE).strip()
    if scope not in {SCOPE_MAINTENANCE, SCOPE_ALL}:
        scope = SCOPE_MAINTENANCE

    filters = {
        "scope": scope,
        "demand_state": request.GET.get("demand_state", "").strip(),
        "issuance_state": request.GET.get("issuance_state", "").strip(),
        "purchasing_state": request.GET.get("purchasing_state", "").strip(),
        "priority": request.GET.get("priority", "").strip(),
        "part_id": request.GET.get("part_id", "").strip(),
        "q": request.GET.get("q", "").strip(),
        "event_id": request.GET.get("event_id", "").strip(),
        "asset_id": request.GET.get("asset_id", "").strip(),
        "event_status": request.GET.get("event_status", "").strip(),
        "my_events": request.GET.get("my_events", "").strip(),
        "created_from": request.GET.get("created_from", "").strip(),
        "created_to": request.GET.get("created_to", "").strip(),
        "updated_from": request.GET.get("updated_from", "").strip(),
        "updated_to": request.GET.get("updated_to", "").strip(),
        "sort": request.GET.get("sort", "").strip(),
    }

    qs = MaintenanceDemandSearch.index_list(
        domain_ids=domain_ids,
        scope=scope,
        demand_state=filters["demand_state"],
        issuance_state=filters["issuance_state"],
        purchasing_state=filters["purchasing_state"],
        priority=filters["priority"],
        part_id=_int(filters["part_id"]),
        q=filters["q"],
        event_id=_int(filters["event_id"]),
        asset_id=_int(filters["asset_id"]),
        event_status=filters["event_status"],
        assigned_user_id=request.user.pk if filters["my_events"] == "1" else None,
        created_from=_date(filters["created_from"]),
        created_to=_date(filters["created_to"]),
        updated_from=_date(filters["updated_from"]),
        updated_to=_date(filters["updated_to"]),
        sort=filters["sort"],
    )

    paginator = Paginator(qs, PAGE_SIZE)
    page = paginator.get_page(request.GET.get("page", "1"))
    demands = list(page.object_list)

    # Attach the Action/Event/Asset context onto each row here rather than
    # looking it up from the template through a dict-index filter — one query
    # for the page, and the template stays free of lookup helpers.
    rows = MaintenanceDemandSearch.maintenance_context_for([d.pk for d in demands])
    for demand in demands:
        demand.maintenance_row = rows.get(demand.pk)

    context = {
        "page": page,
        "demands": demands,
        "pending_count": qs.filter(
            demand_state__in=[DemandState.PROJECTED, DemandState.REQUIRED]
        ).count(),
        "filters": filters,
        "scopes": SCOPE_CHOICES,
        "demand_states": DemandState.choices,
        "issuance_states": IssuanceState.choices,
        "purchasing_states": PurchasingState.choices,
        "priorities": DemandPriority.choices,
        "event_statuses": EventStatus.choices,
        "event_filters_open": any(
            filters[key]
            for key in ("event_id", "asset_id", "event_status", "my_events")
        ),
        "can_manage": can_manage_demand(request),
    }

    if request.GET.get("format") == "htmx-search-results":
        return render(
            request, "maintenance/part_demands/_index_results.html", context
        )
    return render(request, "maintenance/part_demands/index.html", context)


def _handle_bulk(request: HttpRequest, *, domain_ids) -> HttpResponse:
    """Approve / reject / substitute across the checked rows.

    Each row is attempted independently and refusals are collected rather than
    aborting the batch: a queue of forty demands where two are locked should
    move the other thirty-eight and say which two it skipped, not fail whole.
    """
    redirect_to = request.POST.get("next") or reverse("part_demand_index")

    # A per-row button carries BOTH its verb and its row id in one name/value
    # pair (`row_action="bulk_approve:42"`), because a submit button can only
    # contribute one. That keeps row actions exact — they act on their own row
    # whatever is checked elsewhere — with no JavaScript reaching into the form.
    row_action = request.POST.get("row_action", "")
    if row_action:
        verb, _, raw_id = row_action.partition(":")
        action = verb
        ids = [int(raw_id)] if raw_id.isdigit() else []
    else:
        action = request.POST.get("action", "")
        ids = [
            int(v)
            for v in request.POST.getlist("demand_ids")
            if str(v).strip().isdigit()
        ]
    if not ids:
        messages.error(request, "No demands were selected.")
        return redirect(redirect_to)
    if len(ids) > BULK_LIMIT:
        messages.error(
            request,
            f"Select at most {BULK_LIMIT} demands at a time "
            f"({len(ids)} were selected).",
        )
        return redirect(redirect_to)

    # Re-fetch under the domain fence rather than trusting the posted ids:
    # the checkbox list is client-supplied and may name anything.
    demands = list(
        PartDemand.objects.filter(
            pk__in=ids, domain_id__in=domain_ids, deleted_at__isnull=True
        ).select_related("part")
    )
    missing = len(ids) - len(demands)

    notes = request.POST.get("notes", "").strip()
    new_part_id = None

    if action in {"bulk_approve", "bulk_reject"}:
        _require_manage(request, "Approving" if action == "bulk_approve" else "Rejecting")
    elif action == "bulk_substitute_part":
        _require_manage(request, "Substituting the part on")
        new_part_id = _int(request.POST.get("new_part_id"))
        if not new_part_id or not Part.objects.filter(pk=new_part_id).exists():
            messages.error(request, "Choose a replacement part first.")
            return redirect(redirect_to)
    else:
        messages.error(request, "Unknown action.")
        return redirect(redirect_to)

    moved, refusals = 0, []
    for demand in demands:
        ctx = PartDemandContext(demand.pk)
        try:
            if action == "bulk_approve":
                ctx.approve(actor=request.user, notes=notes)
            elif action == "bulk_reject":
                ctx.reject(actor=request.user, notes=notes)
            else:
                ctx.substitute_part(
                    new_part_id=new_part_id, actor=request.user, notes=notes
                )
            moved += 1
        except ProcurementValidationError as exc:
            refusals.extend(exc.errors)

    if moved:
        messages.success(request, f"{moved} demand(s) updated.")
    for refusal in refusals[:10]:
        messages.warning(request, refusal)
    if len(refusals) > 10:
        messages.warning(request, f"…and {len(refusals) - 10} more were skipped.")
    if missing:
        messages.warning(
            request,
            f"{missing} selected demand(s) are outside your domains and were skipped.",
        )
    if not moved and not refusals and not missing:
        messages.error(request, "Nothing was updated.")
    return redirect(redirect_to)


# --------------------------------------------------------------------------- #
# Detail
# --------------------------------------------------------------------------- #

#: `action` -> (PartDemandContext verb, success message, needs demand_manage).
#: A table rather than an if-chain because every entry is the same shape; the
#: two that are not (issuance, substitute_part) take extra POST fields and are
#: handled explicitly below.
_SIMPLE_VERBS = {
    "approve": ("approve", "Demand approved.", True),
    "reject": ("reject", "Demand rejected.", True),
    "resubmit": ("resubmit", "Demand resubmitted for approval.", True),
    "mark_required": ("mark_required", "Demand marked as required.", True),
    "cancel": ("cancel", "Demand cancelled.", True),
}


@require_http_methods(["GET", "POST"])
def part_demand_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """One demand, seen from maintenance (legacy /maintenance/part_demand/<id>/view).

    Deliberately not a duplicate of procurement's own demand_detail: that page
    is the buyer's view, organized around purchasing and shipping. This one is
    organized around the two questions a maintenance manager asks — what work
    is this for, and who still has to say yes.
    """
    demand = _demand_or_404_in_domain(request, pk)

    if request.method == "POST":
        return _handle_detail_post(request, demand)

    if request.GET.get("format") == "htmx-part-search":
        return _part_search_fragment(request)

    context_rows = MaintenanceDemandSearch.maintenance_context_for([pk])
    entry = context_rows.get(pk, {})
    links = entry.get("links", [])
    event = entry.get("event")

    return render(
        request,
        "maintenance/part_demands/detail.html",
        {
            "demand": demand,
            "links": links,
            "action": entry.get("action"),
            "event": event,
            "asset": entry.get("asset"),
            # Rule #5: the Maintenance Context card always renders. These two
            # flags pick which explicit empty state it shows, matching the
            # legacy page's two distinct italic explanations.
            "has_maintenance_link": bool(links),
            "issuance_states": IssuanceState.choices,
            "priorities": DemandPriority.choices,
            "can_manage": can_manage_demand(request),
            "is_requester": demand.requested_by_id == request.user.pk,
        },
    )


def _handle_detail_post(request: HttpRequest, demand: PartDemand) -> HttpResponse:
    action = request.POST.get("action", "")
    ctx = PartDemandContext(demand.pk)
    target = reverse("part_demand_detail", kwargs={"pk": demand.pk})

    try:
        if action in _SIMPLE_VERBS:
            verb, success, needs_manage = _SIMPLE_VERBS[action]
            if needs_manage:
                _require_manage(request, action.replace("_", " ").capitalize() + "ing")
            getattr(ctx, verb)(actor=request.user, notes=request.POST.get("notes", ""))
            messages.success(request, success)

        elif action == "set_issuance":
            # Same actor set as procurement's own edit page: a manager, or the
            # person who raised the demand.
            if not (can_manage_demand(request) or demand.requested_by_id == request.user.pk):
                raise PermissionDenied(
                    "Updating issuance requires the 'demand_manage' permission "
                    "or ownership of this demand."
                )
            ctx.set_issuance_state(
                to_stage=request.POST.get("to_stage", ""),
                actor=request.user,
                notes=request.POST.get("notes", ""),
            )
            messages.success(request, "Issuance status updated.")

        elif action == "substitute_part":
            _require_manage(request, "Substituting the part on")
            new_part_id = _int(request.POST.get("new_part_id"))
            if not new_part_id:
                messages.error(request, "Choose a replacement part first.")
                return redirect(target)
            ctx.substitute_part(
                new_part_id=new_part_id,
                actor=request.user,
                notes=request.POST.get("notes", ""),
            )
            messages.success(request, "Part substituted.")

        elif action == "update_fields":
            if not (can_manage_demand(request) or demand.requested_by_id == request.user.pk):
                raise PermissionDenied(
                    "Editing requires the 'demand_manage' permission or "
                    "ownership of this demand."
                )
            ctx.update_fields(
                priority=request.POST.get("priority") or None,
                notes=request.POST.get("notes", ""),
                quantity_requested=_decimal(request.POST.get("quantity_requested")),
                actor=request.user,
            )
            messages.success(request, "Demand updated.")

        else:
            messages.error(request, "Unknown action.")

    except TransitionRefused as exc:
        # Refusals name what must happen first (e.g. the PO to cancel), never a
        # generic failure — shared_workflows.md §3.
        for error in exc.errors:
            messages.error(request, error)
    except ProcurementValidationError as exc:
        for error in exc.errors:
            messages.error(request, error)

    return redirect(target)


def _decimal(raw) -> Decimal | None:
    raw = str(raw or "").strip()
    if not raw:
        return None
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None
