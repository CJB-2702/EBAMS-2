from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class ActualModification(AuditFieldsMixin):
    """Documents a real modification present on a specific asset."""

    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.CASCADE,
        related_name="actual_modifications",
    )
    defined_modification = models.ForeignKey(
        "assets.DefinedModification",
        on_delete=models.PROTECT,
        related_name="actual_applications",
    )
    applied_at = models.DateField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "actual_modification"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"ActualModification asset={self.asset_id} mod={self.defined_modification_id}"
