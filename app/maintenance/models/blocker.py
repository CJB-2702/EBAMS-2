from django.db import models
from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.administration.models.soft_delete_mixin import SoftDeleteMixin


class BlockerPriority(models.TextChoices):
    LOW = "Low", "Low"
    MEDIUM = "Medium", "Medium"
    HIGH = "High", "High"
    CRITICAL = "Critical", "Critical"


class MaintenanceBlocker(AuditFieldsMixin, SoftDeleteMixin):
    """
    Work stoppage record associated with a Maintenance Detail event.
    """
    maintenance_detail = models.ForeignKey(
        "events.MaintenanceDetail",
        on_delete=models.CASCADE,
        related_name="blockers",
    )
    reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)  # Null means active blocker
    billable_hours = models.FloatField(null=True, blank=True)
    expected_resolution_date = models.DateTimeField(null=True, blank=True)
    priority = models.CharField(
        max_length=20,
        choices=BlockerPriority.choices,
        default=BlockerPriority.MEDIUM,
    )

    class Meta:
        db_table = "maintenance_blocker"
        ordering = ["-start_date"]

    @property
    def allowable_reasons(self) -> list[str]:
        return [
            "Parts Not Available",
            "Equipment Unavailable",
            "Staff Not Available",
            "Facility Not Available",
            "Safety Concerns",
            "Major Issues Discovered",
            "Other",
        ]

    def __str__(self) -> str:
        status_str = "Active" if not self.end_date else "Resolved"
        return f"Blocker ({status_str}): {self.reason}"
