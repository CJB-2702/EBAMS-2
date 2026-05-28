from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class AssetDetailTemplateByAssetClass(AuditFieldsMixin):
    """Declares which asset-detail subclasses are provisioned for assets of an AssetClass."""

    asset_class = models.ForeignKey(
        "assets.AssetClass",
        on_delete=models.CASCADE,
        related_name="asset_detail_templates",
    )
    detail_table_type = models.CharField(max_length=100)
    many_to_one = models.BooleanField(default=False)

    class Meta:
        db_table = "asset_detail_template_by_asset_class"
        constraints = [
            models.UniqueConstraint(
                fields=["asset_class", "detail_table_type"],
                name="uq_asset_detail_template_by_asset_class",
            ),
        ]

    def __str__(self) -> str:
        return f"AssetDetailTemplateByAssetClass {self.asset_class_id}:{self.detail_table_type}"
