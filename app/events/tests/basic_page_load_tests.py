import logging
from pathlib import Path
from django.contrib.auth import get_user_model
User = get_user_model()
from django.test import TestCase, Client
from django.urls import reverse

from app.administration.models.data_ownership.domains import Domain
from app.administration.models.data_ownership.user_assignments.user_domains import UserDomain
from app.events.models import Event, EventType, EventStatus
from app.utils.hashids import encode_id

logger = logging.getLogger(__name__)


class EventPageLoadTests(TestCase):
    """Test that event pages load without errors when logged in as superuser."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = Client()
        cls.test_password = "TestPass123!@"
        cls.superuser = User.objects.create_superuser(
            username="admin",
            email="admin@test.local",
            password=cls.test_password,
        )
        cls.domain = Domain.objects.create(
            name="Test Domain",
            slug="test-domain",
            created_by=cls.superuser,
            updated_by=cls.superuser,
        )
        UserDomain.objects.create(
            user=cls.superuser,
            domain=cls.domain,
            is_active=True,
            created_by=cls.superuser,
            updated_by=cls.superuser,
        )
        cls.event = Event.objects.create(
            title="Test Event",
            event_type=EventType.GENERIC,
            status=EventStatus.PLANNED,
            domain=cls.domain,
            created_by=cls.superuser,
            updated_by=cls.superuser,
        )
        cls.event_hash = encode_id(cls.event.pk)
        cls.test_results = {
            "passed": [],
            "failed": [],
            "errors": [],
        }

    def setUp(self):
        self.client.login(username="admin", password=self.test_password)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._write_test_summary()

    @classmethod
    def _write_test_summary(cls):
        log_dir = Path("app/events/tests/logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "page_load_test_summary.txt"

        total = len(cls.test_results["passed"]) + len(cls.test_results["failed"]) + len(cls.test_results["errors"])
        passed = len(cls.test_results["passed"])
        failed = len(cls.test_results["failed"])
        errors = len(cls.test_results["errors"])
        summary = f"""
================================================================================
EVENT PAGE LOAD TEST SUMMARY
================================================================================
Total Tests: {total}
Passed: {passed}
Failed: {failed}
Errors: {errors}
================================================================================

PASSED PAGES ({passed}):
{chr(10).join(f"  ✓ {page}" for page in cls.test_results["passed"]) if cls.test_results["passed"] else "  (none)"}

FAILED PAGES ({failed}):
{chr(10).join(f"  ✗ {page}: {reason}" for page, reason in cls.test_results["failed"]) if cls.test_results["failed"] else "  (none)"}

PAGES WITH ERRORS ({errors}):
{chr(10).join(f"  ✗ {page}: {reason}" for page, reason in cls.test_results["errors"]) if cls.test_results["errors"] else "  (none)"}

================================================================================
"""
        log_file.write_text(summary)

    def _record_result(self, page_name, status, reason=None):
        if status == "passed":
            self.__class__.test_results["passed"].append(page_name)
        elif status == "failed":
            self.__class__.test_results["failed"].append((page_name, reason))
        elif status == "error":
            self.__class__.test_results["errors"].append((page_name, reason))

    def _check(self, name, url):
        try:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, f"{name} failed to load (status {response.status_code})")
            self._record_result(name, "passed")
        except Exception as e:
            self._record_result(name, "error", str(e))
            raise

    def test_event_index(self):
        self._check("event_index", reverse("event_index"))

    def test_event_create(self):
        self._check("event_create", reverse("event_create"))

    def test_event_detail(self):
        self._check("event_detail", reverse("event_detail", kwargs={"hash": self.event_hash}))

    def test_event_edit(self):
        self._check("event_edit", reverse("event_edit", kwargs={"hash": self.event_hash}))

    def test_unauthenticated_redirects(self):
        client = Client()
        response = client.get(reverse("event_index"), follow=False)
        self.assertEqual(response.status_code, 302)
        self._record_result("auth_redirect", "passed")
