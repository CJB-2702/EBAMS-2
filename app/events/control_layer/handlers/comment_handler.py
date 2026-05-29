"""CommentHandler — add and edit comments, with attachment carry-forward on edit."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

from app.events.models import Attachment, Comment

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


@dataclass
class CommentResult:
    ok: bool
    comment: Comment | None = None
    errors: list[str] = field(default_factory=list)


class CommentHandler:
    """Handles create and edit operations on Comment rows."""

    def __init__(self, actor: "AbstractUser") -> None:
        self.actor = actor

    def add(self, activity_thread, post_data, files=None) -> CommentResult:
        content = post_data.get("content", "").strip()
        if not content:
            return CommentResult(ok=False, errors=["Comment content is required."])

        uploaded_files = [f for f in (files.getlist("files") if files else []) if getattr(f, "name", None)]

        with transaction.atomic():
            comment = Comment.objects.create(
                activity_thread=activity_thread,
                content=content,
                is_human_made=True,
                revision=1,
                created_by=self.actor,
                updated_by=self.actor,
            )

            if uploaded_files:
                from app.events.control_layer.handlers.file_handler import FileHandler
                handler = FileHandler(self.actor)
                for uploaded_file in uploaded_files:
                    result = handler.upload(activity_thread, uploaded_file, comment=comment)
                    if not result.ok:
                        transaction.set_rollback(True)
                        return CommentResult(ok=False, errors=result.errors)

        return CommentResult(ok=True, comment=comment)

    def edit(self, old_comment: Comment, post_data, files=None) -> CommentResult:
        """
        Editing a comment:
          1. Soft-delete the old revision's active Attachment rows.
          2. Soft-delete the old comment.
          3. Create a new comment (new revision) with new Attachment rows
             pointing to the same File rows.
        """
        content = post_data.get("content", "").strip()
        if not content:
            return CommentResult(ok=False, errors=["Comment content cannot be blank."])

        with transaction.atomic():
            now = timezone.now()

            # Soft-delete old revision's active attachment rows first.
            Attachment.objects.filter(
                comment=old_comment, deleted_at__isnull=True
            ).update(deleted_at=now, updated_by=self.actor, updated_at=now)

            old_comment.deleted_at = now
            old_comment.updated_by = self.actor
            old_comment.save(update_fields=["deleted_at", "updated_by", "updated_at"])

            new_comment = Comment.objects.create(
                activity_thread=old_comment.activity_thread,
                content=content,
                is_human_made=True,
                origin_id=old_comment,
                revision=old_comment.revision + 1,
                created_by=self.actor,
                updated_by=self.actor,
            )

            self._carry_forward_attachments(old_comment, new_comment)

            uploaded_files = [f for f in (files.getlist("files") if files else []) if getattr(f, "name", None)]
            if uploaded_files:
                from app.events.control_layer.handlers.file_handler import FileHandler
                handler = FileHandler(self.actor)
                for uploaded_file in uploaded_files:
                    file_result = handler.upload(
                        new_comment.activity_thread, uploaded_file, comment=new_comment
                    )
                    if not file_result.ok:
                        transaction.set_rollback(True)
                        return CommentResult(ok=False, errors=file_result.errors)

        return CommentResult(ok=True, comment=new_comment)

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    def _carry_forward_attachments(
        self, old_comment: Comment, new_comment: Comment
    ) -> None:
        """
        Duplicate attachment rows from old revision onto the new one.
        Queries all attachment rows for old_comment (including just-soft-deleted ones)
        so the same files appear on the new revision.
        """
        old_attachments = Attachment.objects.filter(comment=old_comment)
        for att in old_attachments:
            Attachment.objects.create(
                thread_id=new_comment.activity_thread_id,
                comment=new_comment,
                file=att.file,
                attachment_type=att.attachment_type,
                caption=att.caption,
                display_order=att.display_order,
                created_by=self.actor,
                updated_by=self.actor,
            )
