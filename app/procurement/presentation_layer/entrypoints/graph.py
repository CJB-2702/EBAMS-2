"""The graph visualizer — the only page in the app that renders GraphSummary
membership directly (D85). Every other page keeps using an entity's own
`graph_id`-scoped rollup numbers (D81); this is the exception.

MATERIALIZED READ, NO TRAVERSAL. `PoDemandAssociationGraphResolver` (D70 §3.5)
is not built (D79) — this view reads `GraphSummary` and its three member
querysets straight off their `graph_id` FKs, plus the two edge tables
(`PurchaseOrderDemandLink`, `ShipmentLine.purchase_order_line`), and hands the
result to `MermaidSwimlaneBuilder` for pure string assembly. No BFS, no
recursion, nothing resembling the resolver D79 retired.
"""

from __future__ import annotations

from decimal import Decimal

from django.db.models import DecimalField, Q, Sum
from django.db.models.functions import Coalesce
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from app.procurement.models import (
    GraphSummary,
    PartDemand,
    PurchaseOrderDemandLink,
    PurchaseOrderLine,
    ShipmentLine,
)
from app.procurement.presentation_layer.tools.procurement_access import (
    is_in_domain,
)

TEMPLATE_DIR = "procurement/graph"


@require_http_methods(["GET"])
def procurement_graph_visualizer(request: HttpRequest, graph_id: int) -> HttpResponse:
    """Renders `GraphSummary` #graph_id: its eight metrics + status (D81) at
    the top, a mermaid swimlane diagram of its Demand/PO-Line/Shipment-Line
    membership and edges (D85) in the middle, and a three-column member
    summary below.

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

    demand_ids = {d.pk for d in demands}
    po_line_ids = {l.pk for l in po_lines}

    demand_po_edges = []
    if po_line_ids:
        demand_po_edges = [
            (demand_id, po_line_id)
            for demand_id, po_line_id in PurchaseOrderDemandLink.objects.filter(
                is_active=True,
                deleted_at__isnull=True,
                purchase_order_line_id__in=po_line_ids,
            ).values_list("part_demand_id", "purchase_order_line_id")
            # Defensive: only edges whose demand side is also a member of this
            # graph. A materialized graph should never disagree with itself,
            # but this guards against a read landing mid-recalculation.
            if demand_id in demand_ids
        ]

    po_shipment_edges = [
        (sl.purchase_order_line_id, sl.pk)
        for sl in shipment_lines
        if sl.purchase_order_line_id in po_line_ids
    ]

    for demand in demands:
        demand.is_linkable = is_in_domain(request, demand.domain_id)
    for line in po_lines:
        line.is_linkable = is_in_domain(request, line.purchase_order.domain_id)
    for shipment_line in shipment_lines:
        shipment_line.is_linkable = is_in_domain(
            request, shipment_line.shipment.domain_id
        )

    mermaid_source = MermaidSwimlaneBuilder.build(
        demands=demands,
        po_lines=po_lines,
        shipment_lines=shipment_lines,
        demand_po_edges=demand_po_edges,
        po_shipment_edges=po_shipment_edges,
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
            "mermaid_source": mermaid_source,
        },
    )


class MermaidSwimlaneBuilder:
    """Turns a graph's member rows and edges into mermaid `flowchart LR`
    source — three subgraphs (swimlanes), one per member type, edges drawn
    between them. Pure string assembly from data the view already loaded; no
    business logic (model_patterns.md/standards.md) — same "struct assembles,
    never decides" discipline as every other presentation-layer struct in
    this app.
    """

    @staticmethod
    def build(
        *, demands, po_lines, shipment_lines, demand_po_edges, po_shipment_edges
    ) -> str:
        lines: list[str] = ["flowchart LR"]

        lines.append('  subgraph Demands["Demands"]')
        if demands:
            for demand in demands:
                label = MermaidSwimlaneBuilder._escape(
                    f"D{demand.pk}: {demand.part.part_number} x{demand.quantity_requested}"
                )
                lines.append(f'    D{demand.pk}["{label}"]')
        else:
            lines.append('    D_empty["(none)"]')
        lines.append("  end")

        lines.append('  subgraph POLines["PO Lines"]')
        if po_lines:
            for line in po_lines:
                label = MermaidSwimlaneBuilder._escape(
                    f"P{line.pk}: {line.purchase_order.po_number} L{line.line_number} "
                    f"{line.part.part_number} x{line.quantity_ordered}"
                )
                lines.append(f'    P{line.pk}["{label}"]')
        else:
            lines.append('    P_empty["(none)"]')
        lines.append("  end")

        lines.append('  subgraph ShipmentLines["Shipment Lines"]')
        if shipment_lines:
            for shipment_line in shipment_lines:
                label = MermaidSwimlaneBuilder._escape(
                    f"S{shipment_line.pk}: {shipment_line.shipment.shipment_number} "
                    f"{shipment_line.part.part_number} x{shipment_line.quantity}"
                )
                lines.append(f'    S{shipment_line.pk}["{label}"]')
        else:
            lines.append('    S_empty["(none)"]')
        lines.append("  end")

        for demand_id, po_line_id in demand_po_edges:
            lines.append(f"  D{demand_id} --> P{po_line_id}")
        for po_line_id, shipment_line_id in po_shipment_edges:
            lines.append(f"  P{po_line_id} --> S{shipment_line_id}")

        return "\n".join(lines)

    @staticmethod
    def _escape(text: str) -> str:
        # Mermaid node labels choke on double quotes and square brackets; a
        # plain part number / PO number never legitimately contains either, so
        # a straight substitution is enough — no need for a real escaper.
        return text.replace('"', "'").replace("[", "(").replace("]", ")")
