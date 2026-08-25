"""Tests for assets dashboard density switching (comfortable vs condensed) and HTMX fragment responses.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from app.administration.models import Domain
from app.assets.control_layer.factories.asset_factory import AssetFactory
from app.assets.models import AssetClass, AssetModel

User = get_user_model()


class AssetDashboardDensityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="ad_user", email="ad_user@test.local", password="TestPass123!@"
        )
        cls.domain = Domain.objects.create(
            name="AD Domain", slug="ad-domain",
            created_by=cls.user, updated_by=cls.user,
        )
        cls.asset_class = AssetClass.objects.create(
            name="AD Class", created_by=cls.user, updated_by=cls.user,
        )
        cls.asset_model = AssetModel.objects.create(
            model_name="AD-Model-100", asset_class=cls.asset_class,
            created_by=cls.user, updated_by=cls.user,
        )
        cls.asset = AssetFactory.create(
            data={
                "name": "Fleet Asset Alpha",
                "serial_number": "SN-ALPHA-100",
                "domain_id": cls.domain.pk,
                "model_id": cls.asset_model.pk,
            },
            actor=cls.user,
        )

    def setUp(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["user_domain_ids"] = [self.domain.pk]
        session.save()

    def test_default_display_is_comfortable(self):
        response = self.client.get(reverse("maintenance_asset_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["current_format"], "comfortable")
        self.assertContains(response, "Fleet Asset Alpha")
        self.assertContains(response, "ah-grid")
        self.assertContains(response, "format=condensed")

    def test_condensed_format_renders_table(self):
        response = self.client.get(reverse("maintenance_asset_dashboard"), {"format": "condensed"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["current_format"], "condensed")
        self.assertContains(response, "Fleet Asset Alpha")
        self.assertContains(response, "SN-ALPHA-100")
        self.assertContains(response, "Asset / Serial")
        self.assertContains(response, "Health Status")

    def test_htmx_cards_fragment(self):
        response = self.client.get(reverse("maintenance_asset_dashboard"), {"format": "htmx-asset-cards"})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "<html")
        self.assertContains(response, "ah-card")

    def test_htmx_condensed_fragment(self):
        response = self.client.get(reverse("maintenance_asset_dashboard"), {"format": "htmx-asset-condensed"})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "<html")
        self.assertContains(response, "Fleet Asset Alpha")
        self.assertContains(response, "SN-ALPHA-100")
