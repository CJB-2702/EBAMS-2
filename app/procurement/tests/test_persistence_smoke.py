"""Smoke test: does everything actually land in the database?

Deliberately NOT a behavior suite. Every write goes through the real
control-layer class it is supposed to (factory, context, manager,
orchestrator), and every assertion then re-reads the row **fresh from the
database** rather than trusting the in-memory object the write returned.

That re-read is the whole point. An object held in memory can look correct
while nothing was ever saved — which is exactly the bug the dev seed caught,
where purchased_qty was computed and then discarded because a manager treated
commit=False as "do not write". Asserting against a requeried row is what makes
that class of failure visible.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from app.administration.models import Domain
from app.inventory.control_layer.orchestrators.part_issuance_orchestrator import (
    PartIssuanceOrchestrator,
)
from app.inventory.models import PartIssue
from app.parts.control_layer.factories.part_factory import PartFactory
from app.procurement.control_layer.adapters.purchase_order_draft_adaptor import (
    DraftAllocation,
    DraftLine,
    PurchaseOrderDraft,
)
from app.procurement.control_layer.factories.shipment_factory import ShipmentFactory
from app.procurement.control_layer.factories.part_demand_factory import (
    PartDemandFactory,
)
from app.procurement.control_layer.factories.purchase_order_factory import (
    PurchaseOrderFactory,
)
from app.procurement.control_layer.shipment_context import ShipmentContext
from app.procurement.control_layer.purchase_order_context import PurchaseOrderContext
from app.procurement.models import (
    DemandDimension,
    DemandState,
    IssuanceState,
    Shipment,
    ShipmentLine,
    ShipmentStatus,
    PartDemand,
    PartDemandUpdate,
    PurchaseOrder,
    PurchaseOrderDemandLink,
    PurchaseOrderLine,
    PurchaseOrderStatus,
    PurchasingState,
    ShipmentState,
    Vendor,
)

User = get_user_model()


class ProcurementPersistenceSmokeTests(TestCase):
    """One object per concept, created through its real class, read back."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="procurement_smoke",
            email="smoke@test.local",
            password="TestPass123!@",
        )
        cls.domain = Domain.objects.create(
            name="Smoke Domain",
            slug="smoke-domain",
            created_by=cls.user,
            updated_by=cls.user,
        )
        cls.part = PartFactory.create(
            data={
                "part_number": "PN-SMOKE-01",
                "name": "Smoke Test Widget",
                "part_type": "component",
                "category": "test",
            },
            actor=cls.user,
        )
        cls.vendor = Vendor.objects.create(
            name="Smoke Vendor Co",
            code="SMOKE",
            created_by=cls.user,
            updated_by=cls.user,
        )

    # ------------------------------------------------------------------ #
    # PartDemand
    # ------------------------------------------------------------------ #

    def test_part_demand_factory_persists_the_demand_and_its_four_journal_rows(self):
        demand = PartDemandFactory.create(
            part_id=self.part.pk,
            domain_id=self.domain.pk,
            quantity_requested=Decimal("10"),
            actor=self.user,
        )

        stored = PartDemand.objects.get(pk=demand.pk)
        self.assertEqual(stored.part_id, self.part.pk)
        self.assertEqual(stored.domain_id, self.domain.pk)
        self.assertEqual(stored.quantity_requested, Decimal("10.000"))
        self.assertEqual(stored.demand_state, DemandState.REQUIRED)
        self.assertEqual(stored.purchasing_state, "")
        self.assertEqual(stored.shipment_state, ShipmentState.REQUEST_NOT_SENT)
        self.assertEqual(stored.issuance_state, IssuanceState.NOT_ISSUED)
        self.assertEqual(stored.created_by_id, self.user.pk)

        # One initializing row per axis, previous_stage blank on all four.
        rows = PartDemandUpdate.objects.filter(part_demand_id=demand.pk)
        self.assertEqual(rows.count(), 4)
        self.assertEqual(
            set(rows.values_list("dimension", flat=True)),
            {
                DemandDimension.DEMAND,
                DemandDimension.PURCHASING,
                DemandDimension.SHIPMENT,
                DemandDimension.ISSUANCE,
            },
        )
        self.assertTrue(all(row.previous_stage == "" for row in rows))

    def test_approving_a_demand_persists_both_the_snapshot_and_a_journal_row(self):
        demand = self._demand()

        from app.procurement.control_layer.part_demand_context import (
            PartDemandContext,
        )

        PartDemandContext(demand.pk).approve(actor=self.user, notes="Looks fine.")

        stored = PartDemand.objects.get(pk=demand.pk)
        self.assertEqual(stored.demand_state, DemandState.APPROVED)

        row = PartDemandUpdate.objects.filter(
            part_demand_id=demand.pk, dimension=DemandDimension.DEMAND
        ).latest("id")
        self.assertEqual(row.stage, DemandState.APPROVED)
        self.assertEqual(row.previous_stage, DemandState.REQUIRED)
        self.assertEqual(row.actor_id, self.user.pk)
        self.assertFalse(row.is_system_generated)

    # ------------------------------------------------------------------ #
    # PurchaseOrder
    # ------------------------------------------------------------------ #

    def test_purchase_order_factory_persists_header_event_line_and_allocation(self):
        demand = self._demand(quantity="10")
        po = self._purchase_order(demand=demand, quantity="10", ordered="10")

        stored = PurchaseOrder.objects.get(pk=po.pk)
        self.assertEqual(stored.status, PurchaseOrderStatus.DRAFT)
        self.assertEqual(stored.vendor_id, self.vendor.pk)
        self.assertEqual(stored.domain_id, self.domain.pk)
        self.assertTrue(stored.po_number.startswith("PO-"))
        # The Event is created in the same transaction and always present.
        self.assertIsNotNone(stored.event_id)
        # 10 x 12.50 + 5.00 shipping
        self.assertEqual(stored.total_cost, Decimal("130.00"))

        line = PurchaseOrderLine.objects.get(purchase_order_id=po.pk)
        self.assertEqual(line.part_id, self.part.pk)
        self.assertEqual(line.line_number, 1)
        self.assertEqual(line.quantity_ordered, Decimal("10.000"))

        link = PurchaseOrderDemandLink.objects.get(purchase_order_line_id=line.pk)
        self.assertEqual(link.part_demand_id, demand.pk)
        self.assertEqual(link.quantity_allocated, Decimal("10.000"))
        self.assertTrue(link.is_active)

    def test_allocating_persists_purchased_qty_on_the_demand(self):
        """The regression the dev seed caught: computed, then never saved."""
        demand = self._demand(quantity="10")
        self._purchase_order(demand=demand, quantity="10", ordered="10")

        self.assertEqual(
            PartDemand.objects.get(pk=demand.pk).purchased_qty, Decimal("10.000")
        )

    def test_placing_an_order_persists_the_propagated_demand_axes(self):
        demand = self._demand(quantity="10")
        po = self._purchase_order(demand=demand, quantity="10", ordered="10")

        self._place(po)

        self.assertEqual(
            PurchaseOrder.objects.get(pk=po.pk).status, PurchaseOrderStatus.PLACED
        )
        stored = PartDemand.objects.get(pk=demand.pk)
        # Auto-approved by the link (D42), then purchased by the placement (D40).
        self.assertEqual(stored.demand_state, DemandState.APPROVED)
        self.assertEqual(stored.purchasing_state, PurchasingState.PURCHASED)
        self.assertEqual(
            stored.shipment_state, ShipmentState.REQUEST_RECEIVED_BY_VENDOR
        )

    # ------------------------------------------------------------------ #
    # Shipment
    # ------------------------------------------------------------------ #

    def test_shipment_factory_persists_the_shipment_and_copies_the_po_link(self):
        demand = self._demand(quantity="10")
        po = self._purchase_order(demand=demand, quantity="10", ordered="10")
        self._place(po)

        shipment = ShipmentFactory.create(
            purchase_order=po,
            actor=self.user,
            carrier="Test Freight",
            lines=[{"part_id": self.part.pk, "quantity": Decimal("10")}],
        )

        stored = Shipment.objects.get(pk=shipment.pk)
        self.assertEqual(stored.purchase_order_id, po.pk)
        self.assertEqual(stored.status, ShipmentStatus.AWAITING_SHIPMENT)
        self.assertTrue(stored.shipment_number.startswith("SHP-"))
        self.assertFalse(stored.mixed_po_assignments)

        line = ShipmentLine.objects.get(shipment_id=shipment.pk)
        # Copied from the header PO automatically — the common case needs no
        # per-line assignment.
        self.assertIsNotNone(line.purchase_order_line_id)
        self.assertEqual(line.quantity, Decimal("10.000"))
        # Uninspected is NULL, which differs meaningfully from 0.
        self.assertIsNone(line.quantity_accepted)

    def test_accepting_a_shipment_line_persists_the_accepted_quantity(self):
        demand = self._demand(quantity="10")
        po = self._purchase_order(demand=demand, quantity="10", ordered="10")
        self._place(po)
        shipment = ShipmentFactory.create(
            purchase_order=po,
            actor=self.user,
            lines=[{"part_id": self.part.pk, "quantity": Decimal("10")}],
        )

        context = ShipmentContext(shipment.pk)
        context.advance(to_status=ShipmentStatus.SHIPPED, actor=self.user)
        line = ShipmentLine.objects.get(shipment_id=shipment.pk)
        context.accept_line(
            line=line,
            quantity_accepted=Decimal("8"),
            actor=self.user,
            rejection_notes="2 damaged.",
        )

        stored = ShipmentLine.objects.get(pk=line.pk)
        self.assertEqual(stored.quantity_accepted, Decimal("8.000"))
        self.assertEqual(stored.rejection_notes, "2 damaged.")
        self.assertEqual(
            Shipment.objects.get(pk=shipment.pk).status, ShipmentStatus.SHIPPED
        )
        # Any accepted quantity makes a placed order Partially Received.
        self.assertEqual(
            PurchaseOrder.objects.get(pk=po.pk).status,
            PurchaseOrderStatus.PARTIALLY_RECEIVED,
        )

    # ------------------------------------------------------------------ #
    # Issuance — the cross-app write seam
    # ------------------------------------------------------------------ #

    def test_orchestrator_persists_the_issue_row_and_the_demands_issued_qty(self):
        demand = self._demand(quantity="4")

        PartIssuanceOrchestrator.issue(
            demand_id=demand.pk,
            issued_to=self.user,
            quantity=Decimal("4"),
            to_stage=IssuanceState.ISSUED,
            actor=self.user,
        )

        issue = PartIssue.objects.get(part_demand_id=demand.pk)
        self.assertEqual(issue.quantity, Decimal("4.000"))
        self.assertEqual(issue.issued_to_id, self.user.pk)

        # inventory wrote its own row, then procurement's column followed.
        stored = PartDemand.objects.get(pk=demand.pk)
        self.assertEqual(stored.issued_qty, Decimal("4.000"))
        self.assertEqual(stored.issuance_state, IssuanceState.ISSUED)

    def test_a_return_persists_a_second_negative_row_and_nets_issued_qty_down(self):
        demand = self._demand(quantity="4")
        PartIssuanceOrchestrator.issue(
            demand_id=demand.pk,
            issued_to=self.user,
            quantity=Decimal("4"),
            to_stage=IssuanceState.ISSUED_PENDING_RECONCILIATION,
            actor=self.user,
        )
        PartIssuanceOrchestrator.record_return(
            demand_id=demand.pk,
            issued_to=self.user,
            quantity=Decimal("1"),
            actor=self.user,
        )

        quantities = sorted(
            PartIssue.objects.filter(part_demand_id=demand.pk).values_list(
                "quantity", flat=True
            )
        )
        self.assertEqual(quantities, [Decimal("-1.000"), Decimal("4.000")])
        self.assertEqual(
            PartDemand.objects.get(pk=demand.pk).issued_qty, Decimal("3.000")
        )

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _demand(self, *, quantity: str = "10") -> PartDemand:
        return PartDemandFactory.create(
            part_id=self.part.pk,
            domain_id=self.domain.pk,
            quantity_requested=Decimal(quantity),
            actor=self.user,
        )

    def _purchase_order(
        self, *, demand: PartDemand, quantity: str, ordered: str
    ) -> PurchaseOrder:
        draft = PurchaseOrderDraft(
            vendor_id=self.vendor.pk,
            domain_id=self.domain.pk,
            shipping_cost=Decimal("5.00"),
            lines=[
                DraftLine(
                    part_id=self.part.pk,
                    quantity_ordered=Decimal(ordered),
                    unit_cost=Decimal("12.50"),
                    allocations=[
                        DraftAllocation(
                            demand_id=demand.pk,
                            quantity_allocated=Decimal(quantity),
                        )
                    ],
                )
            ],
        )
        return PurchaseOrderFactory.create_from_draft(draft=draft, actor=self.user)

    def _place(self, po: PurchaseOrder) -> None:
        context = PurchaseOrderContext(po.pk)
        context.submit_for_approval(actor=self.user)
        context.approve_order(actor=self.user)
        context.place(actor=self.user)
