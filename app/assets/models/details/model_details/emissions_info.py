from django.db import models

from app.assets.models.details.model_detail_virtual import ModelDetailVirtual


class EmissionsInfo(ModelDetailVirtual):
    """Emissions specifications for an asset model."""

    emissions_standard = models.CharField(max_length=50, null=True, blank=True)
    tier_level = models.CharField(max_length=50, null=True, blank=True)
    co2_rating = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    certified_year = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        db_table = "emissions_info"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"EmissionsInfo model={self.model_id} standard={self.emissions_standard}"
