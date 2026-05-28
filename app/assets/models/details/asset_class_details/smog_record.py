from django.db import models

from app.assets.models.details.asset_detail_virtual import AssetDetailVirtual


class SmogRecord(AssetDetailVirtual):
    """Smog test record."""

    test_date = models.DateField(null=True, blank=True)
    test_result = models.CharField(max_length=50, null=True, blank=True)
    test_station = models.CharField(max_length=200, null=True, blank=True)
    certificate_number = models.CharField(max_length=100, null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "smog_record"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"SmogRecord asset={self.asset_id} date={self.test_date}"
