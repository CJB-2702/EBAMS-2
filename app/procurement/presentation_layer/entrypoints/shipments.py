"""The Receiving Loop — list / create / receive / detail / edit, plus the
PO-scoped Basic Shipment Manager (Phase 3).

Two boundaries this module holds and must keep holding:

**Intake is a hard boundary.** No storeroom, no bin, no location, no put-away,
no stock level appears anywhere in this sector. The last verb here is `accept`.
If a field asking "where did you put it" ever shows up below, it belongs to a
later Inventory kit, not to this one.

**`quantity_accepted` is a quantity, and `null` is not `0`.** An uninspected
line and a line inspected-and-wholly-rejected are different facts. The accept
input is therefore never defaulted to 0, and the templates render the two
states differently.

Permission gating is `receive` throughout, enforced here at the entrypoint —
never left to a template — and every list is domain-scoped (D5).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_http_methods

from app.administration.models import Domain
from app.parts.models import Part
from app.procurement.control_layer.domain_structs.shipment_struct import (
    ShipmentDetailStruct,
    planning_lines_for_order,
)
from app.procurement.control_layer.errors import ProcurementValidationError
from app.procurement.control_layer.factories.shipment_factory import ShipmentFactory
from app.procurement.control_layer.handlers.basic_shipment_manager_submit_handler import (
    BasicShipmentManagerSubmitHandler,
)
from app.procurement.control_layer.shipment_context import ShipmentContext
from app.procurement.models import (
    Shipment,
    ShipmentLine,
    ShipmentStatus,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseOrderStatus,
    Vendor,
)
from app.procurement.control_layer.guards.shipment_state_guard import (
    SHIPMENT_TRANSITIONS,
)
from app.procurement.presentation_layer.metrics.shipment_metrics import ShipmentMetrics
from app.procurement.presentation_layer.search.shipment_search import ShipmentSearch
from app.procurement.presentation_layer.search.purchase_order_line_search import (
    PurchaseOrderLineSearch,
)
from app.procurement.presentation_layer.tools import basic_shipment_session as session_tool
from app.procurement.presentation_layer.tools.procurement_access import (
    accessible_domain_ids,
    can_receive,
    is_in_domain,
    require_receive,
)

TEMPLATE_DIR = "procurement/shipments"
PAGE_SIZE = 50

#: Statuses a shipment can still be shipping against, for the attach-a-PO
#: dropdown. A cancelled or fully-received order is not what an unexpected box
#: belongs to.
ATTACHABLE_PO_STATUSES = (
    PurchaseOrderStatus.DRAFT,
    PurchaseOrderStatus.PLACED,
    PurchaseOrderStatus.PARTIALLY_RECEIVED,
)


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #


def _shipment_or_404_in_domain(request: HttpRequest, pk: int) -> Shipment:
    """D5: a shipment outside the user's domain access is not reachable at all.

    Distinct from the cross-domain *reference* rule (Phase 0 §5), which is about
    a foreign record surfaced ON a page the user already has. This gate is the
    page itself.
    """
    shipment = get_object_or_404(
        Shipment.objects.select_related(
            "purchase_order", "purchase_order__vendor", "domain", "event"
        ).filter(deleted_at__isnull=True),
        pk=pk,
    )
    if not is_in_domain(request, shipment.domain_id):
        raise Http404
    return shipment


def _purchase_order_or_404_in_domain(request: HttpRequest, pk: int) -> PurchaseOrder:
    purchase_order = get_object_or_404(
        PurchaseOrder.objects.select_related("vendor", "domain").filter(
            deleted_at__isnull=True
        ),
        pk=pk,
    )
    if not is_in_domain(request, purchase_order.domain_id):
        raise Http404
    return purchase_order


def _decimal(raw) -> Decimal | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _int(raw) -> int | None:
    text = str(raw or "").strip()
    return int(text) if text.isdigit() else None


def _report(request: HttpRequest, exc: ProcurementValidationError) -> None:
    for error in exc.errors:
        messages.error(request, error)


def _line_rows_from_post(request: HttpRequest) -> tuple[list[dict], list[str]]:
    """Parse the repeated `line_part_id[]` / `line_quantity[]` inputs shared by
    the create and receive forms.

    Rows where both fields are blank are skipped rather than refused — a form
    that renders five spare rows must not make the receiver clear them.
    """
    part_ids = request.POST.getlist("line_part_id")
    quantities = request.POST.getlist("line_quantity")
    rows: list[dict] = []
    errors: list[str] = []

    for index, (raw_part, raw_qty) in enumerate(zip(part_ids, quantities), start=1):
        part_id = _int(raw_part)
        quantity = _decimal(raw_qty)
        if part_id is None and quantity is None:
            continue
        if part_id is None:
            errors.append(f"Line {index}: choose a part.")
            continue
        if quantity is None or quantity <= 0:
            errors.append(f"Line {index}: quantity must be greater than zero.")
            continue
        rows.append({"part_id": part_id, "quantity": quantity})

    return rows, errors


def _part_search_fragment(request: HttpRequest) -> HttpResponse:
    """`<search-dropdown>` results, served from whichever canonical URL asked
    for them — never a dedicated route (format= contract)."""
    q = request.GET.get("q", "").strip()
    qs = Part.objects.all()
    if q:
        from django.db.models import Q

        qs = qs.filter(Q(part_number__icontains=q) | Q(name__icontains=q))
    return render(
        request,
        f"{TEMPLATE_DIR}/_part_search_results.html",
        {"parts": qs.order_by("part_number")[:25]},
    )


def _po_search_fragment(request: HttpRequest, *, domain_ids) -> HttpResponse:
    q = request.GET.get("q", "").strip()
    qs = PurchaseOrder.objects.filter(
        domain_id__in=domain_ids,
        deleted_at__isnull=True,
        status__in=ATTACHABLE_PO_STATUSES,
    ).select_related("vendor")
    if q:
        from django.db.models import Q

        qs = qs.filter(Q(po_number__icontains=q) | Q(vendor__name__icontains=q))
    return render(
        request,
        f"{TEMPLATE_DIR}/_po_search_results.html",
        {"orders": qs.order_by("-order_date")[:25]},
    )


def _domain_choices(request: HttpRequest):
    """Domain is mandatory on a shipment and is the POINT of the reactive path:
    whoever accepts a shipment has a domain to assign it to. A receiver with
    exactly one gets it resolved silently; only a multi-domain receiver is
    asked."""
    domains = Domain.objects.filter(pk__in=accessible_domain_ids(request)).order_by(
        "name"
    )
    return {
        "domains": domains,
        "show_domain_picker": domains.count() > 1,
        "single_domain": domains.first() if domains.count() == 1 else None,
    }


def _resolve_domain(request: HttpRequest) -> Domain | None:
    domain_id = _int(request.POST.get("domain_id"))
    if domain_id is None or domain_id not in accessible_domain_ids(request):
        return None
    return Domain.objects.filter(pk=domain_id).first()


# --------------------------------------------------------------------------- #
# 3.6 shipment_index
# --------------------------------------------------------------------------- #


@require_http_methods(["GET"])
def shipment_index(request: HttpRequest) -> HttpResponse:
    """The receiving queue (phase_3 §3.6).

    Two filters here are first-class rather than buried, because each maps to a
    real standing job: `mixed_po_assignments` IS the drift review queue, and
    `shipment_id` is how a receiver with a box in hand finds its record —
    they search by what is printed on the label, not by our shipment number.
    """
    domain_ids = accessible_domain_ids(request)

    filters = {
        "status": request.GET.get("status", "").strip(),
        "vendor_id": request.GET.get("vendor_id", "").strip(),
        "shipment_id": request.GET.get("shipment_id", "").strip(),
        # Kept as the raw "1"/"" rather than a bool so the pagination links,
        # which re-emit every filter verbatim, round-trip back into a checked
        # box instead of `mixed_only=True`.
        "mixed_only": "1" if request.GET.get("mixed_only") == "1" else "",
        "unattached_only": "1" if request.GET.get("unattached_only") == "1" else "",
        "arrived_from": request.GET.get("arrived_from", "").strip(),
        "arrived_to": request.GET.get("arrived_to", "").strip(),
        "q": request.GET.get("q", "").strip(),
    }

    qs = ShipmentSearch.index_list(
        domain_ids=domain_ids,
        status=filters["status"],
        vendor_id=_int(filters["vendor_id"]),
        shipment_id=filters["shipment_id"],
        mixed_only=filters["mixed_only"] == "1",
        unattached_only=filters["unattached_only"] == "1",
        arrived_from=parse_date(filters["arrived_from"]) if filters["arrived_from"] else None,
        arrived_to=parse_date(filters["arrived_to"]) if filters["arrived_to"] else None,
        q=filters["q"],
    )

    stats = ShipmentMetrics.summarize(qs)

    paginator = Paginator(qs, PAGE_SIZE)
    page = paginator.get_page(request.GET.get("page", "1"))

    context = {
        "page": page,
        "shipments": page.object_list,
        "stats": stats,
        "filters": filters,
        "statuses": ShipmentStatus.choices,
        "vendors": Vendor.objects.filter(is_active=True).order_by("name"),
        "can_receive": can_receive(request),
    }

    if request.GET.get("format") == "htmx-search-results":
        return render(request, f"{TEMPLATE_DIR}/_index_results.html", context)
    return render(request, f"{TEMPLATE_DIR}/index.html", context)


# --------------------------------------------------------------------------- #
# 3.2 shipment_create  /  3.3 shipment_receive
# --------------------------------------------------------------------------- #


@require_http_methods(["GET", "POST"])
def shipment_create(request: HttpRequest) -> HttpResponse:
    """Simple form with an embedded line table — deliberately NOT a wizard.

    `Shipment` has exactly one reverse FK a user populates at creation (its
    lines) and no secondary signal pushing it over the multi-card trigger.

    There is no line-level demand picker here on purpose: that is the whole
    point of copy-on-create. A line whose part matches exactly one active line
    on the header PO is linked automatically, and the receiver never types an
    assignment they would only have guessed at.
    """
    if request.method == "GET" and request.GET.get("format") == "htmx-search-results":
        return _part_search_fragment(request)

    require_receive(request)
    domain_ids = accessible_domain_ids(request)

    if request.method == "POST":
        return _create_shipment_from_form(request, reactive=False)

    preselected_po = None
    po_id = _int(request.GET.get("purchase_order_id"))
    if po_id is not None:
        preselected_po = PurchaseOrder.objects.filter(
            pk=po_id, domain_id__in=domain_ids, deleted_at__isnull=True
        ).select_related("vendor").first()

    return render(
        request,
        f"{TEMPLATE_DIR}/create.html",
        {
            "preselected_po": preselected_po,
            "purchase_orders": PurchaseOrder.objects.filter(
                domain_id__in=domain_ids,
                deleted_at__isnull=True,
                status__in=ATTACHABLE_PO_STATUSES,
            )
            .select_related("vendor")
            .order_by("-order_date")[:200],
            **_domain_choices(request),
        },
    )


@require_http_methods(["GET", "POST"])
def shipment_receive(request: HttpRequest) -> HttpResponse:
    """The reactive path: a box arrived and there is no purchase order.

    D71/D73's nullable `purchase_order` is what makes this possible, and D74's
    required `domain` is what keeps it from producing an ownerless record.

    THERE IS NO PO FIELD ON THIS FORM. Attachment happens later on the edit
    page, where auto-linking can run against real lines. Offering a PO picker
    here would just recreate `shipment_create` and lose the one thing this route
    exists to say: you do not need the paperwork to record the box.

    Lines land with `purchase_order_line = null`. That is correct, not an
    error state.
    """
    if request.method == "GET" and request.GET.get("format") == "htmx-search-results":
        return _part_search_fragment(request)

    require_receive(request)

    if request.method == "POST":
        return _create_shipment_from_form(request, reactive=True)

    return render(request, f"{TEMPLATE_DIR}/receive.html", _domain_choices(request))


def _create_shipment_from_form(request: HttpRequest, *, reactive: bool) -> HttpResponse:
    """Shared commit path for both creation routes.

    Both redirect to `shipment_edit`, not detail: a fresh shipment is mid-setup —
    lines to assign, maybe a PO to attach — and that is the edit page's job.
    """
    back = reverse("shipment_receive" if reactive else "shipment_create")
    rows, row_errors = _line_rows_from_post(request)
    for error in row_errors:
        messages.error(request, error)
    if row_errors:
        return redirect(back)

    purchase_order = None
    if not reactive:
        po_id = _int(request.POST.get("purchase_order_id"))
        if po_id is not None:
            purchase_order = PurchaseOrder.objects.filter(
                pk=po_id,
                domain_id__in=accessible_domain_ids(request),
                deleted_at__isnull=True,
            ).first()
            if purchase_order is None:
                messages.error(
                    request, "That purchase order is not one you have access to."
                )
                return redirect(back)

    domain = purchase_order.domain if purchase_order else _resolve_domain(request)
    if domain is None:
        messages.error(
            request,
            "Choose a domain — a shipment always belongs to one, even before its "
            "purchase order does.",
        )
        return redirect(back)

    try:
        shipment = ShipmentFactory.create(
            domain=domain,
            purchase_order=purchase_order,
            lines=rows,
            actor=request.user,
            shipment_id=request.POST.get("shipment_id", "").strip(),
            carrier=request.POST.get("carrier", "").strip(),
            shipped_date=parse_date(request.POST.get("shipped_date", "") or ""),
            expected_arrival_date=parse_date(
                request.POST.get("expected_arrival_date", "") or ""
            ),
            notes=request.POST.get("notes", "").strip(),
        )
    except ProcurementValidationError as exc:
        _report(request, exc)
        return redirect(back)

    messages.success(
        request,
        f"Shipment {shipment.shipment_number} recorded with {len(rows)} line(s). "
        f"Check the assignments below before moving on.",
    )
    return redirect(reverse("shipment_edit", kwargs={"pk": shipment.pk}))


# --------------------------------------------------------------------------- #
# 3.5 shipment_detail
# --------------------------------------------------------------------------- #


@require_http_methods(["GET", "POST"])
def shipment_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Work portal (3/4 + 1/4). Where status is advanced and lines are
    inspected and accepted.

    Everything else — reassignment, splitting, header edits, deletions — is a
    link to the edit page. This page's two verbs are `advance` and `accept`.
    """
    shipment = _shipment_or_404_in_domain(request, pk)

    if request.method == "POST":
        return _detail_post(request, shipment)

    detail = ShipmentDetailStruct.load(shipment_id=shipment.pk)

    comments_card = None
    attachments = []
    if shipment.event_id:
        from app.events.presentation_layer.tools.generic_cards import (
            build_activity_card,
        )

        comments_card = build_activity_card(shipment.event, request.user)
        attachments = comments_card["direct_attachments"]

    # files_card and gallery_card each take a PRE-SPLIT list — the fragments do
    # no filtering of their own, and handing the same list to both would show
    # every PDF in the photo carousel.
    return render(
        request,
        f"{TEMPLATE_DIR}/detail.html",
        {
            "shipment": shipment,
            "detail": detail,
            "comments_card": comments_card,
            "documents": [a for a in attachments if not a["is_image"]],
            "images": [a for a in attachments if a["is_image"]],
            "next_statuses": _next_status_choices(shipment),
            "status_history": _status_history(shipment),
            "can_receive": can_receive(request),
            # Cross-domain rule: a PO in another domain renders its identifying
            # data as plain text with no link through.
            "po_linkable": is_in_domain(request, detail.purchase_order_domain_id),
        },
    )


def _next_status_choices(shipment: Shipment) -> list[tuple[str, str]]:
    """Only the CURRENTLY LEGAL next stage(s) — in practice one, plus `Lost`
    where the branch applies.

    Not a full stepper and not jump-to-any-stage: a status list offering
    illegal moves teaches people to expect a refusal, which is exactly how a
    guard stops being read as information.
    """
    labels = dict(ShipmentStatus.choices)
    legal = SHIPMENT_TRANSITIONS.get(shipment.status, frozenset())
    return [(value, labels.get(value, value)) for value in labels if value in legal]


def _status_history(shipment: Shipment) -> list[dict]:
    """The stepper on the rail: where this shipment has been and where it is.

    Kept ALONGSIDE the comments card rather than merged into it — one answers
    "where is it" at a glance, the other answers "why" in prose, and collapsing
    them makes the glance question expensive.
    """
    order = [
        ShipmentStatus.AWAITING_SHIPMENT,
        ShipmentStatus.SHIPPED,
        ShipmentStatus.DELIVERED_TO_DEPOT,
        ShipmentStatus.DELIVERED_TO_LOCAL,
        ShipmentStatus.ACCEPTED,
    ]
    labels = dict(ShipmentStatus.choices)
    if shipment.status == ShipmentStatus.LOST:
        return [
            {"value": ShipmentStatus.LOST, "label": labels[ShipmentStatus.LOST],
             "state": "current"}
        ]
    try:
        current_index = order.index(shipment.status)
    except ValueError:
        current_index = -1
    return [
        {
            "value": value,
            "label": labels[value],
            "state": (
                "done"
                if index < current_index
                else "current"
                if index == current_index
                else "future"
            ),
        }
        for index, value in enumerate(order)
    ]


def _detail_post(request: HttpRequest, shipment: Shipment) -> HttpResponse:
    require_receive(request)
    action = request.POST.get("action", "")
    context = ShipmentContext(shipment.pk)
    back = reverse("shipment_detail", kwargs={"pk": shipment.pk})

    try:
        if action == "advance_status":
            to_status = request.POST.get("to_status", "").strip()
            moved = context.advance(to_status=to_status, actor=request.user)
            messages.success(
                request,
                f"Shipment status updated."
                + (
                    f" {len(moved)} demand(s) moved with it."
                    if moved
                    else " No demand's shipment status changed — the demands behind "
                    "this shipment are waiting on another box too."
                ),
            )
        elif action == "accept_line":
            _accept_line(request, shipment, context)
        else:
            messages.error(request, "Unrecognised action.")
    except ProcurementValidationError as exc:
        _report(request, exc)

    return redirect(back)


def _accept_line(request: HttpRequest, shipment: Shipment, context: ShipmentContext) -> None:
    """Record what survived the trip.

    `quantity_accepted` is deliberately NOT defaulted anywhere in this path: a
    blank input is rejected with a message rather than silently read as 0,
    because "I have not looked yet" and "I looked and it is all scrap" are
    different facts and only one of them should be writable by leaving a box
    empty.
    """
    line = ShipmentLine.objects.filter(
        pk=_int(request.POST.get("line_id")),
        shipment=shipment,
        deleted_at__isnull=True,
    ).select_related("part").first()
    if line is None:
        messages.error(request, "That line is not on this shipment.")
        return

    quantity = _decimal(request.POST.get("quantity_accepted"))
    if quantity is None:
        messages.error(
            request,
            f"Enter an accepted quantity for {line.part.part_number}. Leaving it "
            f"blank means 'not inspected yet', which is what it already says.",
        )
        return

    context.accept_line(
        line=line,
        quantity_accepted=quantity,
        actor=request.user,
        rejection_notes=request.POST.get("rejection_notes", "").strip(),
    )
    messages.success(
        request, f"{line.part.part_number}: {quantity} of {line.quantity} accepted."
    )


# --------------------------------------------------------------------------- #
# 3.4 shipment_edit — Edit & Linkage
# --------------------------------------------------------------------------- #


@require_http_methods(["GET", "POST"])
def shipment_edit(request: HttpRequest, pk: int) -> HttpResponse:
    """The shipment sector's mirror of the PO's Edit & Linkage, inverted: it
    links THIS SHIPMENT'S lines to PO lines, potentially across several vendors'
    open orders.

    This route ABSORBS the old line-splitting wizard entirely — there is no
    `/shipments/<id>/lines/<line_id>/split`. Splitting is what the Assign action
    does when the quantity is partial, so the user makes one decision ("this
    much belongs there") instead of choosing between two verbs.

    `?line_id=` pre-selects a line and round-trips through the URL, which is how
    shipment detail's per-line "Edit assignment" deep-links in and what makes a
    reload reproduce the selection.
    """
    shipment = _shipment_or_404_in_domain(request, pk)

    if request.method == "GET":
        fmt = request.GET.get("format")
        if fmt == "htmx-search-results":
            return _part_search_fragment(request)
        if fmt == "htmx-po-results":
            return _po_search_fragment(
                request, domain_ids=accessible_domain_ids(request)
            )

    if request.method == "POST":
        return _edit_post(request, shipment)

    return _edit_render(request, shipment)


def _edit_render(request: HttpRequest, shipment: Shipment) -> HttpResponse:
    detail = ShipmentDetailStruct.load(shipment_id=shipment.pk)
    context = ShipmentContext(shipment.pk)

    selected_line_id = _int(request.GET.get("line_id"))
    selected = next(
        (line for line in detail.lines if line.line_id == selected_line_id), None
    )

    # The right column's candidates: open PO lines that could account for the
    # selected arriving part. Three quantities per candidate — ordered, already
    # accepted, outstanding — because that is the minimum needed to judge a
    # target before assigning to it, and it is why these are wide cards rather
    # than a typeahead.
    candidates = []
    if selected is not None:
        include_draft = request.GET.get("include_draft") == "1"
        vendor_id = None
        if request.GET.get("vendor_scope", "any") == "header" and shipment.purchase_order_id:
            vendor_id = shipment.purchase_order.vendor_id
        candidates = list(
            PurchaseOrderLineSearch.candidates_for_arriving_part(
                part_id=selected.part_id,
                vendor_id=vendor_id,
                include_draft=include_draft,
            ).filter(purchase_order__domain_id__in=accessible_domain_ids(request))[:50]
        )

    return render(
        request,
        f"{TEMPLATE_DIR}/edit.html",
        {
            "shipment": shipment,
            "detail": detail,
            "selected": selected,
            "selected_line_id": selected_line_id,
            "candidates": candidates,
            "search_filters": {
                "include_draft": request.GET.get("include_draft") == "1",
                "vendor_scope": request.GET.get("vendor_scope", "any"),
            },
            # Every mutation on a delivered or split shipment costs a mandatory
            # comment. The template turns this into a required textarea in each
            # confirmation popup rather than discovering it on submit.
            "requires_audit_comment": context.requires_audit_comment,
            "can_receive": can_receive(request),
        },
    )


def _edit_post(request: HttpRequest, shipment: Shipment) -> HttpResponse:
    require_receive(request)
    action = request.POST.get("action", "")
    context = ShipmentContext(shipment.pk)

    line_id = _int(request.POST.get("line_id"))
    back = reverse("shipment_edit", kwargs={"pk": shipment.pk})
    if line_id and action != "delete_line":
        back = f"{back}?line_id={line_id}"

    audit_comment = request.POST.get("audit_comment", "")

    try:
        if action == "save_header":
            context.update_header(
                shipment_id=request.POST.get("shipment_id", "").strip(),
                carrier=request.POST.get("carrier", "").strip(),
                shipped_date=parse_date(request.POST.get("shipped_date", "") or ""),
                expected_arrival_date=parse_date(
                    request.POST.get("expected_arrival_date", "") or ""
                ),
                notes=request.POST.get("notes", "").strip(),
                actor=request.user,
                audit_comment=audit_comment,
            )
            messages.success(request, "Shipment details saved.")

        elif action == "attach_purchase_order":
            _attach_purchase_order(request, shipment, context, audit_comment)

        elif action == "add_line":
            _add_line(request, shipment, context, audit_comment)

        elif action == "assign":
            _assign_line(request, shipment, context, audit_comment)

        elif action == "unassign":
            line = _line_on_shipment(shipment, line_id)
            if line is None:
                messages.error(request, "That line is not on this shipment.")
            else:
                context.reassign_line(
                    line=line,
                    purchase_order_line=None,
                    actor=request.user,
                    audit_comment=audit_comment,
                )
                messages.success(
                    request,
                    f"{line.part.part_number} is now unassigned. It still counts as "
                    f"arrived — it just does not answer for any order line.",
                )

        elif action == "delete_line":
            _delete_line(request, shipment, context, audit_comment)

        elif action == "delete_shipment":
            return _delete_shipment(request, shipment, context)

        else:
            messages.error(request, "Unrecognised action.")

    except ProcurementValidationError as exc:
        _report(request, exc)

    return redirect(back)


def _line_on_shipment(shipment: Shipment, line_id: int | None) -> ShipmentLine | None:
    if line_id is None:
        return None
    return (
        ShipmentLine.objects.filter(
            pk=line_id, shipment=shipment, deleted_at__isnull=True
        )
        .select_related("part", "purchase_order_line")
        .first()
    )


def _attach_purchase_order(
    request: HttpRequest,
    shipment: Shipment,
    context: ShipmentContext,
    audit_comment: str,
) -> None:
    """Attach a PO to a shipment received without one, then auto-link.

    Auto-linking matches a line's part against the order's active lines. No
    match, OR MORE THAN ONE matching active line, leaves that line unlinked.
    Safe failure — the tool never guesses which of two lines a box belongs to,
    because a wrong guess is invisible and a blank is not.
    """
    if shipment.purchase_order_id is not None:
        messages.error(
            request,
            f"This shipment is already attached to {shipment.purchase_order.po_number}. "
            f"Reassign its lines individually instead.",
        )
        return

    po_id = _int(request.POST.get("purchase_order_id"))
    purchase_order = PurchaseOrder.objects.filter(
        pk=po_id,
        domain_id__in=accessible_domain_ids(request),
        deleted_at__isnull=True,
    ).first()
    if purchase_order is None:
        messages.error(request, "Choose a purchase order you have access to.")
        return

    active_lines = len(
        [line for line in shipment.lines.filter(deleted_at__isnull=True)]
    )
    linked = context.attach_purchase_order(
        purchase_order=purchase_order,
        actor=request.user,
        audit_comment=audit_comment,
    )
    unlinked = active_lines - linked
    text = f"Attached to {purchase_order.po_number}. {linked} line(s) auto-linked."
    if unlinked:
        text += (
            f" {unlinked} line(s) were left unassigned — either no line on that "
            f"order matches the part, or more than one does. Assign those by hand."
        )
    messages.success(request, text)


def _add_line(
    request: HttpRequest,
    shipment: Shipment,
    context: ShipmentContext,
    audit_comment: str,
) -> None:
    part_id = _int(request.POST.get("part_id"))
    quantity = _decimal(request.POST.get("quantity"))
    if part_id is None:
        messages.error(request, "Choose a part for the new line.")
        return
    if quantity is None or quantity <= 0:
        messages.error(request, "The new line needs a quantity greater than zero.")
        return

    po_line = None
    po_line_id = _int(request.POST.get("purchase_order_line_id"))
    if po_line_id is not None:
        po_line = PurchaseOrderLine.objects.filter(
            pk=po_line_id,
            deleted_at__isnull=True,
            purchase_order__domain_id__in=accessible_domain_ids(request),
        ).first()

    line = context.add_line(
        part_id=part_id,
        quantity=quantity,
        actor=request.user,
        purchase_order_line=po_line,
        audit_comment=audit_comment,
    )
    messages.success(request, f"Added {line.quantity} x {line.part.part_number}.")


def _assign_line(
    request: HttpRequest,
    shipment: Shipment,
    context: ShipmentContext,
    audit_comment: str,
) -> None:
    """The right column's Assign action.

    Partial quantity splits the line; the full remaining quantity reassigns it.
    That choice is made in the control layer (`ShipmentContext.assign_line`), not
    here — it is one user decision and should not be two code paths in a view.
    """
    line = _line_on_shipment(shipment, _int(request.POST.get("line_id")))
    if line is None:
        messages.error(request, "That line is not on this shipment.")
        return

    po_line = PurchaseOrderLine.objects.filter(
        pk=_int(request.POST.get("purchase_order_line_id")),
        deleted_at__isnull=True,
        purchase_order__domain_id__in=accessible_domain_ids(request),
    ).select_related("purchase_order").first()
    if po_line is None:
        messages.error(request, "Choose an order line you have access to.")
        return

    quantity = _decimal(request.POST.get("quantity"))
    if quantity is not None and quantity <= 0:
        messages.error(request, "Assigned quantity must be greater than zero.")
        return

    was_partial = quantity is not None and quantity < line.quantity
    context.assign_line(
        line=line,
        purchase_order_line=po_line,
        quantity=quantity,
        actor=request.user,
        audit_comment=audit_comment,
    )
    if was_partial:
        messages.success(
            request,
            f"{quantity} of {line.part.part_number} split onto "
            f"{po_line.purchase_order.po_number} line {po_line.line_number}. The "
            f"remainder stays on the original line, still needing a home.",
        )
    else:
        messages.success(
            request,
            f"{line.part.part_number} assigned to "
            f"{po_line.purchase_order.po_number} line {po_line.line_number}.",
        )


def _delete_line(
    request: HttpRequest,
    shipment: Shipment,
    context: ShipmentContext,
    audit_comment: str,
) -> None:
    line = _line_on_shipment(shipment, _int(request.POST.get("line_id")))
    if line is None:
        messages.error(request, "That line is not on this shipment.")
        return
    context.delete_line(
        line=line,
        actor=request.user,
        reason=request.POST.get("reason", "").strip(),
        audit_comment=audit_comment,
    )
    messages.success(request, f"Removed {line.part.part_number} from this shipment.")


def _delete_shipment(
    request: HttpRequest, shipment: Shipment, context: ShipmentContext
) -> HttpResponse:
    """Soft delete, with a mandatory reason, cascading to every active line.

    `ShipmentLine.shipment`'s CASCADE is a HARD-delete cascade and does nothing
    here, so the context soft-deletes each line explicitly — otherwise they
    survive as active rows under a deleted shipment.
    """
    try:
        context.delete(actor=request.user, reason=request.POST.get("reason", ""))
    except ProcurementValidationError as exc:
        _report(request, exc)
        return redirect(reverse("shipment_edit", kwargs={"pk": shipment.pk}))

    messages.success(request, f"Shipment {shipment.shipment_number} deleted.")
    return redirect(reverse("shipment_index"))


# --------------------------------------------------------------------------- #
# 3.1 basic_shipment_manager — PO-scoped, route declared in urls_purchase_orders
# --------------------------------------------------------------------------- #


@require_http_methods(["GET", "POST"])
def basic_shipment_manager(request: HttpRequest, pk: int) -> HttpResponse:
    """FORWARD-LOOKING. A Buyer planning a PO's *expected* boxes from a
    vendor's shipping confirmation — not a receiver with a carton in hand.
    That job is `shipment_receive`.

    Nothing on this page writes until Submit. The create-shipment form appends a
    session-only card; chips move between cards in the session; the whole
    layout is committed once by BasicShipmentManagerSubmitHandler, all or
    nothing.

    Drag-and-drop is the fast path and never the only path — every gesture has
    a plain form equivalent posting to the same actions, which is what keeps
    the F5 rule true here.
    """
    purchase_order = _purchase_order_or_404_in_domain(request, pk)
    require_receive(request)

    draft = session_tool.load(request, purchase_order=purchase_order)

    if request.method == "POST":
        return _manager_post(request, purchase_order, draft)

    planning_lines = planning_lines_for_order(purchase_order=purchase_order)
    planned = session_tool.planned_by_po_line(draft)

    chips = [
        {
            "line": line,
            # What the DRAFT lays out, which may differ from what is on file —
            # that difference is precisely what Submit will apply.
            "planned": planned.get(line.line_id, Decimal("0")),
            "unplanned": max(
                line.qty_ordered - planned.get(line.line_id, Decimal("0")),
                Decimal("0"),
            ),
        }
        for line in planning_lines
    ]

    return render(
        request,
        f"{TEMPLATE_DIR}/basic_manager.html",
        {
            "po": purchase_order,
            "draft": draft,
            "chips": chips,
            "line_labels": {
                line.line_id: f"{line.line_number}. {line.part_number}"
                for line in planning_lines
            },
            "cards": _manager_cards(draft, planning_lines),
            "card_errors": request.session.pop("basic_shipment_card_errors", {}),
            "can_receive": can_receive(request),
        },
    )


def _manager_cards(draft: dict, planning_lines) -> list[dict]:
    """Marry each session card to the PO-line labels its chips need.

    Done here rather than in the template because a template that has to look
    up a label per chip ends up doing it with a filter over the whole list —
    O(chips x lines) inside the render loop.
    """
    by_id = {line.line_id: line for line in planning_lines}
    cards = []
    for card in draft["shipments"]:
        chips = []
        for chip in card["lines"]:
            line = by_id.get(chip["po_line_id"])
            chips.append(
                {
                    "po_line_id": chip["po_line_id"],
                    "quantity": chip["quantity"],
                    "label": (
                        f"{line.line_number}. {line.part_number}"
                        if line
                        else f"Line {chip['po_line_id']} (no longer on this order)"
                    ),
                    "part_name": line.part_name if line else "",
                    "orphaned": line is None,
                }
            )
        cards.append({"card": card, "chips": chips})
    return cards


def _manager_post(
    request: HttpRequest, purchase_order: PurchaseOrder, draft: dict
) -> HttpResponse:
    action = request.POST.get("action", "")
    back = reverse("basic_shipment_manager", kwargs={"pk": purchase_order.pk})

    if action == "add_shipment":
        session_tool.add_shipment(
            draft,
            fields={
                "shipment_id": request.POST.get("shipment_id", "").strip(),
                "carrier": request.POST.get("carrier", "").strip(),
                "shipped_date": request.POST.get("shipped_date", "").strip(),
                "expected_arrival_date": request.POST.get(
                    "expected_arrival_date", ""
                ).strip(),
                "notes": request.POST.get("notes", "").strip(),
            },
        )
        messages.success(
            request,
            "Shipment added to the plan. Nothing is saved until you submit.",
        )

    elif action == "update_shipment":
        if not session_tool.update_shipment(
            draft,
            temp_id=request.POST.get("temp_id", ""),
            fields={
                key: request.POST.get(key, "").strip()
                for key in (
                    "shipment_id",
                    "carrier",
                    "shipped_date",
                    "expected_arrival_date",
                    "notes",
                )
            },
        ):
            messages.error(request, "That shipment is locked and cannot be edited here.")

    elif action == "remove_shipment":
        if not session_tool.remove_shipment(
            draft, temp_id=request.POST.get("temp_id", "")
        ):
            messages.error(
                request,
                "Only a shipment that has not been saved yet can be dropped here. "
                "Delete a real shipment from its own edit page.",
            )

    elif action == "assign":
        ok = session_tool.assign(
            draft,
            temp_id=request.POST.get("temp_id", ""),
            po_line_id=_int(request.POST.get("po_line_id")),
            quantity=_decimal(request.POST.get("quantity")),
        )
        if not ok:
            messages.error(
                request,
                "Could not add that to the shipment — check the quantity, and note "
                "that a locked shipment cannot take new lines.",
            )

    elif action == "set_quantity":
        session_tool.set_quantity(
            draft,
            temp_id=request.POST.get("temp_id", ""),
            po_line_id=_int(request.POST.get("po_line_id")),
            quantity=_decimal(request.POST.get("quantity")),
        )

    elif action == "unassign":
        session_tool.unassign(
            draft,
            temp_id=request.POST.get("temp_id", ""),
            po_line_id=_int(request.POST.get("po_line_id")),
        )

    elif action == "move":
        # The drag gesture's server-side equivalent. Same code path, so the
        # drag layer cannot develop behaviour the no-JS path lacks.
        if not session_tool.move(
            draft,
            from_temp_id=request.POST.get("from_temp_id", ""),
            to_temp_id=request.POST.get("to_temp_id", ""),
            po_line_id=_int(request.POST.get("po_line_id")),
            quantity=_decimal(request.POST.get("quantity")),
        ):
            messages.error(request, "That move is not possible — one end is locked.")

    elif action == "reset":
        session_tool.discard(request, purchase_order=purchase_order)
        messages.success(request, "Plan reset to what is on file.")
        return redirect(back)

    elif action == "submit":
        return _manager_submit(request, purchase_order, draft)

    else:
        messages.error(request, "Unrecognised action.")

    session_tool.save(request, purchase_order=purchase_order, draft=draft)
    return redirect(back)


def _manager_submit(
    request: HttpRequest, purchase_order: PurchaseOrder, draft: dict
) -> HttpResponse:
    """All or nothing.

    On failure the session draft survives untouched and the page re-renders
    with errors keyed to the card that tripped them — a partial commit would
    leave the Buyer unsure which of several decisions landed.
    """
    handler = BasicShipmentManagerSubmitHandler(
        purchase_order=purchase_order, draft=draft, actor=request.user
    )
    try:
        summary = handler.run()
    except ProcurementValidationError as exc:
        request.session["basic_shipment_card_errors"] = handler.card_errors
        session_tool.save(request, purchase_order=purchase_order, draft=draft)
        messages.error(
            request,
            "Nothing was saved — the whole plan was rejected so you can see "
            "exactly which decisions still need attention.",
        )
        _report(request, exc)
        return redirect(
            reverse("basic_shipment_manager", kwargs={"pk": purchase_order.pk})
        )

    session_tool.discard(request, purchase_order=purchase_order)
    messages.success(request, summary.as_message())
    return redirect(reverse("purchase_order_detail", kwargs={"pk": purchase_order.pk}))
