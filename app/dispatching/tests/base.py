"""Shared setup for dispatching tests — a minimal but complete cross-app
fixture (user, domain, asset class/model/asset, capability, skill, part)
built through each owning app's own factory where one exists, so tests never
bypass required scaffolding (e.g. Asset's photo_gallery/documentation)."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from app.administration.models import Domain
from app.assets.control_layer.factories.asset_factory import AssetFactory
from app.assets.models import AssetClass, AssetModel, CapabilityDefinition
from app.dispatching.models.skills.dispatch_skill import DispatchSkill
from app.parts.models import Part

User = get_user_model()


class DispatchingTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = User.objects.create_user(
            username="dispatch_tester", email="dispatch_tester@test.local", password="TestPass123!@",
        )
        cls.other_user = User.objects.create_user(
            username="other_tester", email="other_tester@test.local", password="TestPass123!@",
        )
        cls.domain = Domain.objects.create(
            name="Dispatching Test Domain", slug="dispatching-test-domain",
            created_by=cls.actor, updated_by=cls.actor,
        )
        cls.asset_class = AssetClass.objects.create(
            name="Test Truck Class", created_by=cls.actor, updated_by=cls.actor,
        )
        cls.asset_model = AssetModel.objects.create(
            model_name="Test Truck Model", asset_class=cls.asset_class,
            created_by=cls.actor, updated_by=cls.actor,
        )
        cls.asset = AssetFactory.create(
            data={
                "name": "Test Truck 1",
                "serial_number": "TT-0001",
                "domain_id": cls.domain.pk,
                "model_id": cls.asset_model.pk,
            },
            actor=cls.actor,
        )
        cls.asset_2 = AssetFactory.create(
            data={
                "name": "Test Truck 2",
                "serial_number": "TT-0002",
                "domain_id": cls.domain.pk,
                "model_id": cls.asset_model.pk,
            },
            actor=cls.actor,
        )
        cls.capability = CapabilityDefinition.objects.create(
            name="Test Capability", code="TESTCAP", created_by=cls.actor, updated_by=cls.actor,
        )
        cls.skill = DispatchSkill.objects.create(
            name="Test CDL", code="TESTCDL", created_by=cls.actor, updated_by=cls.actor,
        )
        cls.part = Part.objects.create(
            part_number="TEST-PART-1", name="Test Wire", created_by=cls.actor, updated_by=cls.actor,
        )
