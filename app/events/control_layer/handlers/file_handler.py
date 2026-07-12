"""FileHandler — blob lifecycle for File rows (create and soft-delete).

Scope is deliberately narrow: the physical File blob only. It knows nothing
about threads, Attachment links, display_order, or narration — those belong to
the attachment handlers (DirectAttachmentHandler / CommentAttachmentHandler),
which compose this handler for the blob half of the work.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from app.events.models import File
from app.events.models.file import MAX_FILE_SIZE_BYTES

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser
    from django.core.files.uploadedfile import UploadedFile


@dataclass
class FileResult:
    ok: bool
    file: File | None = None
    errors: list[str] = field(default_factory=list)


class FileHandler:
    """Creates and soft-deletes the File blob. No threads, no Attachment rows."""

    def __init__(self, actor: "AbstractUser") -> None:
        self.actor = actor

    def create_file(self, uploaded_file: "UploadedFile | None") -> FileResult:
        if not uploaded_file or not getattr(uploaded_file, "name", None):
            return FileResult(ok=False, errors=["No file provided."])

        errors = self._validate(uploaded_file)
        if errors:
            return FileResult(ok=False, errors=errors)

        file = File.objects.create(
            file=uploaded_file,
            original_filename=uploaded_file.name,
            file_size=uploaded_file.size,
            mime_type=uploaded_file.content_type or "",
            created_by=self.actor,
            updated_by=self.actor,
        )
        return FileResult(ok=True, file=file)

    def soft_delete_file(self, file: File) -> FileResult:
        """Soft-delete the blob only. Callers that must also remove the link
        rows use DirectAttachmentHandler.delete_file, which owns the cascade."""
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
