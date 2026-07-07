"""PartThreadManager — the one comments/documents helper for every threaded
parts entity (Part, PartRevision, SupplierItem — D5). Lazily creates the
events.ActivityThread on first write, then delegates to the events handlers.

Event/ActivityThread rows require a domain_id (the shared `event` table's
domain FK is NOT NULL) even though parts entities carry no single ownership
domain of their own (D14 deliberately replaces that with is_domain_limited +
PartDomainAccessMapping). So the caller supplies domain_id only at the moment
a thread is first created; reads and later writes never need it again.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.events.control_layer.handlers.file_handler import FileHandler
from app.events.models import ActivityThread, Comment

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser
    from django.core.files.uploadedfile import UploadedFile


class PartThreadManager:
    """owner = any model instance carrying a nullable `thread` OneToOneField."""

    def __init__(self, owner, actor: "AbstractUser | None" = None) -> None:
        self.owner = owner
        self.actor = actor

    def _ensure_thread(self, *, domain_id: int) -> ActivityThread:
        if self.owner.thread_id is not None:
            return self.owner.thread
        with transaction.atomic():
            thread = ActivityThread.objects.create(
                domain_id=domain_id,
                created_by=self.actor,
                updated_by=self.actor,
            )
            self.owner.thread = thread
            self.owner.save(update_fields=["thread"])
        return thread

    def attach_document(
        self, uploaded_file: "UploadedFile", *, domain_id: int, caption: str = ""
    ):
        thread = self._ensure_thread(domain_id=domain_id)
        result = FileHandler(self.actor).upload(thread, uploaded_file)
        if result.ok and result.file is not None:
            attachment = result.file.attachment_links.filter(thread=thread).latest(
                "created_at"
            )
            if caption:
                attachment.caption = caption
                attachment.save(update_fields=["caption"])
        return result

    def add_comment(self, body: str, *, domain_id: int, is_human_made: bool = True) -> Comment:
        thread = self._ensure_thread(domain_id=domain_id)
        return Comment.objects.create(
            activity_thread=thread,
            content=body,
            is_human_made=is_human_made,
            created_by=self.actor,
            updated_by=self.actor,
        )

    def documents(self) -> list[dict]:
        if self.owner.thread_id is None:
            return []
        attachments = self.owner.thread.attachments.active().select_related("file")
        return [
            {
                "id": str(a.id),
                "file_id": str(a.file_id),
                "filename": a.file.original_filename,
                "caption": a.caption,
                "icon": a.file.get_icon_class(),
                "is_image": a.file.is_image(),
                "file_size": a.file.file_size,
            }
            for a in attachments
        ]

    def comments(self) -> list[dict]:
        if self.owner.thread_id is None:
            return []
        comments = self.owner.thread.comments.visible().select_related("created_by")
        return [
            {
                "id": c.id,
                "author": str(c.created_by) if c.created_by_id else "system",
                "body": c.content,
                "created_at": c.created_at,
                "is_human_made": c.is_human_made,
            }
            for c in comments
        ]
