"""Tests for the Issued Parts Ledger index endpoint (`/inventory/issues/`)."""

from django.test import RequestFactory, TestCase
from django.contrib.sessions.middleware import SessionMiddleware
from django.urls import reverse

from app.administration.models import User
from app.inventory.presentation_layer.entrypoints.issues import issues_index


class IssuesIndexViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            username="issues_test_admin",
            email="issues_admin@test.local",
            password="TestPass123!@",
        )

    def setUp(self):
        self.factory = RequestFactory()

    def _get_request(self, url):
        request = self.factory.get(url)
        request.user = self.user
        middleware = SessionMiddleware(lambda r: None)
        middleware.process_request(request)
        request.session.save()
        return request

    def test_issues_index_sessions_tab_renders(self):
        request = self._get_request(reverse("inventory_issues_index") + "?tab=sessions")
        response = issues_index(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Committed Issue Sessions", response.content.decode())

    def test_issues_index_lines_tab_renders(self):
        request = self._get_request(reverse("inventory_issues_index") + "?tab=lines")
        response = issues_index(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Granular Issued Line Items", response.content.decode())
