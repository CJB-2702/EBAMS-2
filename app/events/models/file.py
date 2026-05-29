"""File — uploaded file record. UUID7 PK, Django FileField storage."""

from __future__ import annotations

from django.db import models
from django.utils import timezone

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.administration.models.soft_delete_mixin import SoftDeleteMixin
from app.events.utils import generate_uuid7


ALLOWED_EXTENSIONS: dict[str, set[str]] = {
    "images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg"},
    "documents": {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".rtf"},
    "archives": {".zip", ".rar", ".7z", ".tar", ".gz"},
    "data": {".csv", ".json", ".xml", ".sql", ".html", ".txt", ".log", ".data"},
    "code": {".cpp", ".py", ".java", ".js", ".css", ".php"},
    # implement later: audio, video
}

TEXT_PREVIEW_EXTENSIONS: set[str] = {".md", ".json", ".yaml", ".yml", ".py"}

_ICON_MAP: dict[str, str] = {
    ".pdf": "bi-file-earmark-pdf",
    ".doc": "bi-file-earmark-word", ".docx": "bi-file-earmark-word",
    ".xls": "bi-file-earmark-excel", ".xlsx": "bi-file-earmark-excel",
    ".ppt": "bi-file-earmark-ppt", ".pptx": "bi-file-earmark-ppt",
    ".zip": "bi-file-earmark-zip", ".rar": "bi-file-earmark-zip",
    ".7z": "bi-file-earmark-zip", ".tar": "bi-file-earmark-zip", ".gz": "bi-file-earmark-zip",
    ".py": "bi-filetype-py",
    ".js": "bi-filetype-js",
    ".html": "bi-filetype-html", ".htm": "bi-filetype-html",
    ".css": "bi-filetype-css",
    ".json": "bi-filetype-json",
    ".xml": "bi-filetype-xml",
    ".csv": "bi-filetype-csv",
    ".sql": "bi-filetype-sql",
    ".txt": "bi-file-earmark-text", ".log": "bi-file-earmark-text",
    ".md": "bi-file-earmark-text",
    ".yaml": "bi-file-earmark-text", ".yml": "bi-file-earmark-text",
}

MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB


def _all_allowed_extensions() -> set[str]:
    result: set[str] = set()
    for exts in ALLOWED_EXTENSIONS.values():
        result |= exts
    return result


class File(AuditFieldsMixin, SoftDeleteMixin):
    """
    Uploaded file attached to the events domain.
    UUID7 primary key — used directly as the URL identifier.
    is_technical_library: placeholder column — no logic implemented yet.
    """

    id = models.UUIDField(primary_key=True, default=generate_uuid7, editable=False)

    file = models.FileField(upload_to="events/files/%Y/%m/")
    original_filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(help_text="Bytes")
    mime_type = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    tags = models.JSONField(null=True, blank=True)

    # Placeholder — do not add routing logic around this field yet.
    is_technical_library = models.BooleanField(default=False)

    objects = models.Manager()

    class Meta:
        db_table = "file"
        ordering = ["-created_at"]

    def _soft_delete(self, actor=None) -> None:
        self.deleted_at = timezone.now()
        update_fields = ["deleted_at"]
        if actor is not None:
            self.updated_by = actor
            update_fields.append("updated_by")
        self.save(update_fields=update_fields)

    @classmethod
    def is_allowed_extension(cls, filename: str) -> bool:
        from pathlib import Path
        return Path(filename).suffix.lower() in _all_allowed_extensions()

    @property
    def extension(self) -> str:
        from pathlib import Path
        return Path(self.original_filename).suffix.lower()

    def is_image(self) -> bool:
        return self.extension in ALLOWED_EXTENSIONS["images"]

    def is_text_preview(self) -> bool:
        return self.extension in TEXT_PREVIEW_EXTENSIONS

    def get_icon_class(self) -> str:
        return _ICON_MAP.get(self.extension, "bi-file-earmark")

    def __str__(self) -> str:
        return self.original_filename
