from django.db import models

from app.assets.models.details.asset_detail_virtual import AssetDetailVirtual


class VehicleRegistration(AssetDetailVirtual):
    """Vehicle registration and licensing information."""

    plate_number = models.CharField(max_length=20, null=True, blank=True)
    registration_expiry = models.DateField(null=True, blank=True)
    state_province = models.CharField(max_length=50, null=True, blank=True)
    vin_number = models.CharField(max_length=17, null=True, blank=True)

    class Meta:
        db_table = "vehicle_registration"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"VehicleRegistration asset={self.asset_id} plate={self.plate_number}"
