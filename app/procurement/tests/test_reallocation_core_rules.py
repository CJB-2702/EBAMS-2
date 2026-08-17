"""Phase 1 (reallocation_resolution_kit): the locked floor and the two silent
auto-update paths on the Demand↔PO Domain's PO-line quantity edit.

Covers acceptance scenarios 1, 2, and 6 from
reallocation_resolution_portal.md §11.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from app.administration.models import Domain
from app.parts.control_layer.factories.part_factory import PartFactory
from app.procurement.control_layer.errors import ProcurementValidationError
from app.procurement.control_layer.factories.part_demand_factory import PartDemandFactory
from app.procurement.control_layer.factories.purchase_order_factory import (
    PurchaseOrderFactory,
)
from app.procurement.control_layer.adapters.purchase_order_draft_adaptor import (
    DraftLine,
    PurchaseOrderDraft,
)
from app.procurement.control_layer.factories.shipment_factory import ShipmentFactory
from app.procurement.control_layer.managers.shipment_line_manager import ShipmentLineManager
from app.procurement.control_layer.purchase_order_context import PurchaseOrderContext
from app.procurement.models import (
    PurchaseOrderDemandLink,
    PurchaseOrderLine,
    ShipmentLine,
    Vendor,
)

User = get_user_model()


class ReallocationCoreRulesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="realloc_p1", email="realloc_p1@test.local", password="TestPass123!@"
        )
        cls.domain = Domain.objects.create(
            name="Realloc Domain", slug="realloc-domain",
            created_by=cls.user, updated_by=cls.user,
        )
        cls.part = PartFactory.create(
            data={
                "part_number": "PN-REALLOC-01",
                "name": "Reallocation Test Widget",
                "part_type": "component",
                "category": "test",
            },
            actor=cls.user,
        )
        cls.vendor = Vendor.objects.create(
            name="Realloc Vendor Co", code="REALLOC",
            created_by=cls.user, updated_by=cls.user,
        )

    def _po_with_line(self, *, ordered: str):
        draft = PurchaseOrderDraft(
            vendor_id=self.vendor.pk,
            domain_id=self.domain.pk,
            lines=[
                DraftLine(
                    part_id=self.part.pk,
                    quantity_ordered=Decimal(ordered),
                    unit_cost=Decimal("10.00"),
                    allocations=[],
                ),
            ],
        )
        po = PurchaseOrderFactory.create_from_draft(draft=draft, actor=self.user)
        line = PurchaseOrderLine.objects.get(purchase_order=po)
        return po, line

    def _demand(self, *, quantity: str):
        return PartDemandFactory.create(
            part_id=self.part.pk, domain_id=self.domain.pk,
            quantity_requested=Decimal(quantity), actor=self.user,
        )

    # Scenario 1: common case, no friction.
    def test_reduction_that_still_covers_all_claims_updates_silently(self):
        po, line = self._po_with_line(ordered="100")
        context = PurchaseOrderContext(po.pk)
        demand = self._demand(quantity="80")
        context.allocate(line=line, demand=demand, quantity_allocated=Decimal("80"), actor=self.user)

        context.edit_line(line=line, changes={"quantity_ordered": Decimal("90")}, actor=self.user)

        line.refresh_from_db()
        self.assertEqual(line.quantity_ordered, Decimal("90.000"))
        link = PurchaseOrderDemandLink.objects.get(purchase_order_line=line, part_demand=demand)
        self.assertEqual(link.quantity_allocated, Decimal("80.000"))

    # Scenario 2: one-to-one shortcut.
    def test_single_unlocked_claim_shortfall_updates_that_claim_silently(self):
        po, line = self._po_with_line(ordered="50")
        context = PurchaseOrderContext(po.pk)
        demand = self._demand(quantity="50")
        context.allocate(line=line, demand=demand, quantity_allocated=Decimal("50"), actor=self.user)

        context.edit_line(line=line, changes={"quantity_ordered": Decimal("30")}, actor=self.user)

        line.refresh_from_db()
        self.assertEqual(line.quantity_ordered, Decimal("30.000"))
        link = PurchaseOrderDemandLink.objects.get(purchase_order_line=line, part_demand=demand)
        self.assertEqual(link.quantity_allocated, Decimal("30.000"))

    # Scenario 6: below-locked refusal.
    def test_reduction_below_locked_total_is_refused_before_any_write(self):
        po, line = self._po_with_line(ordered="100")
        context = PurchaseOrderContext(po.pk)
        demand = self._demand(quantity="100")
        link = context.allocate(
            line=line, demand=demand, quantity_allocated=Decimal("100"), actor=self.user
        )
        shipment = ShipmentFactory.create(
            purchase_order=po, actor=self.user, carrier="Test Freight",
            lines=[{"part_id": self.part.pk, "quantity": Decimal("80")}],
        )
        arriving = ShipmentLine.objects.get(shipment=shipment)
        ShipmentLineManager.accept(
            line=arriving, quantity_accepted=Decimal("80"), actor=self.user
        )
        context.record_receipt(link=link, quantity_received=Decimal("80"), actor=self.user)

        with self.assertRaises(ProcurementValidationError):
            context.edit_line(line=line, changes={"quantity_ordered": Decimal("60")}, actor=self.user)

        line.refresh_from_db()
        link.refresh_from_db()
        self.assertEqual(line.quantity_ordered, Decimal("100.000"))
        self.assertEqual(link.quantity_allocated, Decimal("100.000"))
        self.assertTrue(link.is_locked)

    def test_two_claim_shortfall_raises_reallocation_required(self):
        from app.procurement.control_layer.errors import ReallocationRequired

        po, line = self._po_with_line(ordered="100")
        context = PurchaseOrderContext(po.pk)
        demand_a = self._demand(quantity="40")
        demand_b = self._demand(quantity="60")
        context.allocate(line=line, demand=demand_a, quantity_allocated=Decimal("40"), actor=self.user)
        context.allocate(line=line, demand=demand_b, quantity_allocated=Decimal("60"), actor=self.user)

        with self.assertRaises(ReallocationRequired):
            context.edit_line(line=line, changes={"quantity_ordered": Decimal("70")}, actor=self.user)

        # Nothing was written on the refusal path.
        line.refresh_from_db()
        self.assertEqual(line.quantity_ordered, Decimal("100.000"))
