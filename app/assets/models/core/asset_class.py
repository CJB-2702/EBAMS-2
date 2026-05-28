from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class AssetClass(AuditFieldsMixin):
    """Broad category of asset (e.g. Generator, Pump, Light Vehicle)."""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(null=True, blank=True)
    category = models.CharField(max_length=100, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    restrict_to_domain_set = models.BooleanField(default=False)

    domains = models.ManyToManyField(
        "administration.Domain",
        through="assets.AssetClassDomain",
        related_name="asset_classes",
    )

    class Meta:
        db_table = "asset_class"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
