"""PartDemandManager.record_technician_issue — the work portal's "Issue" verb.

The legacy work portal's Issue button opened a "Record Qty Issued" modal and
posted a NUMBER. The first EBAMS-2 pass called set_issuance_state(), which
deliberately does not touch issued_qty, so the quantity the technician typed
was thrown away and every issued demand read `issued_qty = 0`. These tests pin
the number down, because it is the whole point of the verb.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from app.administration.models import Domain
from app.events.models.details.maintenance import MaintenanceDetail
from app.events.models.event import EventType
from app.maintenance.control_layer.part_demand_manager import PartDemandManager
from app.maintenance.models.action import Action
from app.parts.control_layer.factories.part_factory import PartFactory
from app.procurement.models import IssuanceState

User = get_user_model()


class RecordTechnicianIssueTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="issue_tech", email="issue_tech@test.local",
            password="TestPass123!@",
        )
        cls.domain = Domain.objects.create(
            name="Issue Domain", slug="issue-domain",
            created_by=cls.user, updated_by=cls.user,
        )
        cls.part = PartFactory.create(
            data={
                "part_number": "PN-ISS-01", "name": "Air Filter",
                "part_type": "component", "category": "test",
            },
            actor=cls.user,
        )
        cls.event = MaintenanceDetail.objects.create(
            domain=cls.domain,
            title="Issue event",
            event_type=EventType.MAINTENANCE,
            event_start=timezone.now(),
            maintenance_type="scheduled",
            created_by=cls.user, updated_by=cls.user,
        )
        cls.action = Action.objects.create(
            event_detail=cls.event,
            action_name="Replace air filter",
            sequence_order=1,
            created_by=cls.user, updated_by=cls.user,
        )

    def _demand(self, quantity="2"):
        return PartDemandManager.create_for_action(
            action_id=self.action.pk,
            part_id=self.part.pk,
            quantity_requested=Decimal(quantity),
            actor=self.user,
        ).part_demand

    def test_issuing_moves_the_demand_to_issued_without_stock_adjustment(self):
        demand = self._demand()
        PartDemandManager.record_technician_issue(
            demand_id=demand.pk, qty_issued=Decimal("2"), actor=self.user
        )
        demand.refresh_from_db()
        self.assertEqual(
            demand.issuance_state, IssuanceState.ISSUED_WITHOUT_STOCK_ADJUSTMENT
        )

    def test_issuing_records_the_quantity_the_technician_typed(self):
        demand = self._demand()
        PartDemandManager.record_technician_issue(
            demand_id=demand.pk, qty_issued=Decimal("2"), actor=self.user
        )
        demand.refresh_from_db()
        self.assertEqual(demand.issued_qty, Decimal("2.000"))

    def test_issuing_less_than_demanded_records_the_smaller_number(self):
        # A technician who only needed one of the two asked for says so; the
        # state still closes out, because issuance never auto-derives from a
        # quantity comparison (D30/D36).
        demand = self._demand(quantity="2")
        PartDemandManager.record_technician_issue(
            demand_id=demand.pk, qty_issued=Decimal("1"), actor=self.user
        )
        demand.refresh_from_db()
        self.assertEqual(demand.issued_qty, Decimal("1.000"))
        self.assertEqual(
            demand.issuance_state, IssuanceState.ISSUED_WITHOUT_STOCK_ADJUSTMENT
        )

    def test_a_zero_quantity_is_refused(self):
        demand = self._demand()
        with self.assertRaises(ValueError):
            PartDemandManager.record_technician_issue(
                demand_id=demand.pk, qty_issued=Decimal("0"), actor=self.user
            )
        demand.refresh_from_db()
        self.assertEqual(demand.issuance_state, IssuanceState.NOT_ISSUED)

    def test_a_missing_quantity_is_refused(self):
        demand = self._demand()
        with self.assertRaises(ValueError):
            PartDemandManager.record_technician_issue(
                demand_id=demand.pk, qty_issued=None, actor=self.user
            )
        demand.refresh_from_db()
        self.assertEqual(demand.issued_qty, Decimal("0.000"))
