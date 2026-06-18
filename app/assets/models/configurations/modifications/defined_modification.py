from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.assets.models.configurations.modifications.applicability_mode import ApplicabilityMode


class DefinedModification(AuditFieldsMixin):
    """Reusable catalog entry for a standardized modification."""

    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(null=True, blank=True)
    category = models.CharField(max_length=100, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    # Where this modification may be applied. Default UNRESTRICTED preserves the
    # pre-applicability "apply anywhere" behavior (kit D7). The allow-lists live in
    # the modification_asset_class / modification_model junction tables; how they
    # bind is decided by ApplicabilityPolicy per this mode.
    applicability_mode = models.CharField(
        max_length=20,
        choices=ApplicabilityMode.choices,
        default=ApplicabilityMode.UNRESTRICTED,
    )

    class Meta:
        db_table = "defined_modification"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
