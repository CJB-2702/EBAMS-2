"""The create-shipment wizard: session staging, then one write at submit.

These tests exercise the thing the flat create form could not do — deciding
WHICH order line each arriving item answers before the record exists. The case
that matters most is the ambiguous one: two active lines for the same part on
one order, where copy-on-create deliberately refuses to guess and used to leave
the receiver correcting it afterwards on the edit page.
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
from app.procurement.control_layer.managers.graph_summary_manager import (
    GraphSummaryManager,
)
from app.procurement.control_layer.purchase_order_context import PurchaseOrderContext
from app.procurement.models import (
    PurchaseOrderLine,
    PurchaseOrderShipmentLink,
    Shipment,
    ShipmentLine,
    Vendor,
)

User = get_user_model()


class ShipmentCreateWizardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            username="wizard_smoke",
            email="wizard@test.local",
            password="TestPass123!@",
        )
        cls.domain = Domain.objects.create(
            name="Wizard Domain",
            slug="wizard-domain",
            created_by=cls.user,
            updated_by=cls.user,
        )
        cls.part = PartFactory.create(
            data={
                "part_number": "PN-WIZ-01",
                "name": "Wizard Widget",
                "part_type": "component",
                "category": "test",
            },
            actor=cls.user,
        )
        cls.vendor = Vendor.objects.create(
            name="Wizard Vendor Co",
            code="WIZ",
            created_by=cls.user,
            updated_by=cls.user,
        )

    def setUp(self):
        self.client.force_login(self.user)
        # D5's fence reads the login-time domain snapshot, not the user's
        # groups. A superuser with no domain assignment legitimately sees no
        # rows, so the snapshot is set explicitly rather than assumed.
        session = self.client.session
        session["user_domain_ids"] = [self.domain.pk]
        session.save()
        self.url = reverse("shipment_create")

    # ------------------------------------------------------------------ #

    def test_nothing_is_written_until_submit(self):
        po, line_1, _ = self._placed_po_with_two_lines(ordered_1="10", ordered_2="4")

        self.client.post(
            self.url, {"action": "save_header", "purchase_order_id": po.pk,
                       "carrier": "DHL"}
        )
        self.client.post(
            self.url,
            {
                "action": "add_from_po_lines",
                "po_line_ids": [line_1.pk],
                f"quantity_{line_1.pk}": "6",
            },
        )

        self.assertFalse(Shipment.objects.exists())
        self.assertFalse(PurchaseOrderShipmentLink.objects.exists())

        # ...and the staged work survives a plain reload (the F5 rule).
        page = self.client.get(self.url)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "PN-WIZ-01")

    def test_two_lines_for_one_part_are_allocated_as_staged(self):
        """The case copy-on-create refuses to guess at.

        Both order lines buy the same part, so `resolve_purchase_order_line`
        returns None and the flat form would have produced one unallocated
        line. Staged explicitly, the box arrives already split 10/4 across the
        two — as ONE physical line carrying two allocations, never two rows.
        """
        po, line_1, line_2 = self._placed_po_with_two_lines(ordered_1="10", ordered_2="4")

        self.client.post(
            self.url, {"action": "save_header", "purchase_order_id": po.pk}
        )
        self.client.post(
            self.url,
            {
                "action": "add_from_po_lines",
                "po_line_ids": [line_1.pk, line_2.pk],
                f"quantity_{line_1.pk}": "10",
                f"quantity_{line_2.pk}": "4",
            },
        )
        response = self.client.post(self.url, {"action": "submit"}, follow=True)
        self.assertEqual(response.status_code, 200)

        shipment = Shipment.objects.get()
        arriving = ShipmentLine.objects.get(shipment=shipment)
        self.assertEqual(arriving.quantity, Decimal("14.000"))

        links = {
            link.purchase_order_line_id: link.quantity_allocated
            for link in PurchaseOrderShipmentLink.objects.filter(
                shipment_line=arriving, deleted_at__isnull=True
            )
        }
        self.assertEqual(links, {line_1.pk: Decimal("10.000"), line_2.pk: Decimal("4.000")})

        # The draft is gone — a refresh does not re-offer a shipment already made.
        self.assertNotIn("procurement_shipment_draft", self.client.session)

    def test_staged_allocations_suppress_copy_on_create(self):
        """A line the receiver allocated by hand must not ALSO be auto-linked.

        With one active order line for the part, copy-on-create would allocate
        the whole arriving quantity to it. Running that first would leave no
        headroom for the 3 the receiver actually staged, and the cap would
        reject the write.
        """
        po, line_1 = self._placed_po_with_one_line(ordered="10")

        self.client.post(
            self.url, {"action": "save_header", "purchase_order_id": po.pk}
        )
        self.client.post(
            self.url,
            {"action": "add_unlinked_line", "part_id": self.part.pk, "quantity": "8"},
        )
        self.client.post(
            self.url,
            {
                "action": "allocate",
                "line_index": 0,
                "purchase_order_line_id": line_1.pk,
                "quantity": "3",
            },
        )
        self.client.post(self.url, {"action": "submit"}, follow=True)

        arriving = ShipmentLine.objects.get()
        link = PurchaseOrderShipmentLink.objects.get(
            shipment_line=arriving, deleted_at__isnull=True
        )
        self.assertEqual(link.quantity_allocated, Decimal("3.000"))
        # 5 of the 8 arrived with nothing to answer for — a real state, not an error.
        self.assertEqual(arriving.quantity - link.quantity_allocated, Decimal("5.000"))

    def test_line_with_no_staged_allocation_still_copies_on_create(self):
        """The old flat form's behaviour is the default, not a casualty."""
        po, line_1 = self._placed_po_with_one_line(ordered="10")

        self.client.post(
            self.url, {"action": "save_header", "purchase_order_id": po.pk}
        )
        self.client.post(
            self.url,
            {"action": "add_unlinked_line", "part_id": self.part.pk, "quantity": "10"},
        )
        self.client.post(self.url, {"action": "submit"}, follow=True)

        link = PurchaseOrderShipmentLink.objects.get(deleted_at__isnull=True)
        self.assertEqual(link.purchase_order_line_id, line_1.pk)
        self.assertEqual(link.quantity_allocated, Decimal("10.000"))

    def test_over_allocating_an_arriving_line_is_refused_in_the_draft(self):
        """The cap that keeps the link table honest, enforced while staging so
        the receiver is not told everything is fine right up to submit."""
        po, line_1, line_2 = self._placed_po_with_two_lines(ordered_1="10", ordered_2="10")

        self.client.post(
            self.url, {"action": "save_header", "purchase_order_id": po.pk}
        )
        self.client.post(
            self.url,
            {"action": "add_unlinked_line", "part_id": self.part.pk, "quantity": "10"},
        )
        self.client.post(
            self.url,
            {"action": "allocate", "line_index": 0,
             "purchase_order_line_id": line_1.pk, "quantity": "7"},
        )
        self.client.post(
            self.url,
            {"action": "allocate", "line_index": 0,
             "purchase_order_line_id": line_2.pk, "quantity": "4"},
        )

        draft = self.client.session["procurement_shipment_draft"]
        allocations = draft["lines"][0]["allocations"]
        self.assertEqual(len(allocations), 1)
        self.assertEqual(allocations[0]["purchase_order_line_id"], line_1.pk)

    def test_a_shipment_with_no_order_needs_a_domain(self):
        self.client.post(
            self.url,
            {"action": "add_unlinked_line", "part_id": self.part.pk, "quantity": "2"},
        )
        # No header at all — the line was refused before it could be staged.
        self.assertNotIn("procurement_shipment_draft", self.client.session)

        self.client.post(
            self.url, {"action": "save_header", "domain_id": self.domain.pk}
        )
        self.client.post(
            self.url,
            {"action": "add_unlinked_line", "part_id": self.part.pk, "quantity": "2"},
        )
        self.client.post(self.url, {"action": "submit"}, follow=True)

        shipment = Shipment.objects.get()
        self.assertIsNone(shipment.purchase_order_id)
        self.assertEqual(shipment.domain_id, self.domain.pk)

    # ------------------------------------------------------------------ #

    def _placed_po_with_one_line(self, *, ordered: str):
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
        self._place(po)
        line = PurchaseOrderLine.objects.get(purchase_order=po)
        line.refresh_from_db()
        return po, line

    def _placed_po_with_two_lines(self, *, ordered_1: str, ordered_2: str):
        """Two active lines for the SAME part — D58's soft rule deliberately
        breached, which is exactly the case the wizard exists to resolve."""
        po, line_1 = self._placed_po_with_one_line_unplaced(ordered=ordered_1)
        line_2 = PurchaseOrderLine.objects.create(
            purchase_order=po,
            part_id=self.part.pk,
            line_number=line_1.line_number + 1,
            quantity_ordered=Decimal(ordered_2),
            unit_cost=Decimal("10.00"),
            created_by=self.user,
            updated_by=self.user,
        )
        GraphSummaryManager.initialize_node(entity=line_2, actor=self.user)
        self._place(po)
        line_1.refresh_from_db()
        line_2.refresh_from_db()
        return po, line_1, line_2

    def _placed_po_with_one_line_unplaced(self, *, ordered: str):
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
        return po, PurchaseOrderLine.objects.get(purchase_order=po)

    def _place(self, po):
        context = PurchaseOrderContext(po.pk)
        context.submit_for_approval(actor=self.user)
        context.approve_order(actor=self.user)
        context.place(actor=self.user)
