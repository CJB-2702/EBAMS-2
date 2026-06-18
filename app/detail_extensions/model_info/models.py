from django.db import models

from app.detail_extensions.base.table_contract import ModelExtensionContract


class ModelInfo(ModelExtensionContract):
    """General specifications for an asset model."""

    engine_type = models.CharField(max_length=100, null=True, blank=True)
    horsepower = models.PositiveIntegerField(null=True, blank=True)
    weight_kg = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    length_mm = models.PositiveIntegerField(null=True, blank=True)
    width_mm = models.PositiveIntegerField(null=True, blank=True)
    height_mm = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        db_table = "model_info"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"ModelInfo model={self.model_id}"
