from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class AssetClass(AuditFieldsMixin):
    """Broad category of asset (e.g. Generator, Pump, Light Vehicle)."""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(null=True, blank=True)
    category = models.CharField(max_length=100, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    restrict_to_domain_set = models.BooleanField(default=False)

    # Meter labels are a class-level decision, not a per-model one: every model
    # under a class shares the same meter semantics (all Light Vehicles track
    # Miles on meter 1, not just some of them). Individual reading VALUES still
    # live on Asset.meter1-4 — only the unit labels live here.
    meter1_unit = models.CharField(max_length=100, null=True, blank=True)
    meter2_unit = models.CharField(max_length=100, null=True, blank=True)
    meter3_unit = models.CharField(max_length=100, null=True, blank=True)
    meter4_unit = models.CharField(max_length=100, null=True, blank=True)

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
