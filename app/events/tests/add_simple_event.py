"""
Integration tests for the core Events write path after the ActivityThread refactor.

Covers:
  - EventHandler.create  → Event row created with correct thread_type
  - CommentHandler.add   → Comment linked via activity_thread FK
  - DirectAttachmentHandler.attach  → File + standalone Attachment on the thread
  - CommentAttachmentHandler.attach → File + Attachment linked to a comment
"""

from __future__ import annotations

import io

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.test import TestCase

from app.administration.models.data_ownership.domains import Domain
from app.events.control_layer.handlers.comment_attachment_handler import (
    CommentAttachmentHandler,
)
from app.events.control_layer.handlers.comment_handler import CommentHandler
from app.events.control_layer.handlers.direct_attachment_handler import (
    DirectAttachmentHandler,
)
from app.events.control_layer.handlers.event_handler import EventHandler
from app.events.models import ActivityThreadType, Attachment, Comment, Event, EventStatus, EventType

User = get_user_model()


def _make_text_file(name: str = "test.txt", content: str = "hello") -> InMemoryUploadedFile:
    buf = io.BytesIO(content.encode())
    return InMemoryUploadedFile(
        file=buf,
        field_name="file",
        name=name,
        content_type="text/plain",
        size=len(content),
        charset="utf-8",
    )


class AddSimpleEventTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="test_actor",
            email="actor@test.local",
            password="TestPass123!",
        )
        cls.domain = Domain.objects.create(
            name="Test Domain",
            slug="test-domain-simple",
            created_by=cls.user,
            updated_by=cls.user,
        )

    # ------------------------------------------------------------------
    # Event creation
    # ------------------------------------------------------------------

    def test_create_event_returns_ok(self):
        result = EventHandler(self.user).create({
            "title": "Dummy Event",
            "domain_id": self.domain.pk,
            "event_type": EventType.GENERIC,
            "status": EventStatus.PLANNED,
            "description": "Created by the integration test.",
        })
        self.assertTrue(result.ok, result.errors)
        self.assertIsNotNone(result.event)

    def test_created_event_has_correct_thread_type(self):
        result = EventHandler(self.user).create({
            "title": "Thread Type Check",
            "domain_id": self.domain.pk,
        })
        self.assertTrue(result.ok)
        self.assertEqual(result.event.thread_type, ActivityThreadType.EVENT)

    def test_create_event_missing_title_fails(self):
        result = EventHandler(self.user).create({
            "title": "",
            "domain_id": self.domain.pk,
        })
        self.assertFalse(result.ok)
        self.assertTrue(any("Title" in e for e in result.errors))

    def test_create_event_missing_domain_fails(self):
        result = EventHandler(self.user).create({"title": "No Domain"})
        self.assertFalse(result.ok)
        self.assertTrue(any("Domain" in e for e in result.errors))

    def test_created_event_visible_via_objects_manager(self):
        result = EventHandler(self.user).create({
            "title": "Manager Visibility",
            "domain_id": self.domain.pk,
        })
        self.assertTrue(result.ok)
        self.assertTrue(Event.objects.filter(pk=result.event.pk).exists())

    # ------------------------------------------------------------------
    # Comment creation
    # ------------------------------------------------------------------

    def _make_event(self, title: str = "Base Event") -> Event:
        r = EventHandler(self.user).create({"title": title, "domain_id": self.domain.pk})
        self.assertTrue(r.ok)
        return r.event

    def test_add_comment_returns_ok(self):
        event = self._make_event()
        result = CommentHandler(self.user).add(event, {"content": "First comment."})
        self.assertTrue(result.ok, result.errors)
        self.assertIsNotNone(result.comment)

    def test_comment_linked_to_event_via_activity_thread(self):
        event = self._make_event()
        result = CommentHandler(self.user).add(event, {"content": "Linked comment."})
        self.assertTrue(result.ok)
        self.assertEqual(result.comment.activity_thread_id, event.pk)

    def test_comment_is_human_made(self):
        event = self._make_event()
        result = CommentHandler(self.user).add(event, {"content": "Human comment."})
        self.assertTrue(result.ok)
        self.assertTrue(result.comment.is_human_made)

    def test_add_comment_empty_content_fails(self):
        event = self._make_event()
        result = CommentHandler(self.user).add(event, {"content": "  "})
        self.assertFalse(result.ok)
        self.assertTrue(any("content" in e.lower() for e in result.errors))

    def test_comments_visible_on_event(self):
        event = self._make_event()
        CommentHandler(self.user).add(event, {"content": "Visible comment."})
        count = Comment.objects.active().filter(activity_thread=event).count()
        self.assertEqual(count, 1)

    # ------------------------------------------------------------------
    # Attachment / file upload
    # ------------------------------------------------------------------

    def test_upload_file_returns_ok(self):
        event = self._make_event()
        uploaded = _make_text_file("report.txt", "some content")
        result = DirectAttachmentHandler(self.user).attach(thread=event, uploaded_file=uploaded)
        self.assertTrue(result.ok, result.errors)
        self.assertIsNotNone(result.file)

    def test_upload_creates_attachment_linked_to_thread(self):
        event = self._make_event()
        uploaded = _make_text_file("data.csv", "a,b,c")
        result = DirectAttachmentHandler(self.user).attach(thread=event, uploaded_file=uploaded)
        self.assertTrue(result.ok)
        attachment = Attachment.objects.filter(thread=event, file=result.file).first()
        self.assertIsNotNone(attachment)
        self.assertIsNone(attachment.comment)

    def test_upload_comment_attachment_links_comment(self):
        event = self._make_event()
        comment_result = CommentHandler(self.user).add(event, {"content": "With file."})
        self.assertTrue(comment_result.ok)
        comment = comment_result.comment

        uploaded = _make_text_file("note.txt", "attached note")
        result = CommentAttachmentHandler(self.user).attach(comment=comment, uploaded_file=uploaded)
        self.assertTrue(result.ok)

        attachment = Attachment.objects.filter(file=result.file).first()
        self.assertIsNotNone(attachment)
        self.assertEqual(attachment.comment_id, comment.pk)
        self.assertEqual(attachment.thread_id, event.pk)

    def test_upload_disallowed_extension_fails(self):
        event = self._make_event()
        uploaded = _make_text_file("malware.exe", "bad")
        result = DirectAttachmentHandler(self.user).attach(thread=event, uploaded_file=uploaded)
        self.assertFalse(result.ok)
        self.assertTrue(any("not allowed" in e for e in result.errors))

    def test_upload_no_file_fails(self):
        event = self._make_event()
        result = DirectAttachmentHandler(self.user).attach(thread=event, uploaded_file=None)
        self.assertFalse(result.ok)
