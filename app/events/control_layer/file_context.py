"""FileContext — stateful control object for a single File."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser
    from app.events.models import File
    from app.events.control_layer.factories.attachment_link_factory import AttachmentResult


class FileContext:
    """
    Stateful control object for a single File.
    Owns the delete cascade: soft-deletes the file and all its attachment rows
    (delegated to DirectAttachmentHandler, which also narrates standalone links).

    No create() method — file creation is handled by FileHandler.
    """

    def __init__(self, file_id: str, actor: "AbstractUser") -> None:
        from app.events.models import File
        self.file: File = File.objects.select_related("created_by").get(
            pk=file_id, deleted_at__isnull=True
        )
        self.actor = actor

    @classmethod
    def from_file(cls, file: "File", actor: "AbstractUser") -> "FileContext":
        """Build from a pre-loaded File. Issues no DB queries."""
        instance = cls.__new__(cls)
        instance.file = file
        instance.actor = actor
        return instance

    def delete(self) -> "AttachmentResult":
        from app.events.control_layer.handlers.direct_attachment_handler import (
            DirectAttachmentHandler,
        )
        return DirectAttachmentHandler(self.actor).delete_file(file=self.file)
