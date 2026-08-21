from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class AssetEvent(AuditFieldsMixin):
    """Join table linking an Asset to a lifecycle Event in the events app.

    Owned by the events sub-application so that all modules (maintenance,
    dispatching, inventory, administration, assets) can associate events with assets.
    """

    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.CASCADE,
        related_name="asset_events",
    )
    event = models.ForeignKey(
        "events.Event",
        on_delete=models.PROTECT,
        related_name="asset_links",
    )
    role = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        db_table = "asset_event"
        constraints = [
            models.UniqueConstraint(
                fields=["asset", "event"],
                name="uq_asset_event",
            ),
        ]
        indexes = [
            models.Index(fields=["asset"]),
            models.Index(fields=["event"]),
        ]

    def __str__(self) -> str:
        return f"AssetEvent asset={self.asset_id} event={self.event_id}"
