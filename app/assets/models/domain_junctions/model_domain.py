from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class ModelDomain(AuditFieldsMixin):
    """M2M through: AssetModel × Domain with audit columns."""

    model = models.ForeignKey(
        "assets.AssetModel",
        on_delete=models.CASCADE,
        related_name="domain_links",
    )
    domain = models.ForeignKey(
        "administration.Domain",
        on_delete=models.PROTECT,
        related_name="asset_model_links",
    )

    class Meta:
        db_table = "asset_model_domain"
        constraints = [
            models.UniqueConstraint(
                fields=["model", "domain"],
                name="uq_asset_model_domain",
            ),
        ]

    def __str__(self) -> str:
        return f"ModelDomain {self.model_id}↔{self.domain_id}"
