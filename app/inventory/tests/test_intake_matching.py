"""Phase 5 tests: barcode parsing, the scan-matching engine (1-to-1 / N-to-M
staging / FIFO cascade), and split-allocation conservation.

The reassignment, cross-session pull, and reconciliation-resolution suites
were deleted with the reconciliation tables (intake_portal_workflow.md §12.5).
Their replacements belong to Phase 2's allocation portal (§7.3) and the
over-allocation ban (§7.2), neither of which exists yet.
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
    AllocationLinkSource,
    IntakeSessionMethod,
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

        allocation, _ = session.process_scan(
            raw_payload=self.part.part_number, actor=None
        )
        self.assertEqual(allocation.shipment_line_id, line.pk)
        self.assertEqual(allocation.link_source, AllocationLinkSource.AUTO_SINGLE_MATCH)

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

        allocation, _ = session.process_scan(
            raw_payload=self.part.part_number, actor=None
        )
        self.assertIsNone(allocation.shipment_line_id)
        self.assertEqual(allocation.link_source, AllocationLinkSource.UNLINKED)

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

        allocation, _ = session.process_scan(
            raw_payload=other_part.part_number, actor=None
        )
        self.assertIsNone(allocation.shipment_line_id)
        self.assertEqual(allocation.link_source, AllocationLinkSource.UNLINKED)

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
