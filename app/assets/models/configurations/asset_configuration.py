from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class VerificationStatus(models.TextChoices):
    UNVERIFIED = "unverified", "Unverified"
    PARTIAL = "partial", "Partial"
    COMPLETE = "complete", "Complete"


class AssetConfiguration(AuditFieldsMixin):
    """Links an Asset to a ConfigurationTemplate with documentation status."""

    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.CASCADE,
        related_name="configurations",
    )
    template = models.ForeignKey(
        "assets.ConfigurationTemplate",
        on_delete=models.PROTECT,
        related_name="asset_configurations",
    )
    documented_at = models.DateTimeField(null=True, blank=True)
    is_current = models.BooleanField(default=True)
    verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.UNVERIFIED,
    )
    notes = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "asset_configuration"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"AssetConfiguration asset={self.asset_id} template={self.template_id}"
