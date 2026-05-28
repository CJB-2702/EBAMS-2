from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class AssetDetailTemplateByModelType(AuditFieldsMixin):
    """Declares additional asset-detail subclasses provisioned for assets of a specific AssetModel."""

    model = models.ForeignKey(
        "assets.AssetModel",
        on_delete=models.CASCADE,
        related_name="asset_detail_templates",
    )
    detail_table_type = models.CharField(max_length=100)
    many_to_one = models.BooleanField(default=False)

    class Meta:
        db_table = "asset_detail_template_by_model_type"
        constraints = [
            models.UniqueConstraint(
                fields=["model", "detail_table_type"],
                name="uq_asset_detail_template_by_model_type",
            ),
        ]

    def __str__(self) -> str:
        return f"AssetDetailTemplateByModelType {self.model_id}:{self.detail_table_type}"
