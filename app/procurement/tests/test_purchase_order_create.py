"""Tests for the purchase order create wizard and purchasing queue card interactions."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from app.administration.models import Domain, UserDomain
from app.parts.control_layer.factories.part_factory import PartFactory
from app.procurement.control_layer.factories.part_demand_factory import (
    PartDemandFactory,
)
from app.procurement.presentation_layer.tools import purchasing_queue

User = get_user_model()


class PurchaseOrderCreateWizardQueueTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            username="buyer_user",
            email="buyer@test.local",
            password="Password123!@",
        )
        cls.domain = Domain.objects.create(
            name="Buying Domain",
            slug="buying-domain",
            created_by=cls.user,
            updated_by=cls.user,
        )
        UserDomain.objects.create(
            user=cls.user,
            domain=cls.domain,
            created_by=cls.user,
            updated_by=cls.user,
        )
        cls.part = PartFactory.create(
            data={
                "part_number": "PN-QUEUE-01",
                "name": "Queue Test Part",
                "part_type": "component",
                "category": "test",
            },
            actor=cls.user,
        )
        cls.demand1 = PartDemandFactory.create(
            part_id=cls.part.pk,
            domain_id=cls.domain.pk,
            quantity_requested=Decimal("5"),
            actor=cls.user,
        )
        cls.demand2 = PartDemandFactory.create(
            part_id=cls.part.pk,
            domain_id=cls.domain.pk,
            quantity_requested=Decimal("10"),
            actor=cls.user,
        )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)
        session = self.client.session
        session["user_domain_ids"] = [self.domain.pk]
        session.save()

    def test_remove_from_queue_clears_session_item_and_refreshes_card(self):
        # 1. Queue demands 1 and 2 in session
        session = self.client.session
        key = f"{purchasing_queue.SESSION_KEY_PREFIX}{self.user.pk}"
        session[key] = [self.demand1.pk, self.demand2.pk]
        session.save()

        # 2. GET the wizard page — check queued card is present with both demands
        url = reverse("purchase_order_create")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"#{self.demand1.pk}")
        self.assertContains(response, f"#{self.demand2.pk}")

        # 3. POST action=remove_from_queue for demand1 via HTMX
        response = self.client.post(
            url,
            {"action": "remove_from_queue", "demand_id": str(self.demand1.pk)},
            HTTP_HX_REQUEST="true",
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        # 4. Verify session queue now only contains demand2
        self.assertEqual(self.client.session[key], [self.demand2.pk])

        # 5. Verify the refreshed page contains demand2 but not demand1
        self.assertNotContains(response, f"#{self.demand1.pk}")
        self.assertContains(response, f"#{self.demand2.pk}")

    def test_removing_all_queue_items_renders_explicit_empty_state_card(self):
        session = self.client.session
        key = f"{purchasing_queue.SESSION_KEY_PREFIX}{self.user.pk}"
        session[key] = [self.demand1.pk]
        session.save()

        url = reverse("purchase_order_create")
        response = self.client.post(
            url,
            {"action": "remove_from_queue", "demand_id": str(self.demand1.pk)},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session[key], [])
        # Rule 5: card is always rendered with explicit empty state
        self.assertContains(response, 'id="queued-purchasing-card"')
        self.assertContains(response, "No demands currently in your purchasing queue.")

    def test_htmx_queued_card_format_returns_fresh_card_fragment(self):
        session = self.client.session
        key = f"{purchasing_queue.SESSION_KEY_PREFIX}{self.user.pk}"
        session[key] = [self.demand1.pk]
        session.save()

        url = reverse("purchase_order_create") + "?format=htmx-queued-card"
        response = self.client.get(url, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="queued-purchasing-card"')
        self.assertContains(response, f"#{self.demand1.pk}")
        self.assertContains(response, 'id="queue-btn-purchasing"')

