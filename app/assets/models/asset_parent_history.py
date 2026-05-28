from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class AssetParentHistory(AuditFieldsMixin):
    """Audit trail of parent/root/depth changes for an asset."""

    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.CASCADE,
        related_name="parent_history",
    )

    previous_parent_asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
    )
    new_parent_asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
    )

    previous_root_asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
    )
    new_root_asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
    )

    previous_depth = models.PositiveSmallIntegerField(null=True, blank=True)
    new_depth = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        db_table = "asset_parent_history"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["asset", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"AssetParentHistory asset={self.asset_id} @ {self.created_at:%Y-%m-%d}"
