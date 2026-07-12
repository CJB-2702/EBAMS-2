"""CommentAttachmentHandler — attachment operations for comment attachments.

Files attached to a specific Comment (comment_id NOT NULL). These belong to the
immutable comment-revision snapshot, not the thread timeline, so they never
narrate. Owns the three comment-attachment writes:

    attach        — add a new file to a comment
    supersede     — soft-delete a retired revision's link rows
    carry_forward — clone a revision's links onto its successor

Behavior matches the previous inline logic in CommentHandler; only ownership
moved here so every comment-attachment write has one home.
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
from app.events.models import Attachment

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser
    from django.core.files.uploadedfile import UploadedFile

    from app.events.models import Comment


class CommentAttachmentHandler:
    """Attach / supersede / carry-forward for comment attachments."""

    def __init__(self, actor: "AbstractUser") -> None:
        self.actor = actor

    def attach(
        self, *, comment: "Comment", uploaded_file: "UploadedFile | None", caption: str = ""
    ) -> AttachmentResult:
        with transaction.atomic():
            file_result = FileHandler(self.actor).create_file(uploaded_file)
            if not file_result.ok or file_result.file is None:
                transaction.set_rollback(True)
                return AttachmentResult(ok=False, errors=file_result.errors)

            attachment = AttachmentLinkFactory.create(
                thread=comment.activity_thread,
                file=file_result.file,
                actor=self.actor,
                comment=comment,
                caption=caption,
            )

        return AttachmentResult(
            ok=True, attachment=attachment, file=file_result.file
        )

    def supersede(self, *, comment: "Comment") -> None:
        """Soft-delete a comment revision's active link rows (revision retire)."""
        now = timezone.now()
        Attachment.objects.filter(comment=comment, deleted_at__isnull=True).update(
            deleted_at=now, updated_by=self.actor, updated_at=now
        )

    def carry_forward(
        self,
        *,
        from_comment: "Comment",
        to_comment: "Comment",
        exclude_ids: "list[str] | None" = None,
    ) -> None:
        """Clone every link row from one revision onto its successor — same File
        blobs, same display_order/caption. Queries all rows (including the
        just-superseded ones) so the new revision mirrors the old snapshot.
        `exclude_ids` (Attachment pks, as strings) are dropped instead of carried
        forward — how an edit removes an attachment."""
        exclude = {str(x) for x in (exclude_ids or [])}
        for att in Attachment.objects.filter(comment=from_comment):
            if str(att.pk) in exclude:
                continue
            Attachment.objects.create(
                thread_id=to_comment.activity_thread_id,
                comment=to_comment,
                file=att.file,
                attachment_type=att.attachment_type,
                caption=att.caption,
                display_order=att.display_order,
                created_by=self.actor,
                updated_by=self.actor,
            )
