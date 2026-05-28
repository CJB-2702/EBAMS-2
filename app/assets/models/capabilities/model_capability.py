from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class ModelCapability(AuditFieldsMixin):
    """Model-level capability assignment. Replaces old MakeModelCapability."""

    model = models.ForeignKey(
        "assets.AssetModel",
        on_delete=models.CASCADE,
        related_name="capability_links",
    )
    capability_definition = models.ForeignKey(
        "assets.CapabilityDefinition",
        on_delete=models.PROTECT,
        related_name="model_links",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "asset_model_capability"
        constraints = [
            models.UniqueConstraint(
                fields=["model", "capability_definition"],
                name="uq_asset_model_capability",
            ),
        ]

    def __str__(self) -> str:
        return f"ModelCapability {self.model_id}↔{self.capability_definition_id}"
