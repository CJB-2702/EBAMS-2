"""The Receiving Loop — list / create / detail / edit, plus the
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
from app.procurement.control_layer.domain_structs.arrival_allocation import (
    allocated_by_purchase_order_line,
    unallocated_remainder,
)
from app.procurement.control_layer.domain_structs.package_reallocation_portal_struct import (
    PackageReallocationPortalStruct,
)
from app.procurement.control_layer.domain_structs.shipment_struct import (
    ShipmentDetailStruct,
    planning_lines_for_order,
)
from app.procurement.control_layer.errors import (
    PackageReallocationRequired,
    ProcurementValidationError,
)
from app.procurement.control_layer.factories.shipment_factory import ShipmentFactory
from app.procurement.control_layer.guards.package_reallocation_guard import (
    PackageReallocationValidator,
)
from app.procurement.control_layer.handlers.package_reallocation_waterfall_handler import (
    PackageReallocationWaterfallHandler,
)
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
    PurchaseOrderShipmentLink,
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
from app.procurement.presentation_layer.search.purchase_order_search import (
    PurchaseOrderSearch,
)
from app.procurement.presentation_layer.tools import basic_shipment_session as session_tool
from app.procurement.presentation_layer.tools import shipment_wizard_draft as wizard_draft
from app.procurement.presentation_layer.tools import package_reallocation_draft
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
    """Parse the repeated `line_part_id[]` / `line_quantity[]` inputs used by
    the create form.

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
# 3.2 shipment_create
# --------------------------------------------------------------------------- #


@require_http_methods(["GET", "POST"])
def shipment_create(request: HttpRequest) -> HttpResponse:
    """One route, vertical scroll, progressive enablement, session-backed draft
    — the create-PO wizard's mirror, one level down the chain.

    The PO wizard searches open PART DEMANDS and links them to the order lines
    it is building. This searches open PURCHASE ORDER LINES and links them to
    the arriving lines it is building. Same cards, same gates, same reason for
    the shape: the receiver is answering "what is in the box, and what does each
    of those things answer for", and both halves of that need the same screen.

    NOTHING TOUCHES THE DATABASE UNTIL FINAL SUBMIT. A half-built shipment in
    the database would show up in another receiver's queue, would count against
    its order lines, and would leave orphaned allocations when abandoned. Every
    POST below mutates `request.session` and redirects; only `_wizard_submit`
    writes.

    Copy-on-create still exists and is still the default — a line the receiver
    never allocates by hand is matched against the header PO's lines by part at
    commit, exactly as before. The wizard adds the ability to say otherwise
    BEFORE the record exists, instead of correcting a guess afterwards on the
    edit page.
    """
    if request.method == "GET":
        fmt = request.GET.get("format")
        if fmt == "htmx-search-results":
            return _part_search_fragment(request)
        # No `htmx-po-results` here: the primary order is card 2's own filtered
        # results table, not a typeahead. A dropdown cannot show the booking
        # date and line count the choice is actually made on.

    require_receive(request)
    domain_ids = accessible_domain_ids(request)

    if request.method == "POST":
        return _wizard_post(request, domain_ids=domain_ids)

    return _wizard_render(request, domain_ids=domain_ids)


def _wizard_render(request: HttpRequest, *, domain_ids: list[int]) -> HttpResponse:
    draft = wizard_draft.load(request.session)
    domain_context = _domain_choices(request)

    # A receiver with exactly one domain never gets asked, so nothing they do in
    # card 1 would otherwise establish the draft's home and card 2 would sit
    # locked behind a question that is not on the page. Seed it on first render
    # instead — the hidden input in card 1 says the same thing, but only once
    # something in that card has been touched.
    if (
        domain_context["single_domain"] is not None
        and not draft.get("domain_id")
        and not draft.get("purchase_order_id")
    ):
        draft["domain_id"] = domain_context["single_domain"].pk
        wizard_draft.save(request.session, draft)

    # `?purchase_order_id=` deep-links in from a PO's detail page. It seeds an
    # EMPTY draft's primary order and nothing more — a receiver mid-draft who
    # follows a stale link does not get their staged work silently repointed at
    # another order.
    #
    # "Empty" is measured on the primary order and the staged lines, NOT on
    # `has_header`: the auto-seeded domain above satisfies that for every
    # single-domain receiver, which would make this seeding dead code.
    deep_link_po = _int(request.GET.get("purchase_order_id"))
    if (
        deep_link_po is not None
        and not draft.get("purchase_order_id")
        and not draft.get("lines")
    ):
        if PurchaseOrder.objects.filter(
            pk=deep_link_po, domain_id__in=domain_ids, deleted_at__isnull=True
        ).exists():
            draft["purchase_order_id"] = deep_link_po
            wizard_draft.save(request.session, draft)

    purchase_order = None
    if draft.get("purchase_order_id"):
        purchase_order = (
            PurchaseOrder.objects.filter(
                pk=draft["purchase_order_id"], domain_id__in=domain_ids
            )
            .select_related("vendor", "domain")
            .first()
        )

    # Card 2's pool — the single-select primary-order picker. The receiver is
    # answering "which order is this box mostly against", so the filters are the
    # three things they can read off the box or the paperwork: who sent it, when
    # it was booked, and what part is inside.
    po_pool_filters = {
        "q": request.GET.get("po_q", "").strip(),
        "vendor_id": _int(request.GET.get("po_vendor_id")),
        "part_number": request.GET.get("po_part_number", "").strip(),
        "date_from": request.GET.get("po_date_from", "").strip(),
        "date_to": request.GET.get("po_date_to", "").strip(),
    }

    po_pool = []
    if wizard_draft.has_header(draft):
        po_pool = list(
            PurchaseOrderSearch.attachable_pool(
                domain_ids=domain_ids,
                statuses=ATTACHABLE_PO_STATUSES,
                q=po_pool_filters["q"],
                vendor_id=po_pool_filters["vendor_id"],
                part_number=po_pool_filters["part_number"],
                date_from=(
                    parse_date(po_pool_filters["date_from"])
                    if po_pool_filters["date_from"]
                    else None
                ),
                date_to=(
                    parse_date(po_pool_filters["date_to"])
                    if po_pool_filters["date_to"]
                    else None
                ),
            )[:50]
        )

    # Card 3's pool — cross-part, server-filtered, because the systemwide open
    # order-line pool runs into the hundreds. The per-line pools below it are
    # part-scoped (tens of rows) and ship whole.
    pool_filters = {
        "q": request.GET.get("pool_q", "").strip(),
        "vendor_id": _int(request.GET.get("pool_vendor_id")),
        # Default ON, but only until the filter bar has been used: a receiver
        # opening the wizard from a PO is almost always shipping against that
        # order. An unticked checkbox submits NOTHING, so defaulting on a bare
        # absence would make this one impossible to switch off — the filter
        # form stamps `pool_submitted` precisely so absence can be told apart
        # from never-asked.
        "this_po_only": (
            request.GET.get("pool_this_po_only") == "1"
            if request.GET.get("pool_submitted") == "1"
            else True
        ),
        "include_draft": request.GET.get("pool_include_draft") == "1",
        "show_satisfied": request.GET.get("pool_show_satisfied") == "1",
    }

    po_line_pool = []
    if wizard_draft.has_header(draft):
        po_line_pool = list(
            PurchaseOrderLineSearch.pool(
                domain_ids=domain_ids,
                q=pool_filters["q"],
                vendor_id=pool_filters["vendor_id"],
                purchase_order_id=(
                    purchase_order.pk
                    if purchase_order and pool_filters["this_po_only"]
                    else None
                ),
                include_draft=pool_filters["include_draft"],
                outstanding_only=not pool_filters["show_satisfied"],
            )[:100]
        )

    lines = _draft_line_views(
        draft, domain_ids=domain_ids, include_draft=pool_filters["include_draft"]
    )

    return render(
        request,
        f"{TEMPLATE_DIR}/create.html",
        {
            "draft": draft,
            "purchase_order": purchase_order,
            "lines": lines,
            "po_pool": po_pool,
            "po_pool_filters": po_pool_filters,
            "po_line_pool": po_line_pool,
            "pool_filters": pool_filters,
            "vendors": Vendor.objects.filter(is_active=True).order_by("name"),
            "has_header": wizard_draft.has_header(draft),
            "has_lines": wizard_draft.has_lines(draft),
            "can_submit": wizard_draft.can_submit(draft),
            "unallocated_line_count": sum(
                1 for line in lines if line["unallocated"] > 0
            ),
            **domain_context,
        },
    )


def _draft_line_views(
    draft: dict, *, domain_ids: list[int], include_draft: bool
) -> list[dict]:
    """Hydrate each staged line into something a template can render.

    Parts and PO lines are fetched in two queries for the whole card stack, and
    each line's candidate pool in one query per distinct part — never one per
    line. The same batching rule the PO wizard's equivalent follows, for the
    same reason.
    """
    lines = draft.get("lines") or []
    if not lines:
        return []

    part_ids = [int(line["part_id"]) for line in lines]
    parts_by_id = {p.pk: p for p in Part.objects.filter(pk__in=part_ids)}

    po_line_ids = [
        int(allocation["purchase_order_line_id"])
        for line in lines
        for allocation in (line.get("allocations") or [])
    ]
    po_lines_by_id = {
        po_line.pk: po_line
        for po_line in PurchaseOrderLine.objects.filter(
            pk__in=po_line_ids
        ).select_related("purchase_order", "purchase_order__vendor")
    }

    pools_by_part: dict[int, list] = {}
    for part_id in set(part_ids):
        pools_by_part[part_id] = list(
            PurchaseOrderLineSearch.candidates_for_arriving_part(
                part_id=part_id, include_draft=include_draft
            ).filter(purchase_order__domain_id__in=domain_ids)[:50]
        )

    views = []
    for index, line in enumerate(lines):
        part_id = int(line["part_id"])
        quantity = wizard_draft.to_decimal(line["quantity"]) or Decimal("0")
        allocated = wizard_draft.allocated_total(line)
        allocations = []
        for allocation in line.get("allocations") or []:
            po_line_id = int(allocation["purchase_order_line_id"])
            allocations.append(
                {
                    "purchase_order_line_id": po_line_id,
                    "purchase_order_line": po_lines_by_id.get(po_line_id),
                    "quantity_allocated": wizard_draft.to_decimal(
                        allocation["quantity_allocated"]
                    ),
                }
            )
        allocated_ids = {a["purchase_order_line_id"] for a in allocations}
        views.append(
            {
                "index": index,
                "part": parts_by_id.get(part_id),
                "quantity": quantity,
                "notes": line.get("notes") or "",
                "allocations": allocations,
                "allocated_total": allocated,
                "unallocated": quantity - allocated,
                # Order lines already picked drop out of the pool; allocating a
                # different amount means editing the existing pick, never
                # adding a second — the unique constraint says so.
                "pool": [
                    candidate
                    for candidate in pools_by_part.get(part_id, [])
                    if candidate.pk not in allocated_ids
                ],
            }
        )
    return views


# --------------------------------------------------------------------------- #
# 3.2b  the wizard's POST actions — session only, except `submit`
# --------------------------------------------------------------------------- #


def _wizard_post(request: HttpRequest, *, domain_ids: list[int]) -> HttpResponse:
    action = request.POST.get("action", "")
    draft = wizard_draft.load(request.session)
    back = reverse("shipment_create")

    if action == "clear":
        wizard_draft.clear(request.session)
        messages.info(request, "Draft shipment discarded.")
        return redirect(back)

    if action == "save_header":
        _wizard_save_header(request, draft, domain_ids=domain_ids)
        wizard_draft.save(request.session, draft)
        return redirect(back)

    # Card 2's two actions run BEFORE the header gate, because picking a primary
    # order is itself one of the two ways to give the draft a home — a receiver
    # who arrives by deep link and never touches card 1 must still get through.
    if action == "select_po":
        _wizard_select_po(request, draft, domain_ids=domain_ids)
        wizard_draft.save(request.session, draft)
        return redirect(back)

    if action == "clear_po":
        draft["purchase_order_id"] = None
        wizard_draft.save(request.session, draft)
        messages.info(
            request,
            "Primary order cleared. Anything already in the box keeps the order "
            "lines it was allocated to.",
        )
        return redirect(back)

    if not wizard_draft.has_header(draft):
        messages.error(
            request,
            "Pick a purchase order, or a domain if there is no order yet — a "
            "shipment always belongs to one.",
        )
        return redirect(back)

    if action == "add_unlinked_line":
        _wizard_add_unlinked_line(request, draft)
    elif action == "add_from_po_lines":
        _wizard_add_from_po_lines(request, draft, domain_ids=domain_ids)
    elif action == "remove_line":
        if wizard_draft.remove_line(draft, _int(request.POST.get("line_index")) or -1):
            messages.info(request, "Line removed from the draft.")
    elif action == "edit_line":
        _wizard_edit_line(request, draft)
    elif action == "allocate":
        _wizard_allocate(request, draft, domain_ids=domain_ids)
    elif action == "remove_allocation":
        line = wizard_draft.line_at(draft, _int(request.POST.get("line_index")) or -1)
        po_line_id = _int(request.POST.get("purchase_order_line_id"))
        if line and po_line_id and wizard_draft.remove_allocation(
            line, purchase_order_line_id=po_line_id
        ):
            messages.info(request, "Allocation removed from the draft.")
    elif action == "submit":
        return _wizard_submit(request, draft, domain_ids=domain_ids)
    else:
        messages.error(request, "Unrecognised wizard action.")

    wizard_draft.save(request.session, draft)
    return redirect(back)


def _wizard_save_header(
    request: HttpRequest, draft: dict, *, domain_ids: list[int]
) -> None:
    """Card 1's autosave, fired by `hx-trigger="change"`. Partial state is
    expected and not an error — a receiver who has only typed a tracking number
    so far still gets that saved.

    The domain fence is the one real validation: it guards a write, not a read.
    An order supplies its own domain, so an explicit domain only matters while
    there is no order.
    """
    # The primary order moved to card 2 and this card no longer submits it, so
    # the key is ABSENT rather than blank on every card-1 autosave. Writing an
    # unconditional `None` here would silently drop the chosen order the moment
    # somebody corrected the carrier. It is still honoured when posted, which is
    # what the reactive path and the wizard's own tests do.
    if "purchase_order_id" in request.POST:
        po_id = _int(request.POST.get("purchase_order_id"))
        if po_id is not None and not PurchaseOrder.objects.filter(
            pk=po_id, domain_id__in=domain_ids, deleted_at__isnull=True
        ).exists():
            messages.error(
                request, "That purchase order is not one you have access to."
            )
            po_id = None
        draft["purchase_order_id"] = po_id

    domain_id = _int(request.POST.get("domain_id"))
    if domain_id is not None and domain_id not in domain_ids:
        messages.error(request, "Choose a domain you have access to.")
        domain_id = None

    draft["domain_id"] = domain_id
    draft["shipment_id"] = request.POST.get("shipment_id", "").strip()
    draft["carrier"] = request.POST.get("carrier", "").strip()
    draft["shipped_date"] = request.POST.get("shipped_date") or None
    draft["expected_arrival_date"] = request.POST.get("expected_arrival_date") or None
    draft["notes"] = request.POST.get("notes", "").strip()


def _wizard_select_po(
    request: HttpRequest, draft: dict, *, domain_ids: list[int]
) -> None:
    """Card 2 — the primary order, single-select, with two ways to take it.

    SINGLE-SELECT IS THE POINT. A shipment has exactly one primary order: the
    one whose paperwork came with the box, whose domain the shipment inherits,
    and whose lines copy-on-create matches against. That is a different question
    from "which order lines does this box answer for", which card 3 answers and
    which genuinely spans several orders. Collapsing the two would lose the only
    field that can be copied from — hence a radio, not a checkbox.

    The two buttons are the two real intents, both common enough to deserve
    their own control rather than a checkbox nobody reads:

    * **Copy all lines** — the box is this order, arriving as booked. The
      receiver corrects quantities afterwards instead of re-typing the order.
    * **Primary only** — this order is the box's home, but what is inside is not
      its line list: a partial delivery of two of twelve lines, or material that
      mostly answers to somebody else's order.
    """
    po_id = _int(request.POST.get("primary_purchase_order_id"))
    if po_id is None:
        messages.error(request, "Choose a purchase order first.")
        return

    purchase_order = (
        PurchaseOrder.objects.filter(
            pk=po_id, domain_id__in=domain_ids, deleted_at__isnull=True
        )
        .select_related("vendor")
        .first()
    )
    if purchase_order is None:
        messages.error(request, "That purchase order is not one you have access to.")
        return

    draft["purchase_order_id"] = purchase_order.pk

    if request.POST.get("copy_lines") != "1":
        messages.success(
            request,
            f"{purchase_order.po_number} is this shipment's primary order. Nothing "
            f"was copied — add what is actually in the box below.",
        )
        return

    added, skipped = _copy_po_lines_into_draft(
        draft, purchase_order=purchase_order, domain_ids=domain_ids
    )
    plural = "" if added == 1 else "s"
    if added:
        messages.success(
            request,
            f"{purchase_order.po_number} is this shipment's primary order — "
            f"{added} open line{plural} copied into the box and pre-allocated. "
            f"Correct any quantity the box disagrees with.",
        )
    elif skipped:
        messages.info(
            request,
            f"{purchase_order.po_number} is this shipment's primary order. Its "
            f"{skipped} open line{'s are' if skipped != 1 else ' is'} already in the "
            f"box, so nothing was copied — copying twice would have doubled the "
            f"quantities.",
        )
    else:
        messages.warning(
            request,
            f"{purchase_order.po_number} is this shipment's primary order, but it "
            f"has no open lines left to copy. Add what is in the box below.",
        )
    if added and skipped:
        messages.info(
            request,
            f"{skipped} further line{'s were' if skipped != 1 else ' was'} already "
            f"in the box and left alone.",
        )


def _copy_po_lines_into_draft(
    draft: dict, *, purchase_order: PurchaseOrder, domain_ids: list[int]
) -> tuple[int, int]:
    """Stage every still-outstanding line of the order at its outstanding
    quantity. Returns `(added, skipped)`.

    Lines this draft already carries an allocation for are SKIPPED, not grown.
    Pressing "copy all lines" a second time — after a mis-click, or after
    switching orders and switching back — is a repeat of the same statement, not
    a second delivery, and growing the box for it would be silently wrong. The
    explicit per-line pick in card 3 keeps its additive behaviour, because there
    the receiver is naming a quantity each time.
    """
    added = 0
    skipped = 0
    for po_line in PurchaseOrderLineSearch.pool(
        domain_ids=domain_ids,
        purchase_order_id=purchase_order.pk,
        include_draft=True,
        outstanding_only=True,
    ):
        if wizard_draft.staged_for_purchase_order_line(
            draft, purchase_order_line_id=po_line.pk
        ) > 0:
            skipped += 1
            continue
        _stage_po_line(draft, po_line=po_line, quantity=po_line.outstanding_qty)
        added += 1
    return added, skipped


def _stage_po_line(draft: dict, *, po_line: PurchaseOrderLine, quantity) -> None:
    """Put `quantity` of an order line's part in the box and allocate exactly
    that much back to the order line.

    One physical line per part: a part arriving against two different orders is
    ONE line with TWO allocations, never two lines. The link table exists to say
    that (D90). Growing the line by exactly what is being allocated keeps the
    arriving quantity and its allocations consistent by construction, so this
    path can never breach the line's own cap.
    """
    index = wizard_draft.find_line_for_part(draft, po_line.part_id)
    if index is None:
        draft["lines"].append(
            wizard_draft.new_line(part_id=po_line.part_id, quantity=quantity)
        )
        index = len(draft["lines"]) - 1
    else:
        line = draft["lines"][index]
        previous = wizard_draft.to_decimal(line["quantity"]) or Decimal("0")
        line["quantity"] = str(previous + quantity)

    wizard_draft.set_allocation(
        draft["lines"][index],
        purchase_order_line_id=po_line.pk,
        quantity=quantity,
    )


def _wizard_add_unlinked_line(request: HttpRequest, draft: dict) -> None:
    """The Unlinked tab. A line answering no order line is valid and this is the
    intended path for it — a vendor substitution, a bonus item, or a box whose
    paperwork has not caught up. Dropping it would be the only genuinely wrong
    answer."""
    part_id = _int(request.POST.get("part_id"))
    quantity = _decimal(request.POST.get("quantity"))

    problems = []
    if not part_id or not Part.objects.filter(pk=part_id).exists():
        problems.append("Choose a part.")
    if quantity is None or quantity <= 0:
        problems.append("Shipped quantity must be greater than zero.")
    if problems:
        for problem in problems:
            messages.error(request, problem)
        return

    existing_index = wizard_draft.find_line_for_part(draft, part_id)
    if existing_index is not None:
        # One physical line per part in the box. A part arriving against two
        # different orders is ONE line with TWO allocations, not two lines —
        # that distinction is the whole point of the link table (D90).
        line = draft["lines"][existing_index]
        previous = wizard_draft.to_decimal(line["quantity"]) or Decimal("0")
        line["quantity"] = str(previous + quantity)
        messages.info(
            request,
            f"That part is already on line {existing_index + 1} — its quantity grew "
            f"to {line['quantity']} instead of opening a second line.",
        )
        return

    draft["lines"].append(
        wizard_draft.new_line(
            part_id=part_id,
            quantity=quantity,
            notes=request.POST.get("line_notes", "").strip(),
        )
    )
    messages.success(request, "Line added to the draft.")


def _wizard_add_from_po_lines(
    request: HttpRequest, draft: dict, *, domain_ids: list[int]
) -> None:
    """The From-order-lines tab — the exact counterpart of the PO wizard's
    From-demands tab.

    Picking an order line both creates/grows that part's arriving line AND
    pre-allocates exactly that quantity against the order line. The receiver
    does not re-pick it downstream; they only correct the quantity if the box
    disagrees with the paperwork.
    """
    po_line_ids = [
        value
        for value in (_int(raw) for raw in request.POST.getlist("po_line_ids"))
        if value
    ]
    if not po_line_ids:
        messages.error(request, "Select at least one order line.")
        return

    po_lines = list(
        PurchaseOrderLineSearch.pool(
            domain_ids=domain_ids, include_draft=True, outstanding_only=False
        ).filter(pk__in=po_line_ids)
    )
    if not po_lines:
        messages.error(request, "None of those order lines are in your domains.")
        return

    added = 0
    for po_line in po_lines:
        quantity = _decimal(request.POST.get(f"quantity_{po_line.pk}"))
        if quantity is None:
            quantity = po_line.outstanding_qty
        if quantity <= 0:
            messages.warning(
                request,
                f"{po_line.purchase_order.po_number} line {po_line.line_number} was "
                f"given no quantity — skipped.",
            )
            continue

        _stage_po_line(draft, po_line=po_line, quantity=quantity)
        added += 1

    if added:
        messages.success(
            request,
            f"{added} order line{'s' if added != 1 else ''} added to the draft and "
            f"pre-allocated.",
        )


def _wizard_edit_line(request: HttpRequest, draft: dict) -> None:
    """Card 3's per-line autosave — arriving quantity and notes, via
    `hx-trigger="change"`.

    A rejected edit leaves the line exactly as it was rather than half-applying
    the POST; the autosave has no undo. Reducing the quantity below what is
    already allocated is the one refusal here — it would put the line over its
    own cap, which `ShipmentLineValidator.check_allocation` would reject at
    commit anyway.
    """
    line_index = _int(request.POST.get("line_index"))
    line = wizard_draft.line_at(draft, line_index if line_index is not None else -1)
    if line is None:
        messages.error(request, "That draft line no longer exists.")
        return

    quantity = _decimal(request.POST.get("quantity"))
    if quantity is None or quantity <= 0:
        messages.error(request, "Shipped quantity must be greater than zero.")
        return

    allocated = wizard_draft.allocated_total(line)
    if quantity < allocated:
        messages.error(
            request,
            f"{allocated} of this line is already allocated to order lines — it "
            f"cannot arrive as only {quantity}. Release an allocation first.",
        )
        return

    line["quantity"] = str(quantity)
    line["notes"] = request.POST.get("line_notes", "").strip()


def _wizard_allocate(
    request: HttpRequest, draft: dict, *, domain_ids: list[int]
) -> None:
    """Card 3's per-pick allocation — the mirror of the PO wizard's demand
    allocation, with the cap running the other way.

    On the demand side the cap is on the TARGET (a demand cannot be
    over-claimed) and exceeding it opens a decision dialog. Here the cap is on
    the SOURCE: the arriving line's allocations may not total more than what
    physically arrived, and that one blocks flat — a claim that more of a box
    was assigned than was in the box is not a business event anybody needs to
    approve.

    Over-RECEIPT against the order line is the opposite case and stays legal:
    vendors over-ship, and the honest record says so. It only warns.
    """
    line_index = _int(request.POST.get("line_index"))
    line = wizard_draft.line_at(draft, line_index if line_index is not None else -1)
    po_line_id = _int(request.POST.get("purchase_order_line_id"))
    quantity = _decimal(request.POST.get("quantity"))

    if line is None or not po_line_id:
        messages.error(request, "That draft line no longer exists.")
        return

    po_line = (
        PurchaseOrderLine.objects.filter(
            pk=po_line_id,
            deleted_at__isnull=True,
            purchase_order__domain_id__in=domain_ids,
        )
        .select_related("purchase_order")
        .first()
    )
    if po_line is None:
        messages.error(request, "Choose an order line you have access to.")
        return
    if po_line.part_id != int(line["part_id"]):
        messages.error(
            request,
            f"{po_line.purchase_order.po_number} line {po_line.line_number} buys a "
            f"different part than this line. Allocations must match on part.",
        )
        return

    headroom = (
        wizard_draft.to_decimal(line["quantity"]) or Decimal("0")
    ) - wizard_draft.allocated_total(line, skip_purchase_order_line_id=po_line_id)
    if quantity is None:
        # Blank means "everything still unallocated" — the one-box-one-order
        # case, and the overwhelming majority of picks.
        quantity = headroom
    if quantity <= 0:
        messages.error(request, "Allocated quantity must be greater than zero.")
        return
    if quantity > headroom:
        messages.error(
            request,
            f"Cannot allocate {quantity} — only {headroom} of this arriving line's "
            f"{line['quantity']} is still unallocated.",
        )
        return

    wizard_draft.set_allocation(
        line, purchase_order_line_id=po_line.pk, quantity=quantity
    )

    outstanding = _po_line_outstanding(po_line) - wizard_draft.staged_for_purchase_order_line(
        draft, purchase_order_line_id=po_line.pk, skip_line_index=line_index
    )
    target = f"{po_line.purchase_order.po_number} line {po_line.line_number}"
    if quantity > outstanding:
        messages.warning(
            request,
            f"Allocated {quantity} to {target}, which is more than the {outstanding} "
            f"still outstanding on it. Recorded as-is — vendors over-ship, and the "
            f"honest record says so.",
        )
    else:
        messages.success(request, f"Allocated {quantity} to {target}.")


def _po_line_outstanding(po_line: PurchaseOrderLine) -> Decimal:
    """This line's outstanding balance against already-committed allocations.

    `PurchaseOrderLineSearch` annotates this for rows it fetched; a line loaded
    directly has to compute it, and both must mean the same thing — allocated,
    never accepted (D90).
    """
    allocated = allocated_by_purchase_order_line(
        purchase_order_line_ids=[po_line.pk]
    ).get(po_line.pk, Decimal("0"))
    return po_line.quantity_ordered - allocated


def _wizard_submit(
    request: HttpRequest, draft: dict, *, domain_ids: list[int]
) -> HttpResponse:
    """The only write in the wizard. One transaction; if any step fails, no
    shipment exists.

    Lines carrying staged allocations suppress copy-on-create and get exactly
    what was staged. Lines carrying none still get copy-on-create against the
    header order, so a receiver who never opened card 3 lands in precisely the
    behaviour the old flat form gave them.
    """
    back = reverse("shipment_create")

    purchase_order = None
    if draft.get("purchase_order_id"):
        purchase_order = PurchaseOrder.objects.filter(
            pk=draft["purchase_order_id"],
            domain_id__in=domain_ids,
            deleted_at__isnull=True,
        ).select_related("domain").first()
        if purchase_order is None:
            messages.error(
                request, "That purchase order is not one you have access to."
            )
            return redirect(back)

    domain = purchase_order.domain if purchase_order else None
    if domain is None:
        domain_id = draft.get("domain_id")
        if domain_id in domain_ids:
            domain = Domain.objects.filter(pk=domain_id).first()
    if domain is None:
        messages.error(
            request,
            "Choose a domain — a shipment always belongs to one, even before its "
            "purchase order does.",
        )
        return redirect(back)

    draft_lines = draft.get("lines") or []
    if not draft_lines:
        messages.error(request, "Add at least one line before saving.")
        return redirect(back)

    po_line_ids = [
        int(allocation["purchase_order_line_id"])
        for line in draft_lines
        for allocation in (line.get("allocations") or [])
    ]
    po_lines_by_id = {
        po_line.pk: po_line
        for po_line in PurchaseOrderLine.objects.filter(
            pk__in=po_line_ids,
            deleted_at__isnull=True,
            purchase_order__domain_id__in=domain_ids,
        ).select_related("purchase_order")
    }

    rows = []
    for line in draft_lines:
        quantity = wizard_draft.to_decimal(line.get("quantity"))
        if quantity is None or quantity <= 0:
            messages.error(request, "Every line needs a quantity greater than zero.")
            return redirect(back)

        allocations = []
        for allocation in line.get("allocations") or []:
            po_line = po_lines_by_id.get(int(allocation["purchase_order_line_id"]))
            if po_line is None:
                messages.error(
                    request,
                    "One of the order lines in this draft no longer exists or is no "
                    "longer in your domains. Remove that allocation and try again.",
                )
                return redirect(back)
            allocations.append(
                {
                    "purchase_order_line": po_line,
                    "quantity": wizard_draft.to_decimal(
                        allocation["quantity_allocated"]
                    ),
                }
            )

        rows.append(
            {
                "part_id": int(line["part_id"]),
                "quantity": quantity,
                "allocations": allocations,
            }
        )

    try:
        shipment = ShipmentFactory.create(
            domain=domain,
            purchase_order=purchase_order,
            lines=rows,
            actor=request.user,
            shipment_id=(draft.get("shipment_id") or "").strip(),
            carrier=(draft.get("carrier") or "").strip(),
            shipped_date=parse_date(draft.get("shipped_date") or ""),
            expected_arrival_date=parse_date(draft.get("expected_arrival_date") or ""),
            notes=(draft.get("notes") or "").strip(),
        )
    except ProcurementValidationError as exc:
        _report(request, exc)
        return redirect(back)

    wizard_draft.clear(request.session)
    messages.success(
        request,
        f"Shipment {shipment.shipment_number} recorded with {len(rows)} line(s).",
    )
    return redirect(reverse("shipment_detail", kwargs={"pk": shipment.pk}))


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

    # D85 — a graph (D79-D82) lives on each ShipmentLine's own graph_id, not
    # on the Shipment header, since a shipment's lines are not guaranteed to
    # share one connected component. Distinct, non-null graph ids across this
    # shipment's active lines, so the sidebar can link to each one (usually
    # just one).
    graph_ids = sorted(
        gid
        for gid in ShipmentLine.objects.filter(
            shipment=shipment, deleted_at__isnull=True
        )
        .values_list("graph_id", flat=True)
        .distinct()
        if gid is not None
    )

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
            "graph_ids": graph_ids,
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

    # An active Package Reallocation draft pins the page to its own line — the
    # Portal must never be silently lost behind a different selection
    # (reallocation_resolution_portal.md §5: commit is BLOCKED until the
    # shortfall is resolved). Package↔PO Domain only; no read of the
    # Demand↔PO Domain's own draft here (§7.7).
    package_draft = package_reallocation_draft.load(request.session)
    if package_draft is not None and selected_line_id != package_draft.get(
        "shipment_line_id"
    ):
        selected_line_id = package_draft.get("shipment_line_id")

    selected = next(
        (line for line in detail.lines if line.line_id == selected_line_id), None
    )

    package_portal = None
    package_new_quantity = Decimal("0")
    package_proposed: dict[int, Decimal] = {}
    package_pending_unlock_link_id = None
    package_running_total = Decimal("0")
    if package_draft is not None and selected is not None:
        package_portal = PackageReallocationPortalStruct.load(
            shipment_line_id=selected.line_id
        )
        package_new_quantity = (
            package_reallocation_draft.to_decimal(package_draft.get("new_quantity"))
            or Decimal("0")
        )
        package_proposed = package_reallocation_draft.proposed_values(package_draft)
        package_pending_unlock_link_id = package_draft.get("pending_unlock_link_id")
        # The running total shown to the user must reflect what COMMIT would
        # actually write — staged/proposed values for open claims, falling
        # back to their current DB value for anything not yet touched — not
        # just the struct's own open_total, which is always the live DB state
        # (§10 point 3) and would otherwise look stale the moment the user
        # auto-allocates or manually edits a claim without yet committing.
        package_running_total = package_portal.locked_total + sum(
            (
                package_proposed.get(claim.link_id, claim.quantity_allocated)
                for claim in package_portal.open_claims
            ),
            Decimal("0"),
        )

    # The right column's search tool, top-bottom: a filter bar over a results
    # list, each row carrying its own Allocate action. The PO sector's Edit &
    # Linkage draws its demand search exactly this way, and this is the same
    # job pointing the other direction.
    search_filters = {
        "q": request.GET.get("q", "").strip(),
        "include_draft": request.GET.get("include_draft") == "1",
        "vendor_scope": request.GET.get("vendor_scope", "any"),
    }

    candidates = []
    if selected is not None:
        vendor_id = None
        if search_filters["vendor_scope"] == "header" and shipment.purchase_order_id:
            vendor_id = shipment.purchase_order.vendor_id
        candidates = list(
            PurchaseOrderLineSearch.candidates_for_arriving_part(
                part_id=selected.part_id,
                vendor_id=vendor_id,
                include_draft=search_filters["include_draft"],
                q=search_filters["q"],
            ).filter(purchase_order__domain_id__in=accessible_domain_ids(request))[:50]
        )

    # The current-allocations table wants each target's ordered quantity and
    # vendor, which the struct's allocation slice does not carry — it holds
    # attribution, not commercial terms. One query for the selected line's
    # targets, never one per allocation.
    allocation_targets = {}
    if selected is not None:
        allocation_targets = {
            po_line.pk: po_line
            for po_line in PurchaseOrderLine.objects.filter(
                pk__in=[a.purchase_order_line_id for a in selected.allocations]
            ).select_related("purchase_order", "purchase_order__vendor")
        }

    return render(
        request,
        f"{TEMPLATE_DIR}/edit.html",
        {
            "shipment": shipment,
            "detail": detail,
            "selected": selected,
            "selected_line_id": selected_line_id,
            "candidates": candidates,
            "allocation_targets": allocation_targets,
            "search_filters": search_filters,
            # Every mutation on a delivered shipment costs a mandatory
            # comment. The template turns this into a required textarea in each
            # confirmation popup rather than discovering it on submit.
            "requires_audit_comment": context.requires_audit_comment,
            "can_receive": can_receive(request),
            "package_portal": package_portal,
            "package_new_quantity": package_new_quantity,
            "package_proposed": package_proposed,
            "package_pending_unlock_link_id": package_pending_unlock_link_id,
            "package_running_total": package_running_total,
        },
    )


def _edit_post(request: HttpRequest, shipment: Shipment) -> HttpResponse:
    require_receive(request)
    action = request.POST.get("action", "")
    context = ShipmentContext(shipment.pk)

    # Preserve the selected line across the redirect so a save does not dump the
    # receiver back to "nothing selected" halfway through an allocation session.
    # `line_id` is the ACTION'S TARGET and only appears on forms that have one;
    # `selected_line_id` is the page state the header and add-line forms carry.
    # Merging them is safe for the redirect and nothing else reads this value.
    line_id = _int(request.POST.get("line_id")) or _int(
        request.POST.get("selected_line_id")
    )
    back = reverse("shipment_edit", kwargs={"pk": shipment.pk})
    # A deleted line cannot be re-selected — the redirect drops it rather than
    # landing on a selection that 404s out of the detail struct.
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
            _release_allocation(request, shipment, context, audit_comment)

        elif action == "edit_quantity":
            _edit_shipped_quantity(request, shipment, context, audit_comment)

        elif action == "reallocation_auto_allocate":
            _package_reallocation_auto_allocate(request, shipment)

        elif action == "reallocation_manual_entry":
            _package_reallocation_manual_entry(request, shipment)

        elif action == "reallocation_unlock_claim":
            _package_reallocation_unlock_claim(request, shipment, context)

        elif action == "reallocation_cancel_unlock":
            _package_reallocation_cancel_unlock(request, shipment)

        elif action == "reallocation_commit":
            _package_reallocation_commit(request, shipment, context)

        elif action == "reallocation_cancel":
            package_reallocation_draft.clear(request.session)
            messages.info(request, "Reallocation cancelled; the line was not changed.")

        elif action == "delete_line":
            _delete_line(request, shipment, context, audit_comment)

        elif action == "delete_shipment":
            return _delete_shipment(request, shipment, context)

        else:
            messages.error(request, "Unrecognised action.")

    except ProcurementValidationError as exc:
        _report(request, exc)

    return redirect(back)


def _edit_shipped_quantity(
    request: HttpRequest, shipment: Shipment, context: ShipmentContext, audit_comment: str
) -> None:
    line = _line_on_shipment(shipment, _int(request.POST.get("line_id")))
    if line is None:
        messages.error(request, "That line is not on this shipment.")
        return
    new_quantity = _decimal(request.POST.get("quantity"))
    if new_quantity is None or new_quantity <= 0:
        messages.error(request, "Shipped quantity must be greater than zero.")
        return

    try:
        context.edit_quantity(
            line=line, new_quantity=new_quantity, actor=request.user, audit_comment=audit_comment
        )
        messages.success(request, f"{line.part.part_number}: shipped quantity updated.")
    except PackageReallocationRequired as exc:
        # Phase 5's mirror of the Demand↔PO Domain's ReallocationRequired
        # handling: nothing was saved. Seed the Package Portal's session
        # draft instead of a flat error.
        draft = package_reallocation_draft.empty_draft(
            shipment_line_id=line.pk, new_quantity=new_quantity
        )
        package_reallocation_draft.save(request.session, draft)
        messages.warning(
            request,
            f"{exc.errors[0]} Resolve it through the Reallocation Portal for "
            f"this line.",
        )


# ---------------------------------------------------------------------- #
# Package Reallocation Portal (Package↔PO Domain, Phase 5) — backend actions
# against the session-backed draft in package_reallocation_draft.py. No
# template this session; a later frontend build renders the Portal itself.
# Independent of the Demand↔PO Domain's equivalents — no shared state.
# ---------------------------------------------------------------------- #


def _load_package_reallocation_line(
    request: HttpRequest, shipment: Shipment
) -> tuple[dict | None, ShipmentLine | None]:
    draft = package_reallocation_draft.load(request.session)
    if draft is None:
        messages.error(request, "No reallocation is in progress for this shipment.")
        return None, None
    line = _line_on_shipment(shipment, draft.get("shipment_line_id"))
    if line is None:
        package_reallocation_draft.clear(request.session)
        messages.error(request, "That line is not on this shipment.")
        return None, None
    return draft, line


def _package_open_claims(line: ShipmentLine) -> list[PurchaseOrderShipmentLink]:
    return list(
        PurchaseOrderShipmentLink.objects.filter(
            shipment_line=line, deleted_at__isnull=True, is_locked=False
        ).select_related("purchase_order_line")
    )


def _package_locked_claims(line: ShipmentLine) -> list[PurchaseOrderShipmentLink]:
    return list(
        PurchaseOrderShipmentLink.objects.filter(
            shipment_line=line, deleted_at__isnull=True, is_locked=True
        )
    )


def _package_reallocation_auto_allocate(request: HttpRequest, shipment: Shipment) -> None:
    draft, line = _load_package_reallocation_line(request, shipment)
    if line is None:
        return
    new_qty = package_reallocation_draft.to_decimal(draft["new_quantity"]) or Decimal("0")
    open_claims = _package_open_claims(line)
    locked_total = sum((c.quantity_allocated for c in _package_locked_claims(line)), Decimal("0"))
    open_total = sum((c.quantity_allocated for c in open_claims), Decimal("0"))
    shortfall = max(Decimal("0"), (open_total + locked_total) - new_qty)

    resolutions = PackageReallocationWaterfallHandler.allocate(
        open_claims=open_claims, shortfall=shortfall
    )
    for link_id, qty in resolutions.items():
        package_reallocation_draft.set_proposed(draft, link_id=link_id, quantity=qty)
    package_reallocation_draft.save(request.session, draft)
    messages.success(request, "Auto-allocate applied. Review and commit to save.")


def _package_reallocation_manual_entry(request: HttpRequest, shipment: Shipment) -> None:
    draft, line = _load_package_reallocation_line(request, shipment)
    if line is None:
        return
    new_qty = package_reallocation_draft.to_decimal(draft["new_quantity"]) or Decimal("0")
    open_claim_ids = {c.pk for c in _package_open_claims(line)}
    locked_total = sum((c.quantity_allocated for c in _package_locked_claims(line)), Decimal("0"))

    values: dict[int, Decimal] = {}
    for link_id in open_claim_ids:
        raw = request.POST.get(f"claim_{link_id}")
        if raw is None:
            continue
        parsed = _decimal(raw)
        if parsed is not None:
            values[link_id] = parsed

    PackageReallocationValidator.check_manual_entry(
        values=values, locked_total=locked_total, new_source_qty=new_qty
    )
    for link_id, qty in values.items():
        package_reallocation_draft.set_proposed(draft, link_id=link_id, quantity=qty)
    package_reallocation_draft.save(request.session, draft)
    messages.success(request, "Manual entry saved. Review and commit to save.")


def _package_reallocation_unlock_claim(
    request: HttpRequest, shipment: Shipment, context: ShipmentContext
) -> None:
    draft, line = _load_package_reallocation_line(request, shipment)
    if line is None:
        return
    link = PurchaseOrderShipmentLink.objects.filter(
        pk=_int(request.POST.get("link_id")),
        shipment_line=line,
        deleted_at__isnull=True,
        is_locked=True,
    ).select_related("shipment_line__shipment", "purchase_order_line").first()
    if link is None:
        messages.error(request, "That claim is not a locked claim on this line.")
        return

    if request.POST.get("confirmed") != "1":
        # First call of the two-popup contract (§6): write nothing, remember
        # which claim is pending so the second, explicit confirmation popup
        # survives the POST-redirect-GET round trip and reopens pointed at
        # the same claim (F5 rule) instead of losing the in-progress unlock.
        draft["pending_unlock_link_id"] = link.pk
        package_reallocation_draft.save(request.session, draft)
        messages.warning(
            request,
            f"Unlocking the claim to line {link.purchase_order_line.line_number} "
            f"forces this allocation out of its locked state and may cause "
            f"downstream errors or inconsistencies. Confirm to proceed.",
        )
        return

    context.unlock_claim(link=link, actor=request.user, confirmed=True)
    package_reallocation_draft.mark_unlocked(draft, link_id=link.pk)
    package_reallocation_draft.set_proposed(draft, link_id=link.pk, quantity=link.quantity_allocated)
    draft.pop("pending_unlock_link_id", None)
    package_reallocation_draft.save(request.session, draft)
    messages.success(request, "Claim unlocked.")


def _package_reallocation_cancel_unlock(request: HttpRequest, shipment: Shipment) -> None:
    """The second popup's Cancel — clears the pending confirmation without
    touching the claim's lock state or the rest of the draft. Distinct from
    `reallocation_cancel`, which discards the whole in-progress reallocation."""
    draft, line = _load_package_reallocation_line(request, shipment)
    if line is None:
        return
    draft.pop("pending_unlock_link_id", None)
    package_reallocation_draft.save(request.session, draft)


def _package_reallocation_commit(
    request: HttpRequest, shipment: Shipment, context: ShipmentContext
) -> None:
    draft, line = _load_package_reallocation_line(request, shipment)
    if line is None:
        return
    new_qty = package_reallocation_draft.to_decimal(draft["new_quantity"]) or Decimal("0")
    proposed = package_reallocation_draft.proposed_values(draft)
    open_claims = {c.pk: c for c in _package_open_claims(line)}
    locked_total = sum((c.quantity_allocated for c in _package_locked_claims(line)), Decimal("0"))

    resolutions = {
        link_id: proposed.get(link_id, claim.quantity_allocated)
        for link_id, claim in open_claims.items()
    }
    open_total = sum(resolutions.values(), Decimal("0"))

    PackageReallocationValidator.check_commit_ready(
        open_total=open_total, locked_total=locked_total, new_source_qty=new_qty
    )
    context.apply_reallocation(
        line=line, new_quantity=new_qty, resolutions=resolutions, actor=request.user
    )
    package_reallocation_draft.clear(request.session)
    messages.success(request, "Reallocation committed.")


def _line_on_shipment(shipment: Shipment, line_id: int | None) -> ShipmentLine | None:
    if line_id is None:
        return None
    return (
        ShipmentLine.objects.filter(
            pk=line_id, shipment=shipment, deleted_at__isnull=True
        )
        .select_related("part")
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
    """The right column's Allocate action.

    A blank quantity means "everything still unallocated"; a partial quantity
    allocates that much and leaves the rest as remainder. Either way it is one
    control-layer call (`ShipmentContext.assign_line`) — since D90 there is no
    split-vs-reassign branch for a view to get wrong.
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
        messages.error(request, "Allocated quantity must be greater than zero.")
        return

    link = context.assign_line(
        line=line,
        purchase_order_line=po_line,
        quantity=quantity,
        actor=request.user,
        audit_comment=audit_comment,
    )
    remainder = unallocated_remainder(shipment_line=line)
    target = f"{po_line.purchase_order.po_number} line {po_line.line_number}"
    if remainder > 0:
        messages.success(
            request,
            f"{link.quantity_allocated} of {line.part.part_number} allocated to "
            f"{target}. {remainder} of this line is still unallocated.",
        )
    else:
        messages.success(
            request,
            f"{line.part.part_number} fully allocated to {target}.",
        )


def _release_allocation(
    request: HttpRequest,
    shipment: Shipment,
    context: ShipmentContext,
    audit_comment: str,
) -> None:
    """Take one allocation back off an order line.

    Keyed by LINK id, not line id (D90). A line can hold several allocations,
    so "unassign this line" is no longer a well-formed instruction — the user
    picks which allocation to release.
    """
    link = (
        PurchaseOrderShipmentLink.objects.filter(
            pk=_int(request.POST.get("link_id")),
            shipment_line__shipment=shipment,
            shipment_line__deleted_at__isnull=True,
            deleted_at__isnull=True,
        )
        .select_related(
            "shipment_line__part", "purchase_order_line__purchase_order"
        )
        .first()
    )
    if link is None:
        messages.error(request, "That allocation is not on this shipment.")
        return

    part_number = link.shipment_line.part.part_number
    quantity = link.quantity_allocated
    po_line = link.purchase_order_line
    context.release_allocation(
        link=link, actor=request.user, audit_comment=audit_comment
    )
    messages.success(
        request,
        f"{quantity} x {part_number} released from "
        f"{po_line.purchase_order.po_number} line {po_line.line_number}. It still "
        f"counts as arrived — it just does not answer for any order line now.",
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
    vendor's shipping confirmation — not a receiver with a carton in hand
    logging what already arrived.

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
