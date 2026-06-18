"""ModelAssetClassPropagationHandler — keeps the denormalized Asset.asset_class
in sync when an AssetModel's asset_class changes.

``Asset.asset_class`` is a deliberate denormalization of
``AssetModel.asset_class``. When the model's class changes, every asset of that
model must be bulk-updated. Single heavy step → a Handler.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.assets.models import Asset

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from app.assets.models import AssetModel


class ModelAssetClassPropagationHandler:
    @classmethod
    def run(
        cls,
        *,
        model: "AssetModel",
        new_asset_class_id: int,
        actor: "AbstractUser",
    ) -> int:
        """Set ``model.asset_class`` and propagate to all its assets. Returns the
        number of assets updated."""
        with transaction.atomic():
            model.asset_class_id = new_asset_class_id
            model.updated_by = actor
            model.save(update_fields=["asset_class", "updated_by", "updated_at"])

            return Asset.objects.filter(model_id=model.id).update(
                asset_class_id=new_asset_class_id,
                updated_by=actor,
            )
