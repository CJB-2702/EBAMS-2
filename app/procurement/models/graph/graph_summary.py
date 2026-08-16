from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.procurement.models.demand.enums import DemandPriority
from app.procurement.models.graph.enums import (
    GraphResolutionState,
    GraphSummaryStatus,
    LinearStatus,
    POImbalanceState,
    ShipmentImbalanceState,
)


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

    A GRAPH IS NOT A THING ANYONE CREATES. It forms, merges, splits, and dies
    as a side effect of writes to demands, PO lines, and shipment lines, none
    of it visible to the user doing the writing. There is no create page, and
    despite three reverse FKs pointing at this table, no wizard follows from
    them — the usual "more than one reverse FK a user populates in one sitting"
    heuristic reads three here and would be wrong. A user never populates any
    of them.

    No business logic lives here (model_patterns.md).

    ── THE ONE RULE THAT IS EASY TO BREAK ──────────────────────────────────
    Every column on this model is written exclusively by
    GraphSummaryManager.recalculate() and never assigned directly by a caller
    — EXCEPT the three human-judgment columns at the bottom:

        resolution_state, manually_flagged, priority

    Those three are written ONLY by GraphResolutionManager and recalculate()
    must never touch them. This inverts the discipline of every other column
    here, and the surrounding convention is uniform enough that the natural
    assumption ("everything on this model is derived") will silently wipe a
    user's input on the next recalculate. Stated here because a docstring is
    the only thing standing between that assumption and a data-loss bug.
    """

    # ── Identity and scope ──────────────────────────────────────────────────
    # A graph may never hold members for more than one part — a disagreement
    # is a bug in the guard chain, not a data condition to tolerate, and
    # tolerating it would file the graph under the wrong part in every search
    # from then on. recalculate() sets this from any member and asserts the
    # rest agree.
    #
    # NULLABLE IS A TECHNICAL NECESSITY OF THE CREATE SEQUENCE, not a real
    # "partless graph" state — exactly the same reasoning as the `graph` FK on
    # each member row. GraphSummaryManager.initialize_node() must INSERT this
    # row before it can point a member at it, so there is a moment inside that
    # one transaction where no member exists to read a part from. Outside that
    # transaction a GraphSummary is never observed with part unset. Do not
    # read the null as meaning cross-part graphs are permitted; they are not.
    #
    # This makes PurchaseOrderDemandLinkValidator's part-match rule
    # LOAD-BEARING. That rule is a soft validator check kept out of the
    # database precisely so it could be relaxed later for kits, substitutes,
    # or vendor cross-references. That door is now closed.
    part = models.ForeignKey(
        "parts.Part",
        on_delete=models.PROTECT,
        related_name="graphs",
        null=True,
        blank=True,
    )

    # The scoping guard for SEARCH only. Derived as the most common domain by
    # PO-line count, with a fallback chain: PO lines, then demands, then
    # shipment lines. Ties broken by lowest domain id.
    #
    # Determinism is not a nicety. recalculate() fires constantly, and a
    # primary_domain that flapped between two equally-common domains would
    # make graphs appear and disappear from people's search results with no
    # user-visible cause.
    #
    # KNOWN LOSSY SIMPLIFICATION: a graph's members can legitimately span
    # domains and one FK cannot represent that. Accepted to keep the hot
    # search path a single indexed column. The consequence is that a graph
    # whose primary_domain is not yours, but which contains your member, is
    # reachable by clicking through from your own entity yet absent from your
    # search. First thing to revisit if users report "I know that graph exists
    # but I cannot find it."
    primary_domain = models.ForeignKey(
        "administration.Domain",
        on_delete=models.PROTECT,
        related_name="primary_graphs",
        null=True,
        blank=True,
    )

    # ── Quantities: the inputs every status axis is derived from ────────────
    # Sum of quantity_requested across member demands.
    demand_qty = models.DecimalField(max_digits=12, decimal_places=3, default=0)

    # Sum of PurchaseOrderDemandLink.quantity_allocated over active, non-deleted
    # links to member PO lines. Units spoken for on any PO, draft or placed.
    #
    # FAN-OUT TRAP: this sums across a SECOND multi-row relation relative to
    # the member-line queryset. A joined Sum() alongside another multi-row
    # relation silently multiplies — the exact bug class already caught once in
    # PurchaseOrderFulfillmentStruct (D67). It must be its own query over
    # PurchaseOrderDemandLink filtered by purchase_order_line__graph_id, never
    # annotated onto the line queryset.
    po_qty_allocated = models.DecimalField(
        max_digits=12, decimal_places=3, default=0
    )
    # The same sum, restricted to links whose line's PurchaseOrder reached
    # Placed or later. Units on real, placed orders.
    #
    # NOTE THE CHANGE OF MEANING: this used to be a sum of
    # PurchaseOrderLine.quantity_ordered. It is now allocation-based, so that
    # it is comparable with demand_qty. See POImbalanceState's docstring.
    po_qty_purchased = models.DecimalField(
        max_digits=12, decimal_places=3, default=0
    )

    # Sum of PurchaseOrderShipmentLink.quantity_allocated over non-deleted
    # links from member shipment lines. Units on incoming shipments that
    # somebody has mapped to a PO line. Same fan-out trap as po_qty_allocated
    # — its own query, never an annotation.
    shipment_qty_allocated = models.DecimalField(
        max_digits=12, decimal_places=3, default=0
    )
    # Sum of ShipmentLine.quantity_accepted across member lines. THE arrival
    # figure. An uninspected line (quantity_accepted IS NULL) contributes
    # nothing, which is meaningfully different from a line inspected and fully
    # rejected.
    shipment_qty_accepted = models.DecimalField(
        max_digits=12, decimal_places=3, default=0
    )

    # ── D81's original metric columns, retained ─────────────────────────────
    # These predate the allocation-based columns above and are still read by
    # the graph detail template and the existing narrators. They measure
    # physical shipment movement rather than commercial commitment.
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

    # ── The three derived status axes (D9) ──────────────────────────────────
    # Independent, each with its own precedence chain, none writing another.
    # See models/graph/enums.py for why this is three columns and not one.
    linear_status = models.CharField(
        max_length=40,
        choices=LinearStatus.choices,
        default=LinearStatus.UNLINKED,
    )
    po_imbalance_state = models.CharField(
        max_length=40,
        choices=POImbalanceState.choices,
        default=POImbalanceState.BALANCED,
    )
    shipment_imbalance_state = models.CharField(
        max_length=45,
        choices=ShipmentImbalanceState.choices,
        default=ShipmentImbalanceState.BALANCED,
    )

    # A plain key naming an end-state mismatch, rendered as human language at
    # read time. A KEY, NOT A SENTENCE: the states are schema and change
    # rarely, the wording is judgment and will be tuned for months, and storing
    # the sentence would mean a migration and a full-table recalculate every
    # time somebody improves a phrase.
    #
    # Never accusatory when rendered. A vendor overship is usually the system
    # learning a vendor fact late, not anybody's mistake: "12 more units
    # arrived than were ordered", never "excess receipt discrepancy".
    error_code = models.CharField(max_length=60, blank=True, default="")

    # The original plain label (D81/D86). Superseded in intent by
    # linear_status but still read by existing templates and narrators.
    status = models.CharField(
        max_length=30,
        choices=GraphSummaryStatus.choices,
        default=GraphSummaryStatus.BALANCED,
    )

    # Derived-only cache of the mermaid `flowchart LR` swimlane diagram
    # source for this graph's membership and edges (D88). Recomputed by
    # recalculate() so the graph visualizer view reads a cached column instead
    # of rebuilding the diagram on every request.
    swimlane_diagram = models.TextField(blank=True, default="")

    # ── Human judgment — the ONLY columns recalculate() never touches ───────
    # Written exclusively by GraphResolutionManager. See the class docstring:
    # this inverts the discipline of every column above, and assuming
    # otherwise silently destroys user input.
    #
    # resolution_state and manually_flagged CLEAR on merge and split; priority
    # PROPAGATES. The principle: anything derived from a graph's configuration
    # clears when the configuration changes, anything expressing human
    # judgment about importance survives it. A resolution is a statement about
    # a specific set of nodes — when nodes join or leave, the thing that was
    # looked at no longer exists. Priority is about the underlying work, which
    # restructuring does not invalidate.
    #
    # Keeping the survivor's resolution through a merge was considered and
    # rejected: a resolved graph would silently absorb an unresolved one and
    # stay resolved, making the absorbed graph's problem vanish without anyone
    # addressing it.
    resolution_state = models.CharField(
        max_length=20,
        choices=GraphResolutionState.choices,
        default=GraphResolutionState.OPEN,
    )
    manually_flagged = models.BooleanField(default=False)
    # Reuses DemandPriority rather than inventing a parallel vocabulary.
    # Nullable: most graphs never get one, and "nobody has ranked this" is a
    # real state rather than a default of medium.
    priority = models.CharField(
        max_length=20,
        choices=DemandPriority.choices,
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "graph_summary"
        ordering = ["-created_at"]
        indexes = [
            # The part-scoped surface: "what is happening for this part".
            models.Index(fields=["part"], name="graph_part_idx"),
            # The search scope guard (D4) — one indexed column, which is the
            # entire point of storing primary_domain at all.
            models.Index(fields=["primary_domain"], name="graph_domain_idx"),
            # The part surface filtered by scope, which is the common
            # combination rather than either column alone.
            models.Index(
                fields=["primary_domain", "part"], name="graph_domain_part_idx"
            ),
            # The three filterable status axes. Staff filter the graph list
            # directly on these columns; there is no precedence ranking across
            # axes and no single "needs attention" column to filter instead.
            models.Index(
                fields=["po_imbalance_state"], name="graph_po_imbalance_idx"
            ),
            models.Index(
                fields=["shipment_imbalance_state"], name="graph_ship_imbal_idx"
            ),
            models.Index(fields=["linear_status"], name="graph_linear_idx"),
            # The human columns, filtered alongside the axes above.
            models.Index(
                fields=["resolution_state", "manually_flagged"],
                name="graph_resolution_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"GraphSummary #{self.pk}"
