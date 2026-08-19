"""The new-event page (maintenance_create). Legacy required a procedure
template for every creation path (MaintenanceActionSetFactory.create_from_template
took template_action_set_id as a required positional arg and 404'd without one —
see maintenance_starter_kit notes). This is new capability: creating a
template-less event that starts with zero steps and lands straight on the
edit portal to build its step list from scratch.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from app.administration.models import Domain
from app.administration.models.data_ownership.user_assignments.user_domains import (
    UserDomain,
)
from app.events.models.details.maintenance import MaintenanceDetail
from app.maintenance.models.action import Action
from app.maintenance.models.templates.template_action_item import TemplateActionItem
from app.maintenance.models.templates.template_action_set import TemplateActionSet

User = get_user_model()


class MaintenanceCreateTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="create_user", email="create_user@test.local", password="TestPass123!@"
        )
        cls.domain = Domain.objects.create(
            name="Create Domain", slug="create-domain",
            created_by=cls.user, updated_by=cls.user,
        )
        UserDomain.objects.create(
            user=cls.user, domain=cls.domain,
            created_by=cls.user, updated_by=cls.user,
        )
        cls.template = TemplateActionSet.objects.create(
            domain=cls.domain, task_name="Oil change", is_active=True,
            created_by=cls.user, updated_by=cls.user,
        )
        TemplateActionItem.objects.create(
            template_action_set=cls.template, action_name="Drain oil",
            sequence_order=1, created_by=cls.user, updated_by=cls.user,
        )

    def setUp(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["user_domain_ids"] = [self.domain.pk]
        session.save()

    def _create_url(self):
        return reverse("maintenance_create")


class BlankEventCreationTests(MaintenanceCreateTestCase):
    def test_creating_without_a_template_produces_zero_actions(self):
        response = self.client.post(
            self._create_url(),
            {
                "domain_id": self.domain.pk,
                "title": "Ad-hoc inspection",
                "event_start": timezone.now().strftime("%Y-%m-%dT%H:%M"),
            },
        )
        self.assertEqual(response.status_code, 302)
        detail = MaintenanceDetail.objects.get(title="Ad-hoc inspection")
        self.assertIsNone(detail.template_action_set_id)
        self.assertEqual(Action.objects.filter(event_detail=detail).count(), 0)

    def test_creating_without_a_template_redirects_to_the_edit_portal(self):
        response = self.client.post(
            self._create_url(),
            {
                "domain_id": self.domain.pk,
                "title": "Ad-hoc inspection",
                "event_start": timezone.now().strftime("%Y-%m-%dT%H:%M"),
            },
        )
        detail = MaintenanceDetail.objects.get(title="Ad-hoc inspection")
        self.assertEqual(response.url, reverse("maintenance_edit", kwargs={"pk": detail.pk}))

    def test_blank_creation_without_a_title_is_refused(self):
        response = self.client.post(
            self._create_url(),
            {"domain_id": self.domain.pk, "event_start": timezone.now().strftime("%Y-%m-%dT%H:%M")},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(MaintenanceDetail.objects.filter(template_action_set__isnull=True).exists())


class TemplatedEventCreationTests(MaintenanceCreateTestCase):
    def test_creating_with_a_template_still_expands_its_actions(self):
        response = self.client.post(
            self._create_url(),
            {
                "domain_id": self.domain.pk,
                "template_action_set_id": self.template.pk,
                "event_start": timezone.now().strftime("%Y-%m-%dT%H:%M"),
            },
        )
        self.assertEqual(response.status_code, 302)
        detail = MaintenanceDetail.objects.get(template_action_set=self.template)
        self.assertEqual(Action.objects.filter(event_detail=detail).count(), 1)

    def test_creating_with_a_template_still_redirects_to_the_view_page(self):
        response = self.client.post(
            self._create_url(),
            {
                "domain_id": self.domain.pk,
                "template_action_set_id": self.template.pk,
                "event_start": timezone.now().strftime("%Y-%m-%dT%H:%M"),
            },
        )
        detail = MaintenanceDetail.objects.get(template_action_set=self.template)
        self.assertEqual(response.url, reverse("maintenance_detail", kwargs={"pk": detail.pk}))
