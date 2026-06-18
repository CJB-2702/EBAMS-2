from django.db import models

from app.detail_extensions.base.table_contract import AssetExtensionContract


class PurchaseInfo(AssetExtensionContract):
    """Purchase-related information for an asset."""

    purchase_date = models.DateField(null=True, blank=True)
    purchase_price = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    vendor = models.CharField(max_length=200, null=True, blank=True)
    purchase_order_number = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        db_table = "purchase_info"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"PurchaseInfo asset={self.asset_id}"
