"""Phase 2 acceptance tests: the dual grain (serialized/non-serialized),
withdraw guards, the NULL-location duplicate guard, and the domain gate.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from app.administration.models import Division, Domain
from app.inventory.control_layer.errors import (
    DomainAccessDenied,
    InsufficientStockError,
    InventoryValidationError,
    SerialInUseError,
)
from app.inventory.control_layer.factories.warehouse_factory import WarehouseFactory
from app.inventory.control_layer.managers.stock_ledger_manager import StockLedgerManager
from app.inventory.models.stock.active_inventory import ActiveInventory
from app.inventory.models.topography.room import Room
from app.inventory.presentation_layer.search.active_inventory_search import (
    domain_visible_room_ids,
)
from app.parts.control_layer.factories.part_factory import PartFactory

User = get_user_model()


class StockLedgerManagerTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="stock_smoke", email="stock@test.local", password="TestPass123!@"
        )
        cls.division = Division.objects.create(
            name="Stock Division", slug="stock-division",
            created_by=cls.user, updated_by=cls.user,
        )
        cls.warehouse = WarehouseFactory.create(
            name="Stock Warehouse", code="WH-STOCK-01",
            division_id=cls.division.pk, actor=cls.user,
        )
        cls.intake_room = cls.warehouse.rooms.get(is_intake_room=True)
        cls.racking = Room.objects.create(
            warehouse=cls.warehouse, room_name="Racking",
            created_by=cls.user, updated_by=cls.user,
        )
        cls.room_location = cls.racking.room_locations.create(
            major_coord="0010", minor_coord="0005",
            display_code="0010-0005",
            created_by=cls.user, updated_by=cls.user,
        )
        cls.location = cls.room_location.storage_locations.create(
            atomic_coord="0001",
            display_code="0010-0005-0001",
            created_by=cls.user, updated_by=cls.user,
        )
        cls.part = PartFactory.create(
            data={"part_number": "PN-STOCK-01", "name": "Stock Widget"},
            actor=cls.user,
        )
        cls.sn_part = PartFactory.create(
            data={"part_number": "PN-STOCK-02", "name": "Serialized Widget"},
            actor=cls.user,
        )


class DualGrainTests(StockLedgerManagerTestCase):
    def test_repeated_non_serialized_injects_aggregate_to_one_row(self):
        StockLedgerManager.inject(
            warehouse=self.warehouse, room=self.racking, storage_location=self.location,
            part=self.part, qty=Decimal("5"), actor=self.user,
        )
        StockLedgerManager.inject(
            warehouse=self.warehouse, room=self.racking, storage_location=self.location,
            part=self.part, qty=Decimal("3"), actor=self.user,
        )
        rows = ActiveInventory.objects.filter(
            room=self.racking, storage_location=self.location, part=self.part
        )
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.first().quantity_on_hand, Decimal("8"))

    def test_serialized_injects_create_separate_unit_rows(self):
        StockLedgerManager.inject(
            warehouse=self.warehouse, room=self.racking, storage_location=self.location,
            part=self.sn_part, qty=Decimal("1"), serial="SN-A", actor=self.user,
        )
        StockLedgerManager.inject(
            warehouse=self.warehouse, room=self.racking, storage_location=self.location,
            part=self.sn_part, qty=Decimal("1"), serial="SN-B", actor=self.user,
        )
        rows = ActiveInventory.objects.filter(room=self.racking, part=self.sn_part)
        self.assertEqual(rows.count(), 2)

    def test_duplicate_serial_is_rejected(self):
        StockLedgerManager.inject(
            warehouse=self.warehouse, room=self.racking, storage_location=self.location,
            part=self.sn_part, qty=Decimal("1"), serial="SN-DUP", actor=self.user,
        )
        with self.assertRaises(SerialInUseError):
            StockLedgerManager.inject(
                warehouse=self.warehouse, room=self.racking, storage_location=self.location,
                part=self.sn_part, qty=Decimal("1"), serial="SN-DUP", actor=self.user,
            )

    def test_serialized_quantity_other_than_one_is_rejected(self):
        with self.assertRaises(InventoryValidationError):
            StockLedgerManager.inject(
                warehouse=self.warehouse, room=self.racking, storage_location=self.location,
                part=self.sn_part, qty=Decimal("2"), serial="SN-BAD", actor=self.user,
            )


class WithdrawTests(StockLedgerManagerTestCase):
    def test_insufficient_stock_raises_before_any_write(self):
        StockLedgerManager.inject(
            warehouse=self.warehouse, room=self.racking, storage_location=self.location,
            part=self.part, qty=Decimal("2"), actor=self.user,
        )
        with self.assertRaises(InsufficientStockError):
            StockLedgerManager.withdraw(
                room=self.racking, storage_location=self.location,
                part=self.part, qty=Decimal("5"), actor=self.user,
            )
        row = ActiveInventory.objects.get(
            room=self.racking, storage_location=self.location, part=self.part
        )
        self.assertEqual(row.quantity_on_hand, Decimal("2"))

    def test_serialized_row_is_deleted_at_zero(self):
        StockLedgerManager.inject(
            warehouse=self.warehouse, room=self.racking, storage_location=self.location,
            part=self.sn_part, qty=Decimal("1"), serial="SN-GONE", actor=self.user,
        )
        StockLedgerManager.withdraw(
            room=self.racking, storage_location=self.location,
            part=self.sn_part, qty=Decimal("1"), serial="SN-GONE", actor=self.user,
        )
        self.assertFalse(
            ActiveInventory.objects.filter(
                room=self.racking, part=self.sn_part, serial_number="SN-GONE"
            ).exists()
        )


class NullLocationDuplicateGuardTests(StockLedgerManagerTestCase):
    def test_two_injects_into_intake_room_yield_one_row(self):
        StockLedgerManager.inject(
            warehouse=self.warehouse, room=self.intake_room, storage_location=None,
            part=self.part, qty=Decimal("10"), actor=self.user,
        )
        StockLedgerManager.inject(
            warehouse=self.warehouse, room=self.intake_room, storage_location=None,
            part=self.part, qty=Decimal("15"), actor=self.user,
        )
        rows = ActiveInventory.objects.filter(
            room=self.intake_room, storage_location__isnull=True, part=self.part
        )
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.first().quantity_on_hand, Decimal("25"))
        self.assertTrue(rows.first().is_unassigned)


class DomainGateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="domain_gate_smoke", email="domain_gate@test.local",
            password="TestPass123!@",
        )
        cls.division = Division.objects.create(
            name="Gate Division", slug="gate-division",
            created_by=cls.user, updated_by=cls.user,
        )
        cls.domain_a = Domain.objects.create(
            name="Gate Domain A", slug="gate-domain-a",
            created_by=cls.user, updated_by=cls.user,
        )
        cls.domain_b = Domain.objects.create(
            name="Gate Domain B", slug="gate-domain-b",
            created_by=cls.user, updated_by=cls.user,
        )
        cls.warehouse = WarehouseFactory.create(
            name="Gate Warehouse", code="WH-GATE-01", division_id=cls.division.pk,
            domain_ids=[cls.domain_a.pk], actor=cls.user,
        )
        cls.racking = Room.objects.create(
            warehouse=cls.warehouse, room_name="Racking",
            created_by=cls.user, updated_by=cls.user,
        )
        cls.part = PartFactory.create(
            data={"part_number": "PN-GATE-01", "name": "Gated Widget"},
            actor=cls.user,
        )

    def test_user_without_room_domain_coverage_is_denied(self):
        outsider = User.objects.create_user(
            username="gate_outsider", email="outsider@test.local",
            password="TestPass123!@",
        )
        with self.assertRaises(DomainAccessDenied):
            StockLedgerManager.inject(
                warehouse=self.warehouse, room=self.racking, storage_location=None,
                part=self.part, qty=Decimal("1"), actor=outsider,
            )

    def test_search_hides_rooms_outside_requesting_users_domains(self):
        visible = domain_visible_room_ids(domain_ids=[self.domain_b.pk])
        self.assertNotIn(self.racking.pk, visible)

        visible_covering = domain_visible_room_ids(domain_ids=[self.domain_a.pk])
        self.assertIn(self.racking.pk, visible_covering)
