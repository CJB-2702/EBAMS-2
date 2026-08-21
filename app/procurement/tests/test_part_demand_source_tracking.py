from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from app.administration.models import Domain
from app.assets.models import AssetClass
from app.events.models.details.dispatching import DispatchingDetail
from app.events.models.details.maintenance import MaintenanceDetail
from app.events.models.event import EventType
from app.dispatching.control_layer.managers.dispatch_demand_manager import DispatchDemandManager
from app.maintenance.models.action import Action
from app.maintenance.control_layer.part_demand_manager import PartDemandManager
from app.parts.control_layer.factories.part_factory import PartFactory
from app.procurement.control_layer.factories.part_demand_factory import PartDemandFactory
from app.procurement.presentation_layer.search.open_demand_search import OpenDemandSearch
from app.procurement.models import DemandSourceModule, PartDemand

from app.administration.models.data_ownership.user_assignments.user_domains import UserDomain

User = get_user_model()


class PartDemandSourceTrackingTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="source_tracker", email="source@test.local", password="TestPass123!@"
        )
        cls.domain = Domain.objects.create(
            name="Tracking Domain", slug="tracking-domain",
            created_by=cls.user, updated_by=cls.user,
        )
        UserDomain.objects.create(
            user=cls.user, domain=cls.domain,
            created_by=cls.user, updated_by=cls.user,
        )
        cls.asset_class = AssetClass.objects.create(
            name="Tracking Fleet Class",
            created_by=cls.user, updated_by=cls.user,
        )
        cls.part = PartFactory.create(
            data={
                "part_number": "PN-TRACK-01", "name": "Tracking Part",
                "part_type": "component", "category": "test",
            },
            actor=cls.user,
        )

        # 1. Procurement standalone demand
        cls.procurement_demand = PartDemandFactory.create(
            part_id=cls.part.pk,
            domain_id=cls.domain.pk,
            quantity_requested=Decimal("10"),
            source=DemandSourceModule.PROCUREMENT,
            actor=cls.user,
        )

        # 2. Maintenance event & action demand
        cls.maint_event = MaintenanceDetail.objects.create(
            domain=cls.domain,
            title="Engine overhaul",
            event_type=EventType.MAINTENANCE,
            event_start=timezone.now(),
            maintenance_type="unscheduled",
            assigned_user=cls.user,
            created_by=cls.user,
            updated_by=cls.user,
        )
        cls.action = Action.objects.create(
            event_detail=cls.maint_event,
            action_name="Replace Spark Plugs",
            sequence_order=1,
            created_by=cls.user,
            updated_by=cls.user,
        )
        cls.maint_link = PartDemandManager.create_for_action(
            action_id=cls.action.pk,
            part_id=cls.part.pk,
            quantity_requested=Decimal("4"),
            actor=cls.user,
        )
        cls.maint_demand = cls.maint_link.part_demand

        # 3. Dispatching event demand
        now = timezone.now()
        cls.dispatch_event = DispatchingDetail.objects.create(
            domain=cls.domain,
            title="VIP Flight Dispatch",
            event_type=EventType.DISPATCHING,
            event_start=now,
            desired_start=now,
            desired_end=now + timezone.timedelta(hours=4),
            requested_for=cls.user,
            requested_by=cls.user,
            asset_class=cls.asset_class,
            created_by=cls.user,
            updated_by=cls.user,
        )
        from app.dispatching.control_layer.dispatch_context import DispatchContext
        cls.dispatch_ctx = DispatchContext(cls.dispatch_event.pk, cls.user)
        cls.dispatch_link = cls.dispatch_ctx.demands.raise_demand(
            part_id=cls.part.pk,
            quantity_requested=Decimal("2"),
            actor=cls.user,
        )
        cls.dispatch_demand = cls.dispatch_link.part_demand

    def test_procurement_demand_source_and_event_id(self):
        self.assertEqual(self.procurement_demand.source, DemandSourceModule.PROCUREMENT)
        self.assertIsNone(self.procurement_demand.event_id)

    def test_maintenance_demand_source_and_event_id(self):
        self.maint_demand.refresh_from_db()
        self.assertEqual(self.maint_demand.source, DemandSourceModule.MAINTENANCE)
        self.assertEqual(self.maint_demand.event_id, self.maint_event.pk)
        self.assertEqual(self.maint_demand.event, self.maint_event.event_ptr)

    def test_dispatching_demand_source_and_event_id(self):
        self.dispatch_demand.refresh_from_db()
        self.assertEqual(self.dispatch_demand.source, DemandSourceModule.DISPATCHING)
        self.assertEqual(self.dispatch_demand.event_id, self.dispatch_event.pk)
        self.assertEqual(self.dispatch_demand.event, self.dispatch_event.event_ptr)

    def test_search_filtering_by_source(self):
        qs = OpenDemandSearch.index_list(
            domain_ids=[self.domain.pk],
            source=DemandSourceModule.MAINTENANCE,
        )
        pks = set(qs.values_list("pk", flat=True))
        self.assertIn(self.maint_demand.pk, pks)
        self.assertNotIn(self.procurement_demand.pk, pks)
        self.assertNotIn(self.dispatch_demand.pk, pks)

    def test_search_filtering_by_event_id(self):
        qs = OpenDemandSearch.index_list(
            domain_ids=[self.domain.pk],
            event_id=self.dispatch_event.pk,
        )
        pks = set(qs.values_list("pk", flat=True))
        self.assertEqual(pks, {self.dispatch_demand.pk})

    def test_demand_index_and_detail_views_render(self):
        self.client.force_login(self.user)
        response = self.client.get("/procurement/demands/")
        self.assertEqual(response.status_code, 200)

        detail_resp = self.client.get(f"/procurement/demands/{self.maint_demand.pk}/")
        self.assertEqual(detail_resp.status_code, 200)
