"""Read helper: which AssetModels are eligible for a template's asset class.

A template holds many models but exactly one class, so every picker (builder
checkboxes, detail-page dual listbox, index filter) needs the same
class-scoped queryset.
"""

from __future__ import annotations

from django.db.models import QuerySet

from app.assets.models import AssetModel


def models_for_class(asset_class_id: int | None) -> QuerySet[AssetModel]:
    if not asset_class_id:
        return AssetModel.objects.none()
    return AssetModel.objects.filter(asset_class_id=asset_class_id).order_by(
        "model_name", "version_rank", "version"
    )
