"""The graph visualizer — the only page in the app that renders GraphSummary
membership directly (D85). Every other page keeps using an entity's own
`graph_id`-scoped rollup numbers (D81); this is the exception.

MATERIALIZED READ, NO TRAVERSAL. `PoDemandAssociationGraphResolver` (D70 §3.5)
is not built (D79) — this view reads `GraphSummary` and its three member
querysets straight off their `graph_id` FKs for the member-list table below
the diagram. The mermaid diagram itself is read straight off
`GraphSummary.swimlane_diagram` (D88 follow-up) — GraphSummaryManager.recalculate()
keeps it cached, so this view never rebuilds it from scratch. No BFS, no
recursion, nothing resembling the resolver D79 retired.
"""

from __future__ import annotations

from decimal import Decimal

from django.db.models import DecimalField, Q, Sum
from django.db.models.functions import Coalesce
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from app.procurement.models import GraphSummary, PartDemand, PurchaseOrderLine, ShipmentLine
from app.procurement.presentation_layer.tools.procurement_access import (
    is_in_domain,
)

TEMPLATE_DIR = "procurement/graph"


@require_http_methods(["GET"])
def procurement_graph_visualizer(request: HttpRequest, graph_id: int) -> HttpResponse:
    """Renders `GraphSummary` #graph_id: its eight metrics + status (D81) at
    the top, its cached mermaid swimlane diagram (D85/D88) of
    Demand/PO-Line/Shipment-Line membership and edges in the middle, and a
    three-column member summary below.

    No domain fence on the graph lookup itself — a `GraphSummary` is not
    itself domain-owned; each MEMBER is (a demand/PO-line/shipment-line each
    carries its own domain through its parent). A member outside the viewer's
    accessible domains still renders — plain text, no link through — the same
    cross-domain-reference rule every other page in this sector already
    follows (Phase 0 §5). Never a 404 on the whole graph just because one
    member happens to be out of fence.
    """
    try:
        summary = GraphSummary.objects.get(pk=graph_id)
    except GraphSummary.DoesNotExist:
        raise Http404

    demands = list(
        PartDemand.objects.filter(graph_id=graph_id, deleted_at__isnull=True)
        .select_related("part", "domain")
        .order_by("pk")
    )
    po_lines = list(
        PurchaseOrderLine.objects.filter(graph_id=graph_id, deleted_at__isnull=True)
        .select_related(
            "purchase_order", "purchase_order__vendor", "purchase_order__domain", "part"
        )
        .annotate(
            # A single-relation Sum() only — never alongside another joined
            # multi-row relation on the same queryset, the exact fan-out bug
            # D67 already caught once (see GraphSummaryManager's own comment).
            qty_allocated=Coalesce(
                Sum(
                    "allocations__quantity_allocated",
                    filter=Q(allocations__is_active=True, allocations__deleted_at__isnull=True),
                    output_field=DecimalField(max_digits=12, decimal_places=3),
                ),
                Decimal("0"),
                output_field=DecimalField(max_digits=12, decimal_places=3),
            )
        )
        .order_by("pk")
    )
    shipment_lines = list(
        ShipmentLine.objects.filter(graph_id=graph_id, deleted_at__isnull=True)
        .select_related("shipment", "shipment__domain", "purchase_order_line", "part")
        .order_by("pk")
    )

    for demand in demands:
        demand.is_linkable = is_in_domain(request, demand.domain_id)
    for line in po_lines:
        line.is_linkable = is_in_domain(request, line.purchase_order.domain_id)
    for shipment_line in shipment_lines:
        shipment_line.is_linkable = is_in_domain(
            request, shipment_line.shipment.domain_id
        )

    metrics = [
        {"label": "Demand qty", "value": summary.demand_qty},
        {"label": "PO qty waiting to purchase", "value": summary.po_qty_waiting_for_purchase},
        {"label": "PO qty purchased", "value": summary.po_qty_purchased},
        {"label": "Shipments in route", "value": summary.qty_shipments_in_route},
        {"label": "Shipments delivered", "value": summary.qty_shipments_delivered},
        {"label": "Qty accepted", "value": summary.qty_accepted},
        {"label": "Qty rejected", "value": summary.qty_rejected},
        {"label": "Intake recorded", "value": summary.intake_qty_recorded},
    ]

    return render(
        request,
        f"{TEMPLATE_DIR}/detail.html",
        {
            "summary": summary,
            "metrics": metrics,
            "demands": demands,
            "po_lines": po_lines,
            "shipment_lines": shipment_lines,
            "mermaid_source": summary.swimlane_diagram,
        },
    )
