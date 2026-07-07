"""AssetImageManager — image-gallery sub-area of AssetContext.

Owns the asset's photo gallery: upload (creates the backing ``events.File`` then
the ``AssetImage`` link), set-primary (exactly one primary per asset), and delete.
The first image uploaded becomes primary automatically.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.assets.models import AssetImage
from app.events.models import File

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

    def add_image(self, uploaded: "UploadedFile") -> AssetImage:
        if uploaded is None:
            raise AssetImageError("No file was provided.")
        if not File.is_allowed_extension(uploaded.name):
            raise AssetImageError(f"File type not allowed: {uploaded.name}")

        with transaction.atomic():
            attachment = File.objects.create(
                file=uploaded,
                original_filename=uploaded.name,
                file_size=uploaded.size,
                mime_type=getattr(uploaded, "content_type", "") or "application/octet-stream",
                created_by=self.actor,
                updated_by=self.actor,
            )
            existing = AssetImage.objects.filter(asset=self.asset)
            is_first = not existing.exists()
            next_order = existing.count()
            image = AssetImage.objects.create(
                asset=self.asset,
                attachment=attachment,
                is_primary=is_first,
                sort_order=next_order,
                created_by=self.actor,
                updated_by=self.actor,
            )
        return image

    def set_primary(self, image_id: int) -> None:
        with transaction.atomic():
            target = AssetImage.objects.get(asset=self.asset, id=image_id)
            AssetImage.objects.filter(asset=self.asset, is_primary=True).exclude(
                id=target.id
            ).update(is_primary=False, updated_by=self.actor)
            if not target.is_primary:
                target.is_primary = True
                target.updated_by = self.actor
                target.save(update_fields=["is_primary", "updated_at", "updated_by"])

    def delete_image(self, image_id: int) -> None:
        with transaction.atomic():
            target = AssetImage.objects.get(asset=self.asset, id=image_id)
            was_primary = target.is_primary
            target.delete()
            if was_primary:
                fallback = AssetImage.objects.filter(asset=self.asset).order_by(
                    "sort_order", "created_at"
                ).first()
                if fallback is not None:
                    fallback.is_primary = True
                    fallback.updated_by = self.actor
                    fallback.save(
                        update_fields=["is_primary", "updated_at", "updated_by"]
                    )
