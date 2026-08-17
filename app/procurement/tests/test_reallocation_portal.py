"""Phase 2 (reallocation_resolution_kit): the Reallocation Portal's
waterfall, locked-claim protection, two-popup unlock, and manual-entry cap.

Covers acceptance scenarios 3, 4, 5, and 9 from
reallocation_resolution_portal.md §11.
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
from app.procurement.control_layer.errors import (
    ProcurementValidationError,
    ReallocationRequired,
)
from app.procurement.control_layer.factories.part_demand_factory import PartDemandFactory
from app.procurement.control_layer.factories.purchase_order_factory import (
    PurchaseOrderFactory,
)
from app.procurement.control_layer.factories.shipment_factory import ShipmentFactory
from app.procurement.control_layer.handlers.reallocation_waterfall_handler import (
    ReallocationWaterfallHandler,
)
from app.procurement.control_layer.managers.shipment_line_manager import ShipmentLineManager
from app.procurement.control_layer.purchase_order_context import PurchaseOrderContext
from app.procurement.models import (
    DemandPriority,
    PurchaseOrderDemandLink,
    PurchaseOrderLine,
    ShipmentLine,
    Vendor,
)
from app.procurement.presentation_layer.search.open_demand_search import OpenDemandSearch


class ReallocationPortalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="realloc_p2", email="realloc_p2@test.local", password="TestPass123!@"
        )
        cls.domain = Domain.objects.create(
            name="Realloc Portal Domain", slug="realloc-portal-domain",
            created_by=cls.user, updated_by=cls.user,
        )
        cls.part = PartFactory.create(
            data={
                "part_number": "PN-REALLOC-P2",
                "name": "Reallocation Portal Widget",
                "part_type": "component",
                "category": "test",
            },
            actor=cls.user,
        )
        cls.vendor = Vendor.objects.create(
            name="Realloc Portal Vendor", code="REALLOCP2",
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

    def _demand(self, *, quantity: str, priority=DemandPriority.MEDIUM, needed_by=None):
        return PartDemandFactory.create(
            part_id=self.part.pk, domain_id=self.domain.pk,
            quantity_requested=Decimal(quantity), priority=priority,
            needed_by=needed_by, actor=self.user,
        )

    def _lock(self, *, po, link, quantity: str):
        shipment = ShipmentFactory.create(
            purchase_order=po, actor=self.user, carrier="Test Freight",
            lines=[{"part_id": self.part.pk, "quantity": Decimal(quantity)}],
        )
        arriving = ShipmentLine.objects.get(shipment=shipment)
        ShipmentLineManager.accept(
            line=arriving, quantity_accepted=Decimal(quantity), actor=self.user
        )
        PurchaseOrderContext(po.pk).record_receipt(
            link=link, quantity_received=Decimal(quantity), actor=self.user
        )
        link.refresh_from_db()

    # Scenario 3: waterfall in action.
    def test_waterfall_protects_critical_then_medium_absorbs_the_cut_from_low(self):
        po, line = self._po_with_line(ordered="100")
        context = PurchaseOrderContext(po.pk)
        critical = self._demand(quantity="20", priority=DemandPriority.CRITICAL)
        medium = self._demand(quantity="30", priority=DemandPriority.MEDIUM)
        low = self._demand(quantity="50", priority=DemandPriority.LOW)
        link_c = context.allocate(line=line, demand=critical, quantity_allocated=Decimal("20"), actor=self.user)
        link_m = context.allocate(line=line, demand=medium, quantity_allocated=Decimal("30"), actor=self.user)
        link_l = context.allocate(line=line, demand=low, quantity_allocated=Decimal("50"), actor=self.user)

        with self.assertRaises(ReallocationRequired):
            context.edit_line(line=line, changes={"quantity_ordered": Decimal("70")}, actor=self.user)

        open_claims = list(
            PurchaseOrderDemandLink.objects.filter(purchase_order_line=line, is_active=True)
            .select_related("part_demand")
        )
        resolutions = ReallocationWaterfallHandler.allocate(
            open_claims=open_claims, shortfall=Decimal("30")
        )
        self.assertEqual(resolutions[link_c.pk], Decimal("20"))
        self.assertEqual(resolutions[link_m.pk], Decimal("30"))
        self.assertEqual(resolutions[link_l.pk], Decimal("20"))

        context.apply_reallocation(
            line=line, new_quantity_ordered=Decimal("70"), resolutions=resolutions, actor=self.user
        )
        line.refresh_from_db()
        link_c.refresh_from_db()
        link_m.refresh_from_db()
        link_l.refresh_from_db()
        self.assertEqual(line.quantity_ordered, Decimal("70.000"))
        self.assertEqual(link_c.quantity_allocated, Decimal("20.000"))
        self.assertEqual(link_m.quantity_allocated, Decimal("30.000"))
        self.assertEqual(link_l.quantity_allocated, Decimal("20.000"))

    # Scenario 4: locked claim protected.
    def test_waterfall_never_touches_a_locked_claim(self):
        po, line = self._po_with_line(ordered="100")
        context = PurchaseOrderContext(po.pk)
        critical = self._demand(quantity="20", priority=DemandPriority.CRITICAL)
        medium = self._demand(quantity="30", priority=DemandPriority.MEDIUM)
        low = self._demand(quantity="50", priority=DemandPriority.LOW)
        link_c = context.allocate(line=line, demand=critical, quantity_allocated=Decimal("20"), actor=self.user)
        link_m = context.allocate(line=line, demand=medium, quantity_allocated=Decimal("30"), actor=self.user)
        link_l = context.allocate(line=line, demand=low, quantity_allocated=Decimal("50"), actor=self.user)
        self._lock(po=po, link=link_l, quantity="50")

        open_claims = list(
            PurchaseOrderDemandLink.objects.filter(
                purchase_order_line=line, is_active=True, is_locked=False
            ).select_related("part_demand")
        )
        self.assertEqual({c.pk for c in open_claims}, {link_c.pk, link_m.pk})

        # The full 30-unit shortfall must come from OPEN claims only — the
        # locked Low claim has nowhere for the cut to go.
        resolutions = ReallocationWaterfallHandler.allocate(
            open_claims=open_claims, shortfall=Decimal("30")
        )
        self.assertEqual(resolutions[link_c.pk], Decimal("20"))
        self.assertEqual(resolutions[link_m.pk], Decimal("0"))

    # Scenario 5: deliberate unlock.
    def test_unlock_requires_explicit_confirmation(self):
        po, line = self._po_with_line(ordered="100")
        context = PurchaseOrderContext(po.pk)
        demand = self._demand(quantity="50")
        link = context.allocate(line=line, demand=demand, quantity_allocated=Decimal("50"), actor=self.user)
        self._lock(po=po, link=link, quantity="50")
        self.assertTrue(link.is_locked)

        with self.assertRaises(ProcurementValidationError):
            context.unlock_claim(link=link, actor=self.user, confirmed=False)
        link.refresh_from_db()
        self.assertTrue(link.is_locked)

        context.unlock_claim(link=link, actor=self.user, confirmed=True)
        link.refresh_from_db()
        self.assertFalse(link.is_locked)

    # Manual entry: under-claim allowed, over-claim never.
    def test_manual_entry_allows_under_claim_never_over_claim(self):
        from app.procurement.control_layer.guards.reallocation_guard import (
            ReallocationValidator,
        )

        ReallocationValidator.check_manual_entry(
            values={1: Decimal("10"), 2: Decimal("5")},
            locked_total=Decimal("0"),
            new_source_qty=Decimal("20"),
        )
        with self.assertRaises(ProcurementValidationError):
            ReallocationValidator.check_manual_entry(
                values={1: Decimal("15"), 2: Decimal("10")},
                locked_total=Decimal("0"),
                new_source_qty=Decimal("20"),
            )

    # Scenario 9: bumped demand resurfaces in the open buying queue.
    def test_reduced_claim_puts_demand_back_in_the_open_queue(self):
        po, line = self._po_with_line(ordered="100")
        context = PurchaseOrderContext(po.pk)
        low = self._demand(quantity="50", priority=DemandPriority.LOW)
        link_l = context.allocate(line=line, demand=low, quantity_allocated=Decimal("50"), actor=self.user)

        self.assertNotIn(
            low.pk,
            OpenDemandSearch.for_part(part_id=self.part.pk).values_list("pk", flat=True),
        )

        context.apply_reallocation(
            line=line,
            new_quantity_ordered=Decimal("70"),
            resolutions={link_l.pk: Decimal("20")},
            actor=self.user,
        )

        low.refresh_from_db()
        self.assertEqual(low.purchased_qty, Decimal("20.000"))
        self.assertIn(
            low.pk,
            OpenDemandSearch.for_part(part_id=self.part.pk).values_list("pk", flat=True),
        )
