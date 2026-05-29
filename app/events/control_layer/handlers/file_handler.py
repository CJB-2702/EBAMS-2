"""FileHandler — upload, attach, and soft-delete File rows."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

from app.events.models import Attachment, AttachmentType, Comment, Event, File
from app.events.models.file import ALLOWED_EXTENSIONS, MAX_FILE_SIZE_BYTES

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser
    from django.core.files.uploadedfile import UploadedFile


@dataclass
class FileResult:
    ok: bool
    file: File | None = None
    errors: list[str] = field(default_factory=list)


class FileHandler:
    """Handles file upload, attachment linking, and soft-delete."""

    def __init__(self, actor: "AbstractUser") -> None:
        self.actor = actor

    def upload(
        self,
        thread: Event,
        uploaded_file: "UploadedFile | None",
        comment: Comment | None = None,
    ) -> FileResult:
        if not uploaded_file or not getattr(uploaded_file, "name", None):
            return FileResult(ok=False, errors=["No file provided."])

        if comment is not None and comment.activity_thread_id != thread.pk:
            raise ValueError("Comment does not belong to this thread.")

        errors = self._validate(uploaded_file)
        if errors:
            return FileResult(ok=False, errors=errors)

        with transaction.atomic():
            file = File.objects.create(
                file=uploaded_file,
                original_filename=uploaded_file.name,
                file_size=uploaded_file.size,
                mime_type=uploaded_file.content_type or "",
                created_by=self.actor,
                updated_by=self.actor,
            )
            attachment_type = self._infer_attachment_type(uploaded_file.name)
            existing_count = Attachment.objects.filter(
                thread=thread, deleted_at__isnull=True
            ).count()
            Attachment.objects.create(
                thread=thread,
                comment=comment,
                file=file,
                attachment_type=attachment_type,
                display_order=existing_count,
                created_by=self.actor,
                updated_by=self.actor,
            )

        return FileResult(ok=True, file=file)

    def soft_delete(self, file: File) -> FileResult:
        """
        Soft-delete a file and bulk soft-delete all its attachment rows.
        Unconditional — the caller has already established intent.
        """
        with transaction.atomic():
            now = timezone.now()
            Attachment.objects.filter(file=file).update(
                deleted_at=now,
                updated_by=self.actor,
                updated_at=now,
            )
            file._soft_delete(actor=self.actor)

        return FileResult(ok=True, file=file)

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    def _validate(self, uploaded_file: "UploadedFile") -> list[str]:
        errors: list[str] = []
        name = getattr(uploaded_file, "name", None) or ""
        if not name:
            return ["File has no name."]
        if uploaded_file.size > MAX_FILE_SIZE_BYTES:
            errors.append("File exceeds maximum size of 100 MB.")
        if not File.is_allowed_extension(name):
            ext = Path(name).suffix.lower()
            errors.append(f"File type '{ext}' is not allowed.")
        return errors

    def _infer_attachment_type(self, filename: str) -> str:
        ext = Path(filename).suffix.lower()
        if ext in ALLOWED_EXTENSIONS.get("images", set()):
            return AttachmentType.IMAGE
        return AttachmentType.DOCUMENT
