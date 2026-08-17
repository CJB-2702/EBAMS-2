"""Phase 3 (reallocation_resolution_kit): a demand's claims on OTHER orders
are visible on the linkage screen and inside the Reallocation Portal, always
read-only, always distinct from the arrived/received LOCKED category.

Covers acceptance scenario 8 from reallocation_resolution_portal.md §11.
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
from app.procurement.control_layer.domain_structs.demand_external_claims_struct import (
    DemandExternalClaimsStruct,
)
from app.procurement.control_layer.domain_structs.purchase_order_struct import (
    PurchaseOrderStruct,
)
from app.procurement.control_layer.domain_structs.reallocation_portal_struct import (
    ReallocationPortalStruct,
)
from app.procurement.control_layer.factories.part_demand_factory import PartDemandFactory
from app.procurement.control_layer.factories.purchase_order_factory import (
    PurchaseOrderFactory,
)
from app.procurement.control_layer.purchase_order_context import PurchaseOrderContext
from app.procurement.models import PurchaseOrderLine, Vendor


class ReallocationCrossDomainVisibilityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="realloc_p3", email="realloc_p3@test.local", password="TestPass123!@"
        )
        cls.domain = Domain.objects.create(
            name="Realloc Visibility Domain", slug="realloc-visibility-domain",
            created_by=cls.user, updated_by=cls.user,
        )
        cls.part = PartFactory.create(
            data={
                "part_number": "PN-REALLOC-P3",
                "name": "Reallocation Visibility Widget",
                "part_type": "component",
                "category": "test",
            },
            actor=cls.user,
        )
        cls.vendor = Vendor.objects.create(
            name="Realloc Visibility Vendor", code="REALLOCP3",
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

    def test_a_demands_claim_on_another_order_shows_up_as_external(self):
        po_a, line_a = self._po_with_line(ordered="10")
        po_b, line_b = self._po_with_line(ordered="10")
        demand = PartDemandFactory.create(
            part_id=self.part.pk, domain_id=self.domain.pk,
            quantity_requested=Decimal("5"), actor=self.user,
        )
        PurchaseOrderContext(po_a.pk).allocate(
            line=line_a, demand=demand, quantity_allocated=Decimal("5"), actor=self.user
        )

        external = DemandExternalClaimsStruct.load(
            demand_id=demand.pk, exclude_purchase_order_id=po_b.pk
        )
        self.assertEqual(len(external.claims), 1)
        self.assertEqual(external.claims[0].po_number, po_a.po_number)
        self.assertEqual(external.claims[0].quantity_allocated, Decimal("5.000"))

        # Viewed from Order A's own screen, that same claim is NOT external —
        # it belongs to this order.
        same_order = DemandExternalClaimsStruct.load(
            demand_id=demand.pk, exclude_purchase_order_id=po_a.pk
        )
        self.assertEqual(len(same_order.claims), 0)

    def test_linkage_screen_struct_carries_external_claims_per_row(self):
        po_a, line_a = self._po_with_line(ordered="10")
        po_b, line_b = self._po_with_line(ordered="10")
        demand = PartDemandFactory.create(
            part_id=self.part.pk, domain_id=self.domain.pk,
            quantity_requested=Decimal("5"), actor=self.user,
        )
        PurchaseOrderContext(po_a.pk).allocate(
            line=line_a, demand=demand, quantity_allocated=Decimal("5"), actor=self.user
        )
        from app.procurement.control_layer.managers.part_demand_quantity_manager import (
            PartDemandQuantityManager,
        )
        PartDemandQuantityManager.raise_requested_quantity(
            demand=demand, new_quantity=Decimal("10"), actor=self.user
        )
        PurchaseOrderContext(po_b.pk).allocate(
            line=line_b, demand=demand, quantity_allocated=Decimal("5"), actor=self.user,
        )

        struct_b = PurchaseOrderStruct.load(purchase_order_id=po_b.pk)
        allocation = struct_b.allocations_by_line[line_b.pk][0]
        self.assertEqual(len(allocation.external_claims), 1)
        self.assertEqual(allocation.external_claims[0].po_number, po_a.po_number)

    def test_portal_shows_external_claims_as_a_third_category_never_in_open_or_locked(self):
        po_a, line_a = self._po_with_line(ordered="10")
        po_b, line_b = self._po_with_line(ordered="10")
        demand = PartDemandFactory.create(
            part_id=self.part.pk, domain_id=self.domain.pk,
            quantity_requested=Decimal("5"), actor=self.user,
        )
        PurchaseOrderContext(po_a.pk).allocate(
            line=line_a, demand=demand, quantity_allocated=Decimal("5"), actor=self.user
        )
        from app.procurement.control_layer.managers.part_demand_quantity_manager import (
            PartDemandQuantityManager,
        )
        PartDemandQuantityManager.raise_requested_quantity(
            demand=demand, new_quantity=Decimal("10"), actor=self.user
        )
        PurchaseOrderContext(po_b.pk).allocate(
            line=line_b, demand=demand, quantity_allocated=Decimal("5"), actor=self.user,
        )

        portal = ReallocationPortalStruct.load(line_id=line_b.pk)
        self.assertEqual(len(portal.open_claims), 1)
        claim = portal.open_claims[0]
        self.assertEqual(len(claim.external_claims), 1)
        self.assertEqual(claim.external_claims[0].po_number, po_a.po_number)
        # The external claim's value never enters this line's own totals.
        self.assertEqual(portal.open_total, Decimal("5.000"))
        self.assertEqual(portal.locked_total, Decimal("0"))
