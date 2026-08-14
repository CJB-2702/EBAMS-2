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
                      ShipmentLineManager.add_line/ShipmentLineSplitHandler.

  merge               Creating an active PurchaseOrderDemandLink, or pointing
                      a ShipmentLine at a PurchaseOrderLine in a different
                      graph, coalesces the two graphs. Every member of the
                      SMALLER graph (by row count) is re-pointed onto the
                      LARGER graph's id — cheap because these clusters stay
                      small (D70's sparsity argument) — the absorbed
                      GraphSummary row is deleted, and the survivor is
                      recalculated. Wired into
                      PurchaseOrderDemandLinkManager.allocate() and
                      ShipmentLineManager.add_line/reassign.

  split_if_disconnected
                      Deactivating a PurchaseOrderDemandLink, or reassigning a
                      ShipmentLine away from a PurchaseOrderLine, may sever the
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
                      and ShipmentLineManager.reassign().

  recalculate         Recomputes D81's eight quantity columns plus `status`
                      from current member rows. Every metric is its own
                      single-table aggregate with only forward (to-one) joins
                      (PurchaseOrderLine -> PurchaseOrder, ShipmentLine ->
                      Shipment) — never a joined Sum() alongside another
                      multi-row relation in the same queryset, the exact bug
                      class D67 already caught once in
                      PurchaseOrderFulfillmentStruct. Called at the end of
                      every operation above — never left for a caller to
                      remember separately.

No `commit` parameter anywhere here (D66): every method below writes
immediately, participating in whatever transaction the caller already holds,
rather than silently no-op'ing the way the pre-D66 quantity manager bug did.
"""

from __future__ import annotations

from collections import defaultdict, deque
from decimal import Decimal

from django.db.models import DecimalField, F, Sum
from django.db.models.functions import Coalesce

from app.procurement.models import (
    GraphSummary,
    GraphSummaryStatus,
    PartDemand,
    PurchaseOrderDemandLink,
    PurchaseOrderLine,
    PurchaseOrderStatus,
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

        cls._repoint_all_members(
            from_graph_id=absorbed, to_graph_id=survivor, actor=actor
        )
        GraphSummary.objects.filter(pk=absorbed).delete()
        cls.recalculate(graph_id=survivor)
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
        po_qty_waiting_for_purchase = cls._sum(
            po_lines.filter(purchase_order__status=PurchaseOrderStatus.DRAFT),
            "quantity_ordered",
        )
        po_qty_purchased = cls._sum(
            po_lines.filter(purchase_order__status__in=_PURCHASED_PO_STATUSES),
            "quantity_ordered",
        )

        shipment_lines = ShipmentLine.objects.filter(
            graph_id=graph_id, deleted_at__isnull=True
        )
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
        summary.po_qty_waiting_for_purchase = po_qty_waiting_for_purchase
        summary.po_qty_purchased = po_qty_purchased
        summary.qty_shipments_in_route = qty_shipments_in_route
        summary.qty_shipments_delivered = qty_shipments_delivered
        summary.qty_accepted = qty_accepted
        summary.qty_rejected = qty_rejected
        summary.intake_qty_recorded = intake_qty_recorded
        summary.status = cls._derive_status(
            demand_qty=demand_qty,
            po_qty_waiting_for_purchase=po_qty_waiting_for_purchase,
            po_qty_purchased=po_qty_purchased,
            qty_shipments_in_route=qty_shipments_in_route,
            qty_shipments_delivered=qty_shipments_delivered,
            qty_accepted=qty_accepted,
            qty_rejected=qty_rejected,
        )
        summary.save(
            update_fields=[
                "demand_qty",
                "po_qty_waiting_for_purchase",
                "po_qty_purchased",
                "qty_shipments_in_route",
                "qty_shipments_delivered",
                "qty_accepted",
                "qty_rejected",
                "intake_qty_recorded",
                "status",
                "updated_at",
            ]
        )
        return summary

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

    @staticmethod
    def _derive_status(
        *,
        demand_qty: Decimal,
        po_qty_waiting_for_purchase: Decimal,
        po_qty_purchased: Decimal,
        qty_shipments_in_route: Decimal,
        qty_shipments_delivered: Decimal,
        qty_accepted: Decimal,
        qty_rejected: Decimal,
    ) -> str:
        """The next unmet stage, checked upstream-first: purchase, then
        shipment, then acceptance. Not specified further than the four label
        names in D81 — this ordering is this build's interpretation, recorded
        here for a future decisions.md follow-up rather than left implicit."""
        if demand_qty > 0 and (po_qty_waiting_for_purchase + po_qty_purchased) == 0:
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

        po_shipment_edges = ShipmentLine.objects.filter(
            pk__in=members["shipment_line"],
            deleted_at__isnull=True,
            purchase_order_line_id__in=members["po_line"],
        ).values_list("purchase_order_line_id", "pk")
        for po_line_pk, shipment_line_pk in po_shipment_edges:
            a, b = ("po_line", po_line_pk), ("shipment_line", shipment_line_pk)
            adjacency[a].add(b)
            adjacency[b].add(a)

        return adjacency
