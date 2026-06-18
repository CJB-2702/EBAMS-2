"""Enablement tables — declare which extensions are switched on per class / model.

Each row is a pure on/off switch: ``(scope_fk, extension_key)``.
"""

from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class DetailExtensionsByAssetClass(AuditFieldsMixin):
    """Asset extensions every asset of an AssetClass is provisioned."""

    asset_class = models.ForeignKey(
        "assets.AssetClass",
        on_delete=models.CASCADE,
        related_name="asset_extension_enablements",
    )
    extension_key = models.CharField(max_length=100)

    class Meta:
        db_table = "detail_extensions_by_asset_class"
        constraints = [
            models.UniqueConstraint(
                fields=["asset_class", "extension_key"],
                name="uq_detail_extensions_by_asset_class",
            ),
        ]

    def __str__(self) -> str:
        return f"DetailExtensionsByAssetClass {self.asset_class_id}:{self.extension_key}"


class DetailExtensionsByModel(AuditFieldsMixin):
    """Extra asset extensions provisioned for assets of a specific AssetModel."""

    model = models.ForeignKey(
        "assets.AssetModel",
        on_delete=models.CASCADE,
        related_name="asset_extension_enablements",
    )
    extension_key = models.CharField(max_length=100)

    class Meta:
        db_table = "detail_extensions_by_model"
        constraints = [
            models.UniqueConstraint(
                fields=["model", "extension_key"],
                name="uq_detail_extensions_by_model",
            ),
        ]

    def __str__(self) -> str:
        return f"DetailExtensionsByModel {self.model_id}:{self.extension_key}"


class ModelDetailExtensionsByAssetClass(AuditFieldsMixin):
    """Model extensions every model of an AssetClass is provisioned."""

    asset_class = models.ForeignKey(
        "assets.AssetClass",
        on_delete=models.CASCADE,
        related_name="model_extension_enablements",
    )
    extension_key = models.CharField(max_length=100)

    class Meta:
        db_table = "model_detail_extensions_by_asset_class"
        constraints = [
            models.UniqueConstraint(
                fields=["asset_class", "extension_key"],
                name="uq_model_detail_extensions_by_asset_class",
            ),
        ]

    def __str__(self) -> str:
        return f"ModelDetailExtensionsByAssetClass {self.asset_class_id}:{self.extension_key}"
