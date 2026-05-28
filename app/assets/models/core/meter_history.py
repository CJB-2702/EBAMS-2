from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class MeterHistory(AuditFieldsMixin):
    """Records a single meter reading on an asset at a point in time."""

    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.CASCADE,
        related_name="meter_history",
    )
    meter_index = models.PositiveSmallIntegerField()
    value = models.FloatField()
    recorded_at = models.DateTimeField()
    source = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        db_table = "meter_history"
        ordering = ["-recorded_at"]
        indexes = [
            models.Index(fields=["asset", "meter_index"]),
            models.Index(fields=["recorded_at"]),
        ]

    def __str__(self) -> str:
        return f"MeterHistory asset={self.asset_id} m{self.meter_index}={self.value}"
