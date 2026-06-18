"""
Tests for the three activity-surface classes (Event, ActivityThread, FileSet).

Locks the core contract from docs/Activity_Surfaces.md:
  - The chosen class dictates behavior; callers never pass capability flags.
  - Capability flags are forced on save() regardless of what is passed.
  - The three thread_type families are disjoint across the proxy managers.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from app.administration.models.data_ownership.domains import Domain
from app.events.models import ActivityThread, ActivityThreadType, Event, FileSet

User = get_user_model()


class SurfaceClassBehaviorTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="surface_actor",
            email="surface@test.local",
            password="TestPass123!",
        )
        cls.domain = Domain.objects.create(
            name="Surface Domain",
            slug="surface-domain",
            created_by=cls.user,
            updated_by=cls.user,
        )

    def _kwargs(self, **extra):
        return dict(
            domain=self.domain,
            created_by=self.user,
            updated_by=self.user,
            **extra,
        )

    # ------------------------------------------------------------------
    # Class choice drives behavior — no flags passed
    # ------------------------------------------------------------------

    def test_event_forces_event_behavior(self):
        ev = Event.objects.create(title="An event", **self._kwargs())
        self.assertEqual(ev.thread_type, ActivityThreadType.EVENT)
        self.assertTrue(ev.allow_comments)
        self.assertTrue(ev.allow_direct_attachments)

    def test_activity_thread_forces_comments_on(self):
        at = ActivityThread.objects.create(**self._kwargs())
        self.assertEqual(at.thread_type, ActivityThreadType.DOCUMENTATION)
        self.assertTrue(at.allow_comments)
        self.assertTrue(at.allow_direct_attachments)

    def test_file_set_forces_comments_off(self):
        fs = FileSet.objects.create(**self._kwargs())
        self.assertEqual(fs.thread_type, ActivityThreadType.PHOTO_GALLERY)
        self.assertFalse(fs.allow_comments)
        self.assertTrue(fs.allow_direct_attachments)

    def test_flags_passed_by_caller_are_overridden(self):
        # Even if a caller tries to pass flags, the class wins.
        fs = FileSet.objects.create(allow_comments=True, **self._kwargs())
        fs.refresh_from_db()
        self.assertFalse(fs.allow_comments)

    # ------------------------------------------------------------------
    # Family managers are disjoint
    # ------------------------------------------------------------------

    def test_managers_do_not_leak_across_families(self):
        ev = Event.objects.create(title="E", **self._kwargs())
        at = ActivityThread.objects.create(**self._kwargs())
        fs = FileSet.objects.create(**self._kwargs())

        self.assertFalse(FileSet.objects.filter(pk=at.pk).exists())
        self.assertFalse(FileSet.objects.filter(pk=ev.pk).exists())
        self.assertFalse(ActivityThread.objects.filter(pk=fs.pk).exists())
        self.assertFalse(ActivityThread.objects.filter(pk=ev.pk).exists())
        self.assertFalse(Event.objects.filter(pk=at.pk).exists())
        self.assertFalse(Event.objects.filter(pk=fs.pk).exists())

        self.assertTrue(FileSet.objects.filter(pk=fs.pk).exists())
        self.assertTrue(ActivityThread.objects.filter(pk=at.pk).exists())
        self.assertTrue(Event.objects.filter(pk=ev.pk).exists())
