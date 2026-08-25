"""The events list's asset filter and the search-dropdown that feeds it."""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from app.administration.models.data_ownership.domains import Domain
from app.administration.models.data_ownership.user_assignments.user_domains import (
    UserDomain,
)
from app.assets.control_layer.orchestrators.asset_creation_orchestrator import (
    AssetCreationOrchestrator,
)
from app.assets.models import AssetClass, AssetModel
from app.events.control_layer.managers.asset_event_link_manager import (
    AssetEventLinkManager,
)
from app.events.models import Event, EventStatus, EventType

User = get_user_model()


class EventAssetFilterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = "TestPass123!@"
        cls.user = User.objects.create_superuser(
            username="asset_filter_admin",
            email="af@test.local",
            password=cls.password,
        )
        cls.domain = Domain.objects.create(
            name="Filter Domain",
            slug="filter-domain",
            created_by=cls.user,
            updated_by=cls.user,
        )
        UserDomain.objects.create(
            user=cls.user,
            domain=cls.domain,
            is_active=True,
            created_by=cls.user,
            updated_by=cls.user,
        )
        cls.asset_class = AssetClass.objects.create(
            name="Filter Fleet", created_by=cls.user, updated_by=cls.user
        )
        cls.model = AssetModel.objects.create(
            model_name="Backhoe",
            version="2019",
            asset_class=cls.asset_class,
            created_by=cls.user,
            updated_by=cls.user,
        )
        cls.asset = AssetCreationOrchestrator.create(
            data={
                "name": "Digger One",
                "serial_number": "SN-DIG-1",
                "domain_id": cls.domain.pk,
                "model_id": cls.model.pk,
                "status": "Active",
            },
            actor=cls.user,
        )

        cls.linked = cls._event("Linked event")
        AssetEventLinkManager.link(
            asset_id=cls.asset.pk, event_id=cls.linked.pk, role="target", actor=cls.user
        )
        cls.unlinked = cls._event("Unlinked event")

    @classmethod
    def _event(cls, title: str) -> Event:
        return Event.objects.create(
            title=title,
            domain=cls.domain,
            event_type=EventType.GENERIC,
            status=EventStatus.PLANNED,
            event_start=timezone.now(),
            created_by=cls.user,
            updated_by=cls.user,
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username="asset_filter_admin", password=self.password)

    def test_medium_view_renders_the_asset_search_dropdown(self):
        response = self.client.get(reverse("event_index"), {"format": "medium"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="asset_sn"')

    def test_filtering_by_asset_keeps_only_linked_events(self):
        response = self.client.get(
            reverse("event_index"), {"format": "medium", "asset_sn": self.asset.serial_number}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Linked event")
        self.assertNotContains(response, "Unlinked event")

    def test_no_asset_filter_shows_everything(self):
        response = self.client.get(reverse("event_index"), {"format": "medium"})
        self.assertContains(response, "Linked event")
        self.assertContains(response, "Unlinked event")

    def test_selected_asset_label_is_echoed_back_into_the_dropdown(self):
        """Without value-label the box goes blank on reload and the user cannot
        tell which asset is filtering the list."""
        response = self.client.get(
            reverse("event_index"), {"format": "medium", "asset_sn": self.asset.serial_number}
        )
        self.assertContains(response, f"SN-DIG-1")


class AssetSearchResultsTests(TestCase):
    """The htmx endpoint behind the dropdown: one box, four ways to name an asset."""

    @classmethod
    def setUpTestData(cls):
        cls.password = "TestPass123!@"
        cls.user = User.objects.create_superuser(
            username="asset_search_admin", email="as@test.local", password=cls.password
        )
        cls.domain = Domain.objects.create(
            name="Search Domain",
            slug="search-domain",
            created_by=cls.user,
            updated_by=cls.user,
        )
        cls.asset_class = AssetClass.objects.create(
            name="Search Fleet", created_by=cls.user, updated_by=cls.user
        )
        cls.model = AssetModel.objects.create(
            model_name="Skidsteer",
            version="2022",
            asset_class=cls.asset_class,
            created_by=cls.user,
            updated_by=cls.user,
        )
        cls.asset = AssetCreationOrchestrator.create(
            data={
                "name": "Yard Unit",
                "serial_number": "SN-YARD-9",
                "domain_id": cls.domain.pk,
                "model_id": cls.model.pk,
                "status": "Active",
            },
            actor=cls.user,
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username="asset_search_admin", password=self.password)

    def _search(self, q: str) -> str:
        response = self.client.get(
            reverse("asset_index"), {"format": "htmx-search-results", "q": q}
        )
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_matches_by_name(self):
        self.assertIn(f'data-value="{self.asset.pk}"', self._search("Yard"))

    def test_matches_by_id(self):
        self.assertIn(f'data-value="{self.asset.pk}"', self._search(str(self.asset.pk)))

    def test_matches_by_model_name(self):
        self.assertIn(f'data-value="{self.asset.pk}"', self._search("Skidsteer"))

    def test_matches_by_serial(self):
        self.assertIn(f'data-value="{self.asset.pk}"', self._search("YARD-9"))

    def test_no_match_returns_a_disabled_row_not_an_empty_body(self):
        self.assertIn("No matches.", self._search("zzzznothing"))
