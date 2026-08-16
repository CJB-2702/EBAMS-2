"""PurchaseOrderShipmentLink: allocation, release, the over-allocation cap,
and the one place arrival is prorated (D90).

These are the behaviours the pre-D90 splitting design could not express, plus
the guarantee that replaced its central claim. Splitting's argument for a
single FK was that a link table lets an arriving line's quantity and the sum
of its links disagree; the cap tested here is what makes that impossible, and
the remainder tested alongside it is what the leftover actually means.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from app.administration.models import Domain
from app.parts.control_layer.factories.part_factory import PartFactory
from app.procurement.control_layer.adapters.purchase_order_draft_adaptor import (
    DraftLine,
    PurchaseOrderDraft,
)
from app.procurement.control_layer.domain_structs.arrival_allocation import (
    accepted_by_purchase_order_line,
    unallocated_remainder,
)
from app.procurement.control_layer.domain_structs.shipment_struct import (
    ShipmentDetailStruct,
)
from app.procurement.control_layer.errors import ProcurementValidationError
from app.procurement.control_layer.factories.purchase_order_factory import (
    PurchaseOrderFactory,
)
from app.procurement.control_layer.factories.shipment_factory import ShipmentFactory
from app.procurement.control_layer.managers.shipment_line_manager import (
    ShipmentLineManager,
)
from app.procurement.control_layer.purchase_order_context import PurchaseOrderContext
from app.procurement.control_layer.shipment_context import ShipmentContext
from app.procurement.models import (
    PurchaseOrderLine,
    PurchaseOrderShipmentLink,
    ShipmentLine,
    Vendor,
)

User = get_user_model()


class ShipmentAllocationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="alloc_smoke",
            email="alloc@test.local",
            password="TestPass123!@",
        )
        cls.domain = Domain.objects.create(
            name="Alloc Domain",
            slug="alloc-domain",
            created_by=cls.user,
            updated_by=cls.user,
        )
        cls.part = PartFactory.create(
            data={
                "part_number": "PN-ALLOC-01",
                "name": "Allocation Test Widget",
                "part_type": "component",
                "category": "test",
            },
            actor=cls.user,
        )
        cls.part_other = PartFactory.create(
            data={
                "part_number": "PN-ALLOC-02",
                "name": "Other Widget",
                "part_type": "component",
                "category": "test",
            },
            actor=cls.user,
        )
        cls.vendor = Vendor.objects.create(
            name="Alloc Vendor Co",
            code="ALLOC",
            created_by=cls.user,
            updated_by=cls.user,
        )

    # ------------------------------------------------------------------ #
    # The cap, and what the leftover means
    # ------------------------------------------------------------------ #

    def test_one_arriving_line_can_answer_two_po_lines_without_being_split(self):
        """The whole point of D90: the physical row is never rewritten."""
        po, line_1, line_2 = self._po_with_two_lines(ordered_1="9", ordered_2="6")
        shipment = self._shipment(po, quantity="15", allocate=False)
        arriving = ShipmentLine.objects.get(shipment=shipment)

        context = ShipmentContext(shipment.pk)
        context.assign_line(
            line=arriving, purchase_order_line=line_1, quantity=Decimal("9"),
            actor=self.user,
        )
        context.assign_line(
            line=arriving, purchase_order_line=line_2, quantity=Decimal("6"),
            actor=self.user,
        )

        arriving.refresh_from_db()
        self.assertEqual(arriving.quantity, Decimal("15.000"))
        self.assertEqual(ShipmentLine.objects.filter(shipment=shipment).count(), 1)
        self.assertEqual(
            PurchaseOrderShipmentLink.objects.filter(
                shipment_line=arriving, deleted_at__isnull=True
            ).count(),
            2,
        )
        self.assertEqual(unallocated_remainder(shipment_line=arriving), Decimal("0"))

    def test_allocating_more_than_arrived_is_refused(self):
        po, line_1, line_2 = self._po_with_two_lines(ordered_1="10", ordered_2="10")
        shipment = self._shipment(po, quantity="10", allocate=False)
        arriving = ShipmentLine.objects.get(shipment=shipment)

        ShipmentLineManager.allocate(
            line=arriving, purchase_order_line=line_1, quantity=Decimal("7"),
            actor=self.user,
        )
        with self.assertRaises(ProcurementValidationError):
            ShipmentLineManager.allocate(
                line=arriving, purchase_order_line=line_2, quantity=Decimal("4"),
                actor=self.user,
            )
        # The refusal left the first allocation intact — no partial write.
        self.assertEqual(
            PurchaseOrderShipmentLink.objects.filter(
                shipment_line=arriving, deleted_at__isnull=True
            ).count(),
            1,
        )
        self.assertEqual(unallocated_remainder(shipment_line=arriving), Decimal("3"))

    def test_reallocating_the_same_pairing_sets_rather_than_adds(self):
        """One row per pairing, so a second call is a correction. Without this
        the cap would reject every ordinary amendment."""
        po, line_1, _ = self._po_with_two_lines(ordered_1="10", ordered_2="10")
        shipment = self._shipment(po, quantity="10", allocate=False)
        arriving = ShipmentLine.objects.get(shipment=shipment)

        ShipmentLineManager.allocate(
            line=arriving, purchase_order_line=line_1, quantity=Decimal("6"),
            actor=self.user,
        )
        link = ShipmentLineManager.allocate(
            line=arriving, purchase_order_line=line_1, quantity=Decimal("9"),
            actor=self.user,
        )
        self.assertEqual(link.quantity_allocated, Decimal("9.000"))
        self.assertEqual(
            PurchaseOrderShipmentLink.objects.filter(
                shipment_line=arriving, deleted_at__isnull=True
            ).count(),
            1,
        )

    def test_releasing_an_allocation_returns_the_quantity_to_the_remainder(self):
        po, line_1, _ = self._po_with_two_lines(ordered_1="10", ordered_2="10")
        shipment = self._shipment(po, quantity="10", allocate=False)
        arriving = ShipmentLine.objects.get(shipment=shipment)

        link = ShipmentLineManager.allocate(
            line=arriving, purchase_order_line=line_1, quantity=Decimal("10"),
            actor=self.user,
        )
        ShipmentContext(shipment.pk).release_allocation(link=link, actor=self.user)

        arriving.refresh_from_db()
        # The arrived quantity is untouched — only the claim went away.
        self.assertEqual(arriving.quantity, Decimal("10.000"))
        self.assertEqual(unallocated_remainder(shipment_line=arriving), Decimal("10"))

    def test_a_shipment_line_may_only_be_allocated_to_its_own_part(self):
        po, line_1, _ = self._po_with_two_lines(ordered_1="10", ordered_2="10")
        other_line = PurchaseOrderLine.objects.create(
            purchase_order=po,
            part_id=self.part_other.pk,
            line_number=99,
            quantity_ordered=Decimal("5"),
            unit_cost=Decimal("1.00"),
            created_by=self.user,
            updated_by=self.user,
        )
        shipment = self._shipment(po, quantity="5", allocate=False)
        arriving = ShipmentLine.objects.get(shipment=shipment)

        with self.assertRaises(ProcurementValidationError):
            ShipmentLineManager.allocate(
                line=arriving, purchase_order_line=other_line,
                quantity=Decimal("5"), actor=self.user,
            )

    # ------------------------------------------------------------------ #
    # Derived arrival
    # ------------------------------------------------------------------ #

    def test_single_allocation_arrival_is_exact_not_prorated(self):
        """The common case must never go through the division at all."""
        po, line_1, _ = self._po_with_two_lines(ordered_1="10", ordered_2="10")
        shipment = self._shipment(po, quantity="10", allocate=False)
        arriving = ShipmentLine.objects.get(shipment=shipment)
        ShipmentLineManager.allocate(
            line=arriving, purchase_order_line=line_1, quantity=Decimal("10"),
            actor=self.user,
        )
        ShipmentLineManager.accept(
            line=arriving, quantity_accepted=Decimal("8"), actor=self.user
        )

        arrived = accepted_by_purchase_order_line(
            purchase_order_line_ids=[line_1.pk, ]
        )
        self.assertEqual(arrived[line_1.pk], Decimal("8"))

    def test_multi_allocation_arrival_is_prorated_by_share_and_sums_to_the_total(self):
        po, line_1, line_2 = self._po_with_two_lines(ordered_1="9", ordered_2="6")
        shipment = self._shipment(po, quantity="15", allocate=False)
        arriving = ShipmentLine.objects.get(shipment=shipment)
        ShipmentLineManager.allocate(
            line=arriving, purchase_order_line=line_1, quantity=Decimal("9"),
            actor=self.user,
        )
        ShipmentLineManager.allocate(
            line=arriving, purchase_order_line=line_2, quantity=Decimal("6"),
            actor=self.user,
        )
        # Ten of fifteen survived inspection; nobody inspected "the nine" or
        # "the six" separately, because there was one box.
        ShipmentLineManager.accept(
            line=arriving, quantity_accepted=Decimal("10"), actor=self.user
        )

        arrived = accepted_by_purchase_order_line(
            purchase_order_line_ids=[line_1.pk, line_2.pk]
        )
        self.assertEqual(arrived[line_1.pk], Decimal("6"))
        self.assertEqual(arrived[line_2.pk], Decimal("4"))
        # The property that makes proration defensible: it conserves.
        self.assertEqual(
            arrived[line_1.pk] + arrived[line_2.pk], Decimal("10")
        )

    def test_the_unallocated_remainder_receives_no_share_of_acceptance(self):
        po, line_1, _ = self._po_with_two_lines(ordered_1="10", ordered_2="10")
        shipment = self._shipment(po, quantity="10", allocate=False)
        arriving = ShipmentLine.objects.get(shipment=shipment)
        # Only half the box is claimed by an order line.
        ShipmentLineManager.allocate(
            line=arriving, purchase_order_line=line_1, quantity=Decimal("5"),
            actor=self.user,
        )
        ShipmentLineManager.accept(
            line=arriving, quantity_accepted=Decimal("10"), actor=self.user
        )

        arrived = accepted_by_purchase_order_line(
            purchase_order_line_ids=[line_1.pk]
        )
        # The allocated half takes the whole accepted total, NOT half of it:
        # the denominator is what was allocated, not what arrived. The
        # unallocated 5 belongs to nobody and is credited to nobody.
        self.assertEqual(arrived[line_1.pk], Decimal("10"))

    def test_an_uninspected_line_contributes_nothing_rather_than_zero(self):
        po, line_1, _ = self._po_with_two_lines(ordered_1="10", ordered_2="10")
        shipment = self._shipment(po, quantity="10", allocate=False)
        arriving = ShipmentLine.objects.get(shipment=shipment)
        ShipmentLineManager.allocate(
            line=arriving, purchase_order_line=line_1, quantity=Decimal("10"),
            actor=self.user,
        )

        arrived = accepted_by_purchase_order_line(
            purchase_order_line_ids=[line_1.pk]
        )
        self.assertNotIn(line_1.pk, arrived)

    # ------------------------------------------------------------------ #
    # Graph maintenance
    # ------------------------------------------------------------------ #

    def test_allocating_merges_the_shipment_line_into_the_po_lines_graph(self):
        po, line_1, _ = self._po_with_two_lines(ordered_1="10", ordered_2="10")
        shipment = self._shipment(po, quantity="10", allocate=False)
        arriving = ShipmentLine.objects.get(shipment=shipment)
        self.assertNotEqual(arriving.graph_id, line_1.graph_id)

        ShipmentLineManager.allocate(
            line=arriving, purchase_order_line=line_1, quantity=Decimal("10"),
            actor=self.user,
        )
        arriving.refresh_from_db()
        line_1.refresh_from_db()
        self.assertEqual(arriving.graph_id, line_1.graph_id)

    def test_releasing_the_only_edge_splits_the_shipment_line_onto_its_own_graph(self):
        po, line_1, _ = self._po_with_two_lines(ordered_1="10", ordered_2="10")
        shipment = self._shipment(po, quantity="10", allocate=False)
        arriving = ShipmentLine.objects.get(shipment=shipment)
        link = ShipmentLineManager.allocate(
            line=arriving, purchase_order_line=line_1, quantity=Decimal("10"),
            actor=self.user,
        )
        arriving.refresh_from_db()
        merged_graph_id = arriving.graph_id

        ShipmentLineManager.deallocate(link=link, actor=self.user)

        arriving.refresh_from_db()
        line_1.refresh_from_db()
        self.assertNotEqual(arriving.graph_id, line_1.graph_id)
        self.assertIn(merged_graph_id, {arriving.graph_id, line_1.graph_id})

    # ------------------------------------------------------------------ #
    # The struct the pages read
    # ------------------------------------------------------------------ #

    def test_detail_struct_reports_every_allocation_and_the_remainder(self):
        po, line_1, line_2 = self._po_with_two_lines(ordered_1="9", ordered_2="6")
        shipment = self._shipment(po, quantity="15", allocate=False)
        arriving = ShipmentLine.objects.get(shipment=shipment)
        ShipmentLineManager.allocate(
            line=arriving, purchase_order_line=line_1, quantity=Decimal("9"),
            actor=self.user,
        )

        detail = ShipmentDetailStruct.load(shipment_id=shipment.pk)
        line_slice = detail.lines[0]
        self.assertEqual(len(line_slice.allocations), 1)
        self.assertEqual(line_slice.quantity_allocated, Decimal("9"))
        self.assertEqual(line_slice.unallocated_quantity, Decimal("6"))
        self.assertFalse(line_slice.is_fully_allocated)
        # A partly allocated line is assigned AND still owed — both must be
        # true, or the page hides the leftover.
        self.assertTrue(line_slice.is_assigned)
        self.assertIn(line_slice, detail.unassigned_lines)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _po_with_two_lines(self, *, ordered_1: str, ordered_2: str):
        """Two active lines for the SAME part on one order — D58's soft rule
        deliberately breached, which is the case allocation exists for."""
        draft = PurchaseOrderDraft(
            vendor_id=self.vendor.pk,
            domain_id=self.domain.pk,
            lines=[
                DraftLine(
                    part_id=self.part.pk,
                    quantity_ordered=Decimal(ordered_1),
                    unit_cost=Decimal("10.00"),
                    allocations=[],
                ),
            ],
        )
        po = PurchaseOrderFactory.create_from_draft(draft=draft, actor=self.user)
        line_1 = PurchaseOrderLine.objects.get(purchase_order=po)
        line_2 = PurchaseOrderLine.objects.create(
            purchase_order=po,
            part_id=self.part.pk,
            line_number=line_1.line_number + 1,
            quantity_ordered=Decimal(ordered_2),
            unit_cost=Decimal("10.00"),
            created_by=self.user,
            updated_by=self.user,
        )
        from app.procurement.control_layer.managers.graph_summary_manager import (
            GraphSummaryManager,
        )

        GraphSummaryManager.initialize_node(entity=line_2, actor=self.user)
        context = PurchaseOrderContext(po.pk)
        context.submit_for_approval(actor=self.user)
        context.approve_order(actor=self.user)
        context.place(actor=self.user)
        line_1.refresh_from_db()
        line_2.refresh_from_db()
        return po, line_1, line_2

    def _shipment(self, po, *, quantity: str, allocate: bool):
        """A shipment carrying one line for `self.part`.

        With two active lines for the part on the order, the factory's
        resolve step refuses to guess and the line lands unallocated — which
        is exactly the starting state these tests want.
        """
        return ShipmentFactory.create(
            purchase_order=po,
            actor=self.user,
            carrier="Alloc Freight",
            lines=[{"part_id": self.part.pk, "quantity": Decimal(quantity)}],
        )
