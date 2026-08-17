"""Phase 4 acceptance tests: the Auto Intake floor/cap/delta math
(`auto_intake_workflow_guide.md` §3-4, worked examples A-C verbatim).
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from app.administration.models import Division, Domain
from app.inventory.control_layer.errors import InventoryValidationError
from app.inventory.control_layer.managers.auto_intake_manager import AutoIntakeManager
from app.inventory.models.intake.enums import AllocationCondition
from app.inventory.models.intake.intake_session import IntakeSession
from app.inventory.models.intake.item_allocation import ItemAllocation
from app.parts.control_layer.factories.part_factory import PartFactory
from app.procurement.control_layer.factories.shipment_factory import ShipmentFactory

User = get_user_model()


class AutoIntakeMathTestCase(TestCase):
    """Scenario Setup from the guide: Q_line = 5.000, existing = 1.000
    accepted / 1.000 rejected (total existing 2.000)."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="auto_intake_math", email="aim@test.local", password="TestPass123!@"
        )
        cls.division = Division.objects.create(
            name="Math Division", slug="math-division",
            created_by=cls.user, updated_by=cls.user,
        )
        cls.domain = Domain.objects.create(
            name="Math Domain", slug="math-domain",
            created_by=cls.user, updated_by=cls.user,
        )
        cls.part = PartFactory.create(
            data={"part_number": "PN-MATH-01", "name": "Math Widget"}, actor=cls.user,
        )
        cls.shipment = ShipmentFactory.create(
            domain=cls.domain,
            lines=[{"part_id": cls.part.pk, "quantity": Decimal("5")}],
            actor=cls.user,
        )
        cls.line = cls.shipment.lines.get(deleted_at__isnull=True)

        # A pre-existing session that already logged 1.000 good / 1.000 rejected.
        from app.inventory.control_layer.factories.warehouse_factory import WarehouseFactory
        cls.warehouse = WarehouseFactory.create(
            name="Math Warehouse", code="WH-MATH-01",
            division_id=cls.division.pk, actor=cls.user,
        )
        cls.prior_session = IntakeSession.objects.create(
            operator=cls.user, warehouse=cls.warehouse, status="closed",
            created_by=cls.user, updated_by=cls.user,
        )
        ItemAllocation.objects.create(
            intake_session=cls.prior_session, shipment_line=cls.line, part=cls.part,
            quantity=Decimal("1"), condition=AllocationCondition.GOOD,
            created_by=cls.user, updated_by=cls.user,
        )
        ItemAllocation.objects.create(
            intake_session=cls.prior_session, shipment_line=cls.line, part=cls.part,
            quantity=Decimal("1"), condition=AllocationCondition.REJECTED,
            created_by=cls.user, updated_by=cls.user,
        )

    def test_existing_balances_match_scenario_setup(self):
        good, rejected = AutoIntakeManager.existing_balances(shipment_line_id=self.line.pk)
        self.assertEqual(good, Decimal("1"))
        self.assertEqual(rejected, Decimal("1"))

    def test_example_a_full_line_completion(self):
        result = AutoIntakeManager.compute_delta(
            shipment_line=self.line,
            accepted_target=Decimal("3"),
            rejected_target=Decimal("2"),
        )
        self.assertEqual(result["delta_good"], Decimal("2"))
        self.assertEqual(result["delta_rejected"], Decimal("1"))

    def test_example_b_partial_addition_accepted_only(self):
        result = AutoIntakeManager.compute_delta(
            shipment_line=self.line,
            accepted_target=Decimal("3"),
            rejected_target=Decimal("1"),
        )
        self.assertEqual(result["delta_good"], Decimal("2"))
        self.assertEqual(result["delta_rejected"], Decimal("0"))

    def test_example_c_invalid_decrease_is_rejected(self):
        with self.assertRaises(InventoryValidationError):
            AutoIntakeManager.compute_delta(
                shipment_line=self.line,
                accepted_target=Decimal("0"),
                rejected_target=Decimal("1"),
            )

    def test_cap_violation_is_rejected(self):
        with self.assertRaises(InventoryValidationError):
            AutoIntakeManager.compute_delta(
                shipment_line=self.line,
                accepted_target=Decimal("4"),
                rejected_target=Decimal("4"),
            )

    def test_zero_delta_when_targets_equal_existing(self):
        result = AutoIntakeManager.compute_delta(
            shipment_line=self.line,
            accepted_target=Decimal("1"),
            rejected_target=Decimal("1"),
        )
        self.assertEqual(result["delta_good"], Decimal("0"))
        self.assertEqual(result["delta_rejected"], Decimal("0"))
