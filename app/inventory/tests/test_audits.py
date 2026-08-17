"""Phase 7 acceptance tests: audit sessions, inline edits, log immutability."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase

from app.administration.models import Division, Domain
from app.inventory.control_layer.audit_session_context import AuditSessionContext
from app.inventory.control_layer.errors import InventoryValidationError
from app.inventory.control_layer.factories.warehouse_factory import WarehouseFactory
from app.inventory.control_layer.managers.stock_ledger_manager import StockLedgerManager
from app.inventory.models.audit.audit_session import AuditSession
from app.inventory.models.audit.enums import AuditResolutionType, AuditSessionStatus, DiscrepancyType
from app.inventory.models.audit.inventory_audit_log import InventoryAuditLog
from app.inventory.models.movements.part_movement import PartMovement
from app.inventory.models.stock.active_inventory import ActiveInventory
from app.inventory.models.topography.room import Room
from app.parts.control_layer.factories.part_factory import PartFactory

User = get_user_model()


class AuditTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="audit_tester", email="audit@test.local", password="TestPass123!@"
        )
        perm = Permission.objects.get(codename="can_audit_stock")
        cls.user.user_permissions.add(perm)

        cls.division = Division.objects.create(
            name="Audit Division", slug="audit-division",
            created_by=cls.user, updated_by=cls.user,
        )
        cls.warehouse = WarehouseFactory.create(
            name="Audit Warehouse", code="WH-AUDIT",
            division_id=cls.division.pk, actor=cls.user,
        )
        cls.room = Room.objects.create(
            warehouse=cls.warehouse, room_name="Main Room",
            created_by=cls.user, updated_by=cls.user,
        )
        cls.part = PartFactory.create(
            data={"part_number": "PN-AUDIT-01", "name": "Audit Widget"},
            actor=cls.user,
        )
        
        # Inject starting stock
        StockLedgerManager.inject(
            warehouse=cls.warehouse, room=cls.room, storage_location=None,
            part=cls.part, qty=Decimal("10"), actor=cls.user,
        )
        cls.balance = ActiveInventory.objects.get(room=cls.room, part=cls.part)

    def test_inline_edit_creates_session_and_updates_stock_atomically(self):
        AuditSessionContext.inline_edit(
            active_inventory_id=self.balance.pk,
            new_qty=Decimal("8"),
            actor=self.user,
        )
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.quantity_on_hand, Decimal("8"))
        
        # Session should be created and completed
        session = AuditSession.objects.last()
        self.assertEqual(session.status, AuditSessionStatus.COMPLETED)
        
        # Log should exist
        log = InventoryAuditLog.objects.last()
        self.assertEqual(log.previous_qty, Decimal("10"))
        self.assertEqual(log.new_qty, Decimal("8"))
        self.assertEqual(log.variance_qty, Decimal("-2"))
        self.assertEqual(log.reason_code, "inline_quantity_edit")

    def test_zero_variance_edit_is_noop(self):
        session_count_before = AuditSession.objects.count()
        AuditSessionContext.inline_edit(
            active_inventory_id=self.balance.pk,
            new_qty=Decimal("10"),
            actor=self.user,
        )
        session_count_after = AuditSession.objects.count()
        self.assertEqual(session_count_before, session_count_after)

    def test_finalize_unrecorded_transfer_produces_linked_movement(self):
        # Unrecorded transfer of a surplus withdraws from the intake room.
        intake_room = self.warehouse.rooms.get(is_intake_room=True)
        StockLedgerManager.inject(
            warehouse=self.warehouse, room=intake_room, storage_location=None,
            part=self.part, qty=Decimal("5"), actor=self.user,
        )
        
        ctx = AuditSessionContext.start(
            warehouse_id=self.warehouse.pk,
            room_id=self.room.pk,
            conducted_by=self.user,
            actor=self.user,
        )
        line = ctx.record_line(
            part_id=self.part.pk,
            counted_qty=Decimal("15"), # +5 variance
            actor=self.user,
        )
        self.assertEqual(line.discrepancy_type, DiscrepancyType.SURPLUS_FOUND)
        
        ctx.set_resolution(
            line_id=line.pk,
            resolution_type=AuditResolutionType.UNRECORDED_TRANSFER,
            actor=self.user,
        )
        ctx.finalize(actor=self.user)
        
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.quantity_on_hand, Decimal("15"))
        
        line.refresh_from_db()
        self.assertIsNotNone(line.linked_movement)
        self.assertEqual(line.linked_movement.quantity, Decimal("5"))

    def test_finalize_fails_if_unresolved_lines_exist(self):
        ctx = AuditSessionContext.start(
            warehouse_id=self.warehouse.pk,
            room_id=self.room.pk,
            conducted_by=self.user,
            actor=self.user,
        )
        ctx.record_line(
            part_id=self.part.pk,
            counted_qty=Decimal("15"), # +5 variance
            actor=self.user,
        )
        with self.assertRaises(InventoryValidationError):
            ctx.finalize(actor=self.user)
