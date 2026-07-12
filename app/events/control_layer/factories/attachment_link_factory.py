"""AttachmentLinkFactory — stateless creation of one Attachment link row.

Creates the child row that joins a File to a thread (optionally via a Comment)
and owns the two fields every attachment needs regardless of kind: per-thread
``display_order`` and inferred ``attachment_type``. Both attachment handlers
(DirectAttachmentHandler and CommentAttachmentHandler) *compose* this factory
rather than inheriting a shared base — the link-creation logic lives in exactly
one place (composition over inheritance).

Suffix note: this creates a *child* row (an Attachment always has a parent
thread), a minor stretch of the Factory suffix, chosen because the class is
stateless, uses classmethods, and returns a model instance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from app.events.models import Attachment, AttachmentType, File
from app.events.models.file import ALLOWED_EXTENSIONS

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from app.events.models import Comment, Event


@dataclass
class AttachmentResult:
    """Return type for the attachment handlers. Carries the Attachment directly
    so callers never re-query for the row they just created."""

    ok: bool
    attachment: Attachment | None = None
    file: File | None = None
    errors: list[str] = field(default_factory=list)


def infer_attachment_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext in ALLOWED_EXTENSIONS.get("images", set()):
        return AttachmentType.IMAGE
    return AttachmentType.DOCUMENT


class AttachmentLinkFactory:
    @classmethod
    def create(
        cls,
        *,
        thread: "Event",
        file: File,
        actor: "AbstractUser",
        comment: "Comment | None" = None,
        caption: str = "",
    ) -> Attachment:
        # display_order is per-thread across both standalone and comment
        # attachments — the count of the thread's active links at insert time.
        existing_count = Attachment.objects.filter(
            thread=thread, deleted_at__isnull=True
        ).count()
        return Attachment.objects.create(
            thread=thread,
            comment=comment,
            file=file,
            attachment_type=infer_attachment_type(file.original_filename),
            caption=caption,
            display_order=existing_count,
            created_by=actor,
            updated_by=actor,
        )
