"""Control-layer tests for PartPriceObservation (D79-D92): the guard's hard
rules, the duplicate-warning path, and bulk-factory atomicity.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from app.administration.models import Domain
from app.parts.control_layer.factories.part_factory import PartFactory
from app.procurement.control_layer.adapters.part_price_grid_adaptor import (
    PartPriceGridAdaptor,
)
from app.procurement.control_layer.adapters.purchase_order_draft_adaptor import (
    DraftAllocation,
    DraftLine,
    PurchaseOrderDraft,
)
from app.procurement.control_layer.errors import ProcurementValidationError
from app.procurement.control_layer.factories.part_demand_factory import (
    PartDemandFactory,
)
from app.procurement.control_layer.factories.part_price_observation_bulk_factory import (
    PartPriceObservationBulkFactory,
    PriceObservationInput,
)
from app.procurement.control_layer.factories.purchase_order_factory import (
    PurchaseOrderFactory,
)
from app.procurement.control_layer.guards.part_price_observation_guard import (
    PartPriceObservationValidator,
)
from app.procurement.control_layer.purchase_order_context import PurchaseOrderContext
from app.procurement.models import (
    PartPriceObservation,
    PriceConfidence,
    PriceSourceType,
    Vendor,
)

User = get_user_model()


class PartPriceObservationGuardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="price_guard_smoke",
            email="price_guard@test.local",
            password="TestPass123!@",
        )
        cls.domain = Domain.objects.create(
            name="Guard Domain",
            slug="guard-domain",
            created_by=cls.user,
            updated_by=cls.user,
        )
        cls.other_domain = Domain.objects.create(
            name="Other Domain",
            slug="other-domain",
            created_by=cls.user,
            updated_by=cls.user,
        )
        cls.part = PartFactory.create(
            data={
                "part_number": "PN-PRICE-01",
                "name": "Priced Widget",
                "part_type": "component",
                "category": "test",
            },
            actor=cls.user,
        )
        cls.vendor = Vendor.objects.create(
            name="Price Vendor Co",
            code="PVCO",
            created_by=cls.user,
            updated_by=cls.user,
        )

    def _valid_kwargs(self, **overrides):
        kwargs = dict(
            part_id=self.part.pk,
            vendor_id=self.vendor.pk,
            domain_id=self.domain.pk,
            unit_cost=Decimal("10.00"),
            quantity=None,
            observed_at=date.today(),
            confidence=PriceConfidence.QUOTED,
            is_verified=False,
            visible_part_ids={self.part.pk},
            visible_domain_ids=[self.domain.pk],
            actor_can_establish=False,
        )
        kwargs.update(overrides)
        return kwargs

    def test_recording_is_verified_true_without_establish_authority_raises(self):
        """The one hard rule everything else depends on — write it first."""
        with self.assertRaises(ProcurementValidationError):
            PartPriceObservationValidator.validate(
                **self._valid_kwargs(is_verified=True, actor_can_establish=False)
            )

    def test_is_verified_true_with_establish_authority_is_allowed(self):
        PartPriceObservationValidator.validate(
            **self._valid_kwargs(is_verified=True, actor_can_establish=True)
        )

    def test_negative_unit_cost_raises(self):
        with self.assertRaises(ProcurementValidationError):
            PartPriceObservationValidator.validate(
                **self._valid_kwargs(unit_cost=Decimal("-1.00"))
            )

    def test_zero_quantity_raises(self):
        with self.assertRaises(ProcurementValidationError):
            PartPriceObservationValidator.validate(
                **self._valid_kwargs(quantity=Decimal("0"))
            )

    def test_future_observed_at_raises(self):
        with self.assertRaises(ProcurementValidationError):
            PartPriceObservationValidator.validate(
                **self._valid_kwargs(observed_at=date.today() + timedelta(days=1))
            )

    def test_domain_outside_visible_set_raises(self):
        with self.assertRaises(ProcurementValidationError):
            PartPriceObservationValidator.validate(
                **self._valid_kwargs(domain_id=self.other_domain.pk)
            )

    def test_part_outside_visible_set_raises(self):
        with self.assertRaises(ProcurementValidationError):
            PartPriceObservationValidator.validate(
                **self._valid_kwargs(visible_part_ids=set())
            )

    def test_inactive_vendor_raises(self):
        inactive_vendor = Vendor.objects.create(
            name="Retired Vendor",
            code="RETIRED",
            is_active=False,
            created_by=self.user,
            updated_by=self.user,
        )
        with self.assertRaises(ProcurementValidationError):
            PartPriceObservationValidator.validate(
                **self._valid_kwargs(vendor_id=inactive_vendor.pk)
            )

    def test_exact_duplicate_warns_but_does_not_raise(self):
        PartPriceObservation.objects.create(
            part_id=self.part.pk,
            vendor_id=self.vendor.pk,
            domain_id=self.domain.pk,
            unit_cost=Decimal("10.00"),
            observed_at=date.today(),
            source_type="manual",
            confidence=PriceConfidence.QUOTED,
            created_by=self.user,
            updated_by=self.user,
        )

        warnings = PartPriceObservationValidator.validate(**self._valid_kwargs())

        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0].part_id, self.part.pk)


class PartPriceObservationBulkFactoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="price_bulk_smoke",
            email="price_bulk@test.local",
            password="TestPass123!@",
        )
        cls.domain = Domain.objects.create(
            name="Bulk Domain",
            slug="bulk-domain",
            created_by=cls.user,
            updated_by=cls.user,
        )
        cls.part = PartFactory.create(
            data={
                "part_number": "PN-PRICE-02",
                "name": "Bulk Widget",
                "part_type": "component",
                "category": "test",
            },
            actor=cls.user,
        )
        cls.vendor = Vendor.objects.create(
            name="Bulk Vendor Co",
            code="BVCO",
            created_by=cls.user,
            updated_by=cls.user,
        )

    def _row(self, **overrides) -> PriceObservationInput:
        kwargs = dict(
            part_id=self.part.pk,
            vendor_id=self.vendor.pk,
            domain_id=self.domain.pk,
            unit_cost=Decimal("5.00"),
            observed_at=date.today(),
            source_type="manual",
            confidence=PriceConfidence.QUOTED,
        )
        kwargs.update(overrides)
        return PriceObservationInput(**kwargs)

    def test_one_bad_row_among_ten_writes_zero_rows(self):
        rows = [self._row() for _ in range(9)]
        rows.append(self._row(unit_cost=Decimal("-1.00")))

        with self.assertRaises(ProcurementValidationError):
            PartPriceObservationBulkFactory.create_many(
                rows=rows,
                actor=self.user,
                visible_part_ids={self.part.pk},
                visible_domain_ids=[self.domain.pk],
                actor_can_establish=False,
            )

        self.assertEqual(PartPriceObservation.objects.count(), 0)

    def test_all_valid_rows_commit_together(self):
        rows = [self._row(unit_cost=Decimal(str(n))) for n in range(1, 4)]

        result = PartPriceObservationBulkFactory.create_many(
            rows=rows,
            actor=self.user,
            visible_part_ids={self.part.pk},
            visible_domain_ids=[self.domain.pk],
            actor_can_establish=False,
        )

        self.assertEqual(len(result.created_ids), 3)
        self.assertEqual(PartPriceObservation.objects.count(), 3)
        stored = PartPriceObservation.objects.get(pk=result.created_ids[0])
        self.assertEqual(stored.created_by_id, self.user.pk)


class PartPriceGridAdaptorTests(TestCase):
    def test_costless_row_is_dropped_and_reported(self):
        post = _FakePost(
            {
                "vendor_id": "1",
                "domain_id": "1",
                "observed_at": str(date.today()),
                "source_type": "manual",
                "confidence": PriceConfidence.QUOTED,
                "row_count": "2",
                "rows-0-part_id": "10",
                "rows-0-unit_cost": "",
                "rows-1-part_id": "11",
                "rows-1-unit_cost": "1,234.56",
            }
        )

        parsed = PartPriceGridAdaptor.from_post(post)

        self.assertEqual(parsed.dropped_part_ids, [10])
        self.assertEqual(len(parsed.rows), 1)
        self.assertEqual(parsed.rows[0].part_id, 11)

    def test_dollar_and_thousands_separator_parse_to_decimal(self):
        post = _FakePost(
            {
                "vendor_id": "1",
                "domain_id": "1",
                "observed_at": str(date.today()),
                "source_type": "manual",
                "confidence": PriceConfidence.QUOTED,
                "row_count": "1",
                "rows-0-part_id": "20",
                "rows-0-unit_cost": "$1,234.56",
            }
        )

        parsed = PartPriceGridAdaptor.from_post(post)

        self.assertEqual(parsed.rows[0].unit_cost, Decimal("1234.56"))

    def test_unparseable_cost_is_an_error_not_a_silent_zero(self):
        post = _FakePost(
            {
                "vendor_id": "1",
                "domain_id": "1",
                "observed_at": str(date.today()),
                "source_type": "manual",
                "confidence": PriceConfidence.QUOTED,
                "row_count": "1",
                "rows-0-part_id": "30",
                "rows-0-unit_cost": "not-a-number",
            }
        )

        parsed = PartPriceGridAdaptor.from_post(post)

        self.assertEqual(parsed.rows, [])
        self.assertEqual(len(parsed.errors), 1)


class PlacingAPurchaseOrderWritesOrderedObservationsTests(TestCase):
    """Phase 7 (build_plan.md §8): placing a PO is itself a price fact — one
    `ordered` observation per line, self-maintaining because it costs nothing
    beyond work the Buyer already does."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="price_ordered_smoke",
            email="price_ordered@test.local",
            password="TestPass123!@",
        )
        cls.domain = Domain.objects.create(
            name="Ordered Domain",
            slug="ordered-domain",
            created_by=cls.user,
            updated_by=cls.user,
        )
        cls.part = PartFactory.create(
            data={
                "part_number": "PN-ORDERED-01",
                "name": "Ordered Widget",
                "part_type": "component",
                "category": "test",
            },
            actor=cls.user,
        )
        cls.other_part = PartFactory.create(
            data={
                "part_number": "PN-ORDERED-02",
                "name": "Second Ordered Widget",
                "part_type": "component",
                "category": "test",
            },
            actor=cls.user,
        )
        cls.vendor = Vendor.objects.create(
            name="Ordered Vendor Co",
            code="ORDCO",
            created_by=cls.user,
            updated_by=cls.user,
        )

    def _place(self, *, unit_cost_confidence: str = "") -> "PurchaseOrder":  # noqa: F821
        demand = PartDemandFactory.create(
            part_id=self.part.pk,
            domain_id=self.domain.pk,
            quantity_requested=Decimal("10"),
            actor=self.user,
        )
        draft = PurchaseOrderDraft(
            vendor_id=self.vendor.pk,
            domain_id=self.domain.pk,
            shipping_cost=Decimal("5.00"),
            lines=[
                DraftLine(
                    part_id=self.part.pk,
                    quantity_ordered=Decimal("10"),
                    unit_cost=Decimal("12.50"),
                    unit_cost_confidence=unit_cost_confidence,
                    allocations=[
                        DraftAllocation(demand_id=demand.pk, quantity_allocated=Decimal("10"))
                    ],
                ),
                DraftLine(
                    part_id=self.other_part.pk,
                    quantity_ordered=Decimal("4"),
                    unit_cost=Decimal("3.00"),
                    unit_cost_confidence=unit_cost_confidence,
                    allocations=[],
                ),
            ],
        )
        po = PurchaseOrderFactory.create_from_draft(draft=draft, actor=self.user)
        context = PurchaseOrderContext(po.pk)
        context.submit_for_approval(actor=self.user)
        context.approve_order(actor=self.user)
        context.place(actor=self.user)
        return po

    def test_placing_writes_one_ordered_observation_per_line(self):
        po = self._place(unit_cost_confidence=PriceConfidence.P10)

        observations = PartPriceObservation.objects.filter(source_po_line__purchase_order=po)
        self.assertEqual(observations.count(), 2)
        for observation in observations:
            self.assertEqual(observation.source_type, PriceSourceType.ORDERED)
            self.assertEqual(observation.observed_at, po.order_date)
            self.assertFalse(observation.is_verified)
            self.assertEqual(observation.vendor_id, self.vendor.pk)
            self.assertEqual(observation.domain_id, self.domain.pk)

        by_part = {obs.part_id: obs for obs in observations}
        self.assertEqual(by_part[self.part.pk].unit_cost, Decimal("12.50"))
        self.assertEqual(by_part[self.part.pk].confidence, PriceConfidence.P10)
        self.assertEqual(by_part[self.part.pk].source_po_line.purchase_order_id, po.pk)

    def test_blank_line_confidence_becomes_unknown_rather_than_failing_the_guard(self):
        """PurchaseOrderLine.unit_cost_confidence is blank-by-default (D88);
        the observation's own confidence column has no default and must be a
        real PriceConfidence value."""
        self._place(unit_cost_confidence="")

        observations = PartPriceObservation.objects.filter(
            source_type=PriceSourceType.ORDERED
        )
        self.assertTrue(observations.exists())
        for observation in observations:
            self.assertEqual(observation.confidence, PriceConfidence.UNKNOWN)


class _FakePost(dict):
    """Minimal QueryDict stand-in — .get(key) is all the adaptor needs."""
