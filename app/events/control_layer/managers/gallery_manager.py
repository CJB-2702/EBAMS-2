"""GalleryManager — the one photo-gallery control object, shared across sub-apps.

A gallery is just image ``Attachment`` rows on a thread (a ``FileSet`` or
``ActivityThread``) plus an owner ``primary_image`` FK pointing at one of them.
Every sub-app that carries a gallery — an Asset, an AssetModel, a Part — repeated
the same mechanics: list images, upload (auto-selecting the first as hero), remove
(promoting the next hero), set-primary, and shape rows for the templates. This
class owns that once; owners differ only in field names and a few injected knobs.

Owner contract: any model instance with
  * a gallery-thread FK (``gallery_attr``, default ``photo_gallery``) — may be null
    when the gallery is created lazily on first upload;
  * a ``primary_image`` FK (``primary_attr``).

Configuration (constructor kwargs, all optional):
  gallery_attr        FK name for the gallery thread.
  primary_attr        FK name for the hero image.
  gallery_thread_cls  proxy class (``FileSet`` / ``ActivityThread``) used to lazily
                      create the gallery when the FK is null. ``None`` => the owner
                      must already have one (e.g. an Asset built with its gallery).
  domain_id_resolver  zero-arg callable returning the bootstrap domain id for lazy
                      creation. Overridden per-caller (an Asset uses its own domain;
                      a shared definition uses a bootstrap domain).

Sub-app–specific behavior hooks onto three no-op methods —
``_after_add`` / ``_after_remove`` / ``_after_set_primary`` — and the removal step
``_remove_attachment`` (delete the blob vs. detach the link). Subclasses override
these; see ``app/parts/control_layer/managers/part_image_manager.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.events.control_layer.handlers.direct_attachment_handler import (
    DirectAttachmentHandler,
)
from app.events.models import Attachment, AttachmentType, File
from app.events.presentation_layer.tools.generic_cards import document_dict

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser
    from django.core.files.uploadedfile import UploadedFile

    from app.events.models import Event


class GalleryError(Exception):
    pass


class GalleryManager:
    # When True, only IMAGE-type attachments count as gallery members (the rest of
    # the thread, if any, is ignored). Subclasses may flip this.
    IMAGE_ONLY = False

    def __init__(
        self,
        owner,
        actor: "AbstractUser | None" = None,
        *,
        gallery_attr: str = "photo_gallery",
        primary_attr: str = "primary_image",
        gallery_thread_cls=None,
        domain_id_resolver=None,
    ) -> None:
        self.owner = owner
        self.actor = actor
        self.gallery_attr = gallery_attr
        self.primary_attr = primary_attr
        self._gallery_thread_cls = gallery_thread_cls
        self._domain_id_resolver = domain_id_resolver

    # ── FK helpers ────────────────────────────────────────────────────────────
    def _gallery_id(self):
        return getattr(self.owner, f"{self.gallery_attr}_id")

    def _primary_id(self):
        return getattr(self.owner, f"{self.primary_attr}_id")

    def _ensure_gallery(self, domain_id: int | None = None) -> "Event":
        if self._gallery_id() is not None:
            return getattr(self.owner, self.gallery_attr)
        if self._gallery_thread_cls is None:
            raise GalleryError("This owner has no gallery and none can be created.")
        if domain_id is None and self._domain_id_resolver is not None:
            domain_id = self._domain_id_resolver()
        with transaction.atomic():
            gallery = self._gallery_thread_cls.objects.create(
                domain_id=domain_id,
                created_by=self.actor,
                updated_by=self.actor,
            )
            setattr(self.owner, self.gallery_attr, gallery)
            self.owner.save(update_fields=[self.gallery_attr])
        return gallery

    def _attachments(self):
        if self._gallery_id() is None:
            return Attachment.objects.none()
        qs = Attachment.objects.active().filter(thread_id=self._gallery_id())
        if self.IMAGE_ONLY:
            qs = qs.filter(attachment_type=AttachmentType.IMAGE)
        return qs

    # ── Reads ─────────────────────────────────────────────────────────────────
    def list_attachments(self) -> list[Attachment]:
        """Raw Attachment rows (for templates that render model objects directly)."""
        return list(self._attachments().select_related("file"))

    def image_dicts(self) -> list[dict]:
        """Generic-card document dicts, each flagged with ``is_primary`` (for the
        file-browser / gallery templates)."""
        primary_id = self._primary_id()
        return [
            {**document_dict(a), "is_primary": a.id == primary_id}
            for a in self._attachments().select_related("file", "created_by")
        ]

    # ── Writes ────────────────────────────────────────────────────────────────
    def add_image(
        self, uploaded: "UploadedFile", *, domain_id: int | None = None, caption: str = ""
    ):
        if uploaded is None:
            raise GalleryError("No file was provided.")
        if not File.is_allowed_extension(uploaded.name):
            raise GalleryError(f"File type not allowed: {uploaded.name}")

        with transaction.atomic():
            gallery = self._ensure_gallery(domain_id)
            is_first = not self._attachments().exists()
            result = DirectAttachmentHandler(self.actor).attach(
                thread=gallery, uploaded_file=uploaded, caption=caption
            )
            if not result.ok or result.attachment is None:
                raise GalleryError("; ".join(result.errors) or "Upload failed.")
            attachment = result.attachment
            if is_first:
                self.ensure_primary(attachment)
        self._after_add(attachment)
        return result

    def remove_image(self, attachment_id) -> bool:
        attachment = (
            self._attachments().select_related("file").filter(id=attachment_id).first()
        )
        if attachment is None:
            return False
        filename = attachment.file.original_filename
        with transaction.atomic():
            self._remove_attachment(attachment)
            self.resync_primary(attachment_id)
        self._after_remove(filename)
        return True

    def set_primary(self, attachment_id) -> None:
        with transaction.atomic():
            try:
                target = self._attachments().select_related("file").get(id=attachment_id)
            except Attachment.DoesNotExist as exc:
                raise GalleryError("Image not found in this gallery.") from exc
            self._set_primary(target)
        self._after_set_primary(target)

    def ensure_primary(self, attachment: Attachment) -> None:
        """Auto-select the first image as hero (no-op when one is already set)."""
        if self._primary_id() is None:
            self._set_primary(attachment)

    def resync_primary(self, removed_attachment_id) -> None:
        """After an image leaves the gallery: if it was the hero, promote the next
        remaining image (or clear the FK when none are left)."""
        if str(self._primary_id()) != str(removed_attachment_id):
            return
        self._set_primary(self._attachments().first())

    # ── Overridable steps / hooks ─────────────────────────────────────────────
    def _remove_attachment(self, attachment: Attachment) -> None:
        """How an image leaves the gallery. Default: delete the blob and all its
        links. Subclasses may detach only this link instead."""
        DirectAttachmentHandler(self.actor).delete_file(file=attachment.file)

    def _set_primary(self, attachment: Attachment | None) -> None:
        setattr(self.owner, self.primary_attr, attachment)
        self.owner.updated_by = self.actor
        self.owner.save(update_fields=[self.primary_attr, "updated_at", "updated_by"])

    def _after_add(self, attachment: Attachment) -> None:  # noqa: B027 (intentional hook)
        pass

    def _after_remove(self, filename: str) -> None:  # noqa: B027
        pass

    def _after_set_primary(self, attachment: Attachment) -> None:  # noqa: B027
        pass
