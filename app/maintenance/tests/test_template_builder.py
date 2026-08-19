"""Session-backed template builder wizard — the model-assignment card in
particular (harness/UX_UI/search/left_heavy_assignment_card_pair.md), since
it re-scopes cross-class POSTs server-side and must survive a plain refresh.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from app.administration.models import Domain
from app.assets.models import AssetModel
from app.assets.models.core.asset_class import AssetClass
from app.maintenance.control_layer.adapters.template_builder_session_adapter import (
    SESSION_KEY,
    TemplateBuilderSessionAdapter,
)

User = get_user_model()


class _FakeSession(dict):
    modified = False


class _FakeRequest:
    def __init__(self):
        self.session = _FakeSession()


class TemplateBuilderSessionAdapterTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="builder_user", email="builder_user@test.local", password="TestPass123!@"
        )

    def _adapter(self, request):
        return TemplateBuilderSessionAdapter(request)

    def test_add_and_remove_asset_models_are_idempotent_and_ordered(self):
        request = _FakeRequest()
        adapter = self._adapter(request)
        adapter.add_asset_models([3, 1])
        self.assertEqual(adapter.draft["asset_model_ids"], [1, 3])
        adapter.add_asset_models([1])  # re-adding is a no-op, not a duplicate
        self.assertEqual(adapter.draft["asset_model_ids"], [1, 3])
        adapter.remove_asset_models([1])
        self.assertEqual(adapter.draft["asset_model_ids"], [3])

    def test_changing_asset_class_clears_previously_assigned_models(self):
        request = _FakeRequest()
        adapter = self._adapter(request)
        adapter.set_metadata(asset_class_id=1)
        adapter.add_asset_models([7])
        self.assertEqual(adapter.draft["asset_model_ids"], [7])
        adapter.set_metadata(asset_class_id=2)
        self.assertEqual(adapter.draft["asset_model_ids"], [])

    def test_setting_the_same_asset_class_keeps_assigned_models(self):
        request = _FakeRequest()
        adapter = self._adapter(request)
        adapter.set_metadata(asset_class_id=1)
        adapter.add_asset_models([7])
        adapter.set_metadata(task_name="Renamed", asset_class_id=1)
        self.assertEqual(adapter.draft["asset_model_ids"], [7])


class TemplateBuilderAssignModelsViewTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="builder_view_user", email="builder_view_user@test.local",
            password="TestPass123!@",
        )
        cls.domain = Domain.objects.create(
            name="Builder Domain", slug="builder-domain",
            created_by=cls.user, updated_by=cls.user,
        )
        cls.asset_class = AssetClass.objects.create(
            name="Boom Lift", created_by=cls.user, updated_by=cls.user,
        )
        cls.other_class = AssetClass.objects.create(
            name="Generator", created_by=cls.user, updated_by=cls.user,
        )
        cls.model_in_class = AssetModel.objects.create(
            model_name="Z-45", asset_class=cls.asset_class,
            created_by=cls.user, updated_by=cls.user,
        )
        cls.model_out_of_class = AssetModel.objects.create(
            model_name="Genset-9000", asset_class=cls.other_class,
            created_by=cls.user, updated_by=cls.user,
        )

    def _login(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["user_domain_ids"] = [self.domain.pk]
        session.save()

    def _set_draft_class(self, asset_class_id):
        session = self.client.session
        session[SESSION_KEY] = {
            "task_name": "", "description": "", "asset_class_id": asset_class_id,
            "asset_model_ids": [], "prior_revision_id": None, "revision": "0",
            "actions": [],
        }
        session.save()

    def test_add_asset_models_scopes_to_the_drafts_asset_class(self):
        self._login()
        self._set_draft_class(self.asset_class.pk)
        response = self.client.post(
            reverse("template_builder_update"),
            {
                "action": "add_asset_models",
                "asset_model_ids": [str(self.model_in_class.pk), str(self.model_out_of_class.pk)],
            },
        )
        self.assertEqual(response.status_code, 302)
        session = self.client.session
        # Only the in-class model survives — a forged out-of-class id is dropped
        # server-side even though the picker never renders it.
        self.assertEqual(session[SESSION_KEY]["asset_model_ids"], [self.model_in_class.pk])

    def test_remove_asset_models(self):
        self._login()
        self._set_draft_class(self.asset_class.pk)
        session = self.client.session
        session[SESSION_KEY]["asset_model_ids"] = [self.model_in_class.pk]
        session.save()

        response = self.client.post(
            reverse("template_builder_update"),
            {"action": "remove_asset_models", "asset_model_ids": [str(self.model_in_class.pk)]},
        )
        self.assertEqual(response.status_code, 302)
        session = self.client.session
        self.assertEqual(session[SESSION_KEY]["asset_model_ids"], [])

    def test_builder_get_survives_refresh_with_assigned_models(self):
        self._login()
        self._set_draft_class(self.asset_class.pk)
        session = self.client.session
        session[SESSION_KEY]["asset_model_ids"] = [self.model_in_class.pk]
        session.save()

        response = self.client.get(reverse("template_builder"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [m.pk for m in response.context["models_assigned"]], [self.model_in_class.pk]
        )
        self.assertEqual(response.context["models_available"], [])
