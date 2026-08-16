"""GraphSummaryManager: node-init, merge, split, recalculate (D79-D82).

Each test drives the real control-layer class that owns the write (factory,
manager) rather than calling GraphSummaryManager directly where a real seam
exists, matching this app's persistence-smoke convention of asserting against
freshly re-read rows.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from app.administration.models import Domain
from app.parts.control_layer.factories.part_factory import PartFactory
from app.procurement.control_layer.adapters.purchase_order_draft_adaptor import (
    DraftAllocation,
    DraftLine,
    PurchaseOrderDraft,
)
from app.procurement.control_layer.factories.part_demand_factory import (
    PartDemandFactory,
)
from app.procurement.control_layer.factories.purchase_order_factory import (
    PurchaseOrderFactory,
)
from app.procurement.control_layer.managers.graph_resolution_manager import (
    GraphResolutionManager,
)
from app.procurement.control_layer.managers.graph_summary_manager import (
    GraphSummaryManager,
)
from app.procurement.control_layer.managers.purchase_order_demand_link_manager import (
    PurchaseOrderDemandLinkManager,
)
from app.procurement.models import (
    DemandPriority,
    GraphResolutionState,
    GraphSummary,
    LinearStatus,
    PartDemand,
    POImbalanceState,
    PurchaseOrderDemandLink,
    PurchaseOrderLine,
    PurchaseOrderStatus,
    Vendor,
)

User = get_user_model()


class GraphSummaryManagerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="graph_smoke",
            email="graph_smoke@test.local",
            password="TestPass123!@",
        )
        cls.domain = Domain.objects.create(
            name="Graph Domain",
            slug="graph-domain",
            created_by=cls.user,
            updated_by=cls.user,
        )
        cls.part = PartFactory.create(
            data={
                "part_number": "PN-GRAPH-01",
                "name": "Graph Test Widget",
                "part_type": "component",
                "category": "test",
            },
            actor=cls.user,
        )
        cls.vendor = Vendor.objects.create(
            name="Graph Vendor Co",
            code="GRAPH",
            created_by=cls.user,
            updated_by=cls.user,
        )

    def _demand(self, *, quantity: str = "10") -> PartDemand:
        return PartDemandFactory.create(
            part_id=self.part.pk,
            domain_id=self.domain.pk,
            quantity_requested=Decimal(quantity),
            actor=self.user,
        )

    def _purchase_order_with_allocation(self, *, demand, quantity: str, ordered: str):
        draft = PurchaseOrderDraft(
            vendor_id=self.vendor.pk,
            domain_id=self.domain.pk,
            lines=[
                DraftLine(
                    part_id=self.part.pk,
                    quantity_ordered=Decimal(ordered),
                    unit_cost=Decimal("10.00"),
                    allocations=[
                        DraftAllocation(
                            demand_id=demand.pk,
                            quantity_allocated=Decimal(quantity),
                        )
                    ],
                )
            ],
        )
        po = PurchaseOrderFactory.create_from_draft(draft=draft, actor=self.user)
        line = PurchaseOrderLine.objects.get(purchase_order=po)
        return po, line

    # ------------------------------------------------------------------ #
    # Node init
    # ------------------------------------------------------------------ #

    def test_creating_an_isolated_demand_initializes_its_own_single_member_graph(self):
        demand = self._demand(quantity="5")

        stored = PartDemand.objects.get(pk=demand.pk)
        self.assertIsNotNone(stored.graph_id)

        summary = GraphSummary.objects.get(pk=stored.graph_id)
        self.assertEqual(summary.demands.count(), 1)
        self.assertEqual(summary.purchase_order_lines.count(), 0)
        self.assertEqual(summary.shipment_lines.count(), 0)

    def test_creating_a_po_line_initializes_its_own_single_member_graph(self):
        po = PurchaseOrderFactory.create(
            vendor_id=self.vendor.pk, domain_id=self.domain.pk, actor=self.user
        )
        from app.procurement.control_layer.managers.purchase_order_line_manager import (
            PurchaseOrderLineManager,
        )

        line, _warning = PurchaseOrderLineManager.add_line(
            purchase_order=po,
            part_id=self.part.pk,
            quantity_ordered=Decimal("3"),
            unit_cost=Decimal("10.00"),
            actor=self.user,
        )

        stored = PurchaseOrderLine.objects.get(pk=line.pk)
        self.assertIsNotNone(stored.graph_id)
        summary = GraphSummary.objects.get(pk=stored.graph_id)
        self.assertEqual(summary.purchase_order_lines.count(), 1)
        self.assertEqual(summary.demands.count(), 0)

    # ------------------------------------------------------------------ #
    # Merge
    # ------------------------------------------------------------------ #

    def test_allocating_a_demand_to_a_po_line_merges_their_graphs(self):
        demand = self._demand(quantity="10")

        po, line = self._purchase_order_with_allocation(
            demand=demand, quantity="10", ordered="10"
        )

        stored_demand = PartDemand.objects.get(pk=demand.pk)
        stored_line = PurchaseOrderLine.objects.get(pk=line.pk)

        # Both sides now share exactly one graph — one of the two original
        # single-member graphs was absorbed and deleted (which one survives
        # is a deterministic tie-break, not asserted here), the other is the
        # survivor both rows now point at.
        self.assertEqual(stored_demand.graph_id, stored_line.graph_id)
        self.assertEqual(GraphSummary.objects.count(), 1)

        summary = GraphSummary.objects.get(pk=stored_demand.graph_id)
        self.assertEqual(summary.demands.count(), 1)
        self.assertEqual(summary.purchase_order_lines.count(), 1)

    def test_merge_is_a_no_op_when_both_sides_already_share_a_graph(self):
        demand = self._demand(quantity="10")
        po, line = self._purchase_order_with_allocation(
            demand=demand, quantity="10", ordered="10"
        )
        stored = PartDemand.objects.get(pk=demand.pk)
        graph_id_before = stored.graph_id

        survivor = GraphSummaryManager.merge(
            graph_id_a=graph_id_before,
            graph_id_b=PurchaseOrderLine.objects.get(pk=line.pk).graph_id,
            actor=self.user,
        )
        self.assertEqual(survivor, graph_id_before)
        self.assertTrue(GraphSummary.objects.filter(pk=graph_id_before).exists())

    # ------------------------------------------------------------------ #
    # Split
    # ------------------------------------------------------------------ #

    def test_delinking_the_only_bridge_splits_the_demand_into_a_new_graph(self):
        demand = self._demand(quantity="10")
        po, line = self._purchase_order_with_allocation(
            demand=demand, quantity="10", ordered="10"
        )
        shared_graph_id = PartDemand.objects.get(pk=demand.pk).graph_id
        self.assertEqual(
            PurchaseOrderLine.objects.get(pk=line.pk).graph_id, shared_graph_id
        )

        link = PurchaseOrderDemandLink.objects.get(
            part_demand=demand, purchase_order_line=line
        )
        PurchaseOrderDemandLinkManager.delink(link=link, actor=self.user)

        stored_demand = PartDemand.objects.get(pk=demand.pk)
        stored_line = PurchaseOrderLine.objects.get(pk=line.pk)

        # The bridge is gone: demand and line now belong to two different,
        # single-member graphs, neither of which is the original merged one.
        self.assertNotEqual(stored_demand.graph_id, stored_line.graph_id)
        self.assertNotEqual(stored_demand.graph_id, shared_graph_id)

        demand_graph = GraphSummary.objects.get(pk=stored_demand.graph_id)
        line_graph = GraphSummary.objects.get(pk=stored_line.graph_id)
        self.assertEqual(demand_graph.demands.count(), 1)
        self.assertEqual(demand_graph.purchase_order_lines.count(), 0)
        self.assertEqual(line_graph.purchase_order_lines.count(), 1)
        self.assertEqual(line_graph.demands.count(), 0)

    def test_split_if_disconnected_is_a_no_op_when_still_connected(self):
        demand_a = self._demand(quantity="5")
        demand_b = self._demand(quantity="5")
        # Two demands sharing one PO line: removing one link should NOT
        # disconnect the other demand's side, since the line still bridges
        # demand_b to the shared graph.
        draft = PurchaseOrderDraft(
            vendor_id=self.vendor.pk,
            domain_id=self.domain.pk,
            lines=[
                DraftLine(
                    part_id=self.part.pk,
                    quantity_ordered=Decimal("10"),
                    unit_cost=Decimal("10.00"),
                    allocations=[
                        DraftAllocation(
                            demand_id=demand_a.pk, quantity_allocated=Decimal("5")
                        ),
                        DraftAllocation(
                            demand_id=demand_b.pk, quantity_allocated=Decimal("5")
                        ),
                    ],
                )
            ],
        )
        po = PurchaseOrderFactory.create_from_draft(draft=draft, actor=self.user)
        line = PurchaseOrderLine.objects.get(purchase_order=po)
        shared_graph_id = PurchaseOrderLine.objects.get(pk=line.pk).graph_id

        link_a = PurchaseOrderDemandLink.objects.get(
            part_demand=demand_a, purchase_order_line=line
        )
        PurchaseOrderDemandLinkManager.delink(link=link_a, actor=self.user)

        # demand_b and the line are still bridged — both remain on the
        # original graph, which must therefore still exist.
        self.assertTrue(GraphSummary.objects.filter(pk=shared_graph_id).exists())
        self.assertEqual(
            PurchaseOrderLine.objects.get(pk=line.pk).graph_id, shared_graph_id
        )
        self.assertEqual(
            PartDemand.objects.get(pk=demand_b.pk).graph_id, shared_graph_id
        )
        # demand_a split off on its own.
        self.assertNotEqual(
            PartDemand.objects.get(pk=demand_a.pk).graph_id, shared_graph_id
        )

    # ------------------------------------------------------------------ #
    # Recalculate
    # ------------------------------------------------------------------ #

    def test_recalculate_sums_demand_qty_across_member_demands(self):
        demand_a = self._demand(quantity="5")
        demand_b = self._demand(quantity="5")
        draft = PurchaseOrderDraft(
            vendor_id=self.vendor.pk,
            domain_id=self.domain.pk,
            lines=[
                DraftLine(
                    part_id=self.part.pk,
                    quantity_ordered=Decimal("10"),
                    unit_cost=Decimal("10.00"),
                    allocations=[
                        DraftAllocation(
                            demand_id=demand_a.pk, quantity_allocated=Decimal("5")
                        ),
                        DraftAllocation(
                            demand_id=demand_b.pk, quantity_allocated=Decimal("5")
                        ),
                    ],
                )
            ],
        )
        po = PurchaseOrderFactory.create_from_draft(draft=draft, actor=self.user)
        line = PurchaseOrderLine.objects.get(purchase_order=po)
        graph_id = PurchaseOrderLine.objects.get(pk=line.pk).graph_id

        summary = GraphSummaryManager.recalculate(graph_id=graph_id)

        self.assertEqual(summary.demand_qty, Decimal("10.000"))
        # PO is still Draft — allocated, but nothing purchased yet.
        self.assertEqual(summary.po_qty_allocated, Decimal("10.000"))
        self.assertEqual(summary.po_qty_purchased, Decimal("0.000"))
        self.assertEqual(summary.intake_qty_recorded, Decimal("0.000"))

    def test_recalculate_moves_po_qty_allocated_to_purchased_on_placement(self):
        demand = self._demand(quantity="10")
        po, line = self._purchase_order_with_allocation(
            demand=demand, quantity="10", ordered="10"
        )
        from app.procurement.control_layer.purchase_order_context import (
            PurchaseOrderContext,
        )

        context = PurchaseOrderContext(po.pk)
        context.submit_for_approval(actor=self.user)
        context.approve_order(actor=self.user)
        context.place(actor=self.user)

        graph_id = PurchaseOrderLine.objects.get(pk=line.pk).graph_id
        summary = GraphSummaryManager.recalculate(graph_id=graph_id)

        self.assertEqual(
            PurchaseOrderLine.objects.get(pk=line.pk).purchase_order.status,
            PurchaseOrderStatus.PLACED,
        )
        self.assertEqual(summary.po_qty_allocated, Decimal("10.000"))
        self.assertEqual(summary.po_qty_purchased, Decimal("10.000"))


class GraphIdentityAndStatusTests(GraphSummaryManagerTests):
    """The columns added by the demand-graph surfaces build: identity, the
    three status axes, and the human-judgment columns recalculate() must not
    touch."""

    # ------------------------------------------------------------------ #
    # Identity
    # ------------------------------------------------------------------ #

    def test_recalculate_sets_part_and_primary_domain_from_members(self):
        demand = self._demand(quantity="10")
        summary = GraphSummary.objects.get(
            pk=PartDemand.objects.get(pk=demand.pk).graph_id
        )

        self.assertEqual(summary.part_id, self.part.pk)
        # No PO lines on a fresh demand's graph, so the fallback chain has to
        # reach rule 2 (member demands) to find a domain at all. This is the
        # majority case in the table, not an edge case.
        self.assertEqual(summary.primary_domain_id, self.domain.pk)

    # ------------------------------------------------------------------ #
    # The fan-out regression — the whole reason these are separate queries
    # ------------------------------------------------------------------ #

    def test_po_qty_allocated_does_not_fan_out_across_shipment_links(self):
        """Two allocations on one PO line must sum to their true total, not be
        multiplied by the number of rows in a second multi-row relation.

        A joined Sum() alongside another multi-row relation silently
        multiplies. That bug class was already caught once in
        PurchaseOrderFulfillmentStruct, which is why po_qty_allocated is its
        own query rather than an annotation on the member-line queryset. This
        test fails loudly if somebody 'tidies' it back into one query.
        """
        demand_a = self._demand(quantity="10")
        demand_b = self._demand(quantity="6")
        po, line = self._purchase_order_with_allocation(
            demand=demand_a, quantity="10", ordered="100"
        )
        PurchaseOrderDemandLinkManager.allocate(
            line=line,
            demand=demand_b,
            quantity_allocated=Decimal("6"),
            actor=self.user,
        )

        graph_id = PurchaseOrderLine.objects.get(pk=line.pk).graph_id
        summary = GraphSummaryManager.recalculate(graph_id=graph_id)

        # 10 + 6, exactly. Not 32 (fanned out across two links).
        self.assertEqual(summary.po_qty_allocated, Decimal("16.000"))
        self.assertEqual(summary.demand_qty, Decimal("16.000"))

    def test_allocated_measures_commitment_not_the_lines_ordered_quantity(self):
        """A line ordering 100 against a 10-unit demand is healthy.

        po_qty_allocated must read the allocation (10), never the line's
        quantity_ordered (100) — bulk restocking is modelled as a PO carrying
        more ordered quantity than the sum of its allocations, and reading
        ordered here would report every restock as wildly over-committed.
        """
        demand = self._demand(quantity="10")
        _, line = self._purchase_order_with_allocation(
            demand=demand, quantity="10", ordered="100"
        )

        graph_id = PurchaseOrderLine.objects.get(pk=line.pk).graph_id
        summary = GraphSummaryManager.recalculate(graph_id=graph_id)

        self.assertEqual(summary.po_qty_allocated, Decimal("10.000"))

    # ------------------------------------------------------------------ #
    # The three axes
    # ------------------------------------------------------------------ #

    def test_fresh_demand_reports_demand_exceeds_allocation_and_unlinked(self):
        """The single most common row in the table, and it must be meaningful.

        Every newly created demand gets its own single-member graph. By count
        these dominate the table, so if they landed on BALANCED the whole
        surface would under-report real work on day one.
        """
        demand = self._demand(quantity="10")
        summary = GraphSummary.objects.get(
            pk=PartDemand.objects.get(pk=demand.pk).graph_id
        )

        self.assertEqual(
            summary.po_imbalance_state, POImbalanceState.DEMAND_EXCEEDS_ALLOCATION
        )
        self.assertEqual(summary.linear_status, LinearStatus.UNLINKED)

    def test_allocated_but_unplaced_order_is_caught_structurally(self):
        """A demand fully allocated to a PO nobody placed is doing nothing in
        the world, and it looks covered on the demand-vs-allocation
        comparison. This is the state that catches it."""
        demand = self._demand(quantity="10")
        _, line = self._purchase_order_with_allocation(
            demand=demand, quantity="10", ordered="10"
        )

        graph_id = PurchaseOrderLine.objects.get(pk=line.pk).graph_id
        summary = GraphSummaryManager.recalculate(graph_id=graph_id)

        self.assertEqual(
            summary.po_imbalance_state, POImbalanceState.ALLOCATION_EXCEEDS_PURCHASED
        )
        self.assertEqual(
            summary.linear_status, LinearStatus.PO_ALLOCATED_NOT_PURCHASED
        )

    def test_member_demands_inherit_the_graphs_linear_status(self):
        demand = self._demand(quantity="10")
        _, line = self._purchase_order_with_allocation(
            demand=demand, quantity="10", ordered="10"
        )

        graph_id = PurchaseOrderLine.objects.get(pk=line.pk).graph_id
        summary = GraphSummaryManager.recalculate(graph_id=graph_id)

        self.assertEqual(
            PartDemand.objects.get(pk=demand.pk).linear_status,
            summary.linear_status,
        )

    # ------------------------------------------------------------------ #
    # The inverted-discipline columns
    # ------------------------------------------------------------------ #

    def test_recalculate_never_overwrites_the_human_judgment_columns(self):
        """THE ASSERTION THIS BUILD MOST NEEDS.

        Every other column on GraphSummary is written by recalculate(). These
        three are written only by GraphResolutionManager. The surrounding
        convention is uniform enough that the natural assumption — 'everything
        on this model is derived' — would add them to recalculate()'s
        update_fields and silently wipe user input on the next unrelated
        allocation. A docstring alone will not stop that; this will.
        """
        demand = self._demand(quantity="10")
        graph_id = PartDemand.objects.get(pk=demand.pk).graph_id

        GraphResolutionManager.set_resolution(
            graph_id=graph_id,
            resolution_state=GraphResolutionState.ACCEPTED_AS_IS,
            actor=self.user,
        )
        GraphResolutionManager.set_flag(
            graph_id=graph_id, flagged=True, actor=self.user
        )
        GraphResolutionManager.set_priority(
            graph_id=graph_id, priority=DemandPriority.CRITICAL, actor=self.user
        )

        summary = GraphSummaryManager.recalculate(graph_id=graph_id)

        self.assertEqual(
            summary.resolution_state, GraphResolutionState.ACCEPTED_AS_IS
        )
        self.assertTrue(summary.manually_flagged)
        self.assertEqual(summary.priority, DemandPriority.CRITICAL)

    def test_merge_clears_resolution_but_carries_flag_and_priority(self):
        """The survival principle: configuration-derived state clears, human
        judgment about importance propagates.

        A resolution is a statement about a specific set of nodes; once nodes
        join, the thing that was looked at no longer exists. Priority and
        flagging are about the underlying work, which restructuring does not
        invalidate.
        """
        demand = self._demand(quantity="10")
        demand_graph_id = PartDemand.objects.get(pk=demand.pk).graph_id

        GraphResolutionManager.set_resolution(
            graph_id=demand_graph_id,
            resolution_state=GraphResolutionState.RESOLVED,
            actor=self.user,
        )
        GraphResolutionManager.set_flag(
            graph_id=demand_graph_id, flagged=True, actor=self.user
        )
        GraphResolutionManager.set_priority(
            graph_id=demand_graph_id, priority=DemandPriority.HIGH, actor=self.user
        )

        # Allocating to a PO line merges the demand's graph with the line's.
        self._purchase_order_with_allocation(
            demand=demand, quantity="10", ordered="10"
        )
        survivor_id = PartDemand.objects.get(pk=demand.pk).graph_id
        survivor = GraphSummary.objects.get(pk=survivor_id)

        self.assertEqual(survivor.resolution_state, GraphResolutionState.OPEN)
        self.assertTrue(survivor.manually_flagged)
        self.assertEqual(survivor.priority, DemandPriority.HIGH)
