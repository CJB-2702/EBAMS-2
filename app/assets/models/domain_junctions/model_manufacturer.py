from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class ModelManufacturer(AuditFieldsMixin):
    """M2M through: AssetModel × Manufacturer. One link may be marked primary."""

    model = models.ForeignKey(
        "assets.AssetModel",
        on_delete=models.CASCADE,
        related_name="manufacturer_links",
    )
    manufacturer = models.ForeignKey(
        "assets.Manufacturer",
        on_delete=models.PROTECT,
        related_name="model_links",
    )
    is_primary = models.BooleanField(default=False)

    class Meta:
        db_table = "asset_model_manufacturer"
        constraints = [
            models.UniqueConstraint(
                fields=["model", "manufacturer"],
                name="uq_asset_model_manufacturer",
            ),
        ]

    def __str__(self) -> str:
        return f"ModelManufacturer {self.model_id}↔{self.manufacturer_id}"
