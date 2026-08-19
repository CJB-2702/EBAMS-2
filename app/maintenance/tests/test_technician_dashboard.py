"""The technician dashboard (legacy /maintenance/technician/dashboard).

Covers the surface ported from page_catalog.md #17: stat scoping to the
logged-in user, domain fencing, the assigned/planned list queries, and the
asset-lookup HTMX fragment.
"""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from app.administration.models import Domain
from app.assets.control_layer.factories.asset_factory import AssetFactory
from app.assets.models import AssetClass, AssetModel
from app.events.models.details.maintenance import MaintenanceDetail
from app.events.models.event import EventStatus, EventType

User = get_user_model()


class TechnicianDashboardTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tech = User.objects.create_user(
            username="td_tech", email="td_tech@test.local", password="TestPass123!@"
        )
        cls.other_user = User.objects.create_user(
            username="td_other", email="td_other@test.local", password="TestPass123!@"
        )

        cls.domain = Domain.objects.create(
            name="TD Domain", slug="td-domain",
            created_by=cls.tech, updated_by=cls.tech,
        )
        cls.other_domain = Domain.objects.create(
            name="TD Other Domain", slug="td-other-domain",
            created_by=cls.tech, updated_by=cls.tech,
        )

        cls.asset_class = AssetClass.objects.create(
            name="TD Forklift Class", created_by=cls.tech, updated_by=cls.tech,
        )
        cls.asset_model = AssetModel.objects.create(
            model_name="TD-9000", asset_class=cls.asset_class,
            created_by=cls.tech, updated_by=cls.tech,
        )
        cls.asset = AssetFactory.create(
            data={
                "name": "Forklift", "serial_number": "FL-900",
                "domain_id": cls.domain.pk, "model_id": cls.asset_model.pk,
            },
            actor=cls.tech,
        )

        now = timezone.now()

        cls.assigned_open = MaintenanceDetail.objects.create(
            domain=cls.domain, title="Replace belt", event_type=EventType.MAINTENANCE,
            event_start=now, maintenance_type="scheduled", asset=cls.asset,
            assigned_user=cls.tech, status=EventStatus.PLANNED,
            created_by=cls.tech, updated_by=cls.tech,
        )
        cls.assigned_in_progress = MaintenanceDetail.objects.create(
            domain=cls.domain, title="Inspect brakes", event_type=EventType.MAINTENANCE,
            event_start=now, maintenance_type="scheduled", asset=cls.asset,
            assigned_user=cls.tech, status=EventStatus.IN_PROGRESS,
            created_by=cls.tech, updated_by=cls.tech,
        )
        cls.completed_today = MaintenanceDetail.objects.create(
            domain=cls.domain, title="Oil change", event_type=EventType.MAINTENANCE,
            event_start=now, maintenance_type="scheduled", asset=cls.asset,
            assigned_user=cls.tech, status=EventStatus.COMPLETE,
            created_by=cls.tech, updated_by=cls.tech,
        )
        cls.planned_next_week = MaintenanceDetail.objects.create(
            domain=cls.domain, title="Tire rotation", event_type=EventType.MAINTENANCE,
            event_start=now + timedelta(days=3), maintenance_type="scheduled",
            asset=cls.asset, assigned_user=cls.tech, status=EventStatus.PLANNED,
            created_by=cls.tech, updated_by=cls.tech,
        )
        # Assigned to someone else — must never appear in the technician's lists.
        cls.someone_elses_event = MaintenanceDetail.objects.create(
            domain=cls.domain, title="Not mine", event_type=EventType.MAINTENANCE,
            event_start=now, maintenance_type="scheduled", asset=cls.asset,
            assigned_user=cls.other_user, status=EventStatus.PLANNED,
            created_by=cls.tech, updated_by=cls.tech,
        )
        # Assigned to this user but outside their accessible domain.
        cls.foreign_domain_event = MaintenanceDetail.objects.create(
            domain=cls.other_domain, title="Wrong domain", event_type=EventType.MAINTENANCE,
            event_start=now, maintenance_type="scheduled", asset=cls.asset,
            assigned_user=cls.tech, status=EventStatus.PLANNED,
            created_by=cls.tech, updated_by=cls.tech,
        )

    def setUp(self):
        self.client.force_login(self.tech)
        session = self.client.session
        session["user_domain_ids"] = [self.domain.pk]
        session.save()


class TechnicianDashboardStatsTests(TechnicianDashboardTestCase):
    def test_assigned_work_counts_open_events_assigned_to_the_user(self):
        response = self.client.get(reverse("technician_dashboard"))
        self.assertEqual(response.status_code, 200)
        # assigned_open, assigned_in_progress, planned_next_week — completed excluded.
        self.assertEqual(response.context["stats"]["assigned_work"], 3)

    def test_in_progress_counts_only_in_progress_status(self):
        response = self.client.get(reverse("technician_dashboard"))
        self.assertEqual(response.context["stats"]["in_progress"], 1)

    def test_completed_today_counts_events_completed_today(self):
        response = self.client.get(reverse("technician_dashboard"))
        self.assertEqual(response.context["stats"]["completed_today"], 1)

    def test_other_users_events_are_never_counted(self):
        response = self.client.get(reverse("technician_dashboard"))
        assigned_ids = {e.pk for e in response.context["assigned_events"]}
        self.assertNotIn(self.someone_elses_event.pk, assigned_ids)

    def test_events_outside_the_users_domain_are_never_counted(self):
        response = self.client.get(reverse("technician_dashboard"))
        assigned_ids = {e.pk for e in response.context["assigned_events"]}
        self.assertNotIn(self.foreign_domain_event.pk, assigned_ids)


class TechnicianDashboardListsTests(TechnicianDashboardTestCase):
    def test_planned_this_week_includes_events_in_the_lookahead_window(self):
        response = self.client.get(reverse("technician_dashboard"))
        planned_ids = {e.pk for e in response.context["planned_this_week"]}
        self.assertIn(self.planned_next_week.pk, planned_ids)

    def test_planned_this_week_excludes_closed_events(self):
        response = self.client.get(reverse("technician_dashboard"))
        planned_ids = {e.pk for e in response.context["planned_this_week"]}
        self.assertNotIn(self.completed_today.pk, planned_ids)


class TechnicianAssetLookupTests(TechnicianDashboardTestCase):
    def test_asset_lookup_matches_by_name_or_serial(self):
        response = self.client.get(
            reverse("technician_dashboard"),
            {"format": "htmx-asset-lookup", "q": "FL-900"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Forklift")

    def test_asset_lookup_fragment_is_not_a_full_page(self):
        response = self.client.get(
            reverse("technician_dashboard"),
            {"format": "htmx-asset-lookup", "q": "Forklift"},
        )
        self.assertNotContains(response, "<html")

    def test_blank_query_returns_no_results(self):
        response = self.client.get(
            reverse("technician_dashboard"), {"format": "htmx-asset-lookup", "q": ""}
        )
        self.assertNotContains(response, "Forklift")
