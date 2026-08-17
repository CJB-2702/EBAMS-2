from django.db import models
from django.utils import timezone

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.administration.models.soft_delete_mixin import SoftDeleteMixin
from app.inventory.models.intake.enums import IntakeSessionMethod, IntakeSessionStatus


class IntakeSession(AuditFieldsMixin, SoftDeleteMixin):
    """One receiving run by an operator (FD-10, FD-13).

    `warehouse` anchors the session — required. `room` is optional; when null,
    commit targets the warehouse's protected Intake Room
    (`WarehouseFactory.intake_room`) rather than a `dock_location` model that
    was never built (FD-10 supersedes the kit's `dock_location_id` field).

    `intake_method` distinguishes a human walking the floor with a scanner
    (Phase 5) from the Auto Intake portal's pseudo-session (`MANUAL_PACKAGE`,
    FD-13), which is created and immediately committed in one call.

    `has_unlinked_allocations` is set True the moment any child `ItemAllocation`
    carries `shipment_line = NULL` — unmanifested/excess stock quarantined in
    the Intake Room pending a human's paperwork follow-up
    (overages_shortages_and_reconciliation.md §1.1).
    """

    operator = models.ForeignKey(
        "administration.User",
        on_delete=models.PROTECT,
        related_name="intake_sessions",
    )
    warehouse = models.ForeignKey(
        "inventory.Warehouse",
        on_delete=models.PROTECT,
        related_name="intake_sessions",
    )
    room = models.ForeignKey(
        "inventory.Room",
        on_delete=models.PROTECT,
        related_name="intake_sessions",
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=30,
        choices=IntakeSessionStatus.choices,
        default=IntakeSessionStatus.DRAFT,
    )
    intake_method = models.CharField(
        max_length=30,
        choices=IntakeSessionMethod.choices,
        default=IntakeSessionMethod.MANUAL_PACKAGE,
    )
    has_unlinked_allocations = models.BooleanField(default=False)
    started_at = models.DateTimeField(default=timezone.now)
    closed_at = models.DateTimeField(null=True, blank=True)
    hardware_device_id = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "inventory_intake_session"
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["operator", "status"], name="intake_session_op_status_idx"),
        ]

    def __str__(self) -> str:
        return f"IntakeSession #{self.pk} ({self.status}) @ {self.warehouse_id}"
