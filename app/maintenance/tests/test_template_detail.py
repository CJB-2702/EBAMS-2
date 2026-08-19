"""Procedure template detail page (legacy /maintenance-template/<id>/view,
maintenance_starter_kit/legacy_ui/page_catalog.md §8) — domain scoping, the
roll-up cards, and the deactivate/activate toggle.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from app.administration.models import Domain
from app.maintenance.models.templates.template_action_item import TemplateActionItem
from app.maintenance.models.templates.template_action_set import TemplateActionSet
from app.maintenance.models.templates.template_action_tool import TemplateActionTool
from app.maintenance.models.templates.template_part_demand import TemplatePartDemand
from app.parts.control_layer.factories.part_factory import PartFactory

User = get_user_model()


class TemplateDetailTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="tmpl_viewer", email="tmpl_viewer@test.local", password="TestPass123!@"
        )
        cls.outsider = User.objects.create_user(
            username="tmpl_outsider", email="tmpl_outsider@test.local", password="TestPass123!@"
        )

        cls.domain = Domain.objects.create(
            name="Template Domain", slug="template-domain",
            created_by=cls.user, updated_by=cls.user,
        )

        cls.part = PartFactory.create(
            data={"part_number": "PN-TMPL-01", "name": "Brake Pad Set", "part_type": "component", "category": "test"},
            actor=cls.user,
        )

        cls.template = TemplateActionSet.objects.create(
            task_name="Brake Inspection Procedure",
            description="Standard brake inspection.",
            domain=cls.domain,
            is_active=True,
            created_by=cls.user, updated_by=cls.user,
        )
        cls.item1 = TemplateActionItem.objects.create(
            template_action_set=cls.template,
            action_name="Check Brake Pads",
            sequence_order=1,
            estimated_duration_minutes=20,
            created_by=cls.user, updated_by=cls.user,
        )
        cls.item2 = TemplateActionItem.objects.create(
            template_action_set=cls.template,
            action_name="Test Brake System",
            sequence_order=2,
            estimated_duration_minutes=15,
            created_by=cls.user, updated_by=cls.user,
        )
        cls.tool = TemplateActionTool.objects.create(
            template_action_item=cls.item1,
            tool_name="Jack",
            quantity_required=1,
            created_by=cls.user, updated_by=cls.user,
        )
        cls.demand = TemplatePartDemand.objects.create(
            template_action_item=cls.item2,
            part=cls.part,
            quantity_required=1,
            created_by=cls.user, updated_by=cls.user,
        )

    def _login_as(self, user, domain_ids):
        self.client.force_login(user)
        session = self.client.session
        session["user_domain_ids"] = domain_ids
        session.save()

    def test_detail_renders_with_rollups(self):
        self._login_as(self.user, [self.domain.pk])
        response = self.client.get(reverse("template_detail", kwargs={"pk": self.template.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_action_items"], 2)
        self.assertEqual(len(response.context["all_tools_required"]), 1)
        self.assertEqual(len(response.context["all_parts_required"]), 1)
        # The tool roll-up carries its owning step's name alongside it.
        tool, action_name = response.context["all_tools_required"][0]
        self.assertEqual(tool.pk, self.tool.pk)
        self.assertEqual(action_name, self.item1.action_name)

    def test_detail_404s_outside_the_users_domains(self):
        other_domain = Domain.objects.create(
            name="Other Domain", slug="other-domain",
            created_by=self.user, updated_by=self.user,
        )
        self._login_as(self.outsider, [other_domain.pk])
        response = self.client.get(reverse("template_detail", kwargs={"pk": self.template.pk}))
        self.assertEqual(response.status_code, 404)

    def test_toggle_active_flips_the_flag_and_redirects_back(self):
        self._login_as(self.user, [self.domain.pk])
        response = self.client.post(reverse("template_toggle_active", kwargs={"pk": self.template.pk}))
        self.assertRedirects(response, reverse("template_detail", kwargs={"pk": self.template.pk}))
        self.template.refresh_from_db()
        self.assertFalse(self.template.is_active)

        response = self.client.post(reverse("template_toggle_active", kwargs={"pk": self.template.pk}))
        self.template.refresh_from_db()
        self.assertTrue(self.template.is_active)

    def test_toggle_active_requires_domain_membership(self):
        other_domain = Domain.objects.create(
            name="Other Domain 2", slug="other-domain-2",
            created_by=self.user, updated_by=self.user,
        )
        self._login_as(self.outsider, [other_domain.pk])
        response = self.client.post(reverse("template_toggle_active", kwargs={"pk": self.template.pk}))
        self.assertEqual(response.status_code, 404)
        self.template.refresh_from_db()
        self.assertTrue(self.template.is_active)

    def test_toggle_active_rejects_get(self):
        self._login_as(self.user, [self.domain.pk])
        response = self.client.get(reverse("template_toggle_active", kwargs={"pk": self.template.pk}))
        self.assertEqual(response.status_code, 405)
