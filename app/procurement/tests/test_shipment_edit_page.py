"""Shipment Edit & Linkage: the PO Edit & Linkage page, inverted.

Covers the surface the restructure moved — the inline add-line card that used
to be a modal, the top-bottom candidate search with its text filter, and
selection surviving a header save — plus the allocate/release round trip the
page exists for.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from app.administration.models import Domain
from app.parts.control_layer.factories.part_factory import PartFactory
from app.procurement.control_layer.adapters.purchase_order_draft_adaptor import (
    DraftLine,
    PurchaseOrderDraft,
)
from app.procurement.control_layer.factories.purchase_order_factory import (
    PurchaseOrderFactory,
)
from app.procurement.control_layer.factories.shipment_factory import ShipmentFactory
from app.procurement.control_layer.purchase_order_context import PurchaseOrderContext
from app.procurement.models import (
    PurchaseOrderLine,
    PurchaseOrderShipmentLink,
    ShipmentLine,
    Vendor,
)

User = get_user_model()


class ShipmentEditPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            username="edit_smoke",
            email="edit@test.local",
            password="TestPass123!@",
        )
        cls.domain = Domain.objects.create(
            name="Edit Domain",
            slug="edit-domain",
            created_by=cls.user,
            updated_by=cls.user,
        )
        cls.part = PartFactory.create(
            data={
                "part_number": "PN-EDIT-01",
                "name": "Edit Widget",
                "part_type": "component",
                "category": "test",
            },
            actor=cls.user,
        )
        cls.vendor = Vendor.objects.create(
            name="Edit Vendor Co",
            code="EDIT",
            created_by=cls.user,
            updated_by=cls.user,
        )

    def setUp(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["user_domain_ids"] = [self.domain.pk]
        session.save()

        self.po, self.po_line = self._placed_po(ordered="20")
        # Created with no PO, so nothing is auto-linked and the page has real
        # work to do — the state the edit page is for.
        self.shipment = ShipmentFactory.create(
            domain=self.domain,
            lines=[{"part_id": self.part.pk, "quantity": Decimal("12")}],
            actor=self.user,
        )
        self.line = ShipmentLine.objects.get(shipment=self.shipment)
        self.url = reverse("shipment_edit", kwargs={"pk": self.shipment.pk})

    # ------------------------------------------------------------------ #

    def test_selecting_a_line_shows_its_candidate_order_lines(self):
        page = self.client.get(f"{self.url}?line_id={self.line.pk}")
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, self.po.po_number)
        self.assertContains(page, "current allocations")
        # The add-line control is an in-page card now, not a modal trigger.
        self.assertContains(page, 'value="add_line"')
        self.assertNotContains(page, "add-line-modal")

    def test_no_selection_leaves_the_right_column_inert(self):
        page = self.client.get(self.url)
        self.assertContains(page, "Choose a line on the left")

    def test_candidate_search_filters_by_order_number(self):
        page = self.client.get(f"{self.url}?line_id={self.line.pk}&q=NOTHINGMATCHES")
        self.assertContains(page, "No open order line buys")
        self.assertNotContains(page, f"{self.po.po_number} · {self.po_line.line_number}")

    def test_partial_allocation_then_release(self):
        """The page's whole job: point some of an arriving line at an order
        line, leave the rest as remainder, then take it back off."""
        self.client.post(
            self.url,
            {
                "action": "assign",
                "line_id": self.line.pk,
                "purchase_order_line_id": self.po_line.pk,
                "quantity": "5",
            },
        )
        link = PurchaseOrderShipmentLink.objects.get(deleted_at__isnull=True)
        self.assertEqual(link.quantity_allocated, Decimal("5.000"))

        page = self.client.get(f"{self.url}?line_id={self.line.pk}")
        self.assertContains(page, "Partially allocated")

        self.client.post(
            self.url,
            {"action": "unassign", "link_id": link.pk, "line_id": self.line.pk},
        )
        link.refresh_from_db()
        self.assertIsNotNone(link.deleted_at)
        # Releasing never touches the physical record.
        self.line.refresh_from_db()
        self.assertEqual(self.line.quantity, Decimal("12.000"))

    def test_header_save_keeps_the_selected_line(self):
        response = self.client.post(
            self.url,
            {
                "action": "save_header",
                "selected_line_id": self.line.pk,
                "carrier": "UPS",
                "shipment_id": "TRACK-1",
            },
        )
        self.assertEqual(response["Location"], f"{self.url}?line_id={self.line.pk}")
        self.shipment.refresh_from_db()
        self.assertEqual(self.shipment.carrier, "UPS")

    def test_add_line_from_the_inline_card(self):
        self.client.post(
            self.url,
            {
                "action": "add_line",
                "selected_line_id": self.line.pk,
                "part_id": self.part.pk,
                "quantity": "3",
            },
        )
        self.assertEqual(
            ShipmentLine.objects.filter(
                shipment=self.shipment, deleted_at__isnull=True
            ).count(),
            2,
        )

    def test_deleting_a_line_drops_the_selection(self):
        response = self.client.post(
            self.url,
            {"action": "delete_line", "line_id": self.line.pk, "reason": "mis-keyed"},
        )
        # No ?line_id= — the selection cannot survive its own line.
        self.assertEqual(response["Location"], self.url)
        self.line.refresh_from_db()
        self.assertIsNotNone(self.line.deleted_at)

    # ------------------------------------------------------------------ #

    def _placed_po(self, *, ordered: str):
        po = PurchaseOrderFactory.create_from_draft(
            draft=PurchaseOrderDraft(
                vendor_id=self.vendor.pk,
                domain_id=self.domain.pk,
                lines=[
                    DraftLine(
                        part_id=self.part.pk,
                        quantity_ordered=Decimal(ordered),
                        unit_cost=Decimal("10.00"),
                        allocations=[],
                    )
                ],
            ),
            actor=self.user,
        )
        context = PurchaseOrderContext(po.pk)
        context.submit_for_approval(actor=self.user)
        context.approve_order(actor=self.user)
        context.place(actor=self.user)
        line = PurchaseOrderLine.objects.get(purchase_order=po)
        line.refresh_from_db()
        return po, line
