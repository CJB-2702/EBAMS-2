"""PartThreadManager — the one comments/documents helper for every threaded
parts entity (Part, PartRevision, SupplierItem — D5). Lazily creates the
events.ActivityThread on first write.

Event/ActivityThread rows require a domain_id (the shared `event` table's
domain FK is NOT NULL) even though parts entities carry no single ownership
domain of their own (D14 deliberately replaces that with is_domain_limited +
PartDomainAccessMapping). So the caller supplies domain_id only at the moment
a thread is first created; reads and later writes never need it again. When no
domain is supplied the bootstrap value comes from thread_domain (§1).

Base-app reuse (§3): file attach/detach delegate to
events.DirectAttachmentHandler, and every write is gated by events.ThreadPolicy
so parts respect the thread capability contract rather than assuming it. Comment-row creation is intentionally NOT
delegated to events.CommentHandler: CommentHandler.add hardcodes
is_human_made=True and requires an already-existing thread, so it cannot post
the machine comments (is_human_made=False) the Part audit feed depends on (§5),
nor honor the nullable-thread bootstrap-domain concern, which must stay
parts-specific and out of events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.events.control_layer.handlers.direct_attachment_handler import (
    DirectAttachmentHandler,
)
from app.events.control_layer.policies.thread_policy import ThreadPolicy
from app.events.models import ActivityThread, Attachment, Comment
from app.parts.control_layer.thread_domain import default_domain_id_for

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser
    from django.core.files.uploadedfile import UploadedFile


class ThreadWriteNotAllowed(Exception):
    """The target thread's capability contract forbids this write (§3)."""


class PartThreadManager:
    """owner = any model instance carrying a nullable OneToOneField to
    ``events.ActivityThread``. The field name defaults to ``thread`` (PartRevision,
    SupplierItem) but an owner may expose several — a Part carries both
    ``documents_thread`` and ``gallery_thread`` — so ``thread_attr`` names which
    one this manager instance operates on."""

    def __init__(
        self, owner, actor: "AbstractUser | None" = None, *, thread_attr: str = "thread"
    ) -> None:
        self.owner = owner
        self.actor = actor
        self.thread_attr = thread_attr

    @property
    def _thread(self) -> ActivityThread | None:
        return getattr(self.owner, self.thread_attr)

    @property
    def _thread_id(self):
        return getattr(self.owner, f"{self.thread_attr}_id")

    def _ensure_thread(self, *, domain_id: int | None = None) -> ActivityThread:
        if self._thread_id is not None:
            return self._thread
        # No domain supplied (e.g. a machine comment written from a manager that
        # carries no request domain) → bootstrap with the variant default (§1).
        # Parts always create ActivityThread rows, so the default resolves to the
        # "Activity Thread" domain; the value is incidental, never access control.
        if domain_id is None:
            domain_id = default_domain_id_for(ActivityThread)
        with transaction.atomic():
            thread = ActivityThread.objects.create(
                domain_id=domain_id,
                created_by=self.actor,
                updated_by=self.actor,
            )
            setattr(self.owner, self.thread_attr, thread)
            self.owner.save(update_fields=[self.thread_attr])
        return thread

    def attach_document(
        self, uploaded_file: "UploadedFile", *, domain_id: int | None = None, caption: str = ""
    ):
        thread = self._ensure_thread(domain_id=domain_id)
        if not ThreadPolicy(thread).can_attach_directly():
            raise ThreadWriteNotAllowed("This thread does not accept direct attachments.")
        return DirectAttachmentHandler(self.actor).attach(
            thread=thread, uploaded_file=uploaded_file, caption=caption
        )

    def add_comment(self, body: str, *, domain_id: int | None = None, is_human_made: bool = True) -> Comment:
        thread = self._ensure_thread(domain_id=domain_id)
        if not ThreadPolicy(thread).can_add_comment():
            raise ThreadWriteNotAllowed("This thread does not accept comments.")
        return Comment.objects.create(
            activity_thread=thread,
            content=body,
            is_human_made=is_human_made,
            created_by=self.actor,
            updated_by=self.actor,
        )

    def detach_document(self, attachment_id) -> bool:
        """Soft-delete one attachment from this owner's thread. The underlying
        File row is left intact (it may be linked elsewhere); only the link to
        this thread is removed. Returns False if the attachment is not on this
        thread (already gone / wrong owner)."""
        if self._thread_id is None:
            return False
        try:
            attachment = self._thread.attachments.active().get(id=attachment_id)
        except Attachment.DoesNotExist:
            return False
        DirectAttachmentHandler(self.actor).detach(attachment=attachment)
        return True

    def documents(self) -> list[dict]:
        if self._thread_id is None:
            return []
        attachments = self._thread.attachments.active().select_related(
            "file", "created_by"
        )
        return [
            {
                "id": str(a.id),
                "file_id": str(a.file_id),
                "filename": a.file.original_filename,
                "caption": a.caption,
                "icon": a.file.get_icon_class(),
                "is_image": a.file.is_image(),
                "file_size": a.file.file_size,
                "attachment_type": a.attachment_type,
                # created_at: precise ISO-8601 for client-side sorting, plus a
                # human string for the no-JS fallback rendering.
                "created_at": a.created_at.isoformat(),
                "created_at_display": a.created_at.strftime("%b %d, %Y"),
                "created_by": str(a.created_by) if a.created_by_id else "—",
            }
            for a in attachments
        ]

    def comments(self) -> list[dict]:
        if self._thread_id is None:
            return []
        # active(), not visible(): visible() is human-only, which would hide the
        # machine comments (is_human_made=False) that form the Part audit feed
        # (§5). active() keeps visible machine comments and still drops the
        # soft-deleted shadow/diff rows.
        comments = self._thread.comments.active().select_related("created_by")
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
