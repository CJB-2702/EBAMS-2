from django.db import models
from django.utils import timezone
from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.administration.models.soft_delete_mixin import SoftDeleteMixin


class CapabilityStatus(models.TextChoices):
    NON_CAPABLE = "Non Capable", "Non Capable"
    FUNCTIONAL_LIMITATIONS = (
        "Partially Capable - Functional Limitations",
        "Partially Capable - Functional Limitations",
    )
    TEMPORARY_COMPENSATION = (
        "Partially Capable - Temporary Compensation",
        "Partially Capable - Temporary Compensation",
    )
    FULLY_CAPABLE_COMPENSATION = (
        "Fully Capable - Temporary Compensation",
        "Fully Capable - Temporary Compensation",
    )


class AssetLimitationRecord(AuditFieldsMixin, SoftDeleteMixin):
    """
    Asset Limitation Record - tracks operational capability limitations over time.
    """
    maintenance_detail = models.ForeignKey(
        "events.MaintenanceDetail",
        on_delete=models.CASCADE,
        related_name="limitation_records",
    )
    status = models.CharField(
        max_length=100,
        choices=CapabilityStatus.choices,
    )
    limitation_description = models.TextField(blank=True)
    temporary_modifications = models.TextField(blank=True)
    
    start_time = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField(null=True, blank=True)  # Null means active limitation
    
    maintenance_blocker = models.ForeignKey(
        "maintenance.MaintenanceBlocker",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="limitation_records",
    )

    class Meta:
        db_table = "asset_limitation_record"
        ordering = ["-start_time"]

    @property
    def is_active(self) -> bool:
        return self.end_time is None

    @property
    def allowable_capability_statuses(self) -> list[str]:
        return CapabilityStatus.values

    @property
    def is_degraded(self) -> bool:
        degraded_statuses = [
            CapabilityStatus.NON_CAPABLE,
            CapabilityStatus.FUNCTIONAL_LIMITATIONS,
        ]
        return self.status in degraded_statuses

    @property
    def requires_modification(self) -> bool:
        compensation_statuses = [
            CapabilityStatus.TEMPORARY_COMPENSATION,
            CapabilityStatus.FULLY_CAPABLE_COMPENSATION,
        ]
        return self.status in compensation_statuses

    def __str__(self) -> str:
        active_str = "ACTIVE" if self.is_active else "CLOSED"
        return f"Limitation ({active_str}): {self.status}"
