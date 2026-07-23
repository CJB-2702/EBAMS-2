"""PartImageManager — the Part photo gallery, backed by ``Part.gallery_thread``.

A thin subclass of the shared ``events.GalleryManager``. The generic mechanics
(list, upload with first-image-auto-primary, remove with hero fallback,
set-primary, read-shaping) live once in events; this class supplies only the
Part-specific behavior:

  * the gallery lives on ``gallery_thread`` (an ActivityThread), lazily created
    with a parts bootstrap domain — a Part is a shared, domain-spanning record;
  * removal *detaches the link only* (the File blob may be linked elsewhere),
    rather than deleting the blob;
  * every add/remove/set-primary writes a machine comment (``is_human_made=False``)
    onto the gallery thread — a backend-only audit trail for administrators and
    data engineers, never shown to end users. The write goes through the shared
    ``events.ActivityThreadManager`` (never reimplemented here); the message text
    comes from ``PartImageNarrator``.

``add`` / ``remove`` are kept as aliases for the callers that predate the shared
manager's ``add_image`` / ``remove_image`` names.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.events.control_layer.handlers.direct_attachment_handler import (
    DirectAttachmentHandler,
)
from app.events.control_layer.managers.activity_thread_manager import ActivityThreadManager
from app.events.control_layer.managers.gallery_manager import GalleryError, GalleryManager
from app.events.models import ActivityThread, Attachment
from app.parts.control_layer.narrators.part_image_narrator import PartImageNarrator
from app.parts.control_layer.thread_domain import default_domain_id_for

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from app.parts.models import Part

GALLERY_THREAD = "gallery_thread"

# Preserved for callers that import the parts-specific error name.
PartImageError = GalleryError


class PartImageManager(GalleryManager):
    IMAGE_ONLY = True

    def __init__(self, part: "Part", actor: "AbstractUser | None" = None) -> None:
        super().__init__(
            part,
            actor,
            gallery_attr=GALLERY_THREAD,
            gallery_thread_cls=ActivityThread,
            domain_id_resolver=lambda: default_domain_id_for(ActivityThread),
        )

    # Removal detaches the link only; the File blob is left intact (D5 — it may be
    # linked elsewhere).
    def _remove_attachment(self, attachment: Attachment) -> None:
        DirectAttachmentHandler(self.actor).detach(attachment=attachment)

    # Backend-only audit trail — one machine comment per gallery change.
    def _log(self, message: str) -> None:
        ActivityThreadManager(
            self.owner,
            self.actor,
            thread_attr=GALLERY_THREAD,
            domain_id_resolver=lambda: default_domain_id_for(ActivityThread),
        ).add_comment(message, is_human_made=False)

    def _after_add(self, attachment: Attachment) -> None:
        self._log(PartImageNarrator.added(attachment))

    def _after_remove(self, filename: str) -> None:
        self._log(PartImageNarrator.removed(filename))

    def _after_set_primary(self, attachment: Attachment) -> None:
        self._log(PartImageNarrator.primary_set(attachment))

    # Backward-compatible aliases.
    def add(self, uploaded_file, *, domain_id: int | None = None, caption: str = ""):
        return self.add_image(uploaded_file, domain_id=domain_id, caption=caption)

    def remove(self, attachment_id) -> bool:
        return self.remove_image(attachment_id)
