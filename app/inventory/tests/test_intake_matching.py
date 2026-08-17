"""Phase 5 tests: barcode parsing, the scan-matching engine (1-to-1 / N-to-M
staging / FIFO cascade), reconciliation reassignment, cross-session excess
pulling, and split-allocation conservation.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from app.administration.models import Division, Domain
from app.inventory.control_layer.errors import (
    BarcodeParseError,
    InventoryValidationError,
)
from app.inventory.control_layer.factories.warehouse_factory import WarehouseFactory
from app.inventory.control_layer.intake_context import IntakeContext
from app.inventory.control_layer.managers.intake_matching_manager import (
    IntakeMatchingManager,
)
from app.inventory.models.intake.enums import (
    AllocationCondition,
    IntakeSessionMethod,
    ReconciliationResolutionType,
)
from app.inventory.models.intake.item_allocation import ItemAllocation
from app.parts.control_layer.factories.part_factory import PartFactory
from app.procurement.control_layer.factories.shipment_factory import ShipmentFactory

User = get_user_model()


class IntakeMatchingTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="intake_matching", email="matching@test.local", password="TestPass123!@"
        )
        cls.division = Division.objects.create(
            name="Matching Division", slug="matching-division",
            created_by=cls.user, updated_by=cls.user,
        )
        cls.domain = Domain.objects.create(
            name="Matching Domain", slug="matching-domain",
            created_by=cls.user, updated_by=cls.user,
        )
        cls.warehouse = WarehouseFactory.create(
            name="Matching Warehouse", code="WH-MATCH-01",
            division_id=cls.division.pk, actor=cls.user,
        )
        cls.part = PartFactory.create(
            data={"part_number": "PN-MATCH-A", "name": "Match Widget"}, actor=cls.user,
        )

    def _session(self) -> IntakeContext:
        return IntakeContext.start_session(
            operator=self.user, warehouse_id=self.warehouse.pk,
            intake_method=IntakeSessionMethod.SCAN, actor=None,
        )


# ---------------------------------------------------------------------- #
# Barcode parse matrix
# ---------------------------------------------------------------------- #

class BarcodeParseTests(TestCase):
    def test_plain_sku_no_serial(self):
        sku, serial = IntakeMatchingManager.parse_barcode("PN-001")
        self.assertEqual(sku, "PN-001")
        self.assertEqual(serial, "")

    def test_plain_sku_with_house_convention_serial(self):
        sku, serial = IntakeMatchingManager.parse_barcode("PN-001;SN00042")
        self.assertEqual(sku, "PN-001")
        self.assertEqual(serial, "SN00042")

    def test_gs1_bracketed_ai_notation(self):
        sku, serial = IntakeMatchingManager.parse_barcode(
            "(01)00012345678905(21)SN00042"
        )
        self.assertEqual(sku, "00012345678905")
        self.assertEqual(serial, "SN00042")

    def test_gs1_bracketed_gtin_only_no_serial_ai(self):
        sku, serial = IntakeMatchingManager.parse_barcode("(01)00012345678905")
        self.assertEqual(sku, "00012345678905")
        self.assertEqual(serial, "")

    def test_gs1_raw_digit_stream_with_serial(self):
        raw = "01" + "00012345678905" + "21" + "SN99"
        sku, serial = IntakeMatchingManager.parse_barcode(raw)
        self.assertEqual(sku, "00012345678905")
        self.assertEqual(serial, "SN99")

    def test_gs1_raw_digit_stream_gtin_only(self):
        raw = "01" + "00012345678905"
        sku, serial = IntakeMatchingManager.parse_barcode(raw)
        self.assertEqual(sku, "00012345678905")
        self.assertEqual(serial, "")

    def test_garbage_payload_raises_barcode_parse_error(self):
        with self.assertRaises(BarcodeParseError):
            IntakeMatchingManager.parse_barcode("@@@garbage!! %%%")

    def test_empty_payload_raises_barcode_parse_error(self):
        with self.assertRaises(BarcodeParseError):
            IntakeMatchingManager.parse_barcode("   ")

    def test_barcode_parse_error_is_an_inventory_validation_error(self):
        """The scan entrypoint should be able to catch this generically and
        fall back to manual entry without special-casing the exception."""
        with self.assertRaises(InventoryValidationError):
            IntakeMatchingManager.parse_barcode("")


# ---------------------------------------------------------------------- #
# 1-to-1 vs N-to-M staging vs unmanifested routing
# ---------------------------------------------------------------------- #

class MatchRoutingTests(IntakeMatchingTestCase):
    def test_unambiguous_single_line_scan_links_directly(self):
        shipment = ShipmentFactory.create(
            domain=self.domain,
            lines=[{"part_id": self.part.pk, "quantity": Decimal("10")}],
            actor=None,
        )
        line = shipment.lines.get(deleted_at__isnull=True)

        session = self._session()
        session.associate_shipment(shipment_id=shipment.pk, actor=None)

        allocation = session.process_scan(
            raw_payload=self.part.part_number, actor=None
        )
        self.assertEqual(allocation.shipment_line_id, line.pk)
        self.assertFalse(session.session.has_unlinked_allocations)

    def test_ambiguous_two_line_scan_stages_unlinked(self):
        shipment = ShipmentFactory.create(
            domain=self.domain,
            lines=[
                {"part_id": self.part.pk, "quantity": Decimal("5")},
                {"part_id": self.part.pk, "quantity": Decimal("5")},
            ],
            actor=None,
        )
        session = self._session()
        session.associate_shipment(shipment_id=shipment.pk, actor=None)

        allocation = session.process_scan(
            raw_payload=self.part.part_number, actor=None
        )
        self.assertIsNone(allocation.shipment_line_id)
        self.assertTrue(session.session.has_unlinked_allocations)

    def test_no_matching_line_routes_unmanifested(self):
        other_part = PartFactory.create(
            data={"part_number": "PN-MATCH-UNMANIFESTED", "name": "Unmanifested Widget"},
            actor=None,
        )
        shipment = ShipmentFactory.create(
            domain=self.domain,
            lines=[{"part_id": self.part.pk, "quantity": Decimal("5")}],
            actor=None,
        )
        session = self._session()
        session.associate_shipment(shipment_id=shipment.pk, actor=None)

        allocation = session.process_scan(
            raw_payload=other_part.part_number, actor=None
        )
        self.assertIsNone(allocation.shipment_line_id)
        self.assertTrue(session.session.has_unlinked_allocations)

    def test_process_scan_unknown_sku_raises_validation_error(self):
        session = self._session()
        with self.assertRaises(InventoryValidationError):
            session.process_scan(raw_payload="NOT-A-REAL-SKU", actor=None)

    def test_process_scan_unparseable_payload_falls_back_cleanly(self):
        session = self._session()
        with self.assertRaises(BarcodeParseError):
            session.process_scan(raw_payload="!!!not a barcode!!!", actor=None)


# ---------------------------------------------------------------------- #
# FIFO cascade fill order
# ---------------------------------------------------------------------- #

class FifoCascadeTests(IntakeMatchingTestCase):
    def test_cascade_fills_oldest_line_first_across_two_lines(self):
        shipment = ShipmentFactory.create(
            domain=self.domain,
            lines=[
                {"part_id": self.part.pk, "quantity": Decimal("5")},
                {"part_id": self.part.pk, "quantity": Decimal("5")},
            ],
            actor=None,
        )
        line1, line2 = shipment.lines.filter(deleted_at__isnull=True).order_by("id")

        session = self._session()
        session.associate_shipment(shipment_id=shipment.pk, actor=None)

        # Four unit scans — under line1's 5-unit expected quantity, nothing
        # is fillable yet, so everything stays staged.
        for _ in range(4):
            session.create_manual_allocation(
                shipment_line_id=None, part_id=self.part.pk,
                quantity=Decimal("1"), condition=AllocationCondition.GOOD,
                actor=None,
            )
        IntakeMatchingManager.execute_fifo_cascade(session=session.session, part=self.part)
        self.assertEqual(
            ItemAllocation.objects.filter(
                intake_session=session.session, shipment_line__isnull=True,
                deleted_at__isnull=True,
            ).count(),
            4,
        )

        # The 5th scan crosses line1's threshold — it fills fully, oldest
        # (line1) first, and the pool is empty again afterward.
        session.create_manual_allocation(
            shipment_line_id=None, part_id=self.part.pk,
            quantity=Decimal("1"), condition=AllocationCondition.GOOD,
            actor=None,
        )
        IntakeMatchingManager.execute_fifo_cascade(session=session.session, part=self.part)
        self.assertEqual(
            ItemAllocation.objects.filter(
                intake_session=session.session, shipment_line__isnull=True,
                deleted_at__isnull=True,
            ).count(),
            0,
        )

        # Five more scans cross line2's threshold the same way.
        for _ in range(5):
            session.create_manual_allocation(
                shipment_line_id=None, part_id=self.part.pk,
                quantity=Decimal("1"), condition=AllocationCondition.GOOD,
                actor=None,
            )
        IntakeMatchingManager.execute_fifo_cascade(session=session.session, part=self.part)

        line1_total = sum(
            a.quantity for a in ItemAllocation.objects.filter(
                intake_session=session.session, shipment_line=line1, deleted_at__isnull=True
            )
        )
        line2_total = sum(
            a.quantity for a in ItemAllocation.objects.filter(
                intake_session=session.session, shipment_line=line2, deleted_at__isnull=True
            )
        )
        self.assertEqual(line1_total, Decimal("5"))
        self.assertEqual(line2_total, Decimal("5"))
        self.assertEqual(
            ItemAllocation.objects.filter(
                intake_session=session.session, shipment_line__isnull=True,
                deleted_at__isnull=True,
            ).count(),
            0,
        )

    def test_cascade_leaves_unfillable_remainder_staged(self):
        """Staged total enough for line1 (5) but not enough more to also
        satisfy line2 (5) — line2 stays open, remainder stays staged."""
        shipment = ShipmentFactory.create(
            domain=self.domain,
            lines=[
                {"part_id": self.part.pk, "quantity": Decimal("5")},
                {"part_id": self.part.pk, "quantity": Decimal("5")},
            ],
            actor=None,
        )
        line1, line2 = shipment.lines.filter(deleted_at__isnull=True).order_by("id")
        session = self._session()
        session.associate_shipment(shipment_id=shipment.pk, actor=None)

        for _ in range(7):
            session.create_manual_allocation(
                shipment_line_id=None, part_id=self.part.pk,
                quantity=Decimal("1"), condition=AllocationCondition.GOOD,
                actor=None,
            )
        IntakeMatchingManager.execute_fifo_cascade(session=session.session, part=self.part)

        line1_total = sum(
            a.quantity for a in ItemAllocation.objects.filter(
                intake_session=session.session, shipment_line=line1, deleted_at__isnull=True
            )
        )
        staged_total = sum(
            a.quantity for a in ItemAllocation.objects.filter(
                intake_session=session.session, shipment_line__isnull=True,
                deleted_at__isnull=True,
            )
        )
        self.assertEqual(line1_total, Decimal("5"))
        self.assertEqual(staged_total, Decimal("2"))
        self.assertFalse(
            ItemAllocation.objects.filter(
                intake_session=session.session, shipment_line=line2, deleted_at__isnull=True
            ).exists()
        )


# ---------------------------------------------------------------------- #
# Split allocation conservation
# ---------------------------------------------------------------------- #

class SplitAllocationTests(IntakeMatchingTestCase):
    def test_split_conserves_total_quantity(self):
        shipment = ShipmentFactory.create(
            domain=self.domain,
            lines=[{"part_id": self.part.pk, "quantity": Decimal("10")}],
            actor=None,
        )
        line = shipment.lines.get(deleted_at__isnull=True)
        session = self._session()
        session.associate_shipment(shipment_id=shipment.pk, actor=None)

        allocation = session.create_manual_allocation(
            shipment_line_id=line.pk, part_id=self.part.pk,
            quantity=Decimal("10"), condition=AllocationCondition.GOOD,
            actor=None,
        )
        new_rows = session.split_allocation(
            allocation_id=allocation.pk, good_qty=Decimal("8"),
            rejected_qty=Decimal("2"), actor=None,
        )
        total = sum(row.quantity for row in new_rows)
        self.assertEqual(total, Decimal("10"))

        allocation.refresh_from_db()
        self.assertIsNotNone(allocation.deleted_at)


# ---------------------------------------------------------------------- #
# Reassignment + no cross-line netting regression
# ---------------------------------------------------------------------- #

class ReassignmentAndNettingTests(IntakeMatchingTestCase):
    def test_reassign_allocation_moves_it_to_another_session_line(self):
        shipment = ShipmentFactory.create(
            domain=self.domain,
            lines=[
                {"part_id": self.part.pk, "quantity": Decimal("5")},
                {"part_id": self.part.pk, "quantity": Decimal("5")},
            ],
            actor=None,
        )
        line1, line2 = shipment.lines.filter(deleted_at__isnull=True).order_by("id")
        session = self._session()
        session.associate_shipment(shipment_id=shipment.pk, actor=None)

        allocation = session.create_manual_allocation(
            shipment_line_id=line1.pk, part_id=self.part.pk,
            quantity=Decimal("3"), condition=AllocationCondition.GOOD,
            actor=None,
        )
        moved = session.reassign_allocation(
            allocation_id=allocation.pk, target_shipment_line_id=line2.pk,
            actor=None,
        )
        self.assertEqual(moved.shipment_line_id, line2.pk)

    def test_reassign_to_quarantine_sets_null_and_flags_session(self):
        shipment = ShipmentFactory.create(
            domain=self.domain,
            lines=[{"part_id": self.part.pk, "quantity": Decimal("5")}],
            actor=None,
        )
        line = shipment.lines.get(deleted_at__isnull=True)
        session = self._session()
        session.associate_shipment(shipment_id=shipment.pk, actor=None)

        allocation = session.create_manual_allocation(
            shipment_line_id=line.pk, part_id=self.part.pk,
            quantity=Decimal("3"), condition=AllocationCondition.GOOD,
            actor=None,
        )
        moved = session.reassign_allocation(
            allocation_id=allocation.pk, target_shipment_line_id=None, actor=None,
        )
        self.assertIsNone(moved.shipment_line_id)
        self.assertTrue(session.session.has_unlinked_allocations)

    def test_reassign_rejects_line_not_associated_with_session(self):
        shipment_a = ShipmentFactory.create(
            domain=self.domain,
            lines=[{"part_id": self.part.pk, "quantity": Decimal("5")}],
            actor=None,
        )
        shipment_b = ShipmentFactory.create(
            domain=self.domain,
            lines=[{"part_id": self.part.pk, "quantity": Decimal("5")}],
            actor=None,
        )
        line_a = shipment_a.lines.get(deleted_at__isnull=True)
        line_b = shipment_b.lines.get(deleted_at__isnull=True)

        session = self._session()
        session.associate_shipment(shipment_id=shipment_a.pk, actor=None)

        allocation = session.create_manual_allocation(
            shipment_line_id=line_a.pk, part_id=self.part.pk,
            quantity=Decimal("3"), condition=AllocationCondition.GOOD,
            actor=None,
        )
        with self.assertRaises(InventoryValidationError):
            session.reassign_allocation(
                allocation_id=allocation.pk, target_shipment_line_id=line_b.pk,
                actor=None,
            )

    def test_resolution_on_one_line_does_not_net_against_sibling_line(self):
        """FD-9 / overages_and_shortages_guide.md §2.1: a shortage on one
        vendor shipment's line must never be netted against an overage on
        another vendor shipment's line for the same part, even though both
        roll up under the same PartReconciliationSession parent."""
        shipment_short = ShipmentFactory.create(
            domain=self.domain,
            lines=[{"part_id": self.part.pk, "quantity": Decimal("10")}],
            actor=None, shipment_id="SHP-NET-SHORT",
        )
        shipment_over = ShipmentFactory.create(
            domain=self.domain,
            lines=[{"part_id": self.part.pk, "quantity": Decimal("5")}],
            actor=None, shipment_id="SHP-NET-OVER",
        )
        line_short = shipment_short.lines.get(deleted_at__isnull=True)
        line_over = shipment_over.lines.get(deleted_at__isnull=True)

        session = self._session()
        session.associate_shipment(shipment_id=shipment_short.pk, actor=None)
        session.associate_shipment(shipment_id=shipment_over.pk, actor=None)

        # Short line: only 6 of 10 received.
        session.create_manual_allocation(
            shipment_line_id=line_short.pk, part_id=self.part.pk,
            quantity=Decimal("6"), condition=AllocationCondition.GOOD, actor=None,
        )
        # Over line: 8 received against an expected 5.
        session.create_manual_allocation(
            shipment_line_id=line_over.pk, part_id=self.part.pk,
            quantity=Decimal("8"), condition=AllocationCondition.GOOD, actor=None,
        )

        session.transition_to_reconciliation(actor=None)
        reconciliation = session.session.reconciliations.get(part=self.part)
        short_child = reconciliation.lines.get(shipment_line=line_short)
        over_child = reconciliation.lines.get(shipment_line=line_over)

        # Independently visible discrepancies — no netting to zero.
        self.assertEqual(short_child.expected_quantity, Decimal("10"))
        self.assertEqual(short_child.allocated_quantity, Decimal("6"))
        self.assertEqual(over_child.expected_quantity, Decimal("5"))
        self.assertEqual(over_child.allocated_quantity, Decimal("8"))

        session.resolve_line(
            reconciliation_line_id=short_child.pk,
            resolution_type=ReconciliationResolutionType.ACCEPTED_SHORTAGE,
            actor=None,
        )
        over_child.refresh_from_db()
        # The overage line must still be unresolved — resolving the shortage
        # line must not have silently resolved (or netted against) it.
        self.assertEqual(over_child.resolution_type, ReconciliationResolutionType.NONE)

        session.resolve_line(
            reconciliation_line_id=over_child.pk,
            resolution_type=ReconciliationResolutionType.QUARANTINED_OVERAGE,
            actor=None,
        )
        reconciliation.refresh_from_db()
        self.assertEqual(reconciliation.status, "resolved")


# ---------------------------------------------------------------------- #
# Cross-session excess pull (FD-26)
# ---------------------------------------------------------------------- #

class PullExternalAllocationTests(IntakeMatchingTestCase):
    def test_pull_moves_allocation_and_writes_audit_comment(self):
        shipment_short = ShipmentFactory.create(
            domain=self.domain,
            lines=[{"part_id": self.part.pk, "quantity": Decimal("10")}],
            actor=None, shipment_id="SHP-PULL-SHORT",
        )
        line_short = shipment_short.lines.get(deleted_at__isnull=True)

        session_a = self._session()
        session_a.associate_shipment(shipment_id=shipment_short.pk, actor=None)

        # Session B has excess stock for the same part, unlinked.
        session_b = self._session()
        excess = session_b.create_manual_allocation(
            shipment_line_id=None, part_id=self.part.pk,
            quantity=Decimal("4"), condition=AllocationCondition.GOOD, actor=None,
        )

        moved = session_a.pull_external_allocation(
            allocation_id=excess.pk, target_line_id=line_short.pk, actor=None,
        )
        self.assertEqual(moved.intake_session_id, session_a.session.pk)
        self.assertEqual(moved.shipment_line_id, line_short.pk)

        line_short.refresh_from_db()
        notes = line_short.comments.get("intake_notes", [])
        self.assertEqual(len(notes), 1)
        self.assertIn(str(excess.pk), notes[0]["note"])
        self.assertIn(str(session_b.session.pk), notes[0]["note"])

        session_b.session.refresh_from_db()
        self.assertFalse(session_b.session.has_unlinked_allocations)

    def test_pull_rejects_already_linked_allocation(self):
        shipment = ShipmentFactory.create(
            domain=self.domain,
            lines=[{"part_id": self.part.pk, "quantity": Decimal("5")}],
            actor=None,
        )
        line = shipment.lines.get(deleted_at__isnull=True)
        session_a = self._session()
        session_a.associate_shipment(shipment_id=shipment.pk, actor=None)

        session_b = self._session()
        session_b.associate_shipment(shipment_id=shipment.pk, actor=None)
        linked_allocation = session_b.create_manual_allocation(
            shipment_line_id=line.pk, part_id=self.part.pk,
            quantity=Decimal("2"), condition=AllocationCondition.GOOD, actor=None,
        )
        with self.assertRaises(InventoryValidationError):
            session_a.pull_external_allocation(
                allocation_id=linked_allocation.pk, target_line_id=line.pk, actor=None,
            )

    def test_pull_rejects_target_line_not_associated_with_this_session(self):
        shipment_a = ShipmentFactory.create(
            domain=self.domain,
            lines=[{"part_id": self.part.pk, "quantity": Decimal("5")}],
            actor=None,
        )
        line_a = shipment_a.lines.get(deleted_at__isnull=True)

        session_a = self._session()  # deliberately NOT associated with shipment_a

        session_b = self._session()
        excess = session_b.create_manual_allocation(
            shipment_line_id=None, part_id=self.part.pk,
            quantity=Decimal("2"), condition=AllocationCondition.GOOD, actor=None,
        )
        with self.assertRaises(InventoryValidationError):
            session_a.pull_external_allocation(
                allocation_id=excess.pk, target_line_id=line_a.pk, actor=None,
            )


# ---------------------------------------------------------------------- #
# Rejected-quantity propagation on resolve
# ---------------------------------------------------------------------- #

class RejectionNotePropagationTests(IntakeMatchingTestCase):
    def test_resolving_a_line_with_rejected_quantity_writes_shipment_line_comment(self):
        shipment = ShipmentFactory.create(
            domain=self.domain,
            lines=[{"part_id": self.part.pk, "quantity": Decimal("10")}],
            actor=None, shipment_id="SHP-REJNOTE",
        )
        line = shipment.lines.get(deleted_at__isnull=True)
        session = self._session()
        session.associate_shipment(shipment_id=shipment.pk, actor=None)

        # 6 good + 3 rejected = 9 of 10 expected — a real discrepancy (short
        # by 1), and distinct from the exactly-satisfied case so
        # `generate_tasks` actually spawns a reconciliation task.
        session.create_manual_allocation(
            shipment_line_id=line.pk, part_id=self.part.pk,
            quantity=Decimal("6"), condition=AllocationCondition.GOOD, actor=None,
        )
        session.create_manual_allocation(
            shipment_line_id=line.pk, part_id=self.part.pk,
            quantity=Decimal("3"), condition=AllocationCondition.REJECTED, actor=None,
        )
        session.transition_to_reconciliation(actor=None)
        reconciliation = session.session.reconciliations.get(part=self.part)
        child = reconciliation.lines.get(shipment_line=line)
        self.assertEqual(child.rejected_quantity, Decimal("3"))

        session.resolve_line(
            reconciliation_line_id=child.pk,
            resolution_type=ReconciliationResolutionType.RMA_DISPOSITION,
            notes="3 damaged in transit, RMA filed.",
            actor=None,
        )

        line.refresh_from_db()
        entries = line.comments.get("reconciliation_notes", [])
        self.assertEqual(len(entries), 1)
        self.assertIn("rma_disposition", entries[0]["note"])
        self.assertIn("3", entries[0]["note"])

    def test_resolving_a_line_with_no_rejected_quantity_writes_no_comment(self):
        shipment = ShipmentFactory.create(
            domain=self.domain,
            lines=[{"part_id": self.part.pk, "quantity": Decimal("10")}],
            actor=None, shipment_id="SHP-NOREJNOTE",
        )
        line = shipment.lines.get(deleted_at__isnull=True)
        session = self._session()
        session.associate_shipment(shipment_id=shipment.pk, actor=None)

        session.create_manual_allocation(
            shipment_line_id=line.pk, part_id=self.part.pk,
            quantity=Decimal("6"), condition=AllocationCondition.GOOD, actor=None,
        )
        session.transition_to_reconciliation(actor=None)
        reconciliation = session.session.reconciliations.get(part=self.part)
        child = reconciliation.lines.get(shipment_line=line)
        self.assertEqual(child.rejected_quantity, Decimal("0"))

        session.resolve_line(
            reconciliation_line_id=child.pk,
            resolution_type=ReconciliationResolutionType.ACCEPTED_SHORTAGE,
            actor=None,
        )
        line.refresh_from_db()
        self.assertEqual(line.comments.get("reconciliation_notes", []), [])
