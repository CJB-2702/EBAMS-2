"""Phase 5 route/view tests: the Scan Session portal and the Reconciliation
Hub. Control-layer behavior (barcode parsing, FIFO cascade, resolution
semantics) is already covered by `test_intake_matching.py`/`test_intake.py`
— these tests exercise the HTTP surface (full-page renders, HTMX fragments,
form-POST actions) the way `procurement/tests/test_shipment_edit_page.py`
exercises its own view.
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
from app.inventory.control_layer.errors import ReconciliationBarrierError
from app.inventory.control_layer.factories.warehouse_factory import WarehouseFactory
from app.inventory.control_layer.intake_context import IntakeContext
from app.inventory.models.intake.enums import (
    AllocationCondition,
    IntakeSessionMethod,
    IntakeSessionStatus,
    ReconciliationStatus,
)
from app.inventory.models.intake.item_allocation import ItemAllocation
from app.parts.control_layer.factories.part_factory import PartFactory
from app.procurement.control_layer.factories.shipment_factory import ShipmentFactory
from app.procurement.models import ShipmentLine

User = get_user_model()


class ScanReconciliationTestCase(TestCase):
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


class ScanSessionStartTests(ScanReconciliationTestCase):
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


class ScanPortalTests(ScanReconciliationTestCase):
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

    def test_reassign_staged_allocation_to_open_line(self):
        line = self._shipment_line(part=self.part_a, quantity=Decimal("5"), shipment_id="SHP-REASSIGN")
        ctx = self._active_scan_session(line=line)
        allocation = ctx.create_manual_allocation(
            shipment_line_id=None, part_id=self.part_a.pk,
            quantity=Decimal("2"), condition=AllocationCondition.GOOD, actor=self.user,
        )
        detail_url = reverse(
            "inventory_intake_session_detail", kwargs={"pk": ctx.intake_session_id}
        )

        response = self.client.post(
            detail_url,
            {
                "action": "reassign",
                "allocation_id": allocation.pk,
                "target_shipment_line_id": line.pk,
            },
        )
        self.assertEqual(response.status_code, 303)
        allocation.refresh_from_db()
        self.assertEqual(allocation.shipment_line_id, line.pk)

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

    def test_close_blocked_by_pending_reconciliation_then_succeeds(self):
        line = self._shipment_line(part=self.part_a, quantity=Decimal("10"), shipment_id="SHP-CLOSEBARR")
        ctx = self._active_scan_session(line=line)
        ctx.create_manual_allocation(
            shipment_line_id=line.pk, part_id=self.part_a.pk,
            quantity=Decimal("4"), condition=AllocationCondition.GOOD, actor=self.user,
        )
        detail_url = reverse(
            "inventory_intake_session_detail", kwargs={"pk": ctx.intake_session_id}
        )

        self.client.post(detail_url, {"action": "transition_to_reconciliation"})
        ctx.session.refresh_from_db()
        self.assertEqual(ctx.session.status, IntakeSessionStatus.RECONCILING)

        # Closing now is blocked (a pending PartReconciliationSession exists).
        self.client.post(detail_url, {"action": "close"})
        ctx.session.refresh_from_db()
        self.assertEqual(ctx.session.status, IntakeSessionStatus.RECONCILING)

        reconciliation = ctx.session.reconciliations.get(part=self.part_a)
        recon_line = reconciliation.lines.get(deleted_at__isnull=True)
        ctx.resolve_line(
            reconciliation_line_id=recon_line.pk,
            resolution_type="accepted_shortage",
            actor=self.user,
        )

        self.client.post(detail_url, {"action": "close"})
        ctx.session.refresh_from_db()
        self.assertEqual(ctx.session.status, IntakeSessionStatus.CLOSED)


class ReconciliationHubTests(ScanReconciliationTestCase):
    def _reconciling_session(self):
        line = self._shipment_line(part=self.part_a, quantity=Decimal("10"), shipment_id="SHP-HUB")
        ctx = self._active_scan_session(line=line)
        ctx.create_manual_allocation(
            shipment_line_id=line.pk, part_id=self.part_a.pk,
            quantity=Decimal("6"), condition=AllocationCondition.GOOD, actor=self.user,
        )
        ctx.transition_to_reconciliation(actor=self.user)
        return ctx

    def test_hub_lists_reconciling_sessions_by_default(self):
        ctx = self._reconciling_session()
        response = self.client.get(reverse("inventory_reconciliation_hub"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"#{ctx.intake_session_id}")

    def test_hub_has_unresolved_filter_excludes_fully_resolved_sessions(self):
        ctx = self._reconciling_session()
        reconciliation = ctx.session.reconciliations.get(part=self.part_a)
        recon_line = reconciliation.lines.get(deleted_at__isnull=True)
        ctx.resolve_line(
            reconciliation_line_id=recon_line.pk,
            resolution_type="accepted_shortage",
            actor=self.user,
        )

        response = self.client.get(
            f"{reverse('inventory_reconciliation_hub')}?has_unresolved_parts=1&format=htmx-search-results"
        )
        self.assertNotContains(response, f"#{ctx.intake_session_id}")

        response_any = self.client.get(
            f"{reverse('inventory_reconciliation_hub')}?has_unresolved_parts=0&format=htmx-search-results"
        )
        self.assertContains(response_any, f"#{ctx.intake_session_id}")


class ReconciliationDetailTests(ScanReconciliationTestCase):
    def test_resolving_all_children_resolves_the_parent(self):
        shipment = ShipmentFactory.create(
            domain=self.domain,
            lines=[
                {"part_id": self.part_a.pk, "quantity": Decimal("10")},
                {"part_id": self.part_a.pk, "quantity": Decimal("10")},
            ],
            actor=self.user,
            shipment_id="SHP-DETAIL",
        )
        lines = list(shipment.lines.filter(deleted_at__isnull=True).order_by("id"))
        ctx = IntakeContext.start_session(
            operator=self.user, warehouse_id=self.warehouse.pk,
            intake_method=IntakeSessionMethod.SCAN, actor=self.user,
        )
        ctx.associate_shipment(shipment_id=shipment.pk, actor=self.user)
        ctx.create_manual_allocation(
            shipment_line_id=lines[0].pk, part_id=self.part_a.pk,
            quantity=Decimal("6"), condition=AllocationCondition.GOOD, actor=self.user,
        )
        ctx.create_manual_allocation(
            shipment_line_id=lines[1].pk, part_id=self.part_a.pk,
            quantity=Decimal("7"), condition=AllocationCondition.GOOD, actor=self.user,
        )
        ctx.transition_to_reconciliation(actor=self.user)
        reconciliation = ctx.session.reconciliations.get(part=self.part_a)
        recon_lines = list(reconciliation.lines.filter(deleted_at__isnull=True).order_by("id"))
        self.assertEqual(len(recon_lines), 2)

        detail_url = reverse("inventory_reconciliation_detail", kwargs={"pk": reconciliation.pk})
        page = self.client.get(detail_url)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, self.part_a.part_number)

        self.client.post(
            detail_url,
            {
                "action": "resolve_line",
                "reconciliation_line_id": recon_lines[0].pk,
                "resolution_type": "accepted_shortage",
                "notes": "Vendor shorted us.",
            },
        )
        reconciliation.refresh_from_db()
        self.assertEqual(reconciliation.status, ReconciliationStatus.PENDING)

        self.client.post(
            detail_url,
            {
                "action": "resolve_line",
                "reconciliation_line_id": recon_lines[1].pk,
                "resolution_type": "accepted_shortage",
                "notes": "Vendor shorted us on both.",
            },
        )
        reconciliation.refresh_from_db()
        self.assertEqual(reconciliation.status, ReconciliationStatus.RESOLVED)

    def test_pull_external_allocation_from_another_session(self):
        # Session A: staged excess of part_b sitting unlinked.
        excess_line = self._shipment_line(
            part=self.part_b, quantity=Decimal("5"), shipment_id="SHP-EXCESS-SRC"
        )
        source_ctx = self._active_scan_session(line=excess_line)
        excess_allocation = source_ctx.create_manual_allocation(
            shipment_line_id=None, part_id=self.part_b.pk,
            quantity=Decimal("3"), condition=AllocationCondition.GOOD, actor=self.user,
        )

        # Session B: shortage of part_b, in reconciliation.
        shortage_line = self._shipment_line(
            part=self.part_b, quantity=Decimal("10"), shipment_id="SHP-EXCESS-DST"
        )
        target_ctx = self._active_scan_session(line=shortage_line)
        target_ctx.create_manual_allocation(
            shipment_line_id=shortage_line.pk, part_id=self.part_b.pk,
            quantity=Decimal("4"), condition=AllocationCondition.GOOD, actor=self.user,
        )
        target_ctx.transition_to_reconciliation(actor=self.user)
        reconciliation = target_ctx.session.reconciliations.get(part=self.part_b)

        detail_url = reverse("inventory_reconciliation_detail", kwargs={"pk": reconciliation.pk})
        page = self.client.get(detail_url)
        self.assertContains(page, f"#{source_ctx.intake_session_id}")

        response = self.client.post(
            detail_url,
            {
                "action": "pull_external",
                "allocation_id": excess_allocation.pk,
                "target_line_id": shortage_line.pk,
            },
        )
        self.assertEqual(response.status_code, 303)
        excess_allocation.refresh_from_db()
        self.assertEqual(excess_allocation.intake_session_id, target_ctx.intake_session_id)
        self.assertEqual(excess_allocation.shipment_line_id, shortage_line.pk)
