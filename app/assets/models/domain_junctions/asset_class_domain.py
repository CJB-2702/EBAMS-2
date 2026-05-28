from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class AssetClassDomain(AuditFieldsMixin):
    """M2M through: AssetClass × Domain with audit columns."""

    asset_class = models.ForeignKey(
        "assets.AssetClass",
        on_delete=models.CASCADE,
        related_name="domain_links",
    )
    domain = models.ForeignKey(
        "administration.Domain",
        on_delete=models.PROTECT,
        related_name="asset_class_links",
    )

    class Meta:
        db_table = "asset_class_domain"
        constraints = [
            models.UniqueConstraint(
                fields=["asset_class", "domain"],
                name="uq_asset_class_domain",
            ),
        ]

    def __str__(self) -> str:
        return f"AssetClassDomain {self.asset_class_id}↔{self.domain_id}"
