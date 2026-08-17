"""Phase 4 acceptance tests: intake session lifecycle, commit orchestration,
and the procurement/stock hand-off.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from app.administration.models import Division, Domain
from app.inventory.control_layer.errors import (
    InventoryValidationError,
    ReconciliationBarrierError,
)
from app.inventory.control_layer.factories.warehouse_factory import WarehouseFactory
from app.inventory.control_layer.intake_context import IntakeContext
from app.inventory.control_layer.managers.reconciliation_manager import (
    ReconciliationManager,
)
from app.inventory.models.intake.enums import (
    AllocationCondition,
    IntakeSessionMethod,
    IntakeSessionStatus,
    ReconciliationStatus,
)
from app.inventory.models.intake.intake_session import IntakeSession
from app.inventory.models.intake.item_allocation import ItemAllocation
from app.inventory.models.stock.active_inventory import ActiveInventory
from app.parts.control_layer.factories.part_factory import PartFactory
from app.procurement.control_layer.factories.shipment_factory import ShipmentFactory
from app.procurement.models import ShipmentLine

User = get_user_model()


class IntakeTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="intake_smoke", email="intake@test.local", password="TestPass123!@"
        )
        cls.division = Division.objects.create(
            name="Intake Division", slug="intake-division",
            created_by=cls.user, updated_by=cls.user,
        )
        cls.domain = Domain.objects.create(
            name="Intake Domain", slug="intake-domain",
            created_by=cls.user, updated_by=cls.user,
        )
        cls.warehouse = WarehouseFactory.create(
            name="Intake Warehouse", code="WH-INTAKE-01",
            division_id=cls.division.pk, actor=cls.user,
        )
        cls.intake_room = cls.warehouse.rooms.get(is_intake_room=True)
        cls.part_a = PartFactory.create(
            data={"part_number": "PN-INTAKE-A", "name": "Widget A"}, actor=cls.user,
        )
        cls.part_b = PartFactory.create(
            data={"part_number": "PN-INTAKE-B", "name": "Widget B"}, actor=cls.user,
        )

    def _shipment(self, *, part, quantity, shipment_id: str) -> ShipmentLine:
        shipment = ShipmentFactory.create(
            domain=self.domain,
            lines=[{"part_id": part.pk, "quantity": quantity}],
            actor=self.user,
            shipment_id=shipment_id,
        )
        return shipment.lines.get(deleted_at__isnull=True)


class AutoIntakeCommitTests(IntakeTestCase):
    def test_full_receipt_injects_stock_into_intake_room(self):
        line = self._shipment(part=self.part_a, quantity=Decimal("10"), shipment_id="SHP-FULL")

        context = IntakeContext.commit_auto_intake(
            operator=self.user,
            warehouse_id=self.warehouse.pk,
            room_id=None,
            shipment_id=line.shipment_id,
            line_targets={line.pk: (Decimal("10"), Decimal("0"))},
            actor=None,
        )

        session = context.session
        self.assertEqual(session.status, IntakeSessionStatus.CLOSED)
        line.refresh_from_db()
        self.assertEqual(line.quantity_accepted, Decimal("10"))
        self.assertEqual(line.quantity, Decimal("10"))  # no split — fully received

        balance = ActiveInventory.objects.get(
            room=self.intake_room, storage_location__isnull=True, part=self.part_a
        )
        self.assertEqual(balance.quantity_on_hand, Decimal("10"))

    def test_partial_receipt_splits_the_shipment_line(self):
        line = self._shipment(part=self.part_a, quantity=Decimal("20"), shipment_id="SHP-PARTIAL")

        IntakeContext.commit_auto_intake(
            operator=self.user,
            warehouse_id=self.warehouse.pk,
            room_id=None,
            shipment_id=line.shipment_id,
            line_targets={line.pk: (Decimal("12"), Decimal("0"))},
            actor=None,
        )

        line.refresh_from_db()
        self.assertEqual(line.quantity, Decimal("12"))
        self.assertEqual(line.quantity_accepted, Decimal("12"))

        sibling = ShipmentLine.objects.filter(
            shipment_id=line.shipment_id, deleted_at__isnull=True
        ).exclude(pk=line.pk).get()
        self.assertEqual(sibling.quantity, Decimal("8"))
        self.assertIsNone(sibling.quantity_accepted)

    def test_cumulative_accept_across_two_closed_sessions(self):
        line = self._shipment(part=self.part_a, quantity=Decimal("10"), shipment_id="SHP-CUMUL")

        IntakeContext.commit_auto_intake(
            operator=self.user,
            warehouse_id=self.warehouse.pk,
            room_id=None,
            shipment_id=line.shipment_id,
            line_targets={line.pk: (Decimal("4"), Decimal("0"))},
            actor=None,
        )
        line.refresh_from_db()
        self.assertEqual(line.quantity_accepted, Decimal("4"))
        # First receipt was partial — line stays at its shipped 10, no split yet
        # because 4 < 10 triggers a split down to 4 with 6 remaining open.
        self.assertEqual(line.quantity, Decimal("4"))

        sibling = ShipmentLine.objects.filter(
            shipment_id=line.shipment_id, deleted_at__isnull=True
        ).exclude(pk=line.pk).get()
        self.assertEqual(sibling.quantity, Decimal("6"))

        # Second receipt, against the sibling that carries the remaining balance.
        IntakeContext.commit_auto_intake(
            operator=self.user,
            warehouse_id=self.warehouse.pk,
            room_id=None,
            shipment_id=sibling.shipment_id,
            line_targets={sibling.pk: (Decimal("6"), Decimal("0"))},
            actor=None,
        )
        sibling.refresh_from_db()
        self.assertEqual(sibling.quantity_accepted, Decimal("6"))
        self.assertEqual(sibling.quantity, Decimal("6"))  # fully received, no further split

        total_stock = ActiveInventory.objects.get(
            room=self.intake_room, storage_location__isnull=True, part=self.part_a
        )
        self.assertEqual(total_stock.quantity_on_hand, Decimal("10"))

    def test_stock_is_not_created_until_session_closes(self):
        """No `ActiveInventory` row exists while the session is ACTIVE — the
        commit orchestrator is the only stock-creation path."""
        line = self._shipment(part=self.part_b, quantity=Decimal("5"), shipment_id="SHP-DRAFT")

        session_context = IntakeContext.start_session(
            operator=self.user, warehouse_id=self.warehouse.pk,
            intake_method=IntakeSessionMethod.SCAN, actor=None,
        )
        session_context.associate_shipment(shipment_id=line.shipment_id, actor=None)
        session_context.create_manual_allocation(
            shipment_line_id=line.pk, part_id=self.part_b.pk,
            quantity=Decimal("5"), condition=AllocationCondition.GOOD, actor=None,
        )

        self.assertEqual(session_context.session.status, IntakeSessionStatus.ACTIVE)
        self.assertFalse(
            ActiveInventory.objects.filter(part=self.part_b).exists()
        )

        session_context.close_session(actor=None)
        self.assertTrue(
            ActiveInventory.objects.filter(part=self.part_b).exists()
        )


class UnmanifestedAllocationTests(IntakeTestCase):
    def test_unmanifested_allocation_flags_session_and_quarantines_stock(self):
        line = self._shipment(part=self.part_a, quantity=Decimal("5"), shipment_id="SHP-UNMAN")

        session_context = IntakeContext.start_session(
            operator=self.user, warehouse_id=self.warehouse.pk,
            intake_method=IntakeSessionMethod.MANUAL_PACKAGE, actor=None,
        )
        session_context.associate_shipment(shipment_id=line.shipment_id, actor=None)
        session_context.create_manual_allocation(
            shipment_line_id=line.pk, part_id=self.part_a.pk,
            quantity=Decimal("5"), condition=AllocationCondition.GOOD, actor=None,
        )
        session_context.create_manual_allocation(
            shipment_line_id=None, part_id=self.part_b.pk,
            quantity=Decimal("2"), condition=AllocationCondition.GOOD, actor=None,
        )
        self.assertTrue(session_context.session.has_unlinked_allocations)

        session = session_context.close_session(actor=None)
        self.assertTrue(session.has_unlinked_allocations)

        quarantined = ActiveInventory.objects.get(
            room=self.intake_room, storage_location__isnull=True, part=self.part_b
        )
        self.assertEqual(quarantined.quantity_on_hand, Decimal("2"))


class ReconciliationBarrierTests(IntakeTestCase):
    def test_closing_with_a_pending_reconciliation_is_blocked(self):
        line = self._shipment(part=self.part_a, quantity=Decimal("10"), shipment_id="SHP-RECON")

        session_context = IntakeContext.start_session(
            operator=self.user, warehouse_id=self.warehouse.pk,
            intake_method=IntakeSessionMethod.SCAN, actor=None,
        )
        session_context.associate_shipment(shipment_id=line.shipment_id, actor=None)
        # Only 4 of the 10 physically logged — a real discrepancy.
        session_context.create_manual_allocation(
            shipment_line_id=line.pk, part_id=self.part_a.pk,
            quantity=Decimal("4"), condition=AllocationCondition.GOOD, actor=None,
        )
        session_context.transition_to_reconciliation(actor=None)
        self.assertEqual(
            session_context.session.status, IntakeSessionStatus.RECONCILING
        )

        with self.assertRaises(ReconciliationBarrierError):
            session_context.close_session(actor=None)

        # Resolving the one open line clears the barrier.
        reconciliation = session_context.session.reconciliations.get(
            part=self.part_a, deleted_at__isnull=True
        )
        recon_line = reconciliation.lines.get(deleted_at__isnull=True)
        session_context.resolve_line(
            reconciliation_line_id=recon_line.pk,
            resolution_type="accepted_shortage",
            actor=None,
        )
        reconciliation.refresh_from_db()
        self.assertEqual(reconciliation.status, ReconciliationStatus.RESOLVED)

        session = session_context.close_session(actor=None)
        self.assertEqual(session.status, IntakeSessionStatus.CLOSED)


class CancelSessionTests(IntakeTestCase):
    def test_cancel_soft_deletes_every_child_row(self):
        line = self._shipment(part=self.part_a, quantity=Decimal("5"), shipment_id="SHP-CANCEL")

        session_context = IntakeContext.start_session(
            operator=self.user, warehouse_id=self.warehouse.pk,
            intake_method=IntakeSessionMethod.SCAN, actor=None,
        )
        session_context.associate_shipment(shipment_id=line.shipment_id, actor=None)
        allocation = session_context.create_manual_allocation(
            shipment_line_id=line.pk, part_id=self.part_a.pk,
            quantity=Decimal("5"), condition=AllocationCondition.GOOD, actor=None,
        )

        session = session_context.cancel_session(actor=None, reason="Bad batch, redo.")
        self.assertEqual(session.status, IntakeSessionStatus.CANCELLED)

        allocation.refresh_from_db()
        self.assertIsNotNone(allocation.deleted_at)
        link = session.shipment_associations.get(shipment_id=line.shipment_id)
        self.assertIsNotNone(link.deleted_at)

        # Cancelling never touches stock — nothing was committed.
        self.assertFalse(ActiveInventory.objects.filter(part=self.part_a).exists())

    def test_cancel_from_closed_is_refused(self):
        line = self._shipment(part=self.part_a, quantity=Decimal("3"), shipment_id="SHP-CANCELCLOSED")
        context = IntakeContext.commit_auto_intake(
            operator=self.user,
            warehouse_id=self.warehouse.pk,
            room_id=None,
            shipment_id=line.shipment_id,
            line_targets={line.pk: (Decimal("3"), Decimal("0"))},
            actor=None,
        )
        with self.assertRaises(InventoryValidationError):
            context.cancel_session(actor=None)


class QuantityAcceptedWriteSeamTests(IntakeTestCase):
    def test_accept_line_only_ever_called_through_the_orchestrator(self):
        """Smoke test mirroring the acceptance grep — a fresh line's
        quantity_accepted stays NULL until an intake session closes."""
        line = self._shipment(part=self.part_a, quantity=Decimal("7"), shipment_id="SHP-SEAM")
        self.assertIsNone(line.quantity_accepted)

        IntakeContext.commit_auto_intake(
            operator=self.user,
            warehouse_id=self.warehouse.pk,
            room_id=None,
            shipment_id=line.shipment_id,
            line_targets={line.pk: (Decimal("7"), Decimal("0"))},
            actor=None,
        )
        line.refresh_from_db()
        self.assertEqual(line.quantity_accepted, Decimal("7"))
