"""Phase 5 route/view tests: the Scan Session portal.

Control-layer behavior (barcode parsing, FIFO cascade) is already covered by
`test_intake_matching.py`/`test_intake.py` — these tests exercise the HTTP
surface (full-page renders, HTMX fragments, form-POST actions) the way
`procurement/tests/test_shipment_edit_page.py` exercises its own view.

The Reconciliation Hub / detail suites were deleted with those routes
(intake_portal_workflow.md §7.4, §12.5). Their replacements are Phase 2's
discrepancy report and allocation portal, which do not exist yet.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from app.administration.models import Division, Domain
from app.administration.models.data_ownership.user_assignments.user_domains import (
    UserDomain,
)
from app.inventory.control_layer.factories.warehouse_factory import WarehouseFactory
from app.inventory.control_layer.intake_context import IntakeContext
from app.inventory.models.intake.enums import (
    AllocationCondition,
    IntakeSessionMethod,
    IntakeSessionStatus,
)
from app.inventory.models.intake.item_allocation import ItemAllocation
from app.parts.control_layer.factories.part_factory import PartFactory
from app.procurement.control_layer.factories.shipment_factory import ShipmentFactory
from app.procurement.models import ShipmentLine

User = get_user_model()


class ScanPortalTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            username="scan_smoke", email="scan@test.local", password="TestPass123!@"
        )
        cls.division = Division.objects.create(
            name="Scan Division", slug="scan-division",
            created_by=cls.user, updated_by=cls.user,
        )
        cls.domain = Domain.objects.create(
            name="Scan Domain", slug="scan-domain",
            created_by=cls.user, updated_by=cls.user,
        )
        cls.warehouse = WarehouseFactory.create(
            name="Scan Warehouse", code="WH-SCAN-01",
            division_id=cls.division.pk, actor=cls.user,
        )
        cls.part_a = PartFactory.create(
            data={"part_number": "PN-SCAN-A", "name": "Scan Widget A"}, actor=cls.user,
        )
        cls.part_b = PartFactory.create(
            data={"part_number": "PN-SCAN-B", "name": "Scan Widget B"}, actor=cls.user,
        )
        # `IntakePolicy.check_shipment_domain_access` checks a real `UserDomain`
        # row (not just the session snapshot `accessible_domain_ids` reads) —
        # the session key below is a separate, presentation-layer-only concern.
        UserDomain.objects.create(
            user=cls.user, domain=cls.domain,
            created_by=cls.user, updated_by=cls.user,
        )

    def setUp(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["user_domain_ids"] = [self.domain.pk]
        session.save()

    def _shipment_line(self, *, part, quantity, shipment_id: str) -> ShipmentLine:
        shipment = ShipmentFactory.create(
            domain=self.domain,
            lines=[{"part_id": part.pk, "quantity": quantity}],
            actor=self.user,
            shipment_id=shipment_id,
        )
        return shipment.lines.get(deleted_at__isnull=True)

    def _active_scan_session(self, *, line: ShipmentLine) -> IntakeContext:
        ctx = IntakeContext.start_session(
            operator=self.user, warehouse_id=self.warehouse.pk,
            intake_method=IntakeSessionMethod.SCAN, actor=self.user,
        )
        ctx.associate_shipment(shipment_id=line.shipment_id, actor=self.user)
        return ctx


class ScanSessionStartTests(ScanPortalTestCase):
    def test_start_page_renders(self):
        response = self.client.get(reverse("inventory_scan_intake_start"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Start Scan Session")

    def test_shipment_search_fragment_is_fragment_only(self):
        line = self._shipment_line(part=self.part_a, quantity=Decimal("5"), shipment_id="SHP-SEARCH")
        response = self.client.get(
            f"{reverse('inventory_scan_intake_start')}?format=htmx-search-results"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, line.shipment.shipment_number)
        self.assertNotContains(response, "<!DOCTYPE html>")

    def test_committing_creates_an_active_scan_session_and_redirects(self):
        line = self._shipment_line(part=self.part_a, quantity=Decimal("10"), shipment_id="SHP-START")
        response = self.client.post(
            reverse("inventory_scan_intake_start"),
            {
                "warehouse_id": self.warehouse.pk,
                "shipment_ids": [line.shipment_id],
            },
        )
        self.assertEqual(response.status_code, 303)
        session = self.warehouse.intake_sessions.get(intake_method=IntakeSessionMethod.SCAN)
        self.assertEqual(session.status, IntakeSessionStatus.ACTIVE)
        self.assertEqual(response["Location"], reverse(
            "inventory_intake_session_detail", kwargs={"pk": session.pk}
        ))

    def test_missing_selection_redirects_back_with_no_session_created(self):
        response = self.client.post(
            reverse("inventory_scan_intake_start"), {"warehouse_id": self.warehouse.pk}
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.warehouse.intake_sessions.filter(
            intake_method=IntakeSessionMethod.SCAN
        ).exists())


class ScanPortalTests(ScanPortalTestCase):
    def test_active_scan_session_renders_the_scan_portal(self):
        line = self._shipment_line(part=self.part_a, quantity=Decimal("5"), shipment_id="SHP-PORTAL")
        ctx = self._active_scan_session(line=line)

        response = self.client.get(
            reverse("inventory_intake_session_detail", kwargs={"pk": ctx.intake_session_id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Scan or type barcode payload")
        self.assertContains(response, "Staged")

    def test_full_page_scan_post_redirects_and_creates_an_allocation(self):
        line = self._shipment_line(part=self.part_a, quantity=Decimal("5"), shipment_id="SHP-SCANPOST")
        ctx = self._active_scan_session(line=line)
        detail_url = reverse(
            "inventory_intake_session_detail", kwargs={"pk": ctx.intake_session_id}
        )

        response = self.client.post(
            detail_url,
            {"action": "scan", "raw_payload": self.part_a.part_number, "condition": "good"},
        )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response["Location"], detail_url)
        self.assertTrue(
            ItemAllocation.objects.filter(intake_session_id=ctx.intake_session_id).exists()
        )

    def test_htmx_scan_fragment_response_is_fragment_only(self):
        line = self._shipment_line(part=self.part_a, quantity=Decimal("5"), shipment_id="SHP-FRAGMENT")
        ctx = self._active_scan_session(line=line)
        detail_url = reverse(
            "inventory_intake_session_detail", kwargs={"pk": ctx.intake_session_id}
        )

        response = self.client.post(
            f"{detail_url}?format=htmx-scan-feed",
            {"action": "scan", "raw_payload": self.part_a.part_number, "condition": "good"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "scan-live-region")
        self.assertNotContains(response, "<!DOCTYPE html>")

    def test_unparseable_scan_reports_an_error_without_crashing(self):
        line = self._shipment_line(part=self.part_a, quantity=Decimal("5"), shipment_id="SHP-BADSCAN")
        ctx = self._active_scan_session(line=line)
        detail_url = reverse(
            "inventory_intake_session_detail", kwargs={"pk": ctx.intake_session_id}
        )

        response = self.client.post(
            f"{detail_url}?format=htmx-scan-feed",
            {"action": "scan", "raw_payload": "   ", "condition": "good"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "notification is-danger")

    def test_split_allocation_conserves_quantity(self):
        line = self._shipment_line(part=self.part_a, quantity=Decimal("5"), shipment_id="SHP-SPLIT")
        ctx = self._active_scan_session(line=line)
        allocation = ctx.create_manual_allocation(
            shipment_line_id=line.pk, part_id=self.part_a.pk,
            quantity=Decimal("5"), condition=AllocationCondition.GOOD, actor=self.user,
        )
        detail_url = reverse(
            "inventory_intake_session_detail", kwargs={"pk": ctx.intake_session_id}
        )

        self.client.post(
            detail_url,
            {
                "action": "split",
                "allocation_id": allocation.pk,
                "good_qty": "3",
                "rejected_qty": "2",
            },
        )
        live = ItemAllocation.objects.filter(
            intake_session_id=ctx.intake_session_id, deleted_at__isnull=True
        )
        total = sum((a.quantity for a in live), Decimal("0"))
        self.assertEqual(total, Decimal("5"))

    def test_close_posts_stock_even_when_the_receipt_is_short(self):
        """No barrier, no sign-off (§7.1): 4 of 10 received still posts, so
        the parts are pickable today while the shortage stays visible."""
        line = self._shipment_line(part=self.part_a, quantity=Decimal("10"), shipment_id="SHP-CLOSESHORT")
        ctx = self._active_scan_session(line=line)
        ctx.create_manual_allocation(
            shipment_line_id=line.pk, part_id=self.part_a.pk,
            quantity=Decimal("4"), condition=AllocationCondition.GOOD, actor=self.user,
        )
        detail_url = reverse(
            "inventory_intake_session_detail", kwargs={"pk": ctx.intake_session_id}
        )

        self.client.post(detail_url, {"action": "close"})
        ctx.session.refresh_from_db()
        self.assertEqual(ctx.session.status, IntakeSessionStatus.CLOSED)
        self.assertIsNotNone(ctx.session.stock_posted_at)
