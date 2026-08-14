"""Inventory's mirror of the Receiving Loop (D84) — `inventory/shipments/...`.

D84: Inventory gets a thin duplicate VIEW/EDIT surface over procurement's own
`Shipment`/`ShipmentLine` rows. There is no `inventory.Shipment` model — every
read here is a plain queryset against `app.procurement.models.Shipment` (see
`InventoryShipmentSearch`), and every write goes through procurement's own
`ShipmentContext` control-layer verbs (`advance`, `accept_line`,
`update_header`) — never a raw `.save()` duplicating logic those verbs already
own.

**Scope, deliberately narrower than procurement's own `shipments.py`:**

- No create/receive routes here — receiving a NEW shipment is still
  procurement's job (D83's scope note). Inventory only views and edits
  shipments that already exist.
- No PO attach/line reassignment/line delete/shipment delete here either —
  those are procurement's order-linkage job, not inventory's physical/
  received-side concern. Follow the link back to
  `procurement/shipments/<pk>/edit/` (rendered plainly, cross-app, same as any
  other page-to-page link) for that work.
- What IS in scope: the receiving-queue list, the per-line acceptance/
  rejection recording (`accept_line`), status advancement (`advance`), and
  header edits on the physical fields (`update_header`'s five fields, plus
  `received_date` — see `_set_received_date` below for why that one field is
  a plain guarded model update rather than a control-layer call).

Permission gating is `procurement.receive` throughout (re-declared locally in
`inventory_access`, see that module's docstring for why), enforced here at
the entrypoint, never left to a template. Every list and detail lookup is
domain-scoped (D5), same as procurement's own pages.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_http_methods

from app.procurement.control_layer.errors import ProcurementValidationError
from app.procurement.control_layer.guards.shipment_state_guard import (
    SHIPMENT_TRANSITIONS,
)
from app.procurement.control_layer.shipment_context import ShipmentContext
from app.procurement.models import Shipment, ShipmentLine, ShipmentStatus
from app.inventory.presentation_layer.search.shipment_search import (
    InventoryShipmentSearch,
)
from app.inventory.presentation_layer.tools.inventory_access import (
    accessible_domain_ids,
    can_receive,
    is_in_domain,
    require_receive,
)

TEMPLATE_DIR = "inventory/shipments"
PAGE_SIZE = 50


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #


def _shipment_or_404_in_domain(request: HttpRequest, pk: int) -> Shipment:
    """D5: a shipment outside the user's domain access is not reachable at
    all, mirroring procurement's own `_shipment_or_404_in_domain`."""
    shipment = get_object_or_404(
        Shipment.objects.select_related(
            "purchase_order", "purchase_order__vendor", "domain"
        ).filter(deleted_at__isnull=True),
        pk=pk,
    )
    if not is_in_domain(request, shipment.domain_id):
        raise Http404
    return shipment


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


# --------------------------------------------------------------------------- #
# inventory_shipment_index
# --------------------------------------------------------------------------- #


@require_http_methods(["GET"])
def inventory_shipment_index(request: HttpRequest) -> HttpResponse:
    """The receiving queue, read-only, as seen from Inventory's side."""
    domain_ids = accessible_domain_ids(request)

    filters = {
        "status": request.GET.get("status", "").strip(),
        "shipment_id": request.GET.get("shipment_id", "").strip(),
        "q": request.GET.get("q", "").strip(),
    }

    qs = InventoryShipmentSearch.index_list(
        domain_ids=domain_ids,
        status=filters["status"],
        shipment_id=filters["shipment_id"],
        q=filters["q"],
    )

    paginator = Paginator(qs, PAGE_SIZE)
    page = paginator.get_page(request.GET.get("page", "1"))

    context = {
        "page": page,
        "shipments": page.object_list,
        "filters": filters,
        "statuses": ShipmentStatus.choices,
        "can_receive": can_receive(request),
    }

    if request.GET.get("format") == "htmx-search-results":
        return render(request, f"{TEMPLATE_DIR}/_results_card.html", context)
    return render(request, f"{TEMPLATE_DIR}/index.html", context)


# --------------------------------------------------------------------------- #
# inventory_shipment_detail
# --------------------------------------------------------------------------- #


@require_http_methods(["GET", "POST"])
def inventory_shipment_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Work portal, narrowed to the two verbs that belong to the physical/
    received side: `advance_status` and `accept_line`. Everything about
    order-linkage stays a link out to procurement's own edit page."""
    shipment = _shipment_or_404_in_domain(request, pk)

    if request.method == "POST":
        return _detail_post(request, shipment)

    lines = list(
        ShipmentLine.objects.filter(shipment=shipment, deleted_at__isnull=True)
        .select_related("part", "purchase_order_line", "purchase_order_line__purchase_order")
        .order_by("pk")
    )

    return render(
        request,
        f"{TEMPLATE_DIR}/detail.html",
        {
            "shipment": shipment,
            "lines": lines,
            "next_statuses": _next_status_choices(shipment),
            "can_receive": can_receive(request),
            "po_linkable": is_in_domain(request, shipment.purchase_order.domain_id)
            if shipment.purchase_order_id
            else False,
        },
    )


def _next_status_choices(shipment: Shipment) -> list[tuple[str, str]]:
    labels = dict(ShipmentStatus.choices)
    legal = SHIPMENT_TRANSITIONS.get(shipment.status, frozenset())
    return [(value, labels.get(value, value)) for value in labels if value in legal]


def _detail_post(request: HttpRequest, shipment: Shipment) -> HttpResponse:
    require_receive(request)
    action = request.POST.get("action", "")
    context = ShipmentContext(shipment.pk)
    back = reverse("inventory_shipment_detail", kwargs={"pk": shipment.pk})

    try:
        if action == "advance_status":
            to_status = request.POST.get("to_status", "").strip()
            moved = context.advance(to_status=to_status, actor=request.user)
            messages.success(
                request,
                "Shipment status updated."
                + (
                    f" {len(moved)} demand(s) moved with it."
                    if moved
                    else ""
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
    """Record what survived the trip. Calls `ShipmentContext.accept_line` —
    the same control-layer verb procurement's own detail page uses — never a
    raw `.save()` on the line."""
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
# inventory_shipment_edit — physical/received-side header fields only
# --------------------------------------------------------------------------- #


@require_http_methods(["GET", "POST"])
def inventory_shipment_edit(request: HttpRequest, pk: int) -> HttpResponse:
    """Header edit, narrowed to the physical/received-side fields.

    No PO attach, no line add/reassign/delete, no shipment delete — those stay
    procurement-only (order-linkage is not an inventory concern per D84). This
    page is deliberately smaller than procurement's `shipment_edit`.
    """
    shipment = _shipment_or_404_in_domain(request, pk)

    if request.method == "POST":
        return _edit_post(request, shipment)

    return render(
        request,
        f"{TEMPLATE_DIR}/edit.html",
        {
            "shipment": shipment,
            "can_receive": can_receive(request),
        },
    )


def _edit_post(request: HttpRequest, shipment: Shipment) -> HttpResponse:
    require_receive(request)
    action = request.POST.get("action", "")
    context = ShipmentContext(shipment.pk)
    back = reverse("inventory_shipment_edit", kwargs={"pk": shipment.pk})

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
                audit_comment=request.POST.get("audit_comment", ""),
            )
            messages.success(request, "Shipment details saved.")
        elif action == "set_received_date":
            _set_received_date(request, shipment)
        else:
            messages.error(request, "Unrecognised action.")
    except ProcurementValidationError as exc:
        _report(request, exc)

    return redirect(back)


def _set_received_date(request: HttpRequest, shipment: Shipment) -> None:
    """`received_date` — when the box physically showed up — has no
    control-layer verb anywhere in `ShipmentContext`/`ShipmentLineManager`
    (checked: the model field exists, set nowhere). D84 explicitly allows a
    plain guarded model update for a field with no existing verb rather than
    inventing a new control-layer method for one column in this pass. Guarded
    here by the same `require_receive` gate and domain-scoped lookup every
    other write on this page uses — nothing bypasses the permission or
    ownership checks, only the (nonexistent) business-logic verb.
    """
    raw = request.POST.get("received_date", "")
    received_date = parse_date(raw) if raw else None
    shipment.received_date = received_date
    shipment.updated_by = request.user
    shipment.updated_at = timezone.now()
    shipment.save(update_fields=["received_date", "updated_by", "updated_at"])
    messages.success(
        request,
        "Received date recorded."
        if received_date
        else "Received date cleared.",
    )
