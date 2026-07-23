"""CommentHandler — add and edit comments, with attachment carry-forward on edit."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

from app.events.models import Comment

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

    def add(self, activity_thread, post_data, files=None, *, is_human_made: bool = True) -> CommentResult:
        content = post_data.get("content", "").strip()
        if not content:
            return CommentResult(ok=False, errors=["Comment content is required."])

        uploaded_files = [f for f in (files.getlist("files") if files else []) if getattr(f, "name", None)]

        with transaction.atomic():
            comment = Comment.objects.create(
                activity_thread=activity_thread,
                content=content,
                is_human_made=is_human_made,
                revision=1,
                created_by=self.actor,
                updated_by=self.actor,
            )

            if uploaded_files:
                from app.events.control_layer.handlers.comment_attachment_handler import (
                    CommentAttachmentHandler,
                )
                handler = CommentAttachmentHandler(self.actor)
                for uploaded_file in uploaded_files:
                    result = handler.attach(comment=comment, uploaded_file=uploaded_file)
                    if not result.ok:
                        transaction.set_rollback(True)
                        return CommentResult(ok=False, errors=result.errors)

        return CommentResult(ok=True, comment=comment)

    def edit(
        self, old_comment: Comment, post_data, files=None, remove_attachment_ids=None
    ) -> CommentResult:
        """
        Editing a comment:
          1. Soft-delete the old revision's active Attachment rows.
          2. Soft-delete the old comment.
          3. Create a new comment (new revision) with new Attachment rows
             pointing to the same File rows, minus any `remove_attachment_ids`.
        """
        content = post_data.get("content", "").strip()
        if not content:
            return CommentResult(ok=False, errors=["Comment content cannot be blank."])

        from app.events.control_layer.handlers.comment_attachment_handler import (
            CommentAttachmentHandler,
        )
        attachment_handler = CommentAttachmentHandler(self.actor)

        with transaction.atomic():
            now = timezone.now()

            # Retire the old revision's link rows, then soft-delete the revision.
            attachment_handler.supersede(comment=old_comment)

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

            attachment_handler.carry_forward(
                from_comment=old_comment,
                to_comment=new_comment,
                exclude_ids=remove_attachment_ids,
            )

            uploaded_files = [f for f in (files.getlist("files") if files else []) if getattr(f, "name", None)]
            for uploaded_file in uploaded_files:
                file_result = attachment_handler.attach(
                    comment=new_comment, uploaded_file=uploaded_file
                )
                if not file_result.ok:
                    transaction.set_rollback(True)
                    return CommentResult(ok=False, errors=file_result.errors)

        return CommentResult(ok=True, comment=new_comment)
