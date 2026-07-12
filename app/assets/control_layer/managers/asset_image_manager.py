"""AssetImageManager — image-gallery sub-area of AssetContext.

Owns the asset's photo gallery. Images are ``events.Attachment`` rows on the
asset's ``photo_gallery`` FileSet (the single source of truth); the hero image is
the ``Asset.primary_image`` FK pointing at one of those attachments. Upload and
delete delegate to ``events.DirectAttachmentHandler`` (blob + Attachment,
display_order, image-type inference, whole-file delete cascade). The FileSet
gallery has ``narrate_file_changes`` off, so gallery changes are not narrated.
The first image uploaded becomes primary automatically.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.events.control_layer.handlers.direct_attachment_handler import (
    DirectAttachmentHandler,
)
from app.events.models import Attachment, File

if TYPE_CHECKING:
    from django.core.files.uploadedfile import UploadedFile
    from django.contrib.auth.models import AbstractUser

    from app.assets.models import Asset


class AssetImageError(Exception):
    pass


class AssetImageManager:
    def __init__(self, asset: "Asset", actor: "AbstractUser") -> None:
        self.asset = asset
        self.actor = actor

    def _gallery_attachments(self):
        return Attachment.objects.active().filter(thread_id=self.asset.photo_gallery_id)

    def list_images(self) -> list[Attachment]:
        return list(self._gallery_attachments().select_related("file"))

    def add_image(self, uploaded: "UploadedFile") -> Attachment:
        if uploaded is None:
            raise AssetImageError("No file was provided.")
        if not File.is_allowed_extension(uploaded.name):
            raise AssetImageError(f"File type not allowed: {uploaded.name}")

        with transaction.atomic():
            is_first = not self._gallery_attachments().exists()
            result = DirectAttachmentHandler(self.actor).attach(
                thread=self.asset.photo_gallery, uploaded_file=uploaded
            )
            if not result.ok or result.attachment is None:
                raise AssetImageError("; ".join(result.errors) or "Upload failed.")
            attachment = result.attachment
            if is_first:
                self._set_primary(attachment)
        return attachment

    def set_primary(self, attachment_id) -> None:
        with transaction.atomic():
            target = self._gallery_attachments().get(id=attachment_id)
            self._set_primary(target)

    def delete_image(self, attachment_id) -> None:
        with transaction.atomic():
            target = self._gallery_attachments().get(id=attachment_id)
            was_primary = self.asset.primary_image_id == target.id
            DirectAttachmentHandler(self.actor).delete_file(file=target.file)
            if was_primary:
                fallback = (
                    self._gallery_attachments()
                    .exclude(id=target.id)
                    .order_by("display_order", "created_at")
                    .first()
                )
                self._set_primary(fallback)

    def _set_primary(self, attachment: Attachment | None) -> None:
        self.asset.primary_image = attachment
        self.asset.updated_by = self.actor
        self.asset.save(update_fields=["primary_image", "updated_at", "updated_by"])
