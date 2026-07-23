"""ActivityThreadManager — the one comments/documents helper for any owner that
carries a nullable OneToOneField to ``events.ActivityThread``. Lazily creates
the thread on first write.

Mirrors ``GalleryManager`` (same file): every sub-app that carries a
comments+documents thread — Part, PartRevision, SupplierItem, AssetModel —
repeated the same mechanics (lazy thread creation with a bootstrap domain,
list/add comments, list/attach/detach documents). This class owns that once;
all comment and attachment writes delegate to the base events classes
(``CommentHandler``, ``DirectAttachmentHandler``, ``ThreadPolicy``) — this
class never reimplements Comment/Attachment creation itself. Sub-apps must not
hand-roll their own thread manager; configure this one via constructor kwargs.

Owner contract: any model instance with a thread FK (``thread_attr``, default
``thread``) that may be null until the first write.

Configuration (constructor kwargs, all optional):
  thread_attr         FK name for the activity thread. Owners with more than
                       one thread (e.g. a Part's ``documents_thread`` and
                       ``gallery_thread``) get one manager instance per attr.
  domain_id_resolver   zero-arg callable returning the bootstrap domain id for
                       lazy creation (see ``thread_domain.py`` in each app —
                       the value is incidental, never access control).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.events.control_layer.handlers.direct_attachment_handler import (
    DirectAttachmentHandler,
)
from app.events.control_layer.policies.thread_policy import ThreadPolicy
from app.events.models import ActivityThread, Attachment
from app.events.presentation_layer.tools.generic_cards import comment_dict, document_dict

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser
    from django.core.files.uploadedfile import UploadedFile


class ThreadWriteNotAllowed(Exception):
    """The target thread's capability contract forbids this write."""


class ActivityThreadManager:
    def __init__(
        self,
        owner,
        actor: "AbstractUser | None" = None,
        *,
        thread_attr: str = "thread",
        domain_id_resolver=None,
    ) -> None:
        self.owner = owner
        self.actor = actor
        self.thread_attr = thread_attr
        self._domain_id_resolver = domain_id_resolver

    @property
    def _thread(self) -> ActivityThread | None:
        return getattr(self.owner, self.thread_attr)

    @property
    def _thread_id(self):
        return getattr(self.owner, f"{self.thread_attr}_id")

    def _ensure_thread(self, *, domain_id: int | None = None) -> ActivityThread:
        if self._thread_id is not None:
            return self._thread
        if domain_id is None and self._domain_id_resolver is not None:
            domain_id = self._domain_id_resolver()
        with transaction.atomic():
            thread = ActivityThread.objects.create(
                domain_id=domain_id,
                created_by=self.actor,
                updated_by=self.actor,
            )
            setattr(self.owner, self.thread_attr, thread)
            self.owner.save(update_fields=[self.thread_attr])
        return thread

    # ── Writes ────────────────────────────────────────────────────────────────
    def attach_document(
        self, uploaded_file: "UploadedFile", *, domain_id: int | None = None, caption: str = ""
    ):
        thread = self._ensure_thread(domain_id=domain_id)
        if not ThreadPolicy(thread).can_attach_directly():
            raise ThreadWriteNotAllowed("This thread does not accept direct attachments.")
        return DirectAttachmentHandler(self.actor).attach(
            thread=thread, uploaded_file=uploaded_file, caption=caption
        )

    def add_comment(self, body: str, *, domain_id: int | None = None, is_human_made: bool = True):
        from app.events.control_layer.handlers.comment_handler import CommentHandler

        thread = self._ensure_thread(domain_id=domain_id)
        if not ThreadPolicy(thread).can_add_comment():
            raise ThreadWriteNotAllowed("This thread does not accept comments.")
        return CommentHandler(self.actor).add(
            thread, {"content": body}, is_human_made=is_human_made
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

    # ── Reads ─────────────────────────────────────────────────────────────────
    def documents(self) -> list[dict]:
        if self._thread_id is None:
            return []
        attachments = self._thread.attachments.active().select_related("file", "created_by")
        # attachment_type beyond the base generic-card contract: consumed by the
        # file-browser data-type attribute (parts/assets library templates).
        return [{**document_dict(a), "attachment_type": a.attachment_type} for a in attachments]

    def comments(self) -> list[dict]:
        if self._thread_id is None:
            return []
        # active(), not visible(): visible() is human-only, which would hide
        # machine comments (is_human_made=False) that form audit feeds built on
        # this thread. active() keeps visible machine comments and still drops
        # the soft-deleted shadow/diff rows.
        comments = self._thread.comments.active().select_related("created_by")
        return [comment_dict(c) for c in comments]

    def card(self, user) -> dict:
        """Rich ``events/fragments/comments_card.html``-ready dict for this
        owner's thread: ``{hash, comments, event, direct_attachments}`` — the
        same contract every app renders comments through, never a per-app
        equivalent. Returns a valid empty placeholder (``hash=None``) when the
        thread hasn't been created yet, with no side effects on this read."""
        from app.events.presentation_layer.tools.generic_cards import build_activity_card

        if self._thread_id is None:
            return {"hash": None, "comments": [], "event": {"allow_comments": True}, "direct_attachments": []}
        return build_activity_card(self._thread, user)
