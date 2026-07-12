"""DirectAttachmentHandler — standalone (thread-level) attachment operations.

The API everyone calls for files attached directly to a thread (comment_id is
NULL): attach a new file, detach one link, or delete a whole file with all its
links. Owns display_order/type via AttachmentLinkFactory, the blob via
FileHandler, and file-change narration onto the thread timeline for threads that
opt in (ThreadPolicy.narrates_file_changes).

Narration fires only for standalone links (comment_id is None); comment
attachments belong to CommentAttachmentHandler and never narrate.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

from app.events.control_layer.factories.attachment_link_factory import (
    AttachmentLinkFactory,
    AttachmentResult,
)
from app.events.control_layer.handlers.file_handler import FileHandler
from app.events.control_layer.narrators.file_narrator import FileNarrator
from app.events.control_layer.policies.thread_policy import ThreadPolicy
from app.events.models import Attachment, Comment

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser
    from django.core.files.uploadedfile import UploadedFile

    from app.events.models import Event, File


class DirectAttachmentHandler:
    """Attach / detach / delete-file for standalone thread attachments."""

    def __init__(self, actor: "AbstractUser") -> None:
        self.actor = actor

    def attach(
        self, *, thread: "Event", uploaded_file: "UploadedFile | None", caption: str = ""
    ) -> AttachmentResult:
        with transaction.atomic():
            file_result = FileHandler(self.actor).create_file(uploaded_file)
            if not file_result.ok or file_result.file is None:
                transaction.set_rollback(True)
                return AttachmentResult(ok=False, errors=file_result.errors)

            attachment = AttachmentLinkFactory.create(
                thread=thread,
                file=file_result.file,
                actor=self.actor,
                caption=caption,
            )
            self._narrate(thread, FileNarrator.attached(file_result.file))

        return AttachmentResult(
            ok=True, attachment=attachment, file=file_result.file
        )

    def detach(self, *, attachment: Attachment) -> AttachmentResult:
        """Soft-delete one link. The File blob is left intact (it may be linked
        elsewhere). Narrates only when the link is standalone."""
        with transaction.atomic():
            attachment._soft_delete(actor=self.actor)
            if attachment.comment_id is None:
                self._narrate(attachment.thread, FileNarrator.removed(attachment.file))
        return AttachmentResult(
            ok=True, attachment=attachment, file=attachment.file
        )

    def delete_file(self, *, file: "File") -> AttachmentResult:
        """Soft-delete the blob and every link that points at it. Narrates once
        per standalone link (each on its own thread)."""
        with transaction.atomic():
            # Capture standalone links before the bulk update clears the active
            # set — comment links are skipped (they never narrate).
            standalone_links = list(
                Attachment.objects.filter(
                    file=file, deleted_at__isnull=True, comment__isnull=True
                ).select_related("thread")
            )
            now = timezone.now()
            Attachment.objects.filter(file=file, deleted_at__isnull=True).update(
                deleted_at=now, updated_by=self.actor, updated_at=now
            )
            FileHandler(self.actor).soft_delete_file(file)

            message = FileNarrator.removed(file)
            for link in standalone_links:
                self._narrate(link.thread, message)

        return AttachmentResult(ok=True, file=file)

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    def _narrate(self, thread: "Event", message: str) -> None:
        if not ThreadPolicy(thread).narrates_file_changes():
            return
        Comment.objects.create(
            activity_thread=thread,
            content=message,
            is_human_made=False,
            revision=1,
            created_by=self.actor,
            updated_by=self.actor,
        )
