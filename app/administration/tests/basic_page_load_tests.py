import logging
from pathlib import Path
from django.contrib.auth import get_user_model
User = get_user_model()
from django.test import TestCase, Client
from django.urls import reverse

logger = logging.getLogger(__name__)


class AdminPageLoadTests(TestCase):
    """Test that admin pages load without errors when logged in as superuser."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = Client()
        # Password must be 12+ chars per OWASP policy
        cls.test_password = "TestPass123!@"
        cls.superuser = User.objects.create_superuser(
            username="admin",
            email="admin@test.local",
            password=cls.test_password,
        )
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
        log_dir = Path("app/administration/tests/logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "page_load_test_summary.txt"

        total = len(cls.test_results["passed"]) + len(cls.test_results["failed"]) + len(cls.test_results["errors"])
        passed = len(cls.test_results["passed"])
        failed = len(cls.test_results["failed"])
        errors = len(cls.test_results["errors"])
        summary = f"""
================================================================================
ADMIN PAGE LOAD TEST SUMMARY
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

    def test_administration_index(self):
        self._check("administration_index", reverse("administration_index"))

    def test_user_index(self):
        self._check("user_index", reverse("user_index"))

    def test_organization_index(self):
        self._check("organization_index", reverse("organization_index"))

    def test_division_index(self):
        self._check("division_index", reverse("division_index"))

    def test_permission_index(self):
        self._check("permission_index", reverse("permission_index"))

    def test_permission_group_index(self):
        self._check("permission_group_index", reverse("permission_group_index"))

    def test_role_index(self):
        self._check("role_index", reverse("role_index"))

    def test_domain_index(self):
        self._check("domain_index", reverse("domain_index"))

    def test_domain_template_index(self):
        self._check("domain_template_index", reverse("domain_template_index"))

    def test_domain_organizations_portal(self):
        self._check("domain_organizations_portal", reverse("domain_organizations_portal"))

    def test_create_pages(self):
        self._check("organization_create", reverse("organization_create"))
        self._check("division_create", reverse("division_create"))
        self._check("domain_create", reverse("domain_create"))
        self._check("domain_template_create", reverse("domain_template_create"))
        self._check("permission_group_create", reverse("permission_group_create"))
        self._check("role_create", reverse("role_create"))

    def test_login_page(self):
        client = Client()
        response = client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self._record_result("login", "passed")

    def test_unauthenticated_redirects(self):
        client = Client()
        response = client.get(reverse("administration_index"), follow=False)
        self.assertEqual(response.status_code, 302)
        self._record_result("auth_redirect", "passed")
