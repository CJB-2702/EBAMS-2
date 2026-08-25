"""Phase 6 — Issuance portal workspace (`/inventory/issues/create/` and
`/inventory/issue-parts/`), location-based issuance portal, and the Issued
Parts ledger (sessions index, line item ledger, session detail, & return action).

The portal keeps a session-backed draft of queued lines so the queue survives
F5 — no client-only state. That draft is shared with two other surfaces
(`/procurement/demands/` and `/inventory/active-inventory/` both queue into it),
so it lives in `presentation_layer.tools.issuance_draft` rather than here.

The workspace is two searches stacked on one route:

  Step 1  find the REQUIREMENT — a real demand, or an ad-hoc one the operator
          describes on the spot (staged, not created; see issuance_draft)
  Step 2  find the STOCK to satisfy it, pre-filtered to the parts Step 1 asked
          for

Each step is a left-heavy search: one generic box that covers the identifiers
someone actually has in hand, plus a filter popup carrying the FULL filter set
of that step's canonical list page (`demand_index` / `active_inventory_index`).
Every filter is a `d_`/`s_`-prefixed GET param so the two coexisting forms
cannot read each other's values, and so F5 reproduces both panes exactly.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date, parse_datetime
from django.views.decorators.http import require_http_methods

from app.administration.models import Domain, User
from app.inventory.control_layer.adapters.room_svg_adapter import RoomSvgAdapter
from app.inventory.control_layer.constants import ROOM_SVG_GROUP_LABEL
from app.inventory.control_layer.errors import InventoryValidationError
from app.inventory.control_layer.orchestrators.part_issuance_orchestrator import (
    PartIssuanceOrchestrator,
)
from app.inventory.models import IssueReason, IssueType, PartIssue, PartIssueSession
from app.inventory.models.stock.active_inventory import ActiveInventory
from app.inventory.models.topography.room import Room
from app.inventory.models.topography.storage_location import StorageLocation
from app.inventory.models.topography.warehouse import Warehouse
from app.inventory.presentation_layer.search.active_inventory_search import (
    ActiveInventorySearch,
    domain_visible_room_ids,
)
from app.inventory.presentation_layer.search.issue_search import IssueSearch
from app.inventory.presentation_layer.tools import issuance_draft, location_issuance_draft
from app.inventory.presentation_layer.tools.inventory_access import (
    accessible_domain_ids,
    can_issue,
)
from app.procurement.models import (
    DemandPriority,
    DemandSourceModule,
    DemandState,
    IssuanceState,
    PartDemand,
    PurchasingState,
    ShipmentState,
)
from app.procurement.presentation_layer.search.open_demand_search import OpenDemandSearch

TEMPLATE_DIR = "inventory/issues"
COMPONENT_DIR = "inventory/issues/components"
PAGE_SIZE = 50
POOL_PAGE_SIZE = 12

#: The pool's default: something someone is actually waiting on. The filter
#: popup can widen it to any single state (including Cancelled, to answer
#: "why is this not showing up") — this is only what an unfiltered search
#: assumes you meant.
_SEARCHABLE_DEMAND_STATES = frozenset(
    {DemandState.REQUIRED, DemandState.APPROVED}
)


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


def _dt(raw: str):
    """Accept either a date or a datetime-local value from the same field."""
    raw = (raw or "").strip()
    if not raw:
        return None
    return parse_datetime(raw) or parse_date(raw)


# --------------------------------------------------------------------------- #
# `issuance_location_portal` keeps its OWN queue. It is a different workflow —
# a spatial single-part grab, not a bulk demand run — and sharing one session
# key with the demand-first portal is what produced a list holding three
# different line shapes at once. See
# docs/inventory/issuance_portal_separation.md.
# --------------------------------------------------------------------------- #


def _draft(request: HttpRequest) -> list[dict]:
    return location_issuance_draft.load(request)


def _save_draft(request: HttpRequest, lines: list[dict]) -> None:
    location_issuance_draft.save(request, lines)


# --------------------------------------------------------------------------- #
# Step 1 — the demand pool
# --------------------------------------------------------------------------- #


def _demand_pool_filters(request: HttpRequest) -> dict:
    """Raw GET values, kept as strings so the filter popup repopulates itself
    on a plain reload rather than resetting to blank."""
    get = request.GET.get
    return {
        "dq": get("dq", "").strip(),
        "demand_state": get("d_demand_state", "").strip(),
        "priority": get("d_priority", "").strip(),
        "purchasing_state": get("d_purchasing_state", "").strip(),
        "shipment_state": get("d_shipment_state", "").strip(),
        "issuance_state": get("d_issuance_state", "").strip(),
        "domain_id": get("d_domain_id", "").strip(),
        "source": get("d_source", "").strip(),
        "event_id": get("d_event_id", "").strip(),
        "po_number": get("d_po_number", "").strip(),
        "requested_by": get("d_requested_by", "").strip(),
        "needed_by_from": get("d_needed_by_from", "").strip(),
        "needed_by_to": get("d_needed_by_to", "").strip(),
        "created_from": get("d_created_from", "").strip(),
        "created_to": get("d_created_to", "").strip(),
    }


def _demand_pool(request: HttpRequest, *, domain_ids, filters: dict):
    """Page of demands matching Step 1's search.

    Restricted to `_SEARCHABLE_DEMAND_STATES` unless the popup names one
    explicitly — an operator searching for something to issue against should
    not have to scroll past cancelled demands to find the live one.
    """
    qs = OpenDemandSearch.index_list(
        domain_ids=domain_ids,
        generic_q=filters["dq"],
        demand_states=None if filters["demand_state"] else _SEARCHABLE_DEMAND_STATES,
        demand_state=filters["demand_state"],
        priority=filters["priority"],
        purchasing_state=filters["purchasing_state"],
        shipment_state=filters["shipment_state"],
        issuance_state=filters["issuance_state"],
        domain_id=_int_or_none(filters["domain_id"]),
        source=filters["source"],
        event_id=_int_or_none(filters["event_id"]),
        po_number=filters["po_number"],
        requested_by=filters["requested_by"],
        needed_by_from=_dt(filters["needed_by_from"]),
        needed_by_to=_dt(filters["needed_by_to"]),
        created_from=_dt(filters["created_from"]),
        created_to=_dt(filters["created_to"]),
    )
    paginator = Paginator(qs, POOL_PAGE_SIZE)
    return paginator.get_page(request.GET.get("d_page", "1"))


def _demand_pool_context(request: HttpRequest, *, domain_ids) -> dict:
    filters = _demand_pool_filters(request)
    page = _demand_pool(request, domain_ids=domain_ids, filters=filters)
    staged_ids = set(issuance_draft.load_demands(request))
    return {
        "demand_pool_page": page,
        "demand_pool": page.object_list,
        "demand_filters": filters,
        "demand_filter_active": any(v for k, v in filters.items() if k != "dq"),
        "staged_demand_ids": staged_ids,
        "demand_states": DemandState.choices,
        "priorities": DemandPriority.choices,
        "purchasing_states": PurchasingState.choices,
        "shipment_states": ShipmentState.choices,
        "issuance_states": IssuanceState.choices,
        "sources": DemandSourceModule.choices,
        "domains": Domain.objects.filter(pk__in=domain_ids).order_by("name"),
    }


# --------------------------------------------------------------------------- #
# The portal
# --------------------------------------------------------------------------- #


@require_http_methods(["GET", "POST"])
def issuance_portal(request: HttpRequest) -> HttpResponse:
    """Bulk Issue Parts from Demands — build one receipt for one person.

    DEMAND FIRST. Pick the demands, then fill in which shelf each comes off.
    There is deliberately no way to start from stock here; that is the
    part-first portal's job and it is a different screen (see
    docs/inventory/issuance_portal_separation.md).

    Every write is POST -> redirect -> GET so F5 never re-commits, and the
    demand pool's filter state rides in the querystring so a reload reproduces
    the page exactly.
    """
    domain_ids = accessible_domain_ids(request)

    if request.method == "POST":
        return _portal_post(request, domain_ids=domain_ids)

    normalized = _normalize_deep_link(request, domain_ids=domain_ids)
    if normalized is not None:
        return normalized

    fmt = request.GET.get("format", "")
    if fmt == "htmx-demand-pool":
        return _pool_fragment(
            request,
            f"{COMPONENT_DIR}/_demand_pool_results.html",
            {
                **_demand_pool_context(request, domain_ids=domain_ids),
                "can_issue": can_issue(request),
            },
        )
    if fmt in ("htmx-bin-search", "htmx-bin-search-results"):
        return _bin_search_fragment(
            request, domain_ids=domain_ids, results_only=fmt.endswith("results")
        )

    return render(
        request,
        f"{TEMPLATE_DIR}/create.html",
        _portal_context(request, domain_ids=domain_ids),
    )


def _portal_context(request: HttpRequest, *, domain_ids) -> dict:
    draft = issuance_draft.enrich(issuance_draft.load(request))
    groups = issuance_draft.group_by_demand(
        draft, demand_ids=issuance_draft.load_demands(request)
    )
    header = issuance_draft.load_header(request)

    context = {
        "draft": draft,
        "draft_count": len(draft),
        "groups": groups,
        "recipient": issuance_draft.recipient(request),
        "header": header,
        # Demands on the plan that nothing has been picked for yet. NOT a
        # blocker — the plan commits what it has and leaves the rest owed
        # (a partial issuance), so this is a count the clerk is told about,
        # not a gate they have to clear.
        "empty_groups": [g for g in groups if g["is_empty"]],
        "partial_groups": [g for g in groups if g["is_short"] and not g["is_empty"]],
        "problem_count": sum(
            1 for l in draft if l["status"] in ("mismatch", "orphaned", "short")
        ),
        "over_groups": [g for g in groups if g["is_over"]],
        "issue_reasons": IssueReason.choices,
        "can_issue": can_issue(request),
        "users": User.objects.filter(is_active=True).order_by(
            "first_name", "last_name", "username"
        )[:400],
    }
    context.update(_demand_pool_context(request, domain_ids=domain_ids))
    return context


def _pool_fragment(request: HttpRequest, template: str, context: dict) -> HttpResponse:
    return render(request, template, context)


# --------------------------------------------------------------------------- #
# The location picker — the ONLY way stock joins the plan
#
# Reached from the `+` on a demand's header. One demand routinely comes off
# several shelves (the ordinary case for consumables), so the clerk gets the
# SAME filter set the stock list itself offers
# (`/inventory/active-inventory/`) and can tick several rows at once.
#
# The part is LOCKED to the demand's part. It is not a filter field the clerk
# can widen: the popup is reached from one demand and can only ever add stock
# of that demand's part, enforced in the query rather than by hiding a
# control.
# --------------------------------------------------------------------------- #

#: `b_`-prefixed so the popup's form and the demand pool's `d_` form can both
#: submit to this one route without reading each other's values.
def _bin_search_filters(request: HttpRequest) -> dict:
    get = request.GET.get
    return {
        "warehouse_id": get("b_warehouse_id", "").strip(),
        "room_id": get("b_room_id", "").strip(),
        "storage_location_id": get("b_storage_location_id", "").strip(),
        "serial": get("b_serial", "").strip(),
        "stock_status": get("b_stock_status", "").strip(),
        "stale_days": get("b_stale_days", "").strip(),
        "unassigned_only": "on"
        if get("b_unassigned_only", "") in ("on", "1", "true")
        else "",
    }


def _bin_search_fragment(
    request: HttpRequest, *, domain_ids, results_only: bool
) -> HttpResponse:
    """The large part-locked stock picker's body (or just its result rows).

    Two `format=` values share this builder because the filter form re-renders
    only the table: `htmx-bin-search` is the popup opening, and
    `htmx-bin-search-results` is every keystroke after it.
    """
    demand_id = _int_or_none(request.GET.get("b_demand"))
    draft = issuance_draft.enrich(issuance_draft.load(request))
    filters = _bin_search_filters(request)

    demand = (
        PartDemand.objects.filter(
            pk=demand_id, domain_id__in=domain_ids, deleted_at__isnull=True
        )
        .select_related("part")
        .first()
        if demand_id is not None
        else None
    )
    if demand is None or demand_id not in issuance_draft.load_demands(request):
        return render(
            request,
            f"{COMPONENT_DIR}/_bin_search_popup.html",
            {"demand": None, "filters": filters},
        )

    part = demand.part
    stale_days = int(filters["stale_days"]) if filters["stale_days"].isdigit() else None

    qs = ActiveInventorySearch.index_list(
        domain_ids=domain_ids,
        part_id=part.pk,
        warehouse_id=filters["warehouse_id"],
        room_id=filters["room_id"],
        storage_location_id=filters["storage_location_id"],
        serial=filters["serial"],
        stock_status=filters["stock_status"],
        unassigned_only=bool(filters["unassigned_only"]),
        stale_days=stale_days,
    )
    paginator = Paginator(qs, PAGE_SIZE)
    page = paginator.get_page(request.GET.get("b_page", "1"))

    # Bins the plan already draws on. Shown as such rather than filtered out —
    # "already on the plan" is the answer to "why can I not tick it".
    staged_balance_ids = {
        l.get("active_inventory_id") for l in draft if l.get("active_inventory_id")
    }

    # What this demand still wants after everything already on the plan. It is
    # also the CEILING on every row's suggested quantity: a bin holding more
    # than the demand asked for comes in at the demand's number.
    outstanding = issuance_draft.outstanding_for(demand, issuance_draft.load(request))

    rows = []
    for balance in page.object_list:
        available = balance.quantity_on_hand
        if balance.serial_number:
            suggested = Decimal("1.000")
        elif outstanding > 0:
            suggested = min(outstanding, available)
        else:
            suggested = available
        rows.append(
            {
                "balance": balance,
                "suggested": suggested,
                "covers_demand": outstanding > 0 and available >= outstanding,
                "is_staged": balance.pk in staged_balance_ids,
            }
        )

    context = {
        "part": part,
        "demand": demand,
        "outstanding": outstanding,
        "rows": rows,
        "page": page,
        "filters": filters,
        "filter_active": any(filters.values()),
        "can_issue": can_issue(request),
    }

    if results_only:
        return render(request, f"{COMPONENT_DIR}/_bin_search_results.html", context)

    # The three topography selects are populated from THIS PART's own stock,
    # not from the whole warehouse tree. The part is locked, so a warehouse
    # holding none of it is an option that can only ever return nothing —
    # `/inventory/active-inventory/` has to offer all of them because its part
    # field is free text, and this one does not.
    context.update(
        _bin_search_scope_options(part_id=part.pk, domain_ids=domain_ids)
    )
    return render(request, f"{COMPONENT_DIR}/_bin_search_popup.html", context)


def _bin_search_scope_options(*, part_id: int, domain_ids) -> dict:
    holdings = ActiveInventory.objects.filter(
        part_id=part_id, room_id__in=domain_visible_room_ids(domain_ids=domain_ids)
    )
    return {
        "warehouses": Warehouse.objects.filter(
            pk__in=holdings.values("warehouse_id")
        ).order_by("name"),
        "rooms": Room.objects.filter(pk__in=holdings.values("room_id"))
        .select_related("warehouse")
        .order_by("warehouse__name", "room_name"),
        "storage_locations": StorageLocation.objects.filter(
            pk__in=holdings.values("storage_location_id")
        ).order_by("display_code"),
    }


def _normalize_deep_link(request: HttpRequest, *, domain_ids):
    """`?demand=<pk>` stages that demand and redirects to the clean URL.

    A deep link that rendered directly would bookmark into a state the page
    could not reproduce on reload, and re-staging on every F5 would silently
    duplicate lines.
    """
    demand_id = _int_or_none(request.GET.get("demand"))
    if demand_id is None:
        return None
    if can_issue(request):
        staged, _, _ = issuance_draft.add_demand_lines(
            request, demand_ids=[demand_id], domain_ids=domain_ids
        )
        if not staged:
            messages.warning(
                request, "That demand could not be staged — check your domain access."
            )
    params = request.GET.copy()
    params.pop("demand", None)
    target = reverse("inventory_issue_parts")
    return redirect(f"{target}?{params.urlencode()}" if params else target)


# --------------------------------------------------------------------------- #
# Writes
# --------------------------------------------------------------------------- #


def _portal_post(request: HttpRequest, *, domain_ids) -> HttpResponse:
    """Every write is POST -> redirect -> GET so F5 never re-submits.

    The redirect preserves the querystring: the demand pool's filter state
    lives there, and dropping it would dump the clerk back to an unfiltered
    search after every single Stage click.
    """
    if not can_issue(request):
        messages.error(request, "You do not have permission to issue parts.")
        return redirect(request.get_full_path())

    action = request.POST.get("action", "")

    if action == "set_header":
        _set_header(request)

    elif action == "add_demand":
        ids = request.POST.getlist("demand_ids") or [request.POST.get("add_demand_id")]
        staged, paired, skipped = issuance_draft.add_demand_lines(
            request, demand_ids=ids, domain_ids=domain_ids
        )
        if staged:
            unpaired = staged - paired
            note = (
                f" {unpaired} still need{'s' if unpaired == 1 else ''} a location "
                "choosing — use the + on the demand."
                if unpaired
                else " Each found a single obvious location."
            )
            messages.success(request, f"Added {staged} demand(s) to the plan.{note}")
        else:
            messages.warning(
                request, "Nothing staged — those demands are outside your domains."
            )

    elif action == "add_stock_lines":
        demand_id = _int_or_none(request.POST.get("demand_id"))
        picked = request.POST.getlist("active_inventory_ids")
        entries = [(pk, request.POST.get(f"qty_{pk}", "")) for pk in picked]
        added = (
            issuance_draft.add_stock_lines(
                request, demand_id=demand_id, entries=entries, domain_ids=domain_ids
            )
            if demand_id is not None
            else 0
        )
        if added:
            messages.success(
                request,
                f"Added {added} location{'s' if added != 1 else ''} to demand "
                f"#{demand_id}.",
            )
        else:
            messages.error(
                request,
                "Nothing added — tick at least one location that is not already "
                "on the plan.",
            )

    elif action == "remove_demand":
        demand_id = _int_or_none(request.POST.get("demand_id"))
        removed = (
            issuance_draft.remove_demand(request, demand_id)
            if demand_id is not None
            else 0
        )
        if removed:
            messages.success(
                request,
                f"Removed demand #{demand_id} and its {removed} planned "
                f"issuance{'s' if removed != 1 else ''}.",
            )

    elif action == "remove_line":
        issuance_draft.remove_at(request, _int_or_none(request.POST.get("index")) or -1)

    elif action == "commit_session":
        redirect_to = _commit(request)
        if redirect_to is not None:
            return redirect_to

    elif action == "cancel_draft":
        issuance_draft.clear(request)
        issuance_draft.clear_header(request)
        messages.success(request, "Plan cleared.")

    return redirect(request.get_full_path())


def _set_header(request: HttpRequest) -> None:
    """Who the receipt is for, plus why. Stored, not committed."""
    issued_to_id = _int_or_none(request.POST.get("issued_to_id"))
    if issued_to_id is None:
        messages.error(request, "Choose who is receiving these parts.")
        return
    if not User.objects.filter(pk=issued_to_id, is_active=True).exists():
        messages.error(request, "That is not an active user.")
        return
    issuance_draft.save_header(
        request,
        {
            "issued_to_id": issued_to_id,
            "issue_reason": request.POST.get("issue_reason", "").strip()
            or IssueReason.OTHER,
            "issue_reason_detail": request.POST.get("issue_reason_detail", "").strip(),
            "notes": request.POST.get("notes", "").strip(),
        },
    )


def _commit(request: HttpRequest):
    """Hand it over. One receipt, one recipient, one transaction.

    PARTIAL IS A VALID RECEIPT. A demand covered by less than it asked for
    commits what is there and stays Partially Issued with the remainder owed;
    a demand on the plan with nothing picked for it at all simply contributes
    no lines and is left untouched. Neither blocks the commit — the stock in
    the storeroom is what it is, and refusing to hand over the four that exist
    because a fifth does not is not a rule anyone wants.
    """
    lines = issuance_draft.load(request)
    if not lines:
        messages.error(
            request,
            "Nothing to issue — add at least one inventory location to a demand "
            "with the + on its header.",
        )
        return None

    recipient = issuance_draft.recipient(request)
    if recipient is None:
        messages.error(request, "Name who is receiving these parts first.")
        return None

    enriched = issuance_draft.enrich(lines)
    # Only genuinely broken lines block: a bin that vanished, a part that does
    # not match its demand, or more taken than the shelf holds. Short of the
    # demand is not broken, it is partial.
    blocked = [
        l
        for l in enriched
        if l["status"] in ("needs_stock", "mismatch", "orphaned", "short")
    ]
    if blocked:
        messages.error(
            request,
            f"{len(blocked)} line(s) cannot be issued as planned — check the red "
            "rows. Delete and re-add anything wrong.",
        )
        return None

    # Over-issue is a WARNING, not a gate (D30 puts no cap on issued_qty). The
    # clerk confirms it on the submit button; by the time we are here they have.
    header = issuance_draft.load_header(request)

    try:
        session_obj = PartIssuanceOrchestrator.commit_session(
            lines=lines,
            issued_by=request.user,
            issued_to=recipient,
            issue_reason=header.get("issue_reason") or IssueReason.OTHER,
            issue_reason_detail=header.get("issue_reason_detail", ""),
            notes=header.get("notes", ""),
        )
    except Exception as exc:  # noqa: BLE001
        messages.error(request, str(exc))
        return None

    messages.success(
        request,
        f"Receipt {session_obj.session_number} committed — "
        f"{len(lines)} line(s) to {recipient.get_full_name() or recipient.username}.",
    )
    issuance_draft.clear(request)
    issuance_draft.clear_header(request)
    return redirect(
        reverse("inventory_issue_session_detail", kwargs={"pk": session_obj.pk})
    )


@require_http_methods(["GET", "POST"])
def issuance_queue_panel(request: HttpRequest) -> HttpResponse:
    """The topnav badge's dropdown body.

    Its own route rather than a `format=` on the portal, because it is reached
    from every page in the application — including ones with no notion of an
    inventory workspace — and must not carry the portal's filter contract
    around with it.
    """
    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "remove":
            issuance_draft.remove_at(request, _int_or_none(request.POST.get("index")) or -1)
        elif action == "clear":
            issuance_draft.clear(request)

    return render(
        request,
        f"{COMPONENT_DIR}/_queue_panel.html",
        {
            "draft": issuance_draft.enrich(issuance_draft.load(request)),
            "recipient": issuance_draft.recipient(request),
        },
    )


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


def _location_demand_filters(request: HttpRequest) -> dict:
    """The picker popup's full filter set, mirrored from `demand_index`
    (procurement/demands/index.html) so the two surfaces agree on field
    names and parsing. Returned as the raw strings the form re-renders,
    keeping F5 reproducing whatever was applied."""
    return {
        "domain_id": request.GET.get("domain_id", "").strip(),
        "source": request.GET.get("source", "").strip(),
        "event_id": request.GET.get("event_id", "").strip(),
        "po_number": request.GET.get("po_number", "").strip(),
        "requested_by": request.GET.get("requested_by", "").strip(),
        "needed_by_from": request.GET.get("needed_by_from", "").strip(),
        "needed_by_to": request.GET.get("needed_by_to", "").strip(),
        "created_from": request.GET.get("created_from", "").strip(),
        "created_to": request.GET.get("created_to", "").strip(),
    }


def _location_demand_qs(
    request: HttpRequest, *, domain_ids, limit: int = 25, id_only: bool = False
):
    """Demands the from-location portal's pickers can offer.

    Scoped to the part the operator has selected off the shelf unless they
    explicitly widen it (`scope=all`). That default is the whole reason this is
    a picker and not a plain list: standing at a bin holding one part, the
    demands for THAT part are what you want, and the other four thousand are
    noise.

    `id_only` marks the compact field beside the stock list — an operator
    standing at a bin types the demand number off the pick ticket, so that
    field filters on the id exactly. The popup's own text box stays a full
    multi-field search (part #, demand #, event #, PO #) and never sets it.
    """
    part_id = _int_or_none(request.GET.get("part_id"))
    widened = request.GET.get("scope", "") == "all"
    filters = _location_demand_filters(request)
    q = request.GET.get("q", "").strip()
    qs = OpenDemandSearch.index_list(
        domain_ids=domain_ids,
        generic_q="" if id_only else q,
        demand_states=_SEARCHABLE_DEMAND_STATES,
        domain_id=_int_or_none(filters["domain_id"]),
        source=filters["source"],
        event_id=_int_or_none(filters["event_id"]),
        po_number=filters["po_number"],
        requested_by=filters["requested_by"],
        needed_by_from=_dt(filters["needed_by_from"]),
        needed_by_to=_dt(filters["needed_by_to"]),
        created_from=_dt(filters["created_from"]),
        created_to=_dt(filters["created_to"]),
    )
    if id_only and q:
        if not q.isdigit():
            return qs.none()
        qs = qs.filter(pk=int(q))
    if part_id is not None and not widened:
        qs = qs.filter(part_id=part_id)
    return qs[:limit]


def _location_demand_results(request: HttpRequest, *, domain_ids) -> HttpResponse:
    """`<li>` rows for the `<search-dropdown>`. No wrapper element — the
    component supplies its own `<ul>` (UX_UI/components/search_dropdown.md)."""
    return render(
        request,
        f"{COMPONENT_DIR}/_demand_search_results.html",
        {"results": _location_demand_qs(request, domain_ids=domain_ids, id_only=True)},
    )


def _location_demand_picker(request: HttpRequest, *, domain_ids) -> HttpResponse:
    """The popup utility's body — the same search, rendered wide.

    The dropdown is the default because picking a demand is normally one
    keystroke and a click. This exists for when it is not: the operator wants
    to see who requested it, when it is needed, and how much is still
    outstanding before choosing.
    """
    part_id = _int_or_none(request.GET.get("part_id"))
    filters = _location_demand_filters(request)
    return render(
        request,
        f"{COMPONENT_DIR}/_demand_picker_popup.html",
        {
            "results": _location_demand_qs(request, domain_ids=domain_ids, limit=50),
            "q": request.GET.get("q", "").strip(),
            "part_id": part_id,
            "scope_all": request.GET.get("scope", "") == "all",
            "filters": filters,
            "filters_active": any(filters.values()),
            "domains": Domain.objects.filter(pk__in=domain_ids).order_by("name"),
            "sources": DemandSourceModule.choices,
        },
    )


@require_http_methods(["GET", "POST"])
def issuance_location_portal(request: HttpRequest) -> HttpResponse:
    # Fragments on the same canonical URL, one `format=` each — never a
    # parallel /search route (UX_UI/format_contract.md).
    if request.method == "GET":
        fmt = request.GET.get("format", "")
        if fmt == "htmx-search-results":
            return _location_demand_results(
                request, domain_ids=accessible_domain_ids(request)
            )
        if fmt == "htmx-demand-picker":
            return _location_demand_picker(
                request, domain_ids=accessible_domain_ids(request)
            )

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
            # Demand-anchored only. Staging from here writes straight into
            # Bulk Issue from Demands' own queue (`issuance_draft`) through
            # the exact entry point its own bin picker uses
            # (`add_stock_lines`) — same validation (domain, part match,
            # already-staged, quantity capping), same "nothing added"
            # failure mode, one shared line shape
            # (docs/inventory/issuance_portal_separation.md §4). A
            # demand-less grab never had a home in that shape, which is why
            # the button is disabled client-side until a demand is picked —
            # this check is the server-side backstop for a direct POST.
            try:
                target_stock_id = _int_or_none(request.POST.get("active_inventory_id", ""))
                demand_id = _int_or_none(request.POST.get("demand_id"))
                quantity = _decimal(request.POST.get("quantity"))
                if demand_id is None:
                    raise InventoryValidationError(
                        [
                            "Select a part demand before staging stock — use "
                            "Direct Issue Now for a demand-less grab."
                        ]
                    )
                if quantity is None or quantity <= 0:
                    raise InventoryValidationError(["Enter a valid positive quantity."])

                # Pinpoint WHY before falling back to add_stock_lines's blunt
                # 0-added return — "nothing added" alone left no way to tell a
                # part mismatch from an already-staged balance from a domain
                # a user's demand-picker had not actually scoped to.
                demand = PartDemand.objects.filter(
                    pk=demand_id, domain_id__in=domain_ids, deleted_at__isnull=True
                ).select_related("part").first()
                target_stock = ActiveInventory.objects.filter(
                    pk=target_stock_id, room_id__in=domain_visible_room_ids(domain_ids=domain_ids)
                ).select_related("part").first()
                if demand is None:
                    raise InventoryValidationError(
                        ["That demand could not be found in your accessible domains."]
                    )
                if target_stock is None:
                    raise InventoryValidationError(
                        ["That stock balance is no longer visible — it may have moved or been consumed."]
                    )
                if target_stock.part_id != demand.part_id:
                    raise InventoryValidationError(
                        [
                            f"Demand #{demand_id} is for {demand.part.part_number}, but the "
                            f"selected stock is {target_stock.part.part_number} — pick a demand "
                            "for this part."
                        ]
                    )
                already_staged = {
                    l.get("active_inventory_id") for l in issuance_draft.load(request)
                    if l.get("active_inventory_id")
                }
                if target_stock_id in already_staged:
                    raise InventoryValidationError(
                        ["That stock is already staged on your Bulk Issue from Demands plan."]
                    )

                added = issuance_draft.add_stock_lines(
                    request,
                    demand_id=demand_id,
                    entries=[(target_stock_id, str(quantity))],
                    domain_ids=domain_ids,
                )
                if added:
                    messages.success(
                        request,
                        f"Staged into Bulk Issue from Demands — 1 location added to demand #{demand_id}.",
                    )
                    full_path = request.get_full_path()
                    sep = "&" if "?" in full_path else "?"
                    return redirect(f"{full_path}{sep}staged=1")
                messages.error(
                    request,
                    "Nothing added — that demand's outstanding quantity may "
                    "already be fully covered by lines already on the plan.",
                )
                return redirect(request.get_full_path())
            except InventoryValidationError as exc:
                for error in exc.errors:
                    messages.error(request, error)
            except Exception as exc:  # noqa: BLE001
                messages.error(request, str(exc))

        elif action == "direct_issue":
            # Bypasses the queue entirely — a one-line receipt committed on
            # the spot, for the counter case where staging-then-visiting-the-
            # workspace is more ceremony than a single grab-and-hand-over
            # needs. The existing multi-line draft (if any) is left untouched.
            try:
                target_stock_id = _int_or_none(request.POST.get("active_inventory_id", ""))
                quantity = _decimal(request.POST.get("quantity"))
                if quantity is None or quantity <= 0:
                    raise InventoryValidationError(["Enter a valid positive quantity."])

                session_issued_to_id = _int_or_none(request.POST.get("session_issued_to_id"))
                issued_to = (
                    User.objects.filter(pk=session_issued_to_id).first()
                    if session_issued_to_id
                    else None
                )
                if issued_to is None:
                    raise InventoryValidationError(
                        ["Name who is receiving this part before issuing."]
                    )

                line = {
                    "issue_type": request.POST.get("issue_type", IssueType.FOR_PART_DEMAND),
                    "demand_id": _int_or_none(request.POST.get("demand_id")),
                    "issued_to_asset_id": _int_or_none(request.POST.get("issued_to_asset_id")),
                    "active_inventory_id": target_stock_id,
                    "quantity": str(quantity),
                    "notes": request.POST.get("notes", ""),
                }
                session_obj = PartIssuanceOrchestrator.commit_session(
                    lines=[line],
                    issued_by=request.user,
                    issued_to=issued_to,
                    issue_reason=request.POST.get("session_issue_reason", "") or IssueReason.OTHER,
                    issue_reason_detail=request.POST.get("session_issue_reason_detail", ""),
                )
                messages.success(
                    request,
                    f"Issue session #{session_obj.session_number} committed — issued directly.",
                )
                return redirect(reverse("inventory_issue_session_detail", kwargs={"pk": session_obj.pk}))
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
                    notes = request.POST.get("notes", "")

                    issued_to = User.objects.get(pk=issued_to_id) if issued_to_id else None
                    if issued_to is None:
                        raise InventoryValidationError(
                            ["Name who is receiving these parts before issuing."]
                        )

                    # `issue_type` and the target asset are LINE grain now — a
                    # receipt header is one person, and which asset a grabbed
                    # part went onto describes the part, not the signature.
                    session_obj = PartIssuanceOrchestrator.commit_session(
                        lines=lines,
                        issued_by=request.user,
                        issued_to=issued_to,
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

    users = User.objects.filter(is_active=True).order_by("first_name", "last_name")[:200]

    context = {
        "stock_id": stock_id,
        "selected_stock": selected_stock,
        "available_stock": available_stock,
        "demands": demands,
        "users": users,
        "draft": _draft(request),
        "issue_reasons": IssueReason.choices,
        "can_issue": can_issue(request),
        "staged": request.GET.get("staged") == "1",
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
            "issued_by", "issued_to"
        ).prefetch_related(
            "issues", "issues__part_demand", "issues__part_demand__part"
        ).order_by("-issued_at")

        # Filtered THROUGH the lines: issue type is a property of what was
        # handed over, not of the receipt. The header lost its own copy when a
        # receipt became "one handover to one person" and nothing else.
        if filters["issue_type"]:
            sessions_qs = sessions_qs.filter(
                issues__issue_type=filters["issue_type"]
            ).distinct()

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
            "issued_by", "issued_to"
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
