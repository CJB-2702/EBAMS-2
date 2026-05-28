from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class AssetClassCapability(AuditFieldsMixin):
    """Template-layer capability available to an asset class."""

    asset_class = models.ForeignKey(
        "assets.AssetClass",
        on_delete=models.CASCADE,
        related_name="capability_links",
    )
    capability_definition = models.ForeignKey(
        "assets.CapabilityDefinition",
        on_delete=models.PROTECT,
        related_name="asset_class_links",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "asset_class_capability"
        constraints = [
            models.UniqueConstraint(
                fields=["asset_class", "capability_definition"],
                name="uq_asset_class_capability",
            ),
        ]

    def __str__(self) -> str:
        return f"AssetClassCapability {self.asset_class_id}↔{self.capability_definition_id}"
