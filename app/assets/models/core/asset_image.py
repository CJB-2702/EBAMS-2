from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class AssetImage(AuditFieldsMixin):
    """
    Links a file attachment to an asset. One image per asset may be marked
    primary (hero image). FK targets the events app's EventFile.
    """

    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.CASCADE,
        related_name="images",
    )
    attachment = models.ForeignKey(
        "events.File",
        on_delete=models.PROTECT,
        related_name="asset_image_links",
    )
    is_primary = models.BooleanField(default=False)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "asset_image"
        ordering = ["sort_order", "created_at"]

    def __str__(self) -> str:
        return f"AssetImage asset={self.asset_id} attachment={self.attachment_id}"
