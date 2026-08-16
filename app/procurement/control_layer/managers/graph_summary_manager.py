"""Manager: the whole GraphSummary lifecycle — node-init, merge, split,
recalculate (D79-D82).

MATERIALIZED, NOT ON-DEMAND. D70's PoDemandAssociationGraphResolver design is
reversed (D79): the Demand/PO-Line/Shipment-Line network is a set of
connected components, each backed by one GraphSummary row, with a plain
`graph_id` FK sitting directly on every member row. This manager is the ONLY
writer of `graph_id` and of every GraphSummary column — no other class ever
assigns either.

Four operations, wired into the existing write paths that already own graph
membership changes (no new write path is introduced solely for graph
maintenance):

  initialize_node    A PartDemand / PurchaseOrderLine / ShipmentLine created
                      with no link yet gets its own fresh single-member graph,
                      in the same transaction as its own creation. Called from
                      PartDemandFactory, PurchaseOrderLineManager.add_line,
                      ShipmentLineManager.add_line.

  merge               Creating an active PurchaseOrderDemandLink, or a
                      PurchaseOrderShipmentLink joining a ShipmentLine to a
                      PurchaseOrderLine in a different graph, coalesces the
                      two graphs. Every member of the
                      SMALLER graph (by row count) is re-pointed onto the
                      LARGER graph's id — cheap because these clusters stay
                      small (D70's sparsity argument) — the absorbed
                      GraphSummary row is deleted, and the survivor is
                      recalculated. Wired into
                      PurchaseOrderDemandLinkManager.allocate() and
                      ShipmentLineManager.allocate().

  split_if_disconnected
                      Deactivating a PurchaseOrderDemandLink, or releasing a
                      PurchaseOrderShipmentLink, may sever the
                      only bridge holding a graph together. Runs a bounded BFS
                      over the graph's own remaining active edges from an
                      arbitrary surviving member (`seed_entity`); if some
                      members are unreachable, they are re-pointed onto a
                      freshly created GraphSummary and both summaries are
                      recalculated. No separate safety cap is needed the way
                      D70 section 3.5's resolver needed one — membership is
                      already bounded by the graph itself, not an unbounded
                      traversal target. Wired into
                      PurchaseOrderDemandLinkManager.delink()/remove_for_line()
                      and ShipmentLineManager.deallocate().

  recalculate         Recomputes D81's eight quantity columns plus `status`
                      from current member rows. Every metric is its own
                      single-table aggregate with only forward (to-one) joins
                      (PurchaseOrderLine -> PurchaseOrder, ShipmentLine ->
                      Shipment) — never a joined Sum() alongside another
                      multi-row relation in the same queryset, the exact bug
                      class D67 already caught once in
                      PurchaseOrderFulfillmentStruct. Also rebuilds and caches
                      the mermaid swimlane diagram source onto
                      `swimlane_diagram` (D88 follow-up), via
                      MermaidSwimlaneBuilder in domain_structs/, so the graph
                      visualizer view reads a cached column instead of
                      rebuilding the diagram on every request. Called at the
                      end of every operation above — never left for a caller
                      to remember separately.

No `commit` parameter anywhere here (D66): every method below writes
immediately, participating in whatever transaction the caller already holds,
rather than silently no-op'ing the way the pre-D66 quantity manager bug did.
"""

from __future__ import annotations

from collections import defaultdict, deque
from decimal import Decimal

from django.db.models import Count, DecimalField, F, Sum
from django.db.models.functions import Coalesce

from app.procurement.control_layer.domain_structs.graph_diagram_struct import (
    MermaidSwimlaneBuilder,
)
from app.procurement.control_layer.managers.graph_resolution_manager import (
    GraphResolutionManager,
)
from app.procurement.models import (
    GraphSummary,
    GraphSummaryStatus,
    LinearStatus,
    PartDemand,
    POImbalanceState,
    PurchaseOrderDemandLink,
    PurchaseOrderLine,
    PurchaseOrderShipmentLink,
    PurchaseOrderStatus,
    ShipmentImbalanceState,
    ShipmentLine,
    ShipmentStatus,
)

_DECIMAL = DecimalField(max_digits=14, decimal_places=3)

#: Shipment statuses counted as "in route" for D81's qty_shipments_in_route —
#: everything past Awaiting Shipment, short of arriving locally.
_IN_ROUTE_STATUSES = frozenset(
    {
        ShipmentStatus.SHIPPED,
        ShipmentStatus.DELIVERED_TO_DEPOT,
        ShipmentStatus.BACKORDERED,
    }
)
#: Shipment statuses counted as "delivered" for D81's qty_shipments_delivered.
_DELIVERED_STATUSES = frozenset(
    {ShipmentStatus.DELIVERED_TO_LOCAL, ShipmentStatus.ACCEPTED}
)
#: PurchaseOrder statuses meaning "purchased" for D81's po_qty_purchased —
#: everything past Draft that was not cancelled.
_PURCHASED_PO_STATUSES = frozenset(
    {
        PurchaseOrderStatus.PLACED,
        PurchaseOrderStatus.PARTIALLY_RECEIVED,
        PurchaseOrderStatus.RECEIVED,
    }
)


class GraphSummaryManager:
    # ------------------------------------------------------------------ #
    # Node init
    # ------------------------------------------------------------------ #

    @classmethod
    def initialize_node(cls, *, entity, actor=None) -> GraphSummary:
        """Give an isolated PartDemand / PurchaseOrderLine / ShipmentLine its
        own fresh single-member GraphSummary.

        `entity` must already be saved (it needs a pk to be a graph member).
        Call this only for a row created with no link yet — a row created
        as part of the same wizard step that immediately links it should
        instead rely on the subsequent merge() to fold it into the other
        side's graph without ever holding a throwaway single-member row.
        """
        summary = GraphSummary.objects.create(created_by=actor, updated_by=actor)
        entity.graph = summary
        entity.updated_by = actor
        entity.save(update_fields=["graph", "updated_by", "updated_at"])
        cls.recalculate(graph_id=summary.pk)
        return summary

    # ------------------------------------------------------------------ #
    # Merge
    # ------------------------------------------------------------------ #

    @classmethod
    def merge(cls, *, graph_id_a: int, graph_id_b: int, actor=None) -> int:
        """Coalesce two graphs into one. Returns the surviving graph_id.

        No-op (returns graph_id_a unchanged) when the two ids are already the
        same graph — the common case once a cluster has grown past its first
        link, where a second allocation on an already-shared line lands both
        sides in the same graph already.
        """
        if graph_id_a == graph_id_b:
            return graph_id_a

        count_a = cls._member_count(graph_id=graph_id_a)
        count_b = cls._member_count(graph_id=graph_id_b)
        # Larger membership survives; a tie survives on the lower id so the
        # choice is deterministic rather than incidental.
        if count_b > count_a:
            survivor, absorbed = graph_id_b, graph_id_a
        else:
            survivor, absorbed = graph_id_a, graph_id_b

        # Capture the absorbed graph's human columns BEFORE deleting the row —
        # the survival principle needs them and they are about to be gone.
        absorbed_resolution = (
            GraphSummary.objects.filter(pk=absorbed)
            .values("manually_flagged", "priority")
            .first()
            or {}
        )

        cls._repoint_all_members(
            from_graph_id=absorbed, to_graph_id=survivor, actor=actor
        )
        GraphSummary.objects.filter(pk=absorbed).delete()
        cls.recalculate(graph_id=survivor)
        # Applied AFTER recalculate, not before: recalculate deliberately does
        # not touch these three columns, so ordering is not a correctness
        # matter, but doing it last keeps "derived first, human last" readable.
        GraphResolutionManager.carry_through_merge(
            survivor_id=survivor,
            absorbed_resolution=absorbed_resolution,
            actor=actor,
        )
        return survivor

    # ------------------------------------------------------------------ #
    # Split
    # ------------------------------------------------------------------ #

    @classmethod
    def split_if_disconnected(
        cls, *, graph_id: int, seed_entity, actor=None
    ) -> GraphSummary | None:
        """After an edge was removed from `graph_id`, check whether the graph
        is still one connected piece.

        Runs a BFS over the graph's remaining active edges starting from
        `seed_entity` (any current member — typically one side of the edge
        that was just removed). If some members are unreachable from the
        seed, they are the severed half: re-pointed onto a freshly created
        GraphSummary, and both resulting summaries are recalculated. Returns
        the new GraphSummary, or None if the graph is still fully connected
        (or `seed_entity` no longer belongs to `graph_id` at all).
        """
        members = cls._member_ids(graph_id=graph_id)
        seed_key = cls._node_key(seed_entity)
        if seed_key[1] not in members[seed_key[0]]:
            return None

        all_nodes = {
            (kind, pk) for kind, ids in members.items() for pk in ids
        }
        adjacency = cls._adjacency(members=members)

        visited = {seed_key}
        queue = deque([seed_key])
        while queue:
            node = queue.popleft()
            for neighbor in adjacency.get(node, ()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

        unreached = all_nodes - visited
        if not unreached:
            return None

        new_summary = GraphSummary.objects.create(created_by=actor, updated_by=actor)
        unreached_by_kind: dict[str, list[int]] = defaultdict(list)
        for kind, pk in unreached:
            unreached_by_kind[kind].append(pk)

        if unreached_by_kind["demand"]:
            PartDemand.objects.filter(pk__in=unreached_by_kind["demand"]).update(
                graph_id=new_summary.pk, updated_by=actor
            )
        if unreached_by_kind["po_line"]:
            PurchaseOrderLine.objects.filter(
                pk__in=unreached_by_kind["po_line"]
            ).update(graph_id=new_summary.pk, updated_by=actor)
        if unreached_by_kind["shipment_line"]:
            ShipmentLine.objects.filter(
                pk__in=unreached_by_kind["shipment_line"]
            ).update(graph_id=new_summary.pk, updated_by=actor)

        cls.recalculate(graph_id=graph_id)
        cls.recalculate(graph_id=new_summary.pk)
        GraphResolutionManager.carry_through_split(
            origin_id=graph_id, new_graph_id=new_summary.pk, actor=actor
        )
        return new_summary

    # ------------------------------------------------------------------ #
    # Recalculate
    # ------------------------------------------------------------------ #

    @classmethod
    def recalculate(cls, *, graph_id: int) -> GraphSummary:
        """Recompute D81's eight metric columns plus `status` from current
        member rows. The single entrypoint every other method above ends
        with."""
        summary = GraphSummary.objects.get(pk=graph_id)

        demand_qty = cls._sum(
            PartDemand.objects.filter(graph_id=graph_id, deleted_at__isnull=True),
            "quantity_requested",
        )

        po_lines = PurchaseOrderLine.objects.filter(
            graph_id=graph_id, deleted_at__isnull=True
        )

        # ── The allocation-based quantities ─────────────────────────────────
        # THESE ARE THEIR OWN QUERIES, DELIBERATELY. Each sums across a second
        # multi-row relation (PurchaseOrderDemandLink, PurchaseOrderShipmentLink)
        # relative to the member-line queryset above. A joined Sum() alongside
        # another multi-row relation fans out and silently multiplies — the
        # exact bug class already caught once in PurchaseOrderFulfillmentStruct
        # (D67). Never annotate these onto `po_lines` or `shipment_lines`, no
        # matter how much tidier one query looks.
        demand_links = PurchaseOrderDemandLink.objects.filter(
            purchase_order_line__graph_id=graph_id,
            purchase_order_line__deleted_at__isnull=True,
            is_active=True,
            deleted_at__isnull=True,
        )
        po_qty_allocated = cls._sum(demand_links, "quantity_allocated")
        po_qty_purchased = cls._sum(
            demand_links.filter(
                purchase_order_line__purchase_order__status__in=_PURCHASED_PO_STATUSES
            ),
            "quantity_allocated",
        )

        shipment_lines = ShipmentLine.objects.filter(
            graph_id=graph_id, deleted_at__isnull=True
        )
        shipment_qty_allocated = cls._sum(
            PurchaseOrderShipmentLink.objects.filter(
                shipment_line__graph_id=graph_id,
                shipment_line__deleted_at__isnull=True,
                deleted_at__isnull=True,
            ),
            "quantity_allocated",
        )
        # The arrival figure. An uninspected line contributes nothing, which is
        # meaningfully different from a line inspected and fully rejected.
        shipment_qty_accepted = cls._sum(
            shipment_lines.filter(quantity_accepted__isnull=False),
            "quantity_accepted",
        )

        # po_qty_waiting_for_purchase is RETIRED (D17). It was
        # `po_qty_ordered - po_qty_purchased`, and storing a difference
        # alongside both of its operands is three places for two facts to
        # disagree. Compute it at the point of display if a screen wants it.
        qty_shipments_in_route = cls._sum(
            shipment_lines.filter(shipment__status__in=_IN_ROUTE_STATUSES),
            "quantity",
        )
        qty_shipments_delivered = cls._sum(
            shipment_lines.filter(shipment__status__in=_DELIVERED_STATUSES),
            "quantity",
        )
        inspected = shipment_lines.filter(quantity_accepted__isnull=False)
        qty_accepted = cls._sum(inspected, "quantity_accepted")
        qty_rejected = inspected.aggregate(
            total=Coalesce(
                Sum(F("quantity") - F("quantity_accepted"), output_field=_DECIMAL),
                Decimal("0"),
                output_field=_DECIMAL,
            )
        )["total"]

        # Always 0 this build (D81) — no intake table exists yet.
        intake_qty_recorded = Decimal("0")

        summary.demand_qty = demand_qty
        summary.po_qty_allocated = po_qty_allocated
        summary.po_qty_purchased = po_qty_purchased
        summary.shipment_qty_allocated = shipment_qty_allocated
        summary.shipment_qty_accepted = shipment_qty_accepted
        summary.qty_shipments_in_route = qty_shipments_in_route
        summary.qty_shipments_delivered = qty_shipments_delivered
        summary.qty_accepted = qty_accepted
        summary.qty_rejected = qty_rejected
        summary.intake_qty_recorded = intake_qty_recorded

        # ── Identity, derived from members ──────────────────────────────────
        summary.part_id = cls._derive_part_id(graph_id=graph_id)
        summary.primary_domain_id = cls._derive_primary_domain_id(graph_id=graph_id)

        # ── The three independent status axes (D9) ──────────────────────────
        summary.linear_status = cls._derive_linear_status(
            demand_qty=demand_qty,
            po_qty_allocated=po_qty_allocated,
            po_qty_purchased=po_qty_purchased,
            shipment_qty_allocated=shipment_qty_allocated,
            shipment_qty_accepted=shipment_qty_accepted,
        )
        summary.po_imbalance_state = cls._derive_po_imbalance_state(
            demand_qty=demand_qty,
            po_qty_allocated=po_qty_allocated,
            po_qty_purchased=po_qty_purchased,
        )
        summary.shipment_imbalance_state = cls._derive_shipment_imbalance_state(
            po_qty_purchased=po_qty_purchased,
            shipment_qty_allocated=shipment_qty_allocated,
            shipment_qty_accepted=shipment_qty_accepted,
        )
        summary.error_code = cls._derive_error_code(
            linear_status=summary.linear_status,
            po_imbalance_state=summary.po_imbalance_state,
            shipment_imbalance_state=summary.shipment_imbalance_state,
        )

        summary.status = cls._derive_status(
            demand_qty=demand_qty,
            po_qty_allocated=po_qty_allocated,
            po_qty_purchased=po_qty_purchased,
            qty_shipments_in_route=qty_shipments_in_route,
            qty_shipments_delivered=qty_shipments_delivered,
            qty_accepted=qty_accepted,
            qty_rejected=qty_rejected,
        )
        summary.swimlane_diagram = cls._build_swimlane_diagram(graph_id=graph_id)

        # NOTE THE ABSENCE. resolution_state, manually_flagged, and priority
        # are NOT in this list and must never be added to it. They are written
        # only by GraphResolutionManager; recalculate() runs constantly and
        # would wipe a user's judgment on the next unrelated allocation. This
        # is the one place on this model where the "everything is derived"
        # convention does not hold — see GraphSummary's class docstring.
        summary.save(
            update_fields=[
                "demand_qty",
                "po_qty_allocated",
                "po_qty_purchased",
                "shipment_qty_allocated",
                "shipment_qty_accepted",
                "qty_shipments_in_route",
                "qty_shipments_delivered",
                "qty_accepted",
                "qty_rejected",
                "intake_qty_recorded",
                "part",
                "primary_domain",
                "linear_status",
                "po_imbalance_state",
                "shipment_imbalance_state",
                "error_code",
                "status",
                "swimlane_diagram",
                "updated_at",
            ]
        )

        # Push the graph's pipeline position down onto its member demands, so a
        # demand list can show it without joining to the graph. Excluded from
        # the update above because it writes a different table.
        PartDemand.objects.filter(
            graph_id=graph_id, deleted_at__isnull=True
        ).exclude(linear_status=summary.linear_status).update(
            linear_status=summary.linear_status
        )
        return summary

    @staticmethod
    def _build_swimlane_diagram(*, graph_id: int) -> str:
        """Load the graph's member rows and edges (same queries the graph
        visualizer view used before D88's follow-up) and hand them to
        MermaidSwimlaneBuilder for pure string assembly. Cached onto
        `swimlane_diagram` so the view never rebuilds it on every request."""
        demands = list(
            PartDemand.objects.filter(graph_id=graph_id, deleted_at__isnull=True)
            .select_related("part", "domain")
            .order_by("pk")
        )
        po_lines = list(
            PurchaseOrderLine.objects.filter(
                graph_id=graph_id, deleted_at__isnull=True
            )
            .select_related(
                "purchase_order",
                "purchase_order__vendor",
                "purchase_order__domain",
                "part",
            )
            .order_by("pk")
        )
        shipment_lines = list(
            ShipmentLine.objects.filter(graph_id=graph_id, deleted_at__isnull=True)
            .select_related("shipment", "shipment__domain", "part")
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
                # Defensive: only edges whose demand side is also a member of
                # this graph. A materialized graph should never disagree with
                # itself, but this guards against a read landing mid-recalc.
                if demand_id in demand_ids
            ]

        shipment_line_ids = {sl.pk for sl in shipment_lines}
        po_shipment_edges = []
        if po_line_ids and shipment_line_ids:
            po_shipment_edges = list(
                PurchaseOrderShipmentLink.objects.filter(
                    deleted_at__isnull=True,
                    purchase_order_line_id__in=po_line_ids,
                    shipment_line_id__in=shipment_line_ids,
                ).values_list(
                    "purchase_order_line_id",
                    "shipment_line_id",
                    "quantity_allocated",
                )
            )

        return MermaidSwimlaneBuilder.build(
            demands=demands,
            po_lines=po_lines,
            shipment_lines=shipment_lines,
            demand_po_edges=demand_po_edges,
            po_shipment_edges=po_shipment_edges,
        )

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _sum(queryset, field: str) -> Decimal:
        return (
            queryset.aggregate(
                total=Coalesce(Sum(field, output_field=_DECIMAL), Decimal("0"), output_field=_DECIMAL)
            )["total"]
            or Decimal("0")
        )

    # ------------------------------------------------------------------ #
    # Identity derivation
    # ------------------------------------------------------------------ #

    @staticmethod
    def _derive_part_id(*, graph_id: int) -> int | None:
        """The one part every member shares.

        Read from whichever member type is present, cheapest first. A graph may
        never span parts, so any member is as good as any other — the guard
        chain (PurchaseOrderDemandLinkValidator's part-match rule, and its
        shipment-side equivalent) is what makes that true, and this column is
        now load-bearing on it.

        Returns None only for a graph with no members at all, which is a row
        about to be deleted.
        """
        for model in (PartDemand, PurchaseOrderLine, ShipmentLine):
            part_id = (
                model.objects.filter(graph_id=graph_id, deleted_at__isnull=True)
                .values_list("part_id", flat=True)
                .first()
            )
            if part_id is not None:
                return part_id
        return None

    @staticmethod
    def _derive_primary_domain_id(*, graph_id: int) -> int | None:
        """The single domain this graph is searchable under.

        FALLBACK CHAIN, first rule yielding a domain wins:
          1. most common across member PO lines (PurchaseOrderLine -> PurchaseOrder.domain)
          2. most common across member demands (PartDemand.domain)
          3. most common across member shipment lines (ShipmentLine -> Shipment.domain)

        PO lines lead because purchasing is the centre of this process — the
        domain doing the buying is the one that should own the graph in a list.
        The fallback is not optional: every newly created demand is a
        single-member graph with zero PO lines, and those are the majority of
        rows, so rule 1 alone is undefined for most of the table.

        TIES BREAK ON LOWEST DOMAIN ID. Arbitrary but deterministic, matching
        merge()'s "lower graph_id survives" for the same reason. Determinism is
        the whole point: recalculate() fires constantly, and a primary_domain
        that flapped between two equally-common domains would make graphs
        appear and disappear from people's search results with no visible cause.
        """
        candidates = (
            (PurchaseOrderLine, "purchase_order__domain_id"),
            (PartDemand, "domain_id"),
            (ShipmentLine, "shipment__domain_id"),
        )
        for model, field in candidates:
            counts = (
                model.objects.filter(graph_id=graph_id, deleted_at__isnull=True)
                .exclude(**{f"{field}__isnull": True})
                .values(field)
                .annotate(n=Count("pk"))
                # -n first, then the field itself, so an equal count resolves
                # on the lowest domain id rather than on row order.
                .order_by("-n", field)
            )
            row = counts.first()
            if row is not None:
                return row[field]
        return None

    # ------------------------------------------------------------------ #
    # Status derivation — three independent precedence chains (D9)
    # ------------------------------------------------------------------ #

    @staticmethod
    def _derive_linear_status(
        *,
        demand_qty: Decimal,
        po_qty_allocated: Decimal,
        po_qty_purchased: Decimal,
        shipment_qty_allocated: Decimal,
        shipment_qty_accepted: Decimal,
    ) -> str:
        """Where in the end-to-end pipeline is this graph?

        Precedence, first match wins. Ordering follows the pipeline itself, so
        a graph always reports the earliest stage it has not cleared.
        """
        if po_qty_allocated == 0 and shipment_qty_allocated == 0:
            return LinearStatus.UNLINKED
        if po_qty_allocated > 0 and po_qty_purchased == 0:
            return LinearStatus.PO_ALLOCATED_NOT_PURCHASED
        if po_qty_purchased > 0 and shipment_qty_accepted == 0:
            return LinearStatus.PO_PURCHASED_NOT_SHIPPED
        if 0 < shipment_qty_accepted < demand_qty:
            return LinearStatus.PARTIALLY_DELIVERED
        if shipment_qty_accepted >= demand_qty:
            return LinearStatus.DELIVERED
        # Reachable only with shipment allocations but no PO allocation and
        # nothing accepted — material tracked against nothing ordered.
        return LinearStatus.UNLINKED

    @staticmethod
    def _derive_po_imbalance_state(
        *,
        demand_qty: Decimal,
        po_qty_allocated: Decimal,
        po_qty_purchased: Decimal,
    ) -> str:
        """Are the demands fully committed to purchase orders?

        Precedence, first match wins. See POImbalanceState's docstring for why
        the first two comparisons use ALLOCATION rather than ordered quantity,
        and why PO_QUANTITY_EXCEEDS_DEMAND is surfaced anyway despite being the
        largest population this axis will produce.
        """
        if demand_qty > po_qty_allocated:
            return POImbalanceState.DEMAND_EXCEEDS_ALLOCATION
        if po_qty_allocated >= demand_qty and po_qty_purchased < demand_qty:
            return POImbalanceState.ALLOCATION_EXCEEDS_PURCHASED
        if po_qty_purchased > demand_qty:
            return POImbalanceState.PO_QUANTITY_EXCEEDS_DEMAND
        if po_qty_purchased >= demand_qty and po_qty_allocated > po_qty_purchased:
            return POImbalanceState.DEMAND_SATISFIED_EXCESS_ALLOCATED
        return POImbalanceState.BALANCED

    @staticmethod
    def _derive_shipment_imbalance_state(
        *,
        po_qty_purchased: Decimal,
        shipment_qty_allocated: Decimal,
        shipment_qty_accepted: Decimal,
    ) -> str:
        """Did we receive what we ordered?

        Precedence, first match wins. THE REFERENCE POINT IS po_qty_purchased,
        never demand_qty — shipments are arrivals against orders. Whether the
        demand was covered at all is the PO axis's question, and comparing
        arrivals to demand here would report the same PO-side shortfall twice.
        """
        if po_qty_purchased > shipment_qty_allocated:
            return ShipmentImbalanceState.PO_ORDERED_NOT_ALLOCATED_TO_SHIPMENTS
        if shipment_qty_allocated > po_qty_purchased:
            return ShipmentImbalanceState.SHIPMENT_ALLOCATION_EXCEEDS_PO
        if shipment_qty_accepted > po_qty_purchased:
            return ShipmentImbalanceState.OVER_DELIVERED
        if 0 < shipment_qty_accepted < po_qty_purchased:
            return ShipmentImbalanceState.PARTIAL_DELIVERY_RECEIVED
        if shipment_qty_allocated > 0 and shipment_qty_accepted == 0:
            return ShipmentImbalanceState.SHIPMENTS_ALLOCATED_AWAITING_DELIVERY
        return ShipmentImbalanceState.BALANCED

    @staticmethod
    def _derive_error_code(
        *,
        linear_status: str,
        po_imbalance_state: str,
        shipment_imbalance_state: str,
    ) -> str:
        """A key naming an end-state mismatch, or "" when there is none.

        Fires only where the three axes DISAGREE in a way a human should look
        at — a graph reporting itself finished while an upstream axis says it
        is not. An axis being individually non-balanced is ordinary and is not
        an error; it is already visible on its own column.

        A KEY, NOT A SENTENCE. Rendered as human language at read time, and
        never accusatorily: an over-delivery is usually the system learning a
        vendor fact late rather than anybody's mistake.
        """
        if linear_status == LinearStatus.DELIVERED:
            if po_imbalance_state == POImbalanceState.DEMAND_EXCEEDS_ALLOCATION:
                # Everything demanded arrived, yet part of the demand was never
                # committed to any order. Real, and worth a look: it usually
                # means material was received against the wrong graph.
                return "DELIVERED_WITH_UNCOMMITTED_DEMAND"
            if shipment_imbalance_state == ShipmentImbalanceState.OVER_DELIVERED:
                return "DELIVERY_EXCEEDS_PURCHASE_ORDER"
        if shipment_imbalance_state == (
            ShipmentImbalanceState.SHIPMENT_ALLOCATION_EXCEEDS_PO
        ):
            # More was mapped to shipments than was ever ordered. Always an
            # allocation mix-up rather than a physical fact.
            return "SHIPMENT_ALLOCATION_EXCEEDS_ORDER"
        return ""

    @staticmethod
    def _derive_status(
        *,
        demand_qty: Decimal,
        po_qty_allocated: Decimal,
        po_qty_purchased: Decimal,
        qty_shipments_in_route: Decimal,
        qty_shipments_delivered: Decimal,
        qty_accepted: Decimal,
        qty_rejected: Decimal,
    ) -> str:
        """The next unmet stage, checked upstream-first: purchase, then
        shipment, then acceptance.

        LEGACY (D81/D86), kept because existing narrators and the graph detail
        template read it. linear_status answers the same question against the
        allocation-based quantities and should be preferred by anything new.
        """
        if demand_qty > 0 and po_qty_allocated == 0:
            return GraphSummaryStatus.AWAITING_PURCHASE
        if po_qty_purchased > 0 and (
            qty_shipments_in_route + qty_shipments_delivered
        ) < po_qty_purchased:
            return GraphSummaryStatus.AWAITING_SHIPMENT
        if qty_shipments_delivered > 0 and (
            qty_accepted + qty_rejected
        ) < qty_shipments_delivered:
            return GraphSummaryStatus.AWAITING_ACCEPTANCE
        return GraphSummaryStatus.BALANCED

    @staticmethod
    def _member_count(*, graph_id: int) -> int:
        return (
            PartDemand.objects.filter(graph_id=graph_id, deleted_at__isnull=True).count()
            + PurchaseOrderLine.objects.filter(
                graph_id=graph_id, deleted_at__isnull=True
            ).count()
            + ShipmentLine.objects.filter(
                graph_id=graph_id, deleted_at__isnull=True
            ).count()
        )

    @staticmethod
    def _repoint_all_members(*, from_graph_id: int, to_graph_id: int, actor=None) -> None:
        PartDemand.objects.filter(graph_id=from_graph_id).update(
            graph_id=to_graph_id, updated_by=actor
        )
        PurchaseOrderLine.objects.filter(graph_id=from_graph_id).update(
            graph_id=to_graph_id, updated_by=actor
        )
        ShipmentLine.objects.filter(graph_id=from_graph_id).update(
            graph_id=to_graph_id, updated_by=actor
        )

    @staticmethod
    def _member_ids(*, graph_id: int) -> dict[str, set[int]]:
        return {
            "demand": set(
                PartDemand.objects.filter(
                    graph_id=graph_id, deleted_at__isnull=True
                ).values_list("pk", flat=True)
            ),
            "po_line": set(
                PurchaseOrderLine.objects.filter(
                    graph_id=graph_id, deleted_at__isnull=True
                ).values_list("pk", flat=True)
            ),
            "shipment_line": set(
                ShipmentLine.objects.filter(
                    graph_id=graph_id, deleted_at__isnull=True
                ).values_list("pk", flat=True)
            ),
        }

    @staticmethod
    def _node_key(entity) -> tuple[str, int]:
        if isinstance(entity, PartDemand):
            return ("demand", entity.pk)
        if isinstance(entity, PurchaseOrderLine):
            return ("po_line", entity.pk)
        if isinstance(entity, ShipmentLine):
            return ("shipment_line", entity.pk)
        raise TypeError(f"Not a graph member type: {type(entity)!r}")

    @staticmethod
    def _adjacency(
        *, members: dict[str, set[int]]
    ) -> dict[tuple[str, int], set[tuple[str, int]]]:
        adjacency: dict[tuple[str, int], set[tuple[str, int]]] = defaultdict(set)

        demand_po_edges = PurchaseOrderDemandLink.objects.filter(
            is_active=True,
            deleted_at__isnull=True,
            part_demand_id__in=members["demand"],
            purchase_order_line_id__in=members["po_line"],
        ).values_list("part_demand_id", "purchase_order_line_id")
        for demand_pk, po_line_pk in demand_po_edges:
            a, b = ("demand", demand_pk), ("po_line", po_line_pk)
            adjacency[a].add(b)
            adjacency[b].add(a)

        po_shipment_edges = PurchaseOrderShipmentLink.objects.filter(
            deleted_at__isnull=True,
            shipment_line_id__in=members["shipment_line"],
            shipment_line__deleted_at__isnull=True,
            purchase_order_line_id__in=members["po_line"],
        ).values_list("purchase_order_line_id", "shipment_line_id")
        for po_line_pk, shipment_line_pk in po_shipment_edges:
            a, b = ("po_line", po_line_pk), ("shipment_line", shipment_line_pk)
            adjacency[a].add(b)
            adjacency[b].add(a)

        return adjacency
