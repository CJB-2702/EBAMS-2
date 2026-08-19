from django.db import models
from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.administration.models.soft_delete_mixin import SoftDeleteMixin


class BlockerPriority(models.TextChoices):
    LOW = "Low", "Low"
    MEDIUM = "Medium", "Medium"
    HIGH = "High", "High"
    CRITICAL = "Critical", "Critical"


class BlockerReason(models.TextChoices):
    """The fixed set of reasons work can stop.

    A closed list, not free text, because these are what the maintenance
    manager reports on ("how much of last quarter did we lose to parts?").
    Free text makes that question unanswerable. OTHER is the escape hatch and
    is expected to be paired with `MaintenanceBlocker.notes`.

    Previously this lived as an `allowable_reasons` instance property on the
    model returning a plain list of strings. Nothing enforced it, so any
    string at all could be saved; as TextChoices the database column carries
    the constraint and forms/validators derive from one source.
    """

    PARTS_NOT_AVAILABLE = "Parts Not Available", "Parts Not Available"
    EQUIPMENT_UNAVAILABLE = "Equipment Unavailable", "Equipment Unavailable"
    STAFF_NOT_AVAILABLE = "Staff Not Available", "Staff Not Available"
    FACILITY_NOT_AVAILABLE = "Facility Not Available", "Facility Not Available"
    SAFETY_CONCERNS = "Safety Concerns", "Safety Concerns"
    MAJOR_ISSUES_DISCOVERED = "Major Issues Discovered", "Major Issues Discovered"
    OTHER = "Other", "Other"


class MaintenanceBlocker(AuditFieldsMixin, SoftDeleteMixin):
    """
    Work stoppage record associated with a Maintenance Detail event.
    """
    maintenance_detail = models.ForeignKey(
        "events.MaintenanceDetail",
        on_delete=models.CASCADE,
        related_name="blockers",
    )
    reason = models.CharField(
        max_length=50,
        choices=BlockerReason.choices,
        blank=True,
    )
    notes = models.TextField(blank=True)

    # Why the stoppage ENDED, captured when the blocker is resolved. Kept
    # separate from `notes` above (which describes why work stopped) because
    # overloading one field would make the record read as a contradiction once
    # both halves are present.
    resolution_notes = models.TextField(blank=True)

    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)  # Null means active blocker

    # Hours the stoppage COST, not hours worked. Named in full because
    # `billable_hours` on an Action means the opposite thing (hours earned) —
    # the same short name on both models, meaning hours in and hours out, is
    # how a reporting query ends up silently summing the two together.
    billable_hours_lost = models.FloatField(null=True, blank=True)

    expected_resolution_date = models.DateTimeField(null=True, blank=True)
    priority = models.CharField(
        max_length=20,
        choices=BlockerPriority.choices,
        default=BlockerPriority.MEDIUM,
    )

    class Meta:
        db_table = "maintenance_blocker"
        ordering = ["-start_date"]

    def __str__(self) -> str:
        status_str = "Active" if not self.end_date else "Resolved"
        return f"Blocker ({status_str}): {self.reason}"
