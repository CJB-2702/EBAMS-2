"""AssetHandler — create Asset rows with their required ActivityThread pair."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from django.db import transaction

from app.assets.models.core.asset import Asset
from app.events.models import ActivityThread, ActivityThreadType

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


@dataclass
class AssetResult:
    ok: bool
    asset: Asset | None = None
    errors: list[str] = field(default_factory=list)


class AssetHandler:
    """Handles create operations for Asset rows.

    Asset creation always produces two ActivityThread rows atomically:
      photo_gallery  (allow_comments=False, allow_direct_attachments=True)
      documentation  (allow_comments=True,  allow_direct_attachments=True)
    Both threads are created before the Asset row — no lazy thread creation.
    """

    def __init__(self, actor: "AbstractUser") -> None:
        self.actor = actor

    def create(self, post_data: dict) -> AssetResult:
        errors = self._validate(post_data)
        if errors:
            return AssetResult(ok=False, errors=errors)

        with transaction.atomic():
            photo_thread = ActivityThread.objects.create(
                thread_type=ActivityThreadType.PHOTO_GALLERY,
                allow_comments=False,
                allow_direct_attachments=True,
                domain_id=post_data["domain_id"],
                created_by=self.actor,
                updated_by=self.actor,
            )
            doc_thread = ActivityThread.objects.create(
                thread_type=ActivityThreadType.DOCUMENTATION,
                allow_comments=True,
                allow_direct_attachments=True,
                domain_id=post_data["domain_id"],
                created_by=self.actor,
                updated_by=self.actor,
            )
            asset = Asset.objects.create(
                name=post_data["name"],
                serial_number=post_data["serial_number"],
                domain_id=post_data["domain_id"],
                model_id=post_data["model_id"],
                asset_class_id=post_data["asset_class_id"],
                photo_gallery=photo_thread,
                documentation=doc_thread,
                status=post_data.get("status", "Active"),
                created_by=self.actor,
                updated_by=self.actor,
            )

        return AssetResult(ok=True, asset=asset)

    def _validate(self, post_data: dict) -> list[str]:
        errors: list[str] = []
        for required in ("name", "serial_number", "domain_id", "model_id", "asset_class_id"):
            if not post_data.get(required):
                errors.append(f"{required} is required.")
        return errors
