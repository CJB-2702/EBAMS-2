"""The Buyer's four surfaces: create wizard, detail portal, index, Edit & Linkage.

D44 puts the highest-traffic screens in the application here. Four rules hold
across every view in this module and are not negotiable per-page:

1. **The F5 rule.** Every state is reachable by a plain GET of a URL. Every write
   is POST -> redirect -> GET. The wizard's staged state lives in the session, so
   refreshing mid-build restores it rather than losing it.
2. **The D5 fence.** Every queryset filters on `accessible_domain_ids(request)`.
   A record outside the fence still renders where it is referenced — as plain
   text, with no link through (Phase 0 §5) — but is never listed or reachable.
3. **The permission gates (D2/D3).** `buy` gates create, edit, line editing,
   allocation, de-linking, submit-for-approval, place and cancel;
   `purchase_approve` gates approve/deny alone. D2's old clause letting an
   approve-only holder place an order is retired.
4. **One read per page.** `PurchaseOrderFulfillmentStruct` answers the whole
   detail page. Never a query per line, never a query per row.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_http_methods

from app.administration.models import Domain
from app.parts.models import Part
from app.procurement.control_layer.adapters.purchase_order_draft_adaptor import (
    PurchaseOrderDraftAdaptor,
)
from app.procurement.control_layer.domain_structs.demand_external_claims_struct import (
    DemandExternalClaimsStruct,
)
from app.procurement.control_layer.domain_structs.purchase_order_fulfillment_struct import (
    PurchaseOrderFulfillmentStruct,
)
from app.procurement.control_layer.domain_structs.reallocation_portal_struct import (
    ReallocationPortalStruct,
)
from app.procurement.control_layer.errors import (
    AllocationCapExceeded,
    CrossOrderAllocationExceeded,
    ProcurementValidationError,
    ReallocationRequired,
)
from app.procurement.control_layer.factories.purchase_order_factory import (
    PurchaseOrderFactory,
)
from app.procurement.control_layer.guards.reallocation_guard import ReallocationValidator
from app.procurement.control_layer.handlers.reallocation_waterfall_handler import (
    ReallocationWaterfallHandler,
)
from app.procurement.control_layer.policies.part_price_policy import PartPricePolicy
from app.procurement.control_layer.purchase_order_context import PurchaseOrderContext
from app.procurement.models import (
    DemandPriority,
    ShipmentLine,
    PartDemand,
    PurchaseOrder,
    PurchaseOrderDemandLink,
    PurchaseOrderLine,
    PurchaseOrderStatus,
    Vendor,
)
from app.procurement.presentation_layer.metrics.purchase_order_metrics import (
    PurchaseOrderMetrics,
)
from app.procurement.presentation_layer.search.open_demand_search import (
    ALLOCATABLE_DEMAND_STATE_CHOICES,
    OpenDemandSearch,
)
from app.procurement.presentation_layer.search.purchase_order_search import (
    PurchaseOrderSearch,
)
from app.procurement.presentation_layer.tools import po_approval, po_wizard_draft as draft_tools
from app.procurement.presentation_layer.tools import reallocation_draft
from app.procurement.presentation_layer.tools.procurement_access import (
    accessible_domain_ids,
    can_approve_purchase,
    can_buy,
    is_in_domain,
    require_buy,
    require_purchase_approve,
)

TEMPLATE_DIR = "procurement/purchase_orders"


# ====================================================================== #
# Shared helpers
# ====================================================================== #


def _load_purchase_order(request: HttpRequest, pk: int) -> PurchaseOrder:
    """Fetch a PO the user is allowed to open at all.

    Out-of-domain is a 404, not a 403: the fence should not confirm that a PO
    with this id exists. Cross-domain *references* on a page the user already
    has (a demand from another domain on this PO) are a different case and
    render as plain text — see `is_in_domain`.
    """
    try:
        po = PurchaseOrder.objects.select_related("vendor", "domain", "event").get(
            pk=pk, deleted_at__isnull=True
        )
    except PurchaseOrder.DoesNotExist:
        raise Http404
    if po.domain_id not in accessible_domain_ids(request):
        raise Http404
    return po


def _status_context(purchase_order: PurchaseOrder) -> dict:
    """The two-axis badge pair's context, in one place so the three pages that
    render `_status_tags.html` cannot drift apart."""
    return {
        "po_status": purchase_order.status,
        "po_status_label": purchase_order.get_status_display(),
        "approval_state": po_approval.state_of(purchase_order),
        "approval_label": po_approval.label_of(purchase_order),
        "approval_tag_class": po_approval.tag_class_of(purchase_order),
    }


def _stash_cap_decision(
    request: HttpRequest,
    error: AllocationCapExceeded,
    *,
    form_action: str,
    fields: dict,
    part_label: str = "",
) -> None:
    """Park D28's choice so it survives POST -> redirect -> GET.

    The dialog cannot be rendered from the POST response, because the POST
    response is a redirect — that is what keeps refresh honest. So the numbers
    and the replay fields go in the session and the next GET picks them up.
    """
    request.session[draft_tools.CAP_DECISION_SESSION_KEY] = {
        "form_action": form_action,
        "demand_id": error.demand_id,
        "part_label": part_label,
        "quantity_requested": str(error.quantity_requested),
        "purchased_qty": str(error.purchased_qty),
        "outstanding": str(error.outstanding),
        "attempted": str(error.attempted),
        "binary_allocation": getattr(error, "binary_allocation", False),
        "fields": [{"name": k, "value": str(v)} for k, v in fields.items()],
    }
    request.session.modified = True


def _pop_cap_decision(request: HttpRequest) -> dict | None:
    """One-shot read. A refresh dismisses an unanswered dialog rather than
    re-asking forever — the Buyer simply did not make the allocation."""
    decision = request.session.pop(draft_tools.CAP_DECISION_SESSION_KEY, None)
    if decision is not None:
        request.session.modified = True
    return decision


def _report(request: HttpRequest, error: ProcurementValidationError) -> None:
    for message in error.errors:
        messages.error(request, message)


def _decimal(raw) -> Decimal | None:
    return draft_tools.to_decimal(raw)


def _int(raw) -> int | None:
    return draft_tools.to_int(raw)


# ====================================================================== #
# 2.3  purchase_order_index — /procurement/purchase-orders
# ====================================================================== #


@require_http_methods(["GET"])
def purchase_order_index(request: HttpRequest) -> HttpResponse:
    domain_ids = accessible_domain_ids(request)
    filters = {
        "q": request.GET.get("q", "").strip(),
        "status": request.GET.get("status", "").strip(),
        "approval_state": request.GET.get("approval_state", "").strip(),
        "vendor_id": _int(request.GET.get("vendor_id")),
        "domain_id": _int(request.GET.get("domain_id")),
        "part_id": _int(request.GET.get("part_id")),
        "date_from": parse_date(request.GET.get("date_from", "") or ""),
        "date_to": parse_date(request.GET.get("date_to", "") or ""),
    }

    results = PurchaseOrderSearch.filter(domain_ids=domain_ids, **filters)
    stats = PurchaseOrderMetrics.summarize(results)
    rows = PurchaseOrderSearch.annotate_display(results[:200])

    return render(
        request,
        f"{TEMPLATE_DIR}/index.html",
        {
            "purchase_orders": rows,
            "stats": stats,
            "filters": filters,
            "raw_filters": request.GET,
            "status_choices": PurchaseOrderStatus.choices,
            "approval_choices": po_approval.CHOICES,
            "vendors": Vendor.objects.filter(is_active=True).order_by("name"),
            "domains": Domain.objects.filter(pk__in=domain_ids).order_by("name"),
            "can_buy": can_buy(request),
        },
    )


# ====================================================================== #
# 2.1  purchase_order_create — the wizard
# ====================================================================== #


@require_http_methods(["GET", "POST"])
def purchase_order_create(request: HttpRequest) -> HttpResponse:
    """One route, vertical scroll, progressive enablement, session-backed draft.

    NOTHING TOUCHES THE DATABASE UNTIL FINAL SUBMIT. A half-built PO in the
    database would be visible to other Buyers, would need a status meaning "not
    really a PO yet", and would leave orphans when abandoned. Every POST below
    mutates `request.session` and redirects; only `_wizard_submit` writes.
    """
    require_buy(request)
    domain_ids = accessible_domain_ids(request)

    if request.method == "POST":
        return _wizard_post(request, domain_ids=domain_ids)

    # The one fragment response this route serves: <li> rows for the part
    # search-dropdown on the line-add form. Same canonical URL, `format=` query
    # parameter — not a parallel route.
    if request.GET.get("format") == "htmx-part-results":
        return _part_search_results(request)

    return _wizard_render(request, domain_ids=domain_ids)


def _part_search_results(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip()
    parts = Part.objects.filter(is_active=True)
    if q:
        parts = parts.filter(Q(part_number__icontains=q) | Q(name__icontains=q))
    parts = parts.order_by("part_number")[:25]

    rows = [
        f'<li data-value="{p.pk}" class="is-family-monospace">{p.part_number}'
        f'<span class="has-text-grey is-size-7"> — {p.name}</span></li>'
        for p in parts
    ]
    if not rows:
        rows = ['<li class="is-disabled">No matches.</li>']
    return HttpResponse("\n".join(rows))


def _wizard_render(request: HttpRequest, *, domain_ids: list[int]) -> HttpResponse:
    draft = draft_tools.load(request.session)

    vendor = None
    if draft.get("vendor_id"):
        vendor = Vendor.objects.filter(pk=draft["vendor_id"]).first()

    # Card 2's "from demands" pool — a cross-part, server-filtered list, because
    # the systemwide open-demand pool runs into the hundreds. Card 3's per-line
    # pools are per-part (tens of rows) and ship whole, filtered client-side by
    # the left-heavy pair's own filter bar.
    pool_filters = {
        "q": request.GET.get("pool_q", "").strip(),
        "priority": request.GET.get("pool_priority", "").strip(),
        "part_id": _int(request.GET.get("pool_part_id")),
        "event_id": _int(request.GET.get("pool_event_id")),
    }
    demand_pool = []
    if draft_tools.has_vendor(draft):
        demand_pool = list(
            OpenDemandSearch.pool(domain_ids=domain_ids, **pool_filters)[:100]
        )
        for demand in demand_pool:
            # The chip's DOM handle for this row — computed here rather than
            # in the template, since Django templates cannot concatenate an
            # int onto a string with `add`.
            demand.price_chip_handle = f"unit-cost-{demand.part_id}"

    lines = _draft_line_views(draft, domain_ids=domain_ids)
    price_facts = _price_facts_for_wizard(
        lines=lines, demand_pool=demand_pool, vendor_id=draft.get("vendor_id"), domain_ids=domain_ids
    )

    return render(
        request,
        f"{TEMPLATE_DIR}/create.html",
        {
            "draft": draft,
            "vendor": vendor,
            "lines": lines,
            "demand_pool": demand_pool,
            "price_facts": price_facts,
            "price_vendor_id": draft.get("vendor_id"),
            "pool_filters": pool_filters,
            "priority_choices": DemandPriority.choices,
            "demand_status_choices": ALLOCATABLE_DEMAND_STATE_CHOICES,
            "domains": Domain.objects.filter(pk__in=domain_ids).order_by("name"),
            "has_vendor": draft_tools.has_vendor(draft),
            "has_lines": draft_tools.has_lines(draft),
            "can_submit": draft_tools.can_submit(draft),
            "draft_total": _draft_total(draft),
            "cap_decision": _pop_cap_decision(request),
        },
    )


def _draft_line_views(draft: dict, *, domain_ids: list[int]) -> list[dict]:
    """Hydrate each staged line into something a template can render.

    Parts and demands are fetched in two queries for the whole card stack, not
    one per line — the wizard is the app's busiest screen and a per-line query
    here is the same mistake the legacy portal made.
    """
    lines = draft.get("lines") or []
    if not lines:
        return []

    part_ids = [int(line["part_id"]) for line in lines]
    parts_by_id = {p.pk: p for p in Part.objects.filter(pk__in=part_ids)}

    demand_ids = [
        int(allocation["demand_id"])
        for line in lines
        for allocation in (line.get("allocations") or [])
    ]
    demands_by_id = {
        d.pk: d
        for d in PartDemand.objects.filter(pk__in=demand_ids).select_related("part")
    }

    # Each line's allocatable pool, one query per distinct part (not per line).
    pools_by_part: dict[int, list] = {}
    for part_id in set(part_ids):
        pools_by_part[part_id] = list(
            OpenDemandSearch.for_part(part_id=part_id, domain_ids=domain_ids)[:100]
        )

    views = []
    for index, line in enumerate(lines):
        part_id = int(line["part_id"])
        quantity_ordered = draft_tools.to_decimal(line["quantity_ordered"]) or Decimal("0")
        allocated = draft_tools.allocated_total(line)
        allocations = []
        for allocation in line.get("allocations") or []:
            demand = demands_by_id.get(int(allocation["demand_id"]))
            allocations.append(
                {
                    "demand_id": int(allocation["demand_id"]),
                    "demand": demand,
                    "quantity_allocated": draft_tools.to_decimal(
                        allocation["quantity_allocated"]
                    ),
                    "auto_approve": allocation.get("auto_approve", True),
                    "raise_request": allocation.get("raise_request", False),
                }
            )
        allocated_ids = {a["demand_id"] for a in allocations}
        views.append(
            {
                "index": index,
                "unique_id": f"po-create-{index}",
                "price_chip_handle": f"line-cost-{index}",
                "allocated_ids": ",".join(str(i) for i in allocated_ids),
                "part": parts_by_id.get(part_id),
                "quantity_ordered": quantity_ordered,
                "unit_cost": draft_tools.to_decimal(line["unit_cost"]),
                "line_total": (quantity_ordered)
                * (draft_tools.to_decimal(line["unit_cost"]) or Decimal("0")),
                "expected_delivery_date": line.get("expected_delivery_date"),
                "notes": line.get("notes") or "",
                "allocations": allocations,
                "allocated_total": allocated,
                "unallocated": quantity_ordered - allocated,
                # Demands already picked drop out of the pool; allocating more
                # means editing the existing pick, never adding a second.
                "pool": [
                    d for d in pools_by_part.get(part_id, []) if d.pk not in allocated_ids
                ],
            }
        )
    return views


def _price_facts_for_wizard(
    *, lines: list[dict], demand_pool: list, vendor_id: int | None, domain_ids: list[int]
) -> dict[int, "PartPriceFactsStruct"]:
    """One facts_for_many call for every part on the page — the chip is
    rendered server-side on plain GET for every line (front_end_build_plan.md
    §7.3); a chip per line calling the policy per-line is the mistake this
    kit exists to avoid."""
    if not vendor_id:
        return {}
    part_ids = {line["part"].id for line in lines if line.get("part")}
    part_ids.update(demand.part_id for demand in demand_pool)
    if not part_ids:
        return {}
    return PartPricePolicy.facts_for_many(
        part_ids=list(part_ids), vendor_id=vendor_id, domain_ids=domain_ids
    )


def _draft_total(draft: dict) -> Decimal:
    total = Decimal("0")
    for line in draft.get("lines") or []:
        quantity = draft_tools.to_decimal(line.get("quantity_ordered")) or Decimal("0")
        cost = draft_tools.to_decimal(line.get("unit_cost")) or Decimal("0")
        total += quantity * cost
    for key in ("shipping_cost", "tax_amount", "other_amount"):
        total += draft_tools.to_decimal(draft.get(key)) or Decimal("0")
    return total


def _wizard_post(request: HttpRequest, *, domain_ids: list[int]) -> HttpResponse:
    action = request.POST.get("action", "")
    draft = draft_tools.load(request.session)
    back = reverse("purchase_order_create")

    if action == "clear":
        draft_tools.clear(request.session)
        messages.info(request, "Draft purchase order discarded.")
        return redirect(back)

    if action == "save_header":
        _wizard_save_header(request, draft, domain_ids=domain_ids)
        draft_tools.save(request.session, draft)
        return redirect(back)

    if not draft_tools.has_vendor(draft):
        messages.error(request, "Pick a vendor and a buying domain first.")
        return redirect(back)

    if action == "add_unlinked_line":
        _wizard_add_unlinked_line(request, draft)
    elif action == "add_from_demands":
        _wizard_add_from_demands(request, draft, domain_ids=domain_ids)
    elif action == "remove_line":
        if draft_tools.remove_line(draft, _int(request.POST.get("line_index")) or -1):
            messages.info(request, "Line removed from the draft.")
    elif action == "edit_line":
        _wizard_edit_line(request, draft)
    elif action == "allocate":
        _wizard_allocate(request, draft, back=back)
    elif action == "remove_allocation":
        line = draft_tools.line_at(draft, _int(request.POST.get("line_index")) or -1)
        demand_id = _int(request.POST.get("demand_id"))
        if line and demand_id and draft_tools.remove_allocation(line, demand_id=demand_id):
            messages.info(request, f"Demand #{demand_id} un-allocated.")
    elif action == "submit":
        return _wizard_submit(request, draft)
    else:
        messages.error(request, "Unrecognised wizard action.")

    draft_tools.save(request.session, draft)
    return redirect(back)


def _wizard_save_header(request: HttpRequest, draft: dict, *, domain_ids: list[int]) -> None:
    """Card 1's autosave. There is no "Save vendor & header" button — this
    action fires silently (HTMX `hx-trigger="change"` on the form) every time
    a header field changes, so the draft is always current and item selection
    (card 2, gated on `has_vendor`) unlocks the moment vendor + domain are both
    set, with no explicit save click required.

    Partial state is expected and not an error: a Buyer who has only picked a
    vendor so far still gets that pick saved. The one real validation left is
    the domain fence — that guards a write, not just a read.
    """
    vendor_id = _int(request.POST.get("vendor_id"))
    if vendor_id and not Vendor.objects.filter(pk=vendor_id).exists():
        vendor_id = None

    domain_id = _int(request.POST.get("domain_id"))
    if domain_id and domain_id not in domain_ids:
        messages.error(request, "Choose a buying domain you have access to.")
        domain_id = None

    draft["vendor_id"] = vendor_id
    draft["domain_id"] = domain_id
    draft["vendor_contact"] = request.POST.get("vendor_contact", "").strip()
    draft["vendor_po_id"] = request.POST.get("vendor_po_id", "").strip()
    draft["order_date"] = request.POST.get("order_date") or None
    draft["expected_delivery_date"] = request.POST.get("expected_delivery_date") or None
    draft["shipping_cost"] = request.POST.get("shipping_cost") or None
    draft["tax_amount"] = request.POST.get("tax_amount") or None
    draft["other_amount"] = request.POST.get("other_amount") or None
    draft["notes"] = request.POST.get("notes", "").strip()


def _wizard_edit_line(request: HttpRequest, draft: dict) -> None:
    """Card 3's per-line-card autosave — quantity, unit cost, delivery date,
    and notes update in place via `hx-trigger="change"`, the same pattern as
    card 1's header. Allocations are untouched here; they have their own
    actions inside the line card's "find part demands to link" details.

    A rejected edit (bad quantity/cost) leaves the line as it was rather than
    half-applying the POST — the autosave has no undo, so a typo mid-edit
    should not corrupt the one field that was already valid.
    """
    line_index = _int(request.POST.get("line_index"))
    line = draft_tools.line_at(draft, line_index if line_index is not None else -1)
    if line is None:
        messages.error(request, "That draft line no longer exists.")
        return

    quantity = _decimal(request.POST.get("quantity_ordered"))
    unit_cost = _decimal(request.POST.get("unit_cost"))
    if quantity is None or quantity <= 0:
        messages.error(request, "Ordered quantity must be greater than zero.")
        return
    if unit_cost is None or unit_cost < 0:
        messages.error(request, "Unit cost cannot be negative.")
        return

    line["quantity_ordered"] = str(quantity)
    line["unit_cost"] = str(unit_cost)
    line["expected_delivery_date"] = request.POST.get("expected_delivery_date") or None
    line["notes"] = request.POST.get("line_notes", "").strip()
    _apply_price_provenance(line, request.POST)


def _wizard_add_unlinked_line(request: HttpRequest, draft: dict) -> None:
    """The Unlinked tab. Zero demands on a line is valid (D14) and this is the
    intended path for it — proactive stock, a vendor minimum order quantity, or
    reserve for a demand that does not exist yet."""
    part_id = _int(request.POST.get("part_id"))
    quantity = _decimal(request.POST.get("quantity_ordered"))
    unit_cost = _decimal(request.POST.get("unit_cost"))

    problems = []
    if not part_id or not Part.objects.filter(pk=part_id).exists():
        problems.append("Choose a part.")
    if quantity is None or quantity <= 0:
        problems.append("Ordered quantity must be greater than zero.")
    if unit_cost is None or unit_cost < 0:
        problems.append("Unit cost cannot be negative.")
    if problems:
        for problem in problems:
            messages.error(request, problem)
        return

    existing_index = draft_tools.find_line_for_part(draft, part_id)
    if existing_index is not None:
        # D58 — one active line per part per PO. Grow the line rather than
        # staging a duplicate the commit would only warn about later.
        line = draft["lines"][existing_index]
        previous = draft_tools.to_decimal(line["quantity_ordered"]) or Decimal("0")
        line["quantity_ordered"] = str(previous + quantity)
        line["unit_cost"] = str(unit_cost)
        messages.info(
            request,
            f"That part is already on line {existing_index + 1} — its quantity grew to "
            f"{line['quantity_ordered']} instead of opening a second line.",
        )
        return

    new_line = draft_tools.new_line(
        part_id=part_id,
        quantity_ordered=quantity,
        unit_cost=unit_cost,
        expected_delivery_date=(
            request.POST.get("expected_delivery_date")
            or draft.get("expected_delivery_date")
        ),
        notes=request.POST.get("line_notes", "").strip(),
    )
    _apply_price_provenance(new_line, request.POST)
    draft["lines"].append(new_line)
    messages.success(request, "Line added to the draft.")


def _apply_price_provenance(line: dict, post) -> None:
    """D85/D88 — the price chip's "Use this" and the picker stamp three
    hidden fields alongside the visible cost input; a plain typed number
    carries none of them, which is correct (§7.1: never invented)."""
    source = (post.get("unit_cost_source") or "").strip()
    confidence = (post.get("unit_cost_confidence") or "").strip()
    asserted_at = (post.get("unit_cost_asserted_at") or "").strip()
    if source:
        line["unit_cost_source"] = source
    if confidence:
        line["unit_cost_confidence"] = confidence
    if asserted_at:
        line["unit_cost_asserted_at"] = asserted_at


def _wizard_add_from_demands(
    request: HttpRequest, draft: dict, *, domain_ids: list[int]
) -> None:
    """The From-demands tab.

    Picking demands for a part both creates/updates that part's line AND
    pre-populates card 3's allocation for exactly those demands — the Buyer does
    not re-pick them downstream, they only confirm quantity and resolve any cap.
    """
    demand_ids = [d for d in (_int(v) for v in request.POST.getlist("demand_ids")) if d]
    if not demand_ids:
        messages.error(request, "Select at least one demand.")
        return

    demands = list(
        PartDemand.objects.filter(
            pk__in=demand_ids, domain_id__in=domain_ids, deleted_at__isnull=True
        ).select_related("part")
    )
    if not demands:
        messages.error(request, "None of those demands are in your domains.")
        return

    unit_costs = {
        _int(key.removeprefix("unit_cost_")): _decimal(value)
        for key, value in request.POST.items()
        if key.startswith("unit_cost_")
    }

    added = 0
    for demand in demands:
        outstanding = demand.quantity_requested - demand.purchased_qty
        if outstanding <= 0:
            messages.warning(
                request, f"Demand #{demand.pk} has nothing outstanding — skipped."
            )
            continue

        index = draft_tools.find_line_for_part(draft, demand.part_id)
        if index is None:
            unit_cost = unit_costs.get(demand.part_id) or demand.expected_cost or Decimal("0")
            draft["lines"].append(
                draft_tools.new_line(
                    part_id=demand.part_id,
                    quantity_ordered=outstanding,
                    unit_cost=unit_cost,
                    expected_delivery_date=draft.get("expected_delivery_date"),
                )
            )
            index = len(draft["lines"]) - 1
        else:
            line = draft["lines"][index]
            previous = draft_tools.to_decimal(line["quantity_ordered"]) or Decimal("0")
            line["quantity_ordered"] = str(previous + outstanding)

        # Staged, not written. The cap is re-checked for real at commit; here it
        # cannot be exceeded because the pick is exactly the outstanding amount.
        draft_tools.set_allocation(
            draft["lines"][index],
            demand_id=demand.pk,
            quantity=outstanding,
            auto_approve=True,
        )
        added += 1

    if added:
        messages.success(
            request,
            f"{added} demand{'s' if added != 1 else ''} added to the draft's lines "
            f"and pre-allocated.",
        )


def _wizard_allocate(request: HttpRequest, draft: dict, *, back: str) -> None:
    """Card 3's per-pick allocation, including D28's cap decision.

    The cap is checked against the demand's database outstanding MINUS whatever
    other draft lines have already staged against it. Checking the database
    alone would let the Buyer stage the same demand twice across two lines and
    only find out at commit, after the wizard had told them both were fine.
    """
    line_index = _int(request.POST.get("line_index"))
    line = draft_tools.line_at(draft, line_index if line_index is not None else -1)
    demand_id = _int(request.POST.get("demand_id"))
    quantity = _decimal(request.POST.get("quantity_allocated"))
    # D42: auto-approval is silent unless the Buyer opts out here.
    auto_approve = request.POST.get("auto_approve") != "0"
    resolution = request.POST.get("cap_resolution", "")

    if line is None or not demand_id:
        messages.error(request, "That draft line no longer exists.")
        return
    if quantity is None or quantity <= 0:
        messages.error(request, "Allocated quantity must be greater than zero.")
        return

    demand = PartDemand.objects.filter(pk=demand_id, deleted_at__isnull=True).first()
    if demand is None:
        messages.error(request, f"Demand #{demand_id} no longer exists.")
        return
    if demand.part_id != int(line["part_id"]):
        messages.error(
            request,
            f"Demand #{demand_id} is for a different part than this line. "
            f"Allocations must match on part.",
        )
        return

    staged_elsewhere = draft_tools.staged_for_demand(
        draft, demand_id=demand_id, skip_line_index=line_index
    )
    outstanding = demand.quantity_requested - demand.purchased_qty - staged_elsewhere
    if outstanding < 0:
        outstanding = Decimal("0")

    if outstanding <= 0:
        messages.error(
            request,
            f"Demand #{demand_id} has nothing outstanding — nothing to allocate.",
        )
        return

    if quantity != outstanding and resolution != "raise_request":
        _stash_cap_decision(
            request,
            AllocationCapExceeded(
                demand_id=demand.pk,
                quantity_requested=demand.quantity_requested,
                purchased_qty=demand.purchased_qty + staged_elsewhere,
                outstanding=outstanding,
                attempted=quantity,
                binary_allocation=True,
            ),
            form_action=back,
            fields={
                "action": "allocate",
                "line_index": line_index,
                "demand_id": demand_id,
                "quantity_allocated": quantity,
                "auto_approve": "1" if auto_approve else "0",
            },
            part_label=str(demand.part),
        )
        return

    draft_tools.set_allocation(
        line,
        demand_id=demand.pk,
        quantity=quantity,
        auto_approve=auto_approve,
        raise_request=resolution == "raise_request",
    )
    if resolution == "raise_request":
        messages.warning(
            request,
            f"Demand #{demand.pk}'s requested quantity will be raised to cover "
            f"{quantity} when this order is saved.",
        )
    else:
        messages.success(request, f"Allocated {quantity} to demand #{demand.pk}.")


def _wizard_submit(request: HttpRequest, draft: dict) -> HttpResponse:
    """The only write in the wizard. One transaction; if any step fails, no PO
    exists. The order opens as Draft, never Placed (D52), and as Unsubmitted on
    the approval axis — hence the button says "Save as Draft"."""
    try:
        parsed = PurchaseOrderDraftAdaptor.from_dict(draft)
    except ProcurementValidationError as exc:
        _report(request, exc)
        return redirect(reverse("purchase_order_create"))

    try:
        purchase_order = PurchaseOrderFactory.create_from_draft(
            draft=parsed, actor=request.user
        )
    except ProcurementValidationError as exc:
        _report(request, exc)
        return redirect(reverse("purchase_order_create"))

    # vendor_po_id is Phase 0's column and is not on the adaptor's dataclass yet;
    # the wizard carries it on the draft dict and sets it here. Fold this into
    # the factory once Phase 0's adaptor change lands.
    vendor_po_id = (draft.get("vendor_po_id") or "").strip()
    if vendor_po_id and hasattr(purchase_order, "vendor_po_id"):
        purchase_order.vendor_po_id = vendor_po_id
        purchase_order.save(update_fields=["vendor_po_id", "updated_at"])

    draft_tools.clear(request.session)
    messages.success(
        request,
        f"Purchase order {purchase_order.po_number} saved as a draft. "
        f"Submit it for approval when you are ready to place it.",
    )
    return redirect(reverse("purchase_order_detail", args=[purchase_order.pk]))


# ====================================================================== #
# 2.2  purchase_order_detail — /procurement/purchase-orders/<id>
# ====================================================================== #


@require_http_methods(["GET", "POST"])
def purchase_order_detail(request: HttpRequest, pk: int) -> HttpResponse:
    purchase_order = _load_purchase_order(request, pk)

    if request.method == "POST":
        return _detail_post(request, purchase_order)

    return _detail_render(request, purchase_order)


def _detail_render(request: HttpRequest, purchase_order: PurchaseOrder) -> HttpResponse:
    # ONE annotated read for the whole page — lines, allocations, shipments, the
    # four quantities, per-line attribution mode.
    fulfillment = PurchaseOrderFulfillmentStruct.load(purchase_order_id=purchase_order.pk)

    lines = _detail_line_views(request, purchase_order, fulfillment)
    for line in lines:
        line["price_chip_handle"] = f"edit-cost-{line['struct'].line_id}"

    comments_card = None
    if purchase_order.event_id:
        from app.events.presentation_layer.tools.generic_cards import build_activity_card

        comments_card = build_activity_card(purchase_order.event, request.user)

    buyer = can_buy(request)
    approver = can_approve_purchase(request)

    can_submit_for_approval = buyer and po_approval.can_submit_for_approval(purchase_order)
    can_decide = approver and po_approval.can_decide(purchase_order)
    can_deny = approver and po_approval.can_deny(purchase_order)
    can_place = (
        buyer
        and po_approval.can_place(purchase_order)
        and purchase_order.status == PurchaseOrderStatus.DRAFT
    )
    self_approval = po_approval.is_self_approval(purchase_order, request.user)

    # One dropdown drives every status transition in the hero bar. Each entry
    # mirrors exactly the gating the old per-action buttons used — no
    # permission behavior changes, only how the action is presented.
    available_actions = []
    if can_submit_for_approval:
        available_actions.append({"value": "submit_for_approval", "label": "Submit for approval"})
    if can_decide:
        available_actions.append({"value": "approve", "label": "Approve"})
    if can_deny:
        available_actions.append({"value": "deny", "label": "Deny"})
    if can_place:
        available_actions.append(
            {
                "value": "place",
                "label": "Place order",
                "confirm": f"Place this order with {purchase_order.vendor.name}? "
                "This is the money-moved boundary.",
            }
        )
    if buyer:
        available_actions.append(
            {
                "value": "mark_received",
                "label": "Mark received",
                "confirm": "Mark this order received? This is an explicit close-out, "
                "whatever the quantities say.",
            }
        )
        available_actions.append(
            {
                "value": "cancel",
                "label": "Cancel order",
                "confirm": "Cancel this purchase order? Its allocations are released and "
                "every linked demand is propagated to Cancelled.",
                "needs_reason": True,
            }
        )

    shipment_lines_by_shipment: dict[int, list] = {}
    for shipment_line in ShipmentLine.objects.filter(
        shipment__purchase_order=purchase_order, deleted_at__isnull=True
    ).select_related("part").prefetch_related(
        "purchase_order_links__purchase_order_line"
    ):
        shipment_lines_by_shipment.setdefault(shipment_line.shipment_id, []).append(shipment_line)

    part_demands = [
        {
            "line_number": line["struct"].line_number,
            "part_number": line["struct"].part_number,
            **entry,
        }
        for line in lines
        for entry in line["links"]
    ]

    return render(
        request,
        f"{TEMPLATE_DIR}/detail.html",
        {
            "po": purchase_order,
            "fulfillment": fulfillment,
            "lines": lines,
            "part_demands": part_demands,
            "shipments": fulfillment.shipments,
            "shipment_lines_by_shipment": shipment_lines_by_shipment,
            "unassigned_shipment_line_ids": fulfillment.unassigned_shipment_line_ids,
            "comments_card": comments_card,
            "cap_decision": _pop_cap_decision(request),
            # D57: a placed order stays editable. The banner warns; nothing is
            # disabled. Every mutation writes an audit-snapshot machine comment.
            "show_placed_warning": purchase_order.status != PurchaseOrderStatus.DRAFT,
            "can_buy": buyer,
            "can_approve": approver,
            "available_actions": available_actions,
            "place_blocked_reason": _place_blocked_reason(purchase_order),
            "self_approval": self_approval,
            **_status_context(purchase_order),
        },
    )


def _place_blocked_reason(purchase_order: PurchaseOrder) -> str:
    """Say why Place is unavailable rather than showing a dead button.

    The approval gate is new in this wave, so a Buyer who could place yesterday
    needs to be told what changed, not left guessing.
    """
    if purchase_order.status != PurchaseOrderStatus.DRAFT:
        return f"This order is already {purchase_order.get_status_display()}."
    if not po_approval.can_place(purchase_order):
        return (
            "A purchasing manager must approve this order before it can be placed. "
            f"It is currently {po_approval.label_of(purchase_order)}."
        )
    return ""


def _detail_line_views(
    request: HttpRequest, purchase_order: PurchaseOrder, fulfillment
) -> list[dict]:
    """Marry the struct's per-line quantities to the rows the editor needs.

    The struct deliberately produces three different line classes and no
    per-demand arrival figure on the shared-session branch (D55/D60). This view
    passes `attribution_mode` straight through so the template can render the
    right sentence — it never divides `session_arrived` among members.
    """
    line_rows = {
        line.pk: line
        for line in PurchaseOrderLine.objects.filter(
            purchase_order=purchase_order, deleted_at__isnull=True
        ).select_related("part")
    }

    links_by_line: dict[int, list] = {}
    for link in (
        PurchaseOrderDemandLink.objects.filter(
            purchase_order_line__purchase_order=purchase_order,
            is_active=True,
            deleted_at__isnull=True,
        )
        .select_related("part_demand", "part_demand__part", "part_demand__domain")
        .order_by("pk")
    ):
        links_by_line.setdefault(link.purchase_order_line_id, []).append(link)

    # One query for every demand's external claims on this page (§4 point 1),
    # not one per row. Shared by PO Detail and Edit & Linkage alike — both
    # read this same dict off the same view rows; only the templates differ
    # in whether they render it.
    demand_ids = {
        link.part_demand_id for links in links_by_line.values() for link in links
    }
    external_by_demand = DemandExternalClaimsStruct.load_many(
        demand_ids=demand_ids, exclude_purchase_order_id=purchase_order.pk
    )

    views = []
    for struct_line in fulfillment.lines:
        row = line_rows.get(struct_line.line_id)
        links = links_by_line.get(struct_line.line_id, [])
        views.append(
            {
                "struct": struct_line,
                "unique_id": f"po-detail-{struct_line.line_id}",
                "row": row,
                "part": row.part if row else None,
                "unit_cost": row.unit_cost if row else None,
                "line_total": (row.quantity_ordered * row.unit_cost) if row else None,
                "expected_delivery_date": row.expected_delivery_date if row else None,
                "notes": row.notes if row else "",
                "unallocated": struct_line.qty_ordered - struct_line.qty_allocated,
                "links": [
                    {
                        "link": link,
                        "demand": link.part_demand,
                        # Cross-domain demands render as plain text with no link
                        # through (Phase 0 §5).
                        "linkable": is_in_domain(request, link.part_demand.domain_id),
                        # Reallocation Resolution decision (reallocation_resolution_portal.md
                        # §4, §7.10, §7.2): is_locked is real, stored data, set
                        # only by a deliberate record_receipt action — sufficient
                        # on its own to flag a claim as "manually recorded, not a
                        # safe computed value." external_claims is this demand's
                        # active claims on OTHER orders — read-only here, never
                        # editable from this screen.
                        "is_locked": link.is_locked,
                        "quantity_received": link.quantity_received,
                        "external_claims": external_by_demand.get(
                            link.part_demand_id,
                            DemandExternalClaimsStruct(demand_id=link.part_demand_id),
                        ).claims,
                    }
                    for link in links
                ],
            }
        )
    return views


def _detail_post(request: HttpRequest, purchase_order: PurchaseOrder) -> HttpResponse:
    action = request.POST.get("action", "")
    back = reverse("purchase_order_detail", args=[purchase_order.pk])
    context = PurchaseOrderContext(purchase_order.pk)

    approval_verbs = {
        "submit_for_approval": ("submit_for_approval", "submitted for approval"),
        "approve": ("approve_order", "approved"),
        "deny": ("deny_order", "denied"),
    }

    try:
        if action in approval_verbs:
            verb, past = approval_verbs[action]
            if action == "submit_for_approval":
                require_buy(request)
            else:
                require_purchase_approve(request)
            po_approval.run_verb(context, verb, actor=request.user)
            if action == "approve" and po_approval.is_self_approval(
                purchase_order, request.user
            ):
                # Permitted, and recorded — the narrator posts the machine
                # comment; the Buyer is told to their face that it happened.
                messages.warning(
                    request,
                    "You approved your own purchase order. This is permitted and has "
                    "been recorded on the order's activity thread.",
                )
            messages.success(request, f"Purchase order {past}.")

        elif action == "place":
            require_buy(request)
            if not po_approval.can_place(purchase_order):
                messages.error(request, _place_blocked_reason(purchase_order))
                return redirect(back)
            context.place(actor=request.user)
            messages.success(request, "Purchase order placed with the vendor.")

        elif action == "mark_received":
            # An explicit human act, never a quantity match (D29).
            require_buy(request)
            context.mark_received(actor=request.user)
            messages.success(request, "Purchase order closed out as received.")

        elif action == "cancel":
            require_buy(request)
            context.cancel(actor=request.user, reason=request.POST.get("reason", "").strip())
            messages.success(request, "Purchase order cancelled and its allocations released.")

        elif action == "add_line":
            require_buy(request)
            _detail_add_line(request, context)

        elif action == "edit_line":
            require_buy(request)
            _detail_edit_line(request, purchase_order, context)

        elif action == "cancel_line":
            require_buy(request)
            _detail_cancel_line(request, purchase_order, context)

        elif action == "allocate":
            # D3 — allocation is Buyer-only.
            require_buy(request)
            return _allocate_from_form(request, purchase_order, context, back=back)

        elif action == "delink":
            require_buy(request)
            _delink_from_form(request, purchase_order, context)

        elif action == "record_receipt":
            # Reallocation Resolution decision — marking a claim received is
            # the sole trigger for locking it (§7.2), so it is gated the same
            # as any other Buyer-side allocation write.
            require_buy(request)
            _detail_record_receipt(request, purchase_order, context)

        elif action == "reallocation_auto_allocate":
            require_buy(request)
            _reallocation_auto_allocate(request, purchase_order)

        elif action == "reallocation_manual_entry":
            require_buy(request)
            _reallocation_manual_entry(request, purchase_order)

        elif action == "reallocation_unlock_claim":
            require_buy(request)
            _reallocation_unlock_claim(request, purchase_order, context)

        elif action == "reallocation_commit":
            require_buy(request)
            _reallocation_commit(request, purchase_order, context)

        elif action == "reallocation_cancel":
            require_buy(request)
            reallocation_draft.clear(request.session)
            messages.info(request, "Reallocation cancelled; the line was not changed.")

        else:
            messages.error(request, "Unrecognised action.")

    except ProcurementValidationError as exc:
        _report(request, exc)

    return redirect(back)


def _detail_record_receipt(
    request: HttpRequest, purchase_order: PurchaseOrder, context: PurchaseOrderContext
) -> None:
    link = PurchaseOrderDemandLink.objects.filter(
        pk=_int(request.POST.get("link_id")),
        purchase_order_line__purchase_order=purchase_order,
        is_active=True,
        deleted_at__isnull=True,
    ).select_related("purchase_order_line", "part_demand").first()
    if link is None:
        messages.error(request, "That claim is not on this purchase order.")
        return

    quantity_received = _decimal(request.POST.get("quantity_received"))
    if quantity_received is None:
        messages.error(request, "Enter how much of this claim has been received.")
        return

    context.record_receipt(link=link, quantity_received=quantity_received, actor=request.user)
    messages.success(
        request,
        f"Demand #{link.part_demand_id}'s claim marked {quantity_received} received "
        f"and locked.",
    )


# ---------------------------------------------------------------------- #
# Reallocation Portal (Demand↔PO Domain) — backend actions against the
# session-backed draft in reallocation_draft.py. No template this session;
# a later frontend build renders the Portal itself.
# ---------------------------------------------------------------------- #


def _load_reallocation_line(
    request: HttpRequest, purchase_order: PurchaseOrder
) -> tuple[dict | None, PurchaseOrderLine | None]:
    draft = reallocation_draft.load(request.session)
    if draft is None:
        messages.error(request, "No reallocation is in progress for this order.")
        return None, None
    line = _line_on_po(purchase_order, draft.get("line_id"))
    if line is None:
        reallocation_draft.clear(request.session)
        messages.error(request, "That line is not on this purchase order.")
        return None, None
    return draft, line


def _open_claims(line: PurchaseOrderLine) -> list[PurchaseOrderDemandLink]:
    return list(
        PurchaseOrderDemandLink.objects.filter(
            purchase_order_line=line,
            is_active=True,
            deleted_at__isnull=True,
            is_locked=False,
        ).select_related("part_demand")
    )


def _locked_claims(line: PurchaseOrderLine) -> list[PurchaseOrderDemandLink]:
    return list(
        PurchaseOrderDemandLink.objects.filter(
            purchase_order_line=line,
            is_active=True,
            deleted_at__isnull=True,
            is_locked=True,
        )
    )


def _reallocation_auto_allocate(request: HttpRequest, purchase_order: PurchaseOrder) -> None:
    draft, line = _load_reallocation_line(request, purchase_order)
    if line is None:
        return
    # Taking any forward action retires an unanswered unlock warning from a
    # previous attempt — otherwise the second popup would reappear on the
    # next render for a decision the user has already moved past (§6).
    reallocation_draft.clear_pending_unlock(draft)
    new_qty = reallocation_draft.to_decimal(draft["new_quantity_ordered"]) or Decimal("0")
    open_claims = _open_claims(line)
    locked_total = sum((c.quantity_allocated for c in _locked_claims(line)), Decimal("0"))
    open_total = sum((c.quantity_allocated for c in open_claims), Decimal("0"))
    shortfall = max(Decimal("0"), (open_total + locked_total) - new_qty)

    resolutions = ReallocationWaterfallHandler.allocate(
        open_claims=open_claims, shortfall=shortfall
    )
    for link_id, qty in resolutions.items():
        reallocation_draft.set_proposed(draft, link_id=link_id, quantity=qty)
    reallocation_draft.save(request.session, draft)
    messages.success(request, "Auto-allocate applied. Review and commit to save.")


def _reallocation_manual_entry(request: HttpRequest, purchase_order: PurchaseOrder) -> None:
    draft, line = _load_reallocation_line(request, purchase_order)
    if line is None:
        return
    reallocation_draft.clear_pending_unlock(draft)
    new_qty = reallocation_draft.to_decimal(draft["new_quantity_ordered"]) or Decimal("0")
    open_claim_ids = {c.pk for c in _open_claims(line)}
    locked_total = sum((c.quantity_allocated for c in _locked_claims(line)), Decimal("0"))

    values: dict[int, Decimal] = {}
    for link_id in open_claim_ids:
        raw = request.POST.get(f"claim_{link_id}")
        if raw is None:
            continue
        parsed = _decimal(raw)
        if parsed is not None:
            values[link_id] = parsed

    ReallocationValidator.check_manual_entry(
        values=values, locked_total=locked_total, new_source_qty=new_qty
    )
    for link_id, qty in values.items():
        reallocation_draft.set_proposed(draft, link_id=link_id, quantity=qty)
    reallocation_draft.save(request.session, draft)
    messages.success(request, "Manual entry saved. Review and commit to save.")


def _reallocation_unlock_claim(
    request: HttpRequest, purchase_order: PurchaseOrder, context: PurchaseOrderContext
) -> None:
    draft, line = _load_reallocation_line(request, purchase_order)
    if line is None:
        return
    link = PurchaseOrderDemandLink.objects.filter(
        pk=_int(request.POST.get("link_id")),
        purchase_order_line=line,
        is_active=True,
        deleted_at__isnull=True,
        is_locked=True,
    ).select_related("purchase_order_line__purchase_order", "part_demand").first()
    if link is None:
        messages.error(request, "That claim is not a locked claim on this line.")
        return

    # THE SECOND POPUP'S CONTRACT (§6): this action is called twice — once to
    # surface the warning, once with confirmed=1 after the user explicitly
    # accepts it. Nothing is written on the first call. `pending_unlock`
    # records which claim is awaiting that second popup so the next render
    # (after the redirect this call ends in) knows to reopen it — the F5
    # rule means that state has to live in the session draft, not in memory
    # held only for this request.
    if request.POST.get("confirmed") != "1":
        reallocation_draft.set_pending_unlock(draft, link_id=link.pk)
        reallocation_draft.save(request.session, draft)
        messages.warning(
            request,
            f"Unlocking demand #{link.part_demand_id}'s claim forces an "
            f"automated purchasing-status update on that demand and may cause "
            f"downstream errors or inconsistencies. Confirm to proceed.",
        )
        return

    context.unlock_claim(link=link, actor=request.user, confirmed=True)
    reallocation_draft.mark_unlocked(draft, link_id=link.pk)
    reallocation_draft.set_proposed(draft, link_id=link.pk, quantity=link.quantity_allocated)
    reallocation_draft.clear_pending_unlock(draft)
    reallocation_draft.save(request.session, draft)
    messages.success(request, f"Demand #{link.part_demand_id}'s claim unlocked.")


def _build_portal_view(draft: dict) -> dict:
    """Assemble the Reallocation Portal's render context (Edit & Linkage's
    binding placement, build_plan.md "Confirmed UI placement").

    `ReallocationPortalStruct.load` re-derives LOCKED/OPEN/external live from
    the DB on every call (§10 point 3 — no cached total); this function's only
    job is to join that live picture against the session draft's in-progress
    proposed values, never to compute or cache a total of its own.
    """
    struct = ReallocationPortalStruct.load(line_id=draft["line_id"])
    proposed = reallocation_draft.proposed_values(draft)
    target = reallocation_draft.to_decimal(draft["new_quantity_ordered"]) or Decimal("0")
    pending_unlock = reallocation_draft.pending_unlock_link_id(draft)
    priority_labels = dict(DemandPriority.choices)

    open_claims = []
    open_total_proposed = Decimal("0")
    for claim in struct.open_claims:
        proposed_qty = proposed.get(claim.link_id, claim.quantity_allocated)
        open_total_proposed += proposed_qty
        open_claims.append(
            {
                "link_id": claim.link_id,
                "demand_id": claim.demand_id,
                "priority_display": priority_labels.get(claim.priority, claim.priority),
                "needed_by": claim.needed_by,
                "current_quantity": claim.quantity_allocated,
                "proposed_quantity": proposed_qty,
                "external_claims": claim.external_claims,
            }
        )

    locked_claims = [
        {
            "link_id": claim.link_id,
            "demand_id": claim.demand_id,
            "priority_display": priority_labels.get(claim.priority, claim.priority),
            "needed_by": claim.needed_by,
            "quantity_allocated": claim.quantity_allocated,
            "external_claims": claim.external_claims,
        }
        for claim in struct.locked_claims
    ]

    running_total = open_total_proposed + struct.locked_total
    return {
        "line_id": struct.line_id,
        "line_number": struct.line_number,
        "po_number": struct.po_number,
        "target_quantity": target,
        "open_claims": open_claims,
        "locked_claims": locked_claims,
        "locked_total": struct.locked_total,
        "open_total_proposed": open_total_proposed,
        "running_total": running_total,
        # A courtesy for the button's disabled state (form_style_guide.md
        # still requires a plain POST work correctly regardless — the real
        # gate is ReallocationValidator.check_commit_ready on submit).
        "commit_ready": running_total == target,
        "pending_unlock_link_id": pending_unlock,
    }


def _reallocation_commit(
    request: HttpRequest, purchase_order: PurchaseOrder, context: PurchaseOrderContext
) -> None:
    draft, line = _load_reallocation_line(request, purchase_order)
    if line is None:
        return
    new_qty = reallocation_draft.to_decimal(draft["new_quantity_ordered"]) or Decimal("0")
    proposed = reallocation_draft.proposed_values(draft)
    open_claims = {c.pk: c for c in _open_claims(line)}
    locked_total = sum((c.quantity_allocated for c in _locked_claims(line)), Decimal("0"))

    resolutions = {
        link_id: proposed.get(link_id, claim.quantity_allocated)
        for link_id, claim in open_claims.items()
    }
    open_total = sum(resolutions.values(), Decimal("0"))

    ReallocationValidator.check_commit_ready(
        open_total=open_total, locked_total=locked_total, new_source_qty=new_qty
    )
    context.apply_reallocation(
        line=line, new_quantity_ordered=new_qty, resolutions=resolutions, actor=request.user
    )
    reallocation_draft.clear(request.session)
    messages.success(request, f"Line {line.line_number}'s reallocation committed.")


def _detail_add_line(request: HttpRequest, context: PurchaseOrderContext) -> None:
    part_id = _int(request.POST.get("part_id"))
    quantity = _decimal(request.POST.get("quantity_ordered"))
    unit_cost = _decimal(request.POST.get("unit_cost"))
    if not part_id or quantity is None or unit_cost is None:
        messages.error(request, "A line needs a part, an ordered quantity, and a unit cost.")
        return

    _line, warning = context.add_line(
        part_id=part_id,
        quantity_ordered=quantity,
        unit_cost=unit_cost,
        expected_delivery_date=(
            request.POST.get("expected_delivery_date")
            or context.purchase_order.expected_delivery_date
        ),
        notes=request.POST.get("line_notes", "").strip(),
        unit_cost_source=(request.POST.get("unit_cost_source") or "").strip(),
        unit_cost_confidence=(request.POST.get("unit_cost_confidence") or "").strip(),
        unit_cost_asserted_at=parse_date((request.POST.get("unit_cost_asserted_at") or "").strip() or ""),
        actor=request.user,
    )
    # D58's duplicate-part rule is a SOFT warning, surfaced and proceeded past.
    if warning:
        messages.warning(request, str(warning))
    messages.success(request, "Line added.")


def _detail_edit_line(
    request: HttpRequest, purchase_order: PurchaseOrder, context: PurchaseOrderContext
) -> None:
    line = _line_on_po(purchase_order, _int(request.POST.get("line_id")))
    if line is None:
        messages.error(request, "That line is not on this purchase order.")
        return

    # TODO(D90): soft lock — a Use-level actor may fill a blank unit_cost but
    # not override one that already exists. Deferred: there is no "Use"
    # authority level in the permission set yet (build_plan.md §7.3), so this
    # currently lets any editor overwrite any line's price unconditionally.
    changes = {}
    for field, caster in (
        ("quantity_ordered", _decimal),
        ("unit_cost", _decimal),
    ):
        if field in request.POST:
            value = caster(request.POST.get(field))
            if value is not None:
                changes[field] = value
    if "expected_delivery_date" in request.POST:
        changes["expected_delivery_date"] = request.POST.get("expected_delivery_date") or None
    if "notes" in request.POST:
        changes["notes"] = request.POST.get("notes", "").strip()
    source = (request.POST.get("unit_cost_source") or "").strip()
    if source:
        changes["unit_cost_source"] = source
        changes["unit_cost_confidence"] = (request.POST.get("unit_cost_confidence") or "").strip()
        asserted_at = parse_date((request.POST.get("unit_cost_asserted_at") or "").strip() or "")
        if asserted_at:
            changes["unit_cost_asserted_at"] = asserted_at

    if not changes:
        messages.info(request, "Nothing to change on that line.")
        return

    try:
        context.edit_line(line=line, changes=changes, actor=request.user)
        messages.success(request, f"Line {line.line_number} updated.")
    except ReallocationRequired as exc:
        # §5's flowchart: 2+ claims short, or the sole claim locked — nothing
        # was saved. Seed the Portal's session draft instead of a flat error;
        # the entrypoint's reallocation_* actions pick it up from here.
        draft = reallocation_draft.empty_draft(
            line_id=line.pk,
            new_quantity_ordered=changes.get("quantity_ordered", line.quantity_ordered),
        )
        reallocation_draft.save(request.session, draft)
        messages.warning(
            request,
            f"{exc.errors[0]} Resolve it through the Reallocation Portal for "
            f"line {line.line_number}.",
        )


def _detail_cancel_line(
    request: HttpRequest, purchase_order: PurchaseOrder, context: PurchaseOrderContext
) -> None:
    line = _line_on_po(purchase_order, _int(request.POST.get("line_id")))
    if line is None:
        messages.error(request, "That line is not on this purchase order.")
        return
    released = context.cancel_line(line=line, actor=request.user)
    messages.success(
        request,
        f"Line {line.line_number} cancelled"
        + (f"; {released} allocation{'s' if released != 1 else ''} released." if released else "."),
    )


def _line_on_po(purchase_order: PurchaseOrder, line_id: int | None) -> PurchaseOrderLine | None:
    """A line id from a form is user input — confirm it belongs to this PO
    before handing it to a manager that would happily edit somebody else's."""
    if not line_id:
        return None
    return PurchaseOrderLine.objects.filter(
        pk=line_id, purchase_order=purchase_order, deleted_at__isnull=True
    ).select_related("part", "purchase_order").first()


def _allocate_from_form(
    request: HttpRequest,
    purchase_order: PurchaseOrder,
    context: PurchaseOrderContext,
    *,
    back: str,
) -> HttpResponse:
    """The real allocate — shared by PO detail's inline editor and Edit &
    Linkage. D28's cap surfaces through the same modal component both times."""
    line = _line_on_po(purchase_order, _int(request.POST.get("line_id")))
    demand_id = _int(request.POST.get("demand_id"))
    quantity = _decimal(request.POST.get("quantity_allocated"))
    auto_approve = request.POST.get("auto_approve") != "0"
    resolution = request.POST.get("cap_resolution", "")

    if line is None or not demand_id:
        messages.error(request, "Pick a line and a demand to allocate.")
        return redirect(back)
    if quantity is None or quantity <= 0:
        messages.error(request, "Allocated quantity must be greater than zero.")
        return redirect(back)

    demand = PartDemand.objects.filter(pk=demand_id, deleted_at__isnull=True).first()
    if demand is None:
        messages.error(request, f"Demand #{demand_id} no longer exists.")
        return redirect(back)

    try:
        context.allocate(
            line=line,
            demand=demand,
            quantity_allocated=quantity,
            actor=request.user,
            auto_approve=auto_approve,
            allow_raise_request=resolution == "raise_request",
        )
    except AllocationCapExceeded as exc:
        _stash_cap_decision(
            request,
            exc,
            form_action=back,
            fields={
                "action": "allocate",
                "line_id": line.pk,
                "demand_id": demand_id,
                "quantity_allocated": quantity,
                "auto_approve": "1" if auto_approve else "0",
            },
            part_label=str(line.part),
        )
        return redirect(back)
    except CrossOrderAllocationExceeded as exc:
        # §10 rule 1: always a hard stop, no raise-the-request offer — the
        # opposite of AllocationCapExceeded's choice above. Rule 2: name the
        # conflicting order and link straight to its own linkage screen.
        conflicting_url = reverse(
            "purchase_order_detail", args=[exc.conflicting_purchase_order_id]
        )
        messages.error(
            request,
            f"{exc.errors[0]} Go to {exc.conflicting_po_number}: {conflicting_url}",
        )
        return redirect(back)
    except ProcurementValidationError as exc:
        _report(request, exc)
        return redirect(back)

    if resolution == "raise_request":
        _raise_request_to_cover(request, demand=demand, quantity=quantity)
    messages.success(request, f"Allocated {quantity} to demand #{demand.pk}.")
    return redirect(back)


def _raise_request_to_cover(request: HttpRequest, *, demand: PartDemand, quantity) -> None:
    """D28's raise-the-request branch, applied after the allocation lands.

    `allow_raise_request=True` only tells the validator to stand down; it does
    not itself move the demand's requested quantity. The factory does this
    explicitly for the wizard's staged allocations, so the post-creation call
    sites must do the same or the "raise" half of the choice silently does
    nothing.
    """
    from app.procurement.control_layer.managers.part_demand_quantity_manager import (
        PartDemandQuantityManager,
    )

    demand.refresh_from_db()
    if demand.purchased_qty <= demand.quantity_requested:
        return
    try:
        PartDemandQuantityManager.raise_requested_quantity(
            demand=demand, new_quantity=demand.purchased_qty, actor=request.user
        )
        messages.warning(
            request,
            f"Demand #{demand.pk}'s requested quantity was raised to "
            f"{demand.purchased_qty} to cover this allocation.",
        )
    except ProcurementValidationError as exc:
        _report(request, exc)


def _delink_from_form(
    request: HttpRequest, purchase_order: PurchaseOrder, context: PurchaseOrderContext
) -> None:
    link = PurchaseOrderDemandLink.objects.filter(
        pk=_int(request.POST.get("link_id")) or 0,
        purchase_order_line__purchase_order=purchase_order,
        deleted_at__isnull=True,
    ).first()
    if link is None:
        messages.error(request, "That allocation is not on this purchase order.")
        return
    demand_id = link.part_demand_id
    context.delink(link=link, actor=request.user)
    messages.success(request, f"Demand #{demand_id} de-linked from this order.")


# ====================================================================== #
# 2.4  purchase_order_edit — PO Edit & Linkage
# ====================================================================== #


@require_http_methods(["GET", "POST"])
def purchase_order_edit(request: HttpRequest, pk: int) -> HttpResponse:
    """The renamed Linkage Portal (`/link` -> `/edit`), now with a real header
    edit form on top.

    Line selection is a client-side-feeling interaction that MUST round-trip
    through the URL (`?line_id=`), because that is how Phase 1's demand pages
    deep-link straight to the relevant line, and because a reload or a bookmark
    has to reproduce the selection. The legacy portal used client-only selection
    with no URL sync; that gap is not repeated here.
    """
    purchase_order = _load_purchase_order(request, pk)

    if request.method == "POST":
        return _edit_post(request, purchase_order)

    return _edit_render(request, purchase_order)


def _edit_render(request: HttpRequest, purchase_order: PurchaseOrder) -> HttpResponse:
    domain_ids = accessible_domain_ids(request)
    fulfillment = PurchaseOrderFulfillmentStruct.load(purchase_order_id=purchase_order.pk)
    lines = _detail_line_views(request, purchase_order, fulfillment)

    selected_line_id = _int(request.GET.get("line_id"))
    selected = next((l for l in lines if l["struct"].line_id == selected_line_id), None)

    # The Reallocation Portal (Demand↔PO Domain) — build_plan.md's "Confirmed
    # UI placement": renders as a full-screen overlay on Edit & Linkage,
    # ONLY when a draft is in progress for the line currently selected on
    # this exact render (backend_handoff.md §4). Navigating to a different
    # line does not chase the user with a portal for a line they left.
    reallocation_portal = None
    draft = reallocation_draft.load(request.session)
    if draft is not None and selected is not None and draft.get("line_id") == selected["struct"].line_id:
        reallocation_portal = _build_portal_view(draft)

    # The right column's top-bottom search tool. Part is LOCKED to the selected
    # line's part, never an override — a demand for a different part cannot be
    # linked here anyway (PurchaseOrderDemandLinkValidator), so an editable part
    # field would only invite a search whose results are all unusable.
    search_filters = {
        "q": request.GET.get("q", "").strip(),
        "priority": request.GET.get("priority", "").strip(),
        "created_from": request.GET.get("created_from", "").strip(),
        "created_to": request.GET.get("created_to", "").strip(),
        "requested_by": request.GET.get("requested_by", "").strip(),
        "po_number": request.GET.get("po_number", "").strip(),
        "part_id": selected["struct"].part_id if selected else None,
    }
    candidates = []
    if selected is not None:
        candidates = list(
            OpenDemandSearch.pool(
                domain_ids=domain_ids,
                exclude_purchase_order=purchase_order,
                part_id=search_filters["part_id"],
                q=search_filters["q"],
                priority=search_filters["priority"],
                created_from=(
                    parse_date(search_filters["created_from"])
                    if search_filters["created_from"]
                    else None
                ),
                created_to=(
                    parse_date(search_filters["created_to"])
                    if search_filters["created_to"]
                    else None
                ),
                requested_by=search_filters["requested_by"],
                linked_po_number=search_filters["po_number"],
            )[:100]
        )

    return render(
        request,
        f"{TEMPLATE_DIR}/edit.html",
        {
            "po": purchase_order,
            "lines": lines,
            "selected": selected,
            "selected_line_id": selected_line_id,
            "candidates": candidates,
            "search_filters": search_filters,
            "priority_choices": DemandPriority.choices,
            "vendors": Vendor.objects.filter(is_active=True).order_by("name"),
            "cap_decision": _pop_cap_decision(request),
            "can_buy": can_buy(request),
            "show_placed_warning": purchase_order.status != PurchaseOrderStatus.DRAFT,
            "portal": reallocation_portal,
            **_status_context(purchase_order),
        },
    )


def _edit_post(request: HttpRequest, purchase_order: PurchaseOrder) -> HttpResponse:
    require_buy(request)
    action = request.POST.get("action", "")
    context = PurchaseOrderContext(purchase_order.pk)

    # Preserve the selected line across the redirect so a save does not dump the
    # Buyer back to "nothing selected" halfway through a linking session.
    line_id = _int(request.POST.get("line_id")) or _int(request.POST.get("selected_line_id"))
    back = reverse("purchase_order_edit", args=[purchase_order.pk])
    if line_id:
        back = f"{back}?line_id={line_id}"

    try:
        if action == "save_header":
            _edit_save_header(request, purchase_order)
        elif action == "allocate":
            return _allocate_from_form(request, purchase_order, context, back=back)
        elif action == "delink":
            _delink_from_form(request, purchase_order, context)
        elif action == "add_line":
            _detail_add_line(request, context)
        elif action == "cancel_line":
            _detail_cancel_line(request, purchase_order, context)
        elif action == "edit_line":
            _detail_edit_line(request, purchase_order, context)
        elif action == "record_receipt":
            # Reallocation Resolution decision — marking a claim received is
            # the sole trigger for locking it (§7.2); mirrors _detail_post's
            # branch so record_receipt resolves back onto Edit & Linkage
            # (routing_decision_pending.md, Option A) instead of PO Detail.
            _detail_record_receipt(request, purchase_order, context)
        elif action == "reallocation_auto_allocate":
            _reallocation_auto_allocate(request, purchase_order)
        elif action == "reallocation_manual_entry":
            _reallocation_manual_entry(request, purchase_order)
        elif action == "reallocation_unlock_claim":
            _reallocation_unlock_claim(request, purchase_order, context)
        elif action == "reallocation_commit":
            _reallocation_commit(request, purchase_order, context)
        elif action == "reallocation_cancel":
            reallocation_draft.clear(request.session)
            messages.info(request, "Reallocation cancelled; the line was not changed.")
        else:
            messages.error(request, "Unrecognised action.")
    except ProcurementValidationError as exc:
        _report(request, exc)

    return redirect(back)


def _edit_save_header(request: HttpRequest, purchase_order: PurchaseOrder) -> None:
    """Header fields only. STATUS CHANGES DO NOT HAPPEN HERE — they have their
    own actions on the detail page, the same edit-vs-status-action split D57
    already draws for lines.

    A header edit on a placed-or-later PO posts a pre-edit snapshot machine
    comment, the same shape as a line edit: permissive, paid for in audit.
    """
    vendor_id = _int(request.POST.get("vendor_id"))
    if not vendor_id or not Vendor.objects.filter(pk=vendor_id).exists():
        messages.error(request, "Choose a vendor.")
        return

    order_date = parse_date(request.POST.get("order_date", "") or "")
    if order_date is None:
        messages.error(request, "An order date is required.")
        return

    snapshot = {
        "vendor_id": purchase_order.vendor_id,
        "vendor_contact": purchase_order.vendor_contact,
        "order_date": str(purchase_order.order_date),
        "expected_delivery_date": str(purchase_order.expected_delivery_date or ""),
        "notes": purchase_order.notes,
    }

    fields = ["vendor", "vendor_contact", "order_date", "expected_delivery_date", "notes",
              "updated_by", "updated_at"]
    purchase_order.vendor_id = vendor_id
    purchase_order.vendor_contact = request.POST.get("vendor_contact", "").strip()
    purchase_order.order_date = order_date
    purchase_order.expected_delivery_date = parse_date(
        request.POST.get("expected_delivery_date", "") or ""
    )
    purchase_order.notes = request.POST.get("notes", "").strip()
    if hasattr(purchase_order, "vendor_po_id"):
        purchase_order.vendor_po_id = request.POST.get("vendor_po_id", "").strip()
        snapshot["vendor_po_id"] = purchase_order.vendor_po_id
        fields.append("vendor_po_id")
    purchase_order.updated_by = request.user
    purchase_order.save(update_fields=fields)

    if purchase_order.status != PurchaseOrderStatus.DRAFT:
        from app.procurement.control_layer.narrators.purchase_order_narrator import (
            PurchaseOrderNarrator,
        )

        PurchaseOrderNarrator.post(
            purchase_order=purchase_order,
            message=(
                "Header edited after placement. Values before the edit: "
                + "; ".join(f"{k}={v}" for k, v in snapshot.items())
            ),
            actor=request.user,
        )

    messages.success(request, "Purchase order header saved.")


# The Basic Shipment Manager's route is declared in this wave's URL module
# because it is PO-scoped, but the page belongs to Phase 3 and its view lives
# in `entrypoints/shipments.py` alongside the rest of the shipment sector. PO
# detail links to it by name.
