from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse

from app.administration.models import Domain
from app.administration.models.data_ownership.user_assignments.user_domains import UserDomain
from app.parts.control_layer.factories.part_factory import PartFactory

User = get_user_model()


class PartRevisionDetailTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.test_password = "TestPass123!@"
        cls.user = User.objects.create_user(
            username="testuser",
            email="testuser@test.local",
            password=cls.test_password,
        )
        cls.domain = Domain.objects.create(
            name="Test Domain",
            slug="test-domain",
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
        # Create a Part using the factory
        cls.part = PartFactory.create(
            data={
                "part_number": "PN-TEST-99",
                "name": "Test Alternator",
                "part_type": "assembly",
                "category": "electrical",
            },
            actor=cls.user,
        )
        # The factory automatically creates the base revision (major=1, minor=0)
        cls.revision = cls.part.revisions.first()

    def setUp(self):
        self.client = Client()
        self.client.login(username="testuser", password=self.test_password)

    def test_revision_detail_by_id_page_loads(self):
        url = reverse("revision_detail_by_id", kwargs={"revision_id": self.revision.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Revision 1.0")

    def test_part_revisions_page_links_to_new_url(self):
        revisions_url = reverse("part_revisions", kwargs={"part_id": self.part.id})
        response = self.client.get(revisions_url)
        self.assertEqual(response.status_code, 200)
        detail_url = reverse("revision_detail_by_id", kwargs={"revision_id": self.revision.id})
        self.assertContains(response, detail_url)

    def test_part_detail_page_links_to_new_url(self):
        detail_url = reverse("part_detail", kwargs={"part_id": self.part.id})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 200)
        revision_detail_url = reverse("revision_detail_by_id", kwargs={"revision_id": self.revision.id})
        self.assertContains(response, revision_detail_url)

    def test_unauthenticated_redirects(self):
        anon_client = Client()
        url = reverse("revision_detail_by_id", kwargs={"revision_id": self.revision.id})
        response = anon_client.get(url)
        self.assertEqual(response.status_code, 302)
