from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class AssetCapability(AuditFieldsMixin):
    """Per-asset capability assignment."""

    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.CASCADE,
        related_name="capability_links",
    )
    capability_definition = models.ForeignKey(
        "assets.CapabilityDefinition",
        on_delete=models.PROTECT,
        related_name="asset_links",
    )
    is_active = models.BooleanField(default=True)
    notes = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "asset_capability"
        constraints = [
            models.UniqueConstraint(
                fields=["asset", "capability_definition"],
                name="uq_asset_capability",
            ),
        ]

    def __str__(self) -> str:
        return f"AssetCapability {self.asset_id}↔{self.capability_definition_id}"
