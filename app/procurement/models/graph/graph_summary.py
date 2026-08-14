from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.procurement.models.graph.enums import GraphSummaryStatus


class GraphSummary(AuditFieldsMixin):
    """One row per connected component of the Demand / PO-Line / Shipment-Line
    execution network (D79-D82).

    MATERIALIZED, NOT COMPUTED ON READ. D70's on-demand
    PoDemandAssociationGraphResolver design is reversed (D79): every member
    row of the network — PartDemand, PurchaseOrderLine, ShipmentLine — carries
    a direct `graph_id` FK back to its GraphSummary, so any routine page gets
    cluster-wide numbers with a plain `WHERE graph_id = X`, never a join
    fan-out or an on-request traversal. GraphSummaryManager is the only
    writer: node-init on isolated creation, a coalescing merge when a link is
    created, a bounded BFS split when a link is severed, and a single
    recalculate() entrypoint that is always the last step of the other three.

    No business logic lives here (model_patterns.md) — every column below is
    written exclusively by GraphSummaryManager, never assigned directly by a
    caller, same discipline as PartDemand's four state-axis snapshot columns.
    """

    # ── D81's eight metric columns ──────────────────────────────────────────
    demand_qty = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    po_qty_waiting_for_purchase = models.DecimalField(
        max_digits=12, decimal_places=3, default=0
    )
    po_qty_purchased = models.DecimalField(
        max_digits=12, decimal_places=3, default=0
    )
    qty_shipments_in_route = models.DecimalField(
        max_digits=12, decimal_places=3, default=0
    )
    qty_shipments_delivered = models.DecimalField(
        max_digits=12, decimal_places=3, default=0
    )
    qty_accepted = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    qty_rejected = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    # ALWAYS 0 THIS BUILD (D81). No intake table exists yet (D47) — there is
    # nothing to count. The column exists now purely so the metric has a home
    # and this is wired up when the Inventory intake build lands; it is
    # documented here as always-zero, not silently omitted, so a future
    # reader does not mistake a permanent 0 for a bug.
    intake_qty_recorded = models.DecimalField(
        max_digits=12, decimal_places=3, default=0
    )

    # Derived-only, never set by a caller directly — same discipline as
    # PartDemand's four state axes (D22/D65). Recomputed by
    # GraphSummaryManager.recalculate() alongside the eight columns above.
    status = models.CharField(
        max_length=30,
        choices=GraphSummaryStatus.choices,
        default=GraphSummaryStatus.BALANCED,
    )

    class Meta:
        db_table = "graph_summary"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"GraphSummary #{self.pk}"
