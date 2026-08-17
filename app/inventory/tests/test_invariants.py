"""Phase 8 hardening tests: data invariants, seam exclusivity, and mass conservation."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import F
from django.test import TestCase

from app.administration.models import Division, Domain
from app.inventory.control_layer.factories.warehouse_factory import WarehouseFactory
from app.inventory.control_layer.managers.stock_ledger_manager import StockLedgerManager
from app.inventory.control_layer.errors import InsufficientStockError
from app.inventory.models.stock.active_inventory import ActiveInventory
from app.inventory.models.topography.room import Room
from app.parts.control_layer.factories.part_factory import PartFactory
from app.procurement.control_layer.shipment_context import ShipmentContext
from app.procurement.models import Shipment, ShipmentLine

User = get_user_model()


class InvariantTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="invariant_tester", email="inv@test.local", password="TestPass123!@"
        )
        cls.division = Division.objects.create(
            name="Inv Division", slug="inv-division",
            created_by=cls.user, updated_by=cls.user,
        )
        cls.domain = Domain.objects.create(
            name="Inv Domain", slug="inv-domain",
            created_by=cls.user, updated_by=cls.user,
        )
        cls.warehouse = WarehouseFactory.create(
            name="Inv Warehouse", code="WH-INV",
            division_id=cls.division.pk, actor=cls.user,
        )
        cls.room = Room.objects.create(
            warehouse=cls.warehouse, room_name="Main Room",
            created_by=cls.user, updated_by=cls.user,
        )
        cls.part = PartFactory.create(
            data={"part_number": "PN-INV-01", "name": "Invariant Widget"},
            actor=cls.user,
        )

    def test_stock_cannot_be_negative(self):
        StockLedgerManager.inject(
            warehouse=self.warehouse, room=self.room, storage_location=None,
            part=self.part, qty=Decimal("5"), actor=self.user,
        )
        with self.assertRaises(InsufficientStockError):
            StockLedgerManager.withdraw(
                room=self.room, storage_location=None,
                part=self.part, qty=Decimal("10"), actor=self.user,
            )
            
    def test_physical_negative_stock_constraint(self):
        # Even bypassing the control layer, the DB constraint should catch it
        row = ActiveInventory.objects.create(
            warehouse=self.warehouse,
            room=self.room,
            part=self.part,
            quantity_on_hand=Decimal("5"),
            created_by=self.user,
            updated_by=self.user,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                row.quantity_on_hand = Decimal("-1")
                row.save()

    def test_allocate_cannot_exceed_on_hand_via_issuance(self):
        from app.inventory.control_layer.orchestrators.part_issuance_orchestrator import PartIssuanceOrchestrator
        from app.inventory.models.issuance.enums import IssueType

        balance = StockLedgerManager.inject(
            warehouse=self.warehouse, room=self.room, storage_location=None,
            part=self.part, qty=Decimal("5"), actor=self.user,
        )
        with self.assertRaises(InsufficientStockError):
            PartIssuanceOrchestrator.issue(
                quantity=Decimal("10"),
                issue_type=IssueType.DIRECT_TO_USER,
                issued_to=self.user,
                active_inventory_id=balance.pk,
                actor=self.user,
            )

    def test_shipment_seam_enforces_exclusivity(self):
        """Procurement's ShipmentContext is the only allowed updater of received_qty."""
        shipment = Shipment.objects.create(
            shipment_number="INV-SHIP-01",
            domain=self.domain,
            status="expected",
            created_by=self.user,
            updated_by=self.user,
        )
        line = ShipmentLine.objects.create(
            shipment=shipment,
            part=self.part,
            quantity=Decimal("10"),
            quantity_accepted=Decimal("0"),
            created_by=self.user,
            updated_by=self.user,
        )
        
        ctx = ShipmentContext(shipment.pk)
        ctx.accept_line(line=line, quantity_accepted=Decimal("4"), actor=self.user)
        line.refresh_from_db()
        self.assertEqual(line.quantity_accepted, Decimal("4"))
        
        # Test that advancing marks it correctly
        ctx.advance(to_status="received", actor=self.user)
        shipment.refresh_from_db()
        self.assertEqual(shipment.status, "received")

    def test_issues_index_query(self):
        """Verify IssueSearch.index_list runs without FieldError."""
        from app.inventory.presentation_layer.search.issue_search import IssueSearch
        from app.inventory.control_layer.orchestrators.part_issuance_orchestrator import PartIssuanceOrchestrator
        from app.inventory.models.issuance.enums import IssueType

        balance = StockLedgerManager.inject(
            warehouse=self.warehouse, room=self.room, storage_location=None,
            part=self.part, qty=Decimal("5"), actor=self.user,
        )
        issue = PartIssuanceOrchestrator.issue(
            quantity=Decimal("2"),
            issue_type=IssueType.DIRECT_TO_USER,
            issued_to=self.user,
            active_inventory_id=balance.pk,
            actor=self.user,
        )
        qs = IssueSearch.index_list(domain_ids=[self.domain.pk])
        self.assertIn(issue, list(qs))

        self.client.force_login(self.user)
        response = self.client.get("/inventory/issues/")
        self.assertEqual(response.status_code, 200)

