"""PartImageManager — the Part photo gallery, backed by ``Part.gallery_thread``.

Parts carry no dedicated photo-gallery FileSet: an ActivityThread already holds
its own attachments, so the part's gallery images are the image-type attachments
on ``Part.gallery_thread`` — a Part-level thread decoupled from any revision.
``Part.primary_image`` is a FK to one of those attachments.

This manager owns adding, removing and hero-selection of gallery images, and
keeps a backend-only audit trail: every add/remove/set-primary writes a machine
comment (``is_human_made=False``) onto the gallery thread. Those comments are
never shown to end users — they exist for administrators and data engineers.
Attachment I/O delegates to ``PartThreadManager`` (D5); this manager never
touches the ORM for attachments directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.events.models import Attachment, AttachmentType
from app.parts.control_layer.managers.part_thread_manager import PartThreadManager

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from app.parts.models import Part

GALLERY_THREAD = "gallery_thread"


class PartImageError(Exception):
    pass


class PartImageManager:
    def __init__(self, part: "Part", actor: "AbstractUser | None" = None) -> None:
        self.part = part
        self.actor = actor

    def _thread_manager(self) -> PartThreadManager:
        return PartThreadManager(self.part, self.actor, thread_attr=GALLERY_THREAD)

    def _gallery_images(self):
        """Every image attachment on the part's gallery thread (empty until the
        first image is added and the thread is lazily created)."""
        if self.part.gallery_thread_id is None:
            return Attachment.objects.none()
        return Attachment.objects.active().filter(
            thread_id=self.part.gallery_thread_id,
            attachment_type=AttachmentType.IMAGE,
        )

    def _log(self, message: str) -> None:
        """Record one machine comment on the gallery thread — backend-only audit
        history, never displayed to end users."""
        self._thread_manager().add_comment(message, is_human_made=False)

    def add(self, uploaded_file, *, domain_id: int | None = None, caption: str = ""):
        """Attach one image to the gallery thread, auto-select it as primary when
        it is the first, and log the addition. Returns the attach result."""
        result = self._thread_manager().attach_document(
            uploaded_file, domain_id=domain_id, caption=caption
        )
        if result.ok and result.attachment is not None:
            self.ensure_primary(result.attachment)
            self._log(
                f"Added image '{result.attachment.file.original_filename}' to the gallery."
            )
        return result

    def remove(self, attachment_id) -> bool:
        """Detach one image from the gallery, promote the next hero if it was
        primary, and log the removal. False if it is not on the gallery thread."""
        image = self._gallery_images().select_related("file").filter(id=attachment_id).first()
        if image is None:
            return False
        filename = image.file.original_filename
        if not self._thread_manager().detach_document(attachment_id):
            return False
        self.resync_primary(attachment_id)
        self._log(f"Removed image '{filename}' from the gallery.")
        return True

    def set_primary(self, attachment_id) -> None:
        with transaction.atomic():
            try:
                target = self._gallery_images().select_related("file").get(id=attachment_id)
            except Attachment.DoesNotExist as exc:
                raise PartImageError("Image not found in this part's gallery.") from exc
            self._set_primary(target)
        self._log(f"Set primary image to '{target.file.original_filename}'.")

    def ensure_primary(self, attachment: Attachment) -> None:
        """Auto-select the first uploaded image as primary (no-op if one is set).
        Does not log — the caller (``add``) records the addition instead."""
        if self.part.primary_image_id is None:
            self._set_primary(attachment)

    def resync_primary(self, removed_attachment_id) -> None:
        """Called after an image is removed from the gallery: if the removed image
        was the part's hero, promote the next remaining gallery image (or clear
        the FK when none are left)."""
        if str(self.part.primary_image_id) != str(removed_attachment_id):
            return
        self._set_primary(self._gallery_images().first())

    def _set_primary(self, attachment: Attachment | None) -> None:
        self.part.primary_image = attachment
        self.part.updated_by = self.actor
        self.part.save(update_fields=["primary_image", "updated_at", "updated_by"])
